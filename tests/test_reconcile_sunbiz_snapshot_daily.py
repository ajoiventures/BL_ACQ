import json
import sqlite3

from tools.reconcile_sunbiz_snapshot_daily import reconcile


def test_reconciliation_keeps_repeats_and_ambiguous_matches(tmp_path):
    snapshot = tmp_path / "snapshot.sqlite"
    daily = tmp_path / "daily.sqlite"
    with sqlite3.connect(snapshot) as db:
        db.execute("CREATE TABLE snapshot_manifest(sha256, receipt)")
        db.execute("INSERT INTO snapshot_manifest VALUES (?, ?)", ("snapshot", '{"quarantined": 2}'))
        db.execute("CREATE TABLE snapshot_observations(sha256, document)")
        db.executemany("INSERT INTO snapshot_observations VALUES (?, ?)",
                       [("snapshot", "A"), ("snapshot", "B"), ("snapshot", "B"), ("older", "C")])
    with sqlite3.connect(daily) as db:
        db.execute("CREATE TABLE filing_manifest(artifact, receipt)")
        db.execute("INSERT INTO filing_manifest VALUES (?, ?)",
                   ("daily", json.dumps({"sha256": "filing", "artifact": "daily", "accepted": 4})))
        db.execute("CREATE TABLE filing_observations(artifact, document)")
        db.executemany("INSERT INTO filing_observations VALUES (?, ?)",
                       [("daily", key) for key in ("A", "A", "B", "C")])
    result = reconcile(snapshot, daily, "snapshot", "daily")
    assert result["documents_by_snapshot_match"] == {
        "absent_from_staged_snapshot": 1, "one_snapshot_match": 1, "ambiguous_snapshot_matches": 1
    }
    assert result["filing_rows_by_snapshot_match"]["one_snapshot_match"] == 2
    assert result["events_applied"] == 0
