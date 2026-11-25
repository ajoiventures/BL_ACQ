import argparse
from pathlib import Path
import hashlib
import json
import sqlite3
import subprocess
import sys
from zipfile import ZipFile

from backend.core import tickets, release_sync
from tools.sync_ticket_release import event


def main():
    parser = argparse.ArgumentParser(description="Rehearse a release on a disposable SQLite database")
    parser.add_argument("baseline_zip", type=Path)
    parser.add_argument("scratch", type=Path)
    parser.add_argument("--receipt", type=Path, help="Write the receipt to a new path")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    temp = args.scratch.resolve()
    temp.mkdir(exist_ok=False)
    manifest = root / "docs/session-tickets.json"
    prior = temp / "prior-manifest.json"
    with ZipFile(args.baseline_zip) as z:
        prior.write_bytes(z.read("black-river/docs/session-tickets.json"))
    current = json.loads(manifest.read_bytes())
    candidate_sha = hashlib.sha256(release_sync.canonical(current).encode()).hexdigest()
    db = temp / "disposable.db"
    backup = temp / "disposable-backup.db"

    def open_db(path):
        c = sqlite3.connect(path)
        c.row_factory = sqlite3.Row
        return c

    def snapshot(path):
        with open_db(path) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            records = [dict(r) for r in c.execute("SELECT * FROM project_tickets ORDER BY id")]
            audit = [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY seq")]
            previous = "GENESIS"
            for row in audit:
                assert row["prev_hash"] == previous
                assert hashlib.sha256((previous + row["body"]).encode()).hexdigest() == row["hash"]
                previous = row["hash"]
            return release_sync.state_digest(c), records, audit

    def cli(path, *extra, fail=False):
        p = subprocess.run([sys.executable, "-X", "utf8=0", "-m", "tools.sync_ticket_release",
                            "--manifest", str(manifest), "--db", str(path), *map(str, extra)],
                           cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=30)
        if fail:
            assert p.returncode != 0 and "Backup does not match preflight state" in p.stderr
            return
        if p.returncode:
            raise RuntimeError(p.stderr)
        return json.loads(p.stdout)

    with open_db(db) as c:
        c.execute("CREATE TABLE audit(seq INTEGER PRIMARY KEY,domain,actor,action,object_id,body,prev_hash,hash,at)")
        tickets.import_manifest(c, event, prior)
        c.execute("UPDATE project_tickets SET status='review_required',evidence=?,version=version+1 WHERE id='BR-T049'",
                  ("Synthetic existing review packet anchor",))
        event(c, "PROJECT_INTERNAL", "FIXTURE_REVIEWER", "REHEARSAL_REVIEW_STATE", "BR-T049",
              {"fixture": True})
    before, original_rows, original_audit = snapshot(db)
    dry = cli(db)
    assert not dry["applied"] and dry["release_sha256"] == candidate_sha
    assert snapshot(db) == (before, original_rows, original_audit)
    applied = cli(db, "--apply", "--expect-sha", candidate_sha, "--expect-state", before, "--backup", backup)
    after, actual_rows, actual_audit = snapshot(db)
    assert applied["applied"] and applied["existing_states_preserved"] == applied["existing_evidence_preserved"] == 145
    assert actual_rows == original_rows and actual_audit[:-1] == original_audit
    assert actual_audit[-1]["action"] == "RELEASE_SYNC"
    assert snapshot(backup) == (before, original_rows, original_audit)
    replay_backup = temp / "replay-backup.db"
    replay = cli(db, "--apply", "--expect-sha", candidate_sha, "--expect-state", after, "--backup", replay_backup)
    assert replay["replay"] and snapshot(db) == (after, actual_rows, actual_audit)
    with open_db(db) as c:
        try:
            c.execute("DELETE FROM release_receipts")
        except sqlite3.IntegrityError:
            c.rollback()
        else:
            raise AssertionError("receipt can be deleted")
        c.execute("UPDATE project_tickets SET evidence='later local observation' WHERE id='BR-T049'")
        event(c, "PROJECT_INTERNAL", "FIXTURE_REVIEWER", "REHEARSAL_LOCAL_OBSERVATION", "BR-T049", {"fixture": True})
    drift_snapshot = snapshot(db)
    cli(db, "--apply", "--expect-sha", candidate_sha, "--expect-state", after, "--backup", temp / "drift.db", fail=True)
    assert snapshot(db) == drift_snapshot
    with open_db(backup) as c, open_db(temp / "restored.db") as restore:
        c.backup(restore)
    assert snapshot(temp / "restored.db") == (before, original_rows, original_audit)
    evidence = root / "docs/acquisition/current-release-rehearsal"
    evidence.mkdir(exist_ok=True)
    receipt = args.receipt or evidence / "receipt.json"
    with receipt.open("x" if args.receipt else "w", encoding="utf-8") as output:
        json.dump({
            "mode":"disposable_sqlite_rehearsal", "ticket":"BR-T133",
            "candidate_canonical_sha256":candidate_sha, "candidate_file_sha256":hashlib.sha256(manifest.read_bytes()).hexdigest(),
            "baseline_file_sha256":hashlib.sha256(prior.read_bytes()).hexdigest(),
            "preserved_ticket_rows":len(original_rows), "preserved_audit_events":len(original_audit),
            "prior_runtime_sha256":before, "applied_runtime_sha256":after,
            "dry_run_left_runtime_unchanged":True, "review_state_preserved":True,
            "all_audit_hashes_verified":True, "replay_no_op":True,
            "immutable_release_receipt_verified":True, "stale_preflight_rejected":True,
            "backup_restore_verified":True, "windows_default_encoding_disabled":True,
            "production_migrated":False, "independent_acceptance":False
        }, output, indent=2)
        output.write("\n")
    print("Verified dry run, apply, replay, stale preflight rejection, immutable audit and restore on 145 rows.")


if __name__ == "__main__":
    main()
