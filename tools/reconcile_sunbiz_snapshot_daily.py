"""Reconcile staged daily document IDs against the quarterly snapshot."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3


def reconcile(snapshot, daily, archive_hash, artifact):
    with sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro", uri=True) as db:
        snapshot_manifest = db.execute("SELECT receipt FROM snapshot_manifest WHERE sha256=?",
                                       (archive_hash,)).fetchone()
        if snapshot_manifest is None:
            raise ValueError("Snapshot receipt not found")
        db.execute("ATTACH DATABASE ? AS daily", (daily.resolve().as_uri() + "?mode=ro",))
        filing_manifest = db.execute("SELECT receipt FROM daily.filing_manifest WHERE artifact=?",
                                     (artifact,)).fetchone()
        if filing_manifest is None:
            raise ValueError("Daily filing receipt not found")
        filing = json.loads(filing_manifest[0])
        # Group daily observations to retain any repeated references to one exact key.
        result = db.execute("""
            WITH filings AS (
                SELECT document, count(*) AS filing_rows
                FROM daily.filing_observations WHERE artifact=? GROUP BY document
            ), snapshot_matches AS (
                SELECT s.document, count(*) AS matches
                FROM snapshot_observations s CROSS JOIN filings f
                WHERE s.sha256=? AND s.document=f.document
                GROUP BY s.document
            ), matches AS (
                SELECT f.document, f.filing_rows, coalesce(s.matches, 0) AS matches
                FROM filings f LEFT JOIN snapshot_matches s
                  ON s.document=f.document

            )
            SELECT matches, count(*), sum(filing_rows) FROM matches GROUP BY matches
        """, (artifact, archive_hash)).fetchall()
    documents = Counter()
    observations = Counter()
    for matches, document_count, filing_count in result:
        category = "one_snapshot_match" if matches == 1 else "ambiguous_snapshot_matches" if matches else "absent_from_staged_snapshot"
        documents[category] += document_count
        observations[category] += filing_count
    if sum(observations.values()) != filing["accepted"]:
        raise ValueError("Daily reconciliation differs from staging receipt")
    return {
        "snapshot_sha256": archive_hash,
        "filing_sha256": filing["sha256"],
        "filing_artifact": filing["artifact"],
        "documents_by_snapshot_match": dict(documents),
        "filing_rows_by_snapshot_match": dict(observations),
        "snapshot_quarantined_count": json.loads(snapshot_manifest[0])["quarantined"],
        "events_applied": 0,
        "registry_state_modified": False,
        "commercial_release_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_db", type=Path)
    parser.add_argument("daily_db", type=Path)
    parser.add_argument("archive_hash")
    parser.add_argument("daily_artifact")
    args = parser.parse_args()
    print(json.dumps(reconcile(args.snapshot_db, args.daily_db, args.archive_hash,
                               args.daily_artifact), indent=2))


if __name__ == "__main__":
    main()
