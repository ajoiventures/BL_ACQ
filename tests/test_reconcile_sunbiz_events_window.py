import sqlite3

import pytest

from tools.reconcile_sunbiz_events_window import reconcile


def test_exact_filing_keys_are_compared_only_for_events_absent_from_snapshot(tmp_path):
    events = tmp_path / "events.db"
    snapshot = tmp_path / "snapshot.db"
    filings = tmp_path / "filings.db"
    listing = tmp_path / "listing.txt"
    with sqlite3.connect(events) as db:
        db.executescript("""
            CREATE TABLE event_manifest(artifact, sha256);
            INSERT INTO event_manifest VALUES ('20261123ce.txt','event-hash');
            CREATE TABLE event_observation(artifact, document);
            INSERT INTO event_observation VALUES
                ('20261123ce.txt','L12345678901'),('20261123ce.txt','123456'),
                ('20261123ce.txt','L12345678902');
        """)
    with sqlite3.connect(snapshot) as db:
        db.executescript("""
            CREATE TABLE snapshot_manifest(sha256);
            INSERT INTO snapshot_manifest VALUES ('snapshot-hash');
            CREATE TABLE snapshot_observations(sha256, document);
            INSERT INTO snapshot_observations VALUES ('snapshot-hash','L12345678901');
        """)
    listing.write_text("20261123c.txt\n")
    (tmp_path / "20261123c.txt").write_bytes(b"123456".ljust(1440) + b"\n")
    result = reconcile(events, snapshot, filings, listing, tmp_path)
    assert result["event_documents"] == 3
    assert result["quarterly_exact_matches"] == 1
    assert result["exact_filing_matches_of_quarterly_absent"] == 1
    assert result["absent_from_both_staged_sources"] == 1
    assert result["registry_updates"] == 0
    listing.write_text("../20261123c.txt\n")
    with pytest.raises(ValueError, match="directory listing"):
        reconcile(events, snapshot, filings, listing, tmp_path)
