"""Audit quarantined quarterly identifiers against source bytes and staged keys."""

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

from tools.stage_sunbiz_filings import DOCUMENT
from tools.verify_sunbiz_quarterly import archive_members, digest, profile_member


def audit(source, database, receipt):
    archive_hash = digest(source)
    if archive_hash != receipt["sha256"]:
        raise ValueError("Archive digest differs from staging receipt")
    findings = []
    positions = defaultdict(set)
    with sqlite3.connect(database) as db:
        rows = db.execute("""SELECT member,source_line,reason FROM snapshot_quarantine
                             WHERE sha256=? ORDER BY member,source_line""", (archive_hash,)).fetchall()
        expected = [(row["member"], row["source_line"], row["reason"])
                    for row in receipt["quarantine_locations"]]
        if rows != expected:
            raise ValueError("Quarantine positions differ from receipt")
        for member, line, reason in rows:
            if reason != "document_number":
                raise ValueError("Unexpected quarantine reason")
            positions[member].add(line)
        for member in archive_members(source):
            pending = positions.get(member.filename)
            if not pending:
                continue

            def consume(offset, values):
                for line in sorted(pending):
                    if not offset < line <= offset + len(values):
                        continue
                    row = values[line - offset - 1]
                    field = row[:12].tobytes()
                    document = field.strip(b" ")
                    if DOCUMENT.fullmatch(document):
                        raise ValueError("Quarantined document now passes original validation")
                    case_variant = bool(DOCUMENT.fullmatch(document.upper()))
                    short_numeric = document.isdigit() and len(document) < 6
                    candidate = document.upper().decode("ascii") if case_variant else None
                    collisions = None
                    if candidate:
                        collisions = db.execute("""SELECT count(*) FROM snapshot_observations
                            WHERE sha256=? AND member=? AND document=?""",
                            (archive_hash, member.filename, candidate)).fetchone()[0]
                    findings.append({
                        "member": member.filename, "source_line": line,
                        "field_sha256": hashlib.sha256(field).hexdigest(),
                        "raw_status_hex": row[204:205].tobytes().hex(),
                        "filing_type": row[205:220].tobytes().strip().decode("ascii"),
                        "trimmed_length": len(document),
                        "uppercase_candidate": case_variant,
                        "uppercase_candidate_matches_in_suffix_partition": collisions,
                        "short_numeric": short_numeric,
                    })
                    pending.remove(line)

            profile_member(source, member, consume)
        if any(positions.values()) or len(findings) != receipt["quarantined"]:
            raise ValueError("Quarantine audit did not reconcile")
    return {"archive_sha256": archive_hash, "findings": findings,
            "normalized_identities_approved": 0, "commercial_release_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "database", "receipt", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = audit(args.source, args.database, json.loads(args.receipt.read_bytes()))
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)


if __name__ == "__main__":
    main()
