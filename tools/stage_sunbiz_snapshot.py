"""Stage the verified Sunbiz quarterly snapshot as local corporate observations."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

from tools.stage_sunbiz_filings import DOCUMENT
from tools.verify_sunbiz_quarterly import archive_members, digest, profile_member


def stage_snapshot(source, verification, database):
    source_hash = digest(source)
    if (not verification["all_member_crcs_verified"]
            or verification["archive_sha256"] != source_hash
            or verification["archive_bytes"] != source.stat().st_size):
        raise ValueError("Snapshot does not match the verified archive")
    members = archive_members(source)
    expected = {member["member"]: member for member in verification["members"]}
    if set(expected) != {member.filename for member in members}:
        raise ValueError("Snapshot member set does not match the receipt")

    db = sqlite3.connect(database)
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshot_manifest (
                sha256 TEXT PRIMARY KEY, receipt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshot_observations (
                sha256 TEXT, member TEXT, source_line INTEGER, document TEXT,
                raw_status BLOB, filing_type BLOB,
                PRIMARY KEY (sha256, member, source_line)
            ) WITHOUT ROWID;
            CREATE TABLE IF NOT EXISTS snapshot_quarantine (
                sha256 TEXT, member TEXT, source_line INTEGER, reason TEXT,
                PRIMARY KEY (sha256, member, source_line)
            ) WITHOUT ROWID;
        """)
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT receipt FROM snapshot_manifest WHERE sha256=?",
                           (source_hash,)).fetchone()
        if prior:
            return {**json.loads(prior[0]), "replay": True}

        status_counts = Counter()
        slices = []
        for member in members:
            counts = Counter()

            def consume(offset, values):
                observations = []
                quarantined = []
                projected = values[:, [*range(12), *range(204, 220)]].tobytes()
                for index in range(0, len(projected), 28):
                    line = offset + index // 28 + 1
                    identity = projected[index:index + 12].strip(b" ")
                    if DOCUMENT.fullmatch(identity):
                        observations.append((source_hash, member.filename, line,
                                             identity.decode("ascii"),
                                             projected[index + 12:index + 13],
                                             projected[index + 13:index + 28]))
                    else:
                        quarantined.append((source_hash, member.filename, line, "document_number"))
                db.executemany("INSERT INTO snapshot_observations VALUES (?, ?, ?, ?, ?, ?)",
                               observations)
                db.executemany("INSERT INTO snapshot_quarantine VALUES (?, ?, ?, ?)", quarantined)
                counts.update(accepted=len(observations), quarantined=len(quarantined))

            profile = profile_member(source, member, consume)
            pinned_profile = expected[member.filename]
            comparable_profile = dict(profile)
            if "lowercase_document_key_rows" not in pinned_profile:
                comparable_profile.pop("lowercase_document_key_rows", None)
            if comparable_profile != pinned_profile:
                raise ValueError(f"Snapshot member differs from receipt: {member.filename}")
            if counts["accepted"] + counts["quarantined"] != profile["records"]:
                raise ValueError(f"Snapshot staging did not reconcile: {member.filename}")
            status_counts.update(profile["status"])
            slices.append({"member": member.filename, "records": profile["records"], **counts})
        total = sum(item["records"] for item in slices)
        if total != verification["records"] or dict(status_counts) != verification["status"]:
            raise ValueError("Snapshot totals differ from receipt")
        receipt = {
            "contract": "sunbiz-quarterly-corporate-snapshot-v1",
            "artifact": verification["artifact"],
            "source": verification["portal"],
            "sha256": source_hash,
            "records": total,
            "status": dict(status_counts),
            "accepted": sum(item.get("accepted", 0) for item in slices),
            "quarantined": sum(item.get("quarantined", 0) for item in slices),
            "members": slices,
            "commercial_release_authorized": False,
        }
        db.execute("INSERT INTO snapshot_manifest VALUES (?, ?)",
                   (source_hash, json.dumps(receipt, sort_keys=True)))
        db.commit()
        return {**receipt, "replay": False}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("verification", type=Path)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    verification = json.loads(args.verification.read_bytes())
    print(json.dumps(stage_snapshot(args.source, verification, args.database), indent=2))


if __name__ == "__main__":
    main()
