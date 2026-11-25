"""Compare event document keys with a verified quarterly snapshot and a bounded filing window."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .stage_sunbiz_filings import stage_daily


def reconcile(events, snapshot, filing_db, filing_list, filing_dir):
    names = filing_list.read_text().splitlines()
    if not 1 <= len(names) <= 62 or sorted(set(names)) != names or any(not re.fullmatch(r"[0-9]{8}c\.txt", name) for name in names):
        raise ValueError("Expected an ordered, unique public directory listing")
    filings = [stage_daily(filing_dir / name, filing_db) for name in names]
    with closing(sqlite3.connect(events.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        event_manifests = db.execute("SELECT artifact,sha256 FROM event_manifest").fetchall()
        if len(event_manifests) != 1:
            raise ValueError("Expected exactly one staged event artifact")
        artifact, event_hash = event_manifests[0]
        documents = {key for (key,) in db.execute(
            "SELECT DISTINCT document FROM event_observation WHERE artifact=?", (artifact,))}
        db.execute("ATTACH DATABASE ? AS snap", (snapshot.resolve().as_uri() + "?mode=ro",))
        snapshot_manifests = db.execute("SELECT sha256 FROM snap.snapshot_manifest").fetchall()
        if len(snapshot_manifests) != 1:
            raise ValueError("Expected exactly one quarterly snapshot")
        snapshot_hash = snapshot_manifests[0][0]
        quarterly_counts = Counter(key for (key,) in db.execute(
            "SELECT document FROM snap.snapshot_observations WHERE sha256=?", (snapshot_hash,))
            if key in documents)
        missing = documents - quarterly_counts.keys()
    matches = {}
    with closing(sqlite3.connect(filing_db.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        for name in names:
            for key, in db.execute("SELECT document FROM filing_observations WHERE artifact=?", (name,)):
                if key in missing:
                    matches.setdefault(key, set()).add(name)
    return {
        "source": "https://dos.fl.gov/sunbiz/other-services/data-downloads/daily-data/",
        "event_artifact": artifact,
        "event_sha256": event_hash,
        "snapshot_sha256": snapshot_hash,
        "filing_listing_sha256": hashlib.sha256(filing_list.read_bytes()).hexdigest(),
        "filing_artifacts": [{key: filing[key] for key in ("artifact", "sha256", "records", "accepted", "quarantined")} for filing in filings],
        "event_documents": len(documents),
        "quarterly_exact_matches": len(quarterly_counts),
        "quarterly_ambiguous_matches": sum(count > 1 for count in quarterly_counts.values()),
        "absent_from_staged_quarterly": len(missing),
        "exact_filing_matches_of_quarterly_absent": len(matches),
        "filing_matches_by_first_artifact": dict(sorted(Counter(min(files) for files in matches.values()).items())),
        "keys_seen_in_multiple_filing_artifacts": sum(len(files) > 1 for files in matches.values()),
        "absent_from_both_staged_sources": len(missing - matches.keys()),
        "registry_updates": 0,
        "commercial_release_authorized": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("events", "snapshot", "filing_db", "filing_list", "filing_dir", "receipt"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    payload = reconcile(args.events, args.snapshot, args.filing_db, args.filing_list, args.filing_dir)
    with args.receipt.open("x", encoding="utf-8") as output:
        json.dump(payload, output, indent=2)
        output.write("\n")
    print({key: value for key, value in payload.items() if isinstance(value, int)})
