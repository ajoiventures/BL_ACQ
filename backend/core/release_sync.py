"""Explicit offline release metadata synchronization; never closes tickets."""
import hashlib
import json
from . import tickets
from .acquisition_patterns import digest as pattern_digest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def validate(rows):
    by = {r['id']: r for r in rows}
    if len(by) != len(rows):
        raise ValueError('Duplicate ticket')
    active, done = set(), set()
    def visit(key):
        if key in active: raise ValueError('Dependency cycle')
        if key in done: return
        active.add(key)
        r = by[key]
        if r['status'] not in tickets.WORK_STATES | {'closed','review_required'}: raise ValueError('Bad status')
        deps = r['dependencies']
        if not isinstance(deps,list) or len(deps)!=len(set(deps)) or set(deps)-by.keys(): raise ValueError('Invalid dependencies')
        for d in deps: visit(d)
        active.remove(key); done.add(key)
    for key in by: visit(key)
    return by


def state_digest(db):
    """Fingerprint ticket rows, current release, and audit head for offline preflight."""
    rows = [dict(r) for r in db.execute('SELECT * FROM project_tickets ORDER BY id')]
    has_receipts = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='release_receipts'").fetchone()
    latest = db.execute('SELECT sha FROM release_receipts ORDER BY rowid DESC LIMIT 1').fetchone() if has_receipts else None
    audit = db.execute('SELECT seq,hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
    return hashlib.sha256(canonical({'tickets':rows,'latest_release':latest[0] if latest else None,'audit_head':list(audit) if audit else None}).encode()).hexdigest()



def latest_ticket_evidence(db, ticket_id):
    """Read the ticket's preserved release evidence without changing its live state."""
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='release_receipts'"
    ).fetchone()
    if not exists:
        return None
    receipt = db.execute(
        "SELECT sha, manifest FROM release_receipts ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if receipt is None:
        return None
    sha, manifest = receipt
    if hashlib.sha256(manifest.encode("utf-8")).hexdigest() != sha:
        raise tickets.TicketError(409, "Release receipt digest mismatch")
    row = next((item for item in json.loads(manifest) if item["id"] == ticket_id), None)
    if row is None:
        return None
    evidence = {
        "ticket_id": ticket_id,
        "release_sha256": sha,
        "evidence": row["evidence"],
        "source": f"docs/session-tickets.json#{ticket_id}",
    }
    if row.get("reviewed_execution_links"):
        try:
            evidence["reviewed_execution_links"] = reviewed_execution_links(db, [row])
        except ValueError as exc:
            raise tickets.TicketError(409, "Release execution link could not be verified") from exc
    return evidence


def reviewed_execution_links(db, rows):
    """Validate explicitly declared Commercial Academy-to-execution links."""
    links = []
    for row in rows:
        declarations = row.get("reviewed_execution_links", [])
        if not isinstance(declarations, list) or len(declarations) > 20:
            raise ValueError("Invalid release execution links")
        if declarations and tickets.DOMAIN.get(row["area"]) != "COMMERCIAL":
            raise ValueError("Execution links require a Commercial ticket")
        seen = set()
        for link in declarations:
            fields = {"assessment_id", "operation_id"}
            if (not isinstance(link, dict) or set(link) != fields
                    or any(not isinstance(link[key], str) or not link[key].strip() for key in fields)):
                raise ValueError("Invalid release execution link")
            key = (link["assessment_id"], link["operation_id"])
            if key in seen:
                raise ValueError("Duplicate release execution link")
            seen.add(key)
            assessment = db.execute(
                "SELECT skill_id, evidence, reviewer, verdict FROM assessments WHERE id=?",
                (link["assessment_id"],),
            ).fetchone()
            receipt = db.execute(
                "SELECT body, prior_hash, receipt_hash FROM acquisition_pattern_receipts WHERE operation_id=?",
                (link["operation_id"],),
            ).fetchone()
            if not assessment or not receipt or (assessment["reviewer"], assessment["verdict"]) != ("SW-13", "PASS_SIMULATION"):
                raise ValueError("Execution link requires a reviewed simulation and retained receipt")
            fingerprint = pattern_digest({
                "operation_id": link["operation_id"], "body": receipt["body"],
                "prior_hash": receipt["prior_hash"],
            })
            if (fingerprint != receipt["receipt_hash"]
                    or f"receipt_sha256:{fingerprint}" not in assessment["evidence"].splitlines()):
                raise ValueError("Assessment does not reference this exact execution receipt")
            links.append({"ticket_id": row["id"], **link, "skill_id": assessment["skill_id"],
                          "receipt_sha256": fingerprint, "verdict": assessment["verdict"]})
    return links


def synchronize(db, event, rows, expected_sha, expected_state=None):
    """Caller holds BEGIN IMMEDIATE. No deletion or live status/evidence replacement."""
    if expected_state is not None and state_digest(db) != expected_state: raise ValueError('Runtime drift since preflight')
    by=validate(rows); payload=canonical(rows); sha=hashlib.sha256(payload.encode()).hexdigest()
    if sha != expected_sha: raise ValueError('Release digest mismatch')
    db.execute('CREATE TABLE IF NOT EXISTS release_receipts(sha TEXT PRIMARY KEY, manifest TEXT NOT NULL, result TEXT NOT NULL)')
    for op in ('UPDATE','DELETE'):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS release_no_{op.lower()} BEFORE {op} ON release_receipts BEGIN SELECT RAISE(ABORT,'Immutable release'); END")
    old = {r['id']:tickets.unpack(r) for r in db.execute('SELECT * FROM project_tickets')}
    if set(old)-by.keys(): raise ValueError('Release would omit existing tickets')
    previous=db.execute('SELECT manifest, result FROM release_receipts WHERE sha=?',(sha,)).fetchone()
    if previous:
        latest=db.execute('SELECT sha FROM release_receipts ORDER BY rowid DESC LIMIT 1').fetchone()[0]
        if latest!=sha: raise ValueError('Historical release; explicit rollback review required')
        if previous["manifest"] != payload:
            raise ValueError("Stored release manifest does not match replay digest")
        result = json.loads(previous["result"])
        audit = db.execute(
            "SELECT body FROM audit WHERE action='RELEASE_SYNC' AND object_id=? ORDER BY seq DESC LIMIT 1",
            (sha,),
        ).fetchone()
        if audit is None or canonical(json.loads(audit["body"])[4]) != canonical(result):
            raise ValueError("Stored release result does not match its audit event")
        fields=('title','leader','owner','acceptance','dependencies')
        if set(old)!=set(by) or any(old[k]['area']!=r['area'] or old[k]['domain']!=tickets.DOMAIN.get(r['area'],'PROJECT_INTERNAL') or any(old[k][f]!=r[f] for f in fields) for k,r in by.items()):
            raise ValueError('Runtime metadata drift on replay')
        return {**result,'replay':True}
    links = reviewed_execution_links(db, rows)
    changes=[]; added=[]
    for key,r in by.items():
        domain=tickets.DOMAIN.get(r['area'],'PROJECT_INTERNAL')
        if key not in old:
            # New ticket metadata only: cannot introduce pre-closed work via release.
            if r['status'] in {'closed','review_required'}: raise ValueError('New ticket must use a work state')
            db.execute('INSERT INTO project_tickets(id,area,domain,title,leader,owner,status,acceptance,evidence,dependencies,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (key,r['area'],domain,r['title'],r['leader'],r['owner'],r['status'],r['acceptance'],r['evidence'],json.dumps(r['dependencies']), 'docs/session-tickets.json#'+key))
            event(db,domain,'SYSTEM','TICKET_IMPORT',key,r); added.append(key); continue
        prior=old[key]
        if prior['domain']!=domain or prior['area']!=r['area']: raise ValueError('Domain/area change requires separate authorized migration')
        fields=('title','leader','owner','acceptance','dependencies')
        diff={f:{'before':prior[f],'after':r[f]} for f in fields if prior[f]!=r[f]}
        if prior['status'] in {'closed','review_required'} and diff: raise ValueError('Reviewed ticket metadata requires separate approval')
        if diff:
            db.execute('UPDATE project_tickets SET title=?,leader=?,owner=?,acceptance=?,dependencies=?,version=version+1 WHERE id=?',
                (r['title'],r['leader'],r['owner'],r['acceptance'],json.dumps(r['dependencies']),key))
            event(db,domain,'SYSTEM','TICKET_METADATA_SYNC',key,{'release_sha256':sha,'changes':diff,'version':prior['version']+1});changes.append(key)
    result={'release_sha256':sha,'inserted':added,'metadata_updated':changes,'existing_states_preserved':len(old),'existing_evidence_preserved':len(old),'replay':False,'external_authority':0}
    if links:
        result['reviewed_execution_links'] = links
    db.execute('INSERT INTO release_receipts VALUES(?,?,?)',(sha,payload,canonical(result)))
    event(db,'COMMERCIAL','SYSTEM','RELEASE_SYNC',sha,result)
    return result
