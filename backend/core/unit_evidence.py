"""Scoped unit-count research claims. Review is a local attestation, not legal approval.
No source is fetched by this adapter; retained excerpts and independent references are required.
"""
import json
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timezone
from .acquisition_runs import encode, sha, now, get
from .acquisition_cohorts import evidence

VERSION='br-unit-evidence/1'
PROJECTION_VERSION = 'br-unit-evidence-projection/2'
UNIT_METRIC = "reviewed_research_unit_count"
METRICS = {"lot_coverage_ratio": ("ratio", Decimal("1")),
           "contiguous_upland_acres": ("acre", Decimal("1000000"))}

def today():return datetime.now(timezone.utc).date().isoformat()
def day(s):
    if type(s)!=str or date.fromisoformat(s).isoformat()!=s:raise ValueError('Canonical ISO date required')
    return s

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS unit_claims(id TEXT PRIMARY KEY,snapshot_id TEXT NOT NULL,parcel_key TEXT NOT NULL,body TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS unit_claim_subject ON unit_claims(snapshot_id,parcel_key);
    CREATE INDEX IF NOT EXISTS unit_claim_parcel ON unit_claims(parcel_key);
    CREATE TABLE IF NOT EXISTS unit_reviews(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,claim_id TEXT NOT NULL,body TEXT NOT NULL,FOREIGN KEY(claim_id) REFERENCES unit_claims(id));''')
    for t in ('unit_claims','unit_reviews'):
        for op in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} BEGIN SELECT RAISE(ABORT,'Immutable unit evidence'); END")

def source(ref,excerpt,source_date):
    if not isinstance(ref,str) or not ref.strip() or len(ref)>500 or not isinstance(excerpt,str) or not excerpt.strip() or len(excerpt)>4000:raise ValueError('Source locator and retained excerpt required')
    if day(source_date)>today():raise ValueError('Source date is in the future')
    return {'reference':ref.strip(),'excerpt':excerpt.strip(),'excerpt_sha256':sha(excerpt.strip()),'source_date':source_date}

def propose(db,run_id,parcel_key,units,source_ref,excerpt,source_date,valid_until,valid_from=None,supersedes_claim_id=None):
    if type(units)!=int or not 1<=units<=100000:raise ValueError('Invalid unit count')
    return _propose(db, run_id, parcel_key, UNIT_METRIC, {"claimed_units": units},
                    source_ref, excerpt, source_date, valid_until, valid_from, supersedes_claim_id)


def propose_metric(db, run_id, parcel_key, metric, value, source_ref, excerpt, source_date, valid_until, valid_from=None):
    if metric not in METRICS:
        raise ValueError("Unsupported parcel metric")
    unit, maximum = METRICS[metric]
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Metric must be a finite decimal") from exc
    if not number.is_finite() or not 0 <= number <= maximum or number.as_tuple().exponent < -9:
        raise ValueError("Metric must be in range and have at most nine decimal places")
    canonical_value = "0" if not number else format(number.normalize(), "f")
    return _propose(db, run_id, parcel_key, metric,
                    {"metric": metric, "unit": unit, "value": canonical_value},
                    source_ref, excerpt, source_date, valid_until, valid_from)


def _propose(db,run_id,parcel_key,metric,value_fields,source_ref,excerpt,source_date,valid_until,valid_from=None,supersedes_claim_id=None):
    if day(valid_until)<today() or valid_until<source_date:raise ValueError('Claim must have a nonexpired review horizon')
    if valid_from is not None and day(valid_from) > valid_until:
        raise ValueError("Effective start cannot follow the end of the claim window")
    run=get(db,run_id);ev=evidence(db,run['snapshot_id'],parcel_key)
    body={'version':VERSION,'snapshot_id':run['snapshot_id'],'parcel_key':parcel_key,'record_sha256':ev['record_sha256'],**value_fields,'source':source(source_ref,excerpt,source_date),'valid_until':valid_until,'scope':'LOCAL_RESEARCH_ATTESTATION_ONLY'}
    if valid_from is not None:
        body["valid_from"] = valid_from
    if supersedes_claim_id is not None:
        if valid_from is None:
            raise ValueError("A correction requires an explicit effective start")
        row = db.execute(
            "SELECT body FROM unit_claims WHERE id=? AND snapshot_id=? AND parcel_key=?",
            (supersedes_claim_id, run["snapshot_id"], parcel_key),
        ).fetchone()
        if not row:
            raise ValueError("Superseded claim must belong to this parcel and snapshot")
        prior = json.loads(row[0])
        if "claimed_units" not in prior or prior["record_sha256"] != ev["record_sha256"]:
            raise ValueError("Superseded claim must describe the same unit evidence subject")
        body["supersedes_claim_id"] = supersedes_claim_id
    for entry in state(db,run['snapshot_id'],parcel_key, metric=metric)['entries']:
        prior=entry['claim']
        if (prior.get("valid_from") == valid_from
                and prior.get("supersedes_claim_id") == supersedes_claim_id
                and all(prior.get(k)==v for k,v in body.items() if k!='snapshot_id')):
            return {'claim':prior,'replay':True}
    cid=sha(body);old=db.execute('SELECT body FROM unit_claims WHERE id=?',(cid,)).fetchone()
    if old:return {'claim':json.loads(old[0]),'replay':True}
    record={**body,'id':cid,'recorded_at':now()};db.execute('INSERT INTO unit_claims VALUES(?,?,?,?)',(cid,run['snapshot_id'],parcel_key,encode(record)));return {'claim':record,'replay':False}

def adjudicate(db,cid,decision,source_ref,excerpt,source_date,expected_review_id):
    row=db.execute('SELECT body FROM unit_claims WHERE id=?',(cid,)).fetchone()
    if not row:raise LookupError('Claim not found')
    claim=json.loads(row[0]);second=source(source_ref,excerpt,source_date)
    if decision not in ('ACCEPT_RESEARCH','REJECT','REVOKE'):raise ValueError('Invalid decision')
    if decision=='ACCEPT_RESEARCH' and (second['reference'].casefold()==claim['source']['reference'].casefold() or second['excerpt_sha256']==claim['source']['excerpt_sha256'] or claim['valid_until']<today()):raise ValueError('Distinct independent source and unexpired claim required')
    body={'version':VERSION,'claim_id':cid,'decision':decision,'reviewer':'SW-13','independent_source':second,'previous_review_id':expected_review_id,'scope':'LOCAL_RESEARCH_ATTESTATION_ONLY'}
    rid=sha(body);old=db.execute('SELECT body FROM unit_reviews WHERE id=?',(rid,)).fetchone()
    if old:return {'review':json.loads(old[0]),'replay':True}
    last=db.execute('SELECT id FROM unit_reviews WHERE claim_id=? ORDER BY seq DESC LIMIT 1',(cid,)).fetchone()
    if expected_review_id!=(last[0] if last else None):raise ValueError('Stale review; reload')
    record={**body,'id':rid,'recorded_at':now()};db.execute('INSERT INTO unit_reviews(id,claim_id,body) VALUES(?,?,?)',(rid,cid,encode(record)));return {'review':record,'replay':False}

COHORT_FIELDS = {"cohort_id", "parent_snapshot_id", "cohort_filters", "cohort_count"}


def source_revision(manifest):
    inventory_sha = manifest.get("inventory_sha256")
    orange_pinned = (
        manifest.get("snapshot_source") == "orange_2026_final_roll"
        and isinstance(inventory_sha, str)
        and len(inventory_sha) == 64
        and all(ch in "0123456789abcdef" for ch in inventory_sha)
    )
    if not (manifest.get("sources") or orange_pinned):
        return None
    return {key: value for key, value in manifest.items() if key not in COHORT_FIELDS}


def state(db, snapshot_id, parcel_key, *, as_of=None, valid_on=None, metric=UNIT_METRIC):
    if metric != UNIT_METRIC and metric not in METRICS:
        raise ValueError("Unsupported parcel metric")
    value_field = "claimed_units" if metric == UNIT_METRIC else "value"
    if as_of is None or len(as_of) == 10:
        cutoff = today() if as_of is None else day(as_of)
        if cutoff > today():
            raise ValueError("Unit evidence cutoff is in the future")
        recorded_cutoff = cutoff + "T23:59:59.999999+00:00"
        displayed_cutoff = cutoff
    else:
        instant = datetime.fromisoformat(as_of)
        if "T" not in as_of or instant.tzinfo is None:
            raise ValueError("Unit evidence timestamp needs an explicit offset")
        if instant > datetime.fromisoformat(now()):
            raise ValueError("Unit evidence cutoff is in the future")
        recorded_cutoff = instant.astimezone(timezone.utc).isoformat(timespec="microseconds")
        cutoff = recorded_cutoff[:10]
        displayed_cutoff = recorded_cutoff
    effective_day = cutoff if valid_on is None else day(valid_on)
    if effective_day > cutoff:
        raise ValueError("Effective date cannot follow the recorded-knowledge cutoff")
    # Reuse only exact records and source revisions across cohort projections.
    ev=evidence(db,snapshot_id,parcel_key)
    revision = source_revision(ev['source_manifest'])
    rows = db.execute("""
        SELECT c.snapshot_id, c.body AS claim, s.manifest,
               (SELECT r.body FROM unit_reviews r
                WHERE r.claim_id=c.id AND json_extract(r.body,'$.recorded_at')<=?
                ORDER BY r.seq DESC LIMIT 1) AS review
        FROM unit_claims c JOIN acq_snapshots s ON s.id=c.snapshot_id
        WHERE c.parcel_key=? AND json_extract(c.body,'$.recorded_at')<=?
          AND coalesce(json_extract(c.body,'$.metric'),?)=?
        ORDER BY c.id
    """, (recorded_cutoff, parcel_key, recorded_cutoff, UNIT_METRIC, metric)).fetchall()
    entries=[]
    recorded_claims = {}
    for x in rows:
        claim=json.loads(x['claim'])
        if claim['record_sha256']!=ev['record_sha256']:continue
        if x['snapshot_id']!=snapshot_id and (revision is None or source_revision(json.loads(x['manifest'])) != revision):continue
        recorded_claims[claim["id"]] = claim
        if valid_on is not None and claim.get("valid_from", claim["source"]["source_date"]) > effective_day:
            continue
        entries.append({'claim':claim,'review':json.loads(x['review']) if x['review'] else None})
    effective = [
        x for x in entries
        if x["claim"].get("valid_from", effective_day) <= effective_day <= x["claim"]["valid_until"]
    ]
    active=[x for x in effective if x['review'] and x['review']['decision']=='ACCEPT_RESEARCH']
    # An accepted revision replaces its lineage, even if an intermediate
    # revision is outside the effective window or has since been revoked.
    superseded = set()
    for entry in active:
        predecessor = entry["claim"].get("supersedes_claim_id")
        while predecessor in recorded_claims and predecessor not in superseded:
            superseded.add(predecessor)
            predecessor = recorded_claims[predecessor].get("supersedes_claim_id")
    active = [x for x in active if x["claim"]["id"] not in superseded]
    values=sorted({x['claim'][value_field] for x in active})
    # Pending competing claims also prevent a match; rejected/revoked claims do not.
    pending=[x for x in effective if not x['review'] and x["claim"]["id"] not in superseded]
    competing_values = set(values) | {x['claim'][value_field] for x in pending}
    conflict = len(competing_values) > 1
    reviewed_status = 'REVIEWED_RESEARCH_COUNT' if metric == UNIT_METRIC else 'REVIEWED_RESEARCH_METRIC'
    status = 'CONFLICT' if conflict else reviewed_status if values else 'UNKNOWN'
    manifest={'status':status,("reviewed_units" if metric == UNIT_METRIC else "reviewed_value"): values[0] if status == reviewed_status else None,'active_review_ids':[x['review']['id'] for x in active],'pending_claim_ids':[x['claim']['id'] for x in pending]}
    subject = {
        "projection_version": PROJECTION_VERSION,
        "parcel_key": parcel_key,
        "domain": "COMMERCIAL",
        "predicate": metric,
        "unit": "dwelling_unit" if metric == UNIT_METRIC else METRICS[metric][0],
        "denominator": "parcel",
        "review_scope": "LOCAL_RESEARCH_ATTESTATION_ONLY",
        "geography_revision": ev["source_manifest"].get("geography_revision"),
        "record_sha256": ev["record_sha256"],
        "source_revision_sha256": sha(revision) if revision is not None else None,
        "unversioned_snapshot_id": snapshot_id if revision is None else None,
    }
    if valid_on is not None:
        subject["valid_on"] = effective_day
    return {
        **({"as_of": displayed_cutoff} if as_of is not None else {}),
        **({"valid_on": effective_day} if valid_on is not None else {}),
        **manifest, "subject": subject, "evidence_sha256": sha({**subject, **manifest}),
        "entries": entries, "legal_units": None, "external_authority": False,
    }

def pattern_projection(db, snapshot_id, parcel_key, as_of, metric=UNIT_METRIC):
    """Translate the stored research result into a deterministic pattern input."""
    projection = state(db, snapshot_id, parcel_key, as_of=as_of, metric=metric)
    if projection["status"] not in {"REVIEWED_RESEARCH_COUNT", "REVIEWED_RESEARCH_METRIC"}:
        return projection, {}
    # An immutable projection is available only for the evaluation day read.
    return projection, {
        metric: {
            "value": projection["reviewed_units" if metric == UNIT_METRIC else "reviewed_value"],
            "unit": projection["subject"]["unit"],
            "review_status": "ACCEPTED",
            "evidence_id": projection["evidence_sha256"],
            "valid_from": as_of,
            "binding": {
                "subject_id": parcel_key,
                **{key: projection["subject"][key] for key in (
                    "domain", "denominator", "geography_revision", "source_revision_sha256",
                )},
            },
        },
    }


def fit(strategy_id,st,pilots):
    if strategy_id not in pilots:return 'RESEARCH_DEFERRED'
    if st['status']=='CONFLICT':return 'CONFLICTING_UNIT_COUNTS'
    n=st['reviewed_units']
    if n is None:return 'NEEDS_LEGAL_UNIT_EVIDENCE'
    return 'REVIEWED_RESEARCH_UNIT_MATCH_ONLY' if n in pilots[strategy_id] else 'OUTSIDE_PILOT_UNIT_RANGE'
