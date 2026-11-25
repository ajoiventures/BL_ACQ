"""Offline database migration with explicit digest and optional dry run.
Stop the local app before running --apply. Back up first; no remote actions.
"""
import argparse,hashlib,json,sqlite3,datetime
from pathlib import Path
from uuid import UUID, uuid4
from backend.core.release_sync import canonical,synchronize,state_digest
from backend.core.tickets import SEED

def event(c,domain,actor,action,obj,payload):
    prev=c.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone();prev=prev[0] if prev else 'GENESIS'
    body=json.dumps([domain,actor,action,obj,payload],sort_keys=True);h=hashlib.sha256((prev+body).encode()).hexdigest()
    c.execute('INSERT INTO audit(domain,actor,action,object_id,body,prev_hash,hash,at) VALUES(?,?,?,?,?,?,?,?)',(domain,actor,action,obj,body,prev,h,datetime.datetime.now(datetime.timezone.utc).isoformat()))

def attempt_recorder(directory, predecessor, sha, applying):
    """Prepare a separate receipt so failed attempts survive database rollback."""
    if predecessor:
        prior_path = directory / (str(UUID(predecessor)) + ".json")
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        if (prior.get("schema_version") != 1 or prior.get("attempt_id") != predecessor
                or prior.get("outcome") != "FAILED"):
            raise ValueError("Retry predecessor must be a recorded failed attempt")
    directory.mkdir(parents=True, exist_ok=True)
    attempt_id = str(uuid4())
    receipt = {
        "schema_version": 1, "attempt_id": attempt_id, "retry_of": predecessor,
        "manifest_sha256": sha, "operation": "apply" if applying else "dry_run",
    }

    def record(outcome, **details):
        with (directory / (attempt_id + ".json")).open("x", encoding="utf-8") as output:
            json.dump({**receipt, "outcome": outcome, **details}, output, indent=2)
            output.write("\n")
        return attempt_id

    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',type=Path,required=True);p.add_argument('--manifest',type=Path,default=SEED);p.add_argument('--apply',action='store_true');p.add_argument('--expect-sha');p.add_argument('--backup',type=Path);p.add_argument('--expect-state',help='Runtime state digest from dry run');p.add_argument('--attempt-log',type=Path);p.add_argument('--retry-of');a=p.parse_args()
    rows=json.loads(a.manifest.read_text(encoding="utf-8"));sha=hashlib.sha256(canonical(rows).encode()).hexdigest()
    if not a.db.is_file():p.error('Existing local database required')
    if a.apply and (a.expect_sha!=sha or not a.backup or not a.expect_state):p.error('--apply requires matching --expect-sha, --expect-state and unused --backup path')
    if a.retry_of and not a.attempt_log:
        p.error('--retry-of requires --attempt-log')
    record = attempt_recorder(a.attempt_log, a.retry_of, sha, a.apply) if a.attempt_log else None
    stage = "open_database"
    c=sqlite3.connect(a.db);c.row_factory=sqlite3.Row
    try:
        if a.apply:
            stage = "backup"
            # exclusive creation prevents overwriting a prior backup
            with a.backup.open('xb'):pass
            with sqlite3.connect(a.backup) as b:
                c.backup(b);b.row_factory=sqlite3.Row
                if state_digest(b)!=a.expect_state:raise ValueError('Backup does not match preflight state')
        stage = "synchronize"
        c.execute('BEGIN IMMEDIATE')
        before=state_digest(c)
        result=synchronize(c,event,rows,sha,a.expect_state if a.apply else None)
        stage = "finalize"
        if a.apply:c.commit()
        else:c.rollback()
    except Exception as error:
        c.rollback()
        if record:
            record("FAILED", stage=stage, error_type=type(error).__name__)
        raise
    else:
        if record:
            result["attempt_id"] = record("SUCCEEDED", preflight_state_sha256=before)
        print(json.dumps({**result,'preflight_state_sha256':before,'applied':a.apply,'backup':str(a.backup) if a.apply else None},indent=2))
    finally:c.close()
if __name__=='__main__':main()
