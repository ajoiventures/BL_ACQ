"""Stage bounded Sunbiz corporate filing observations without changing registry state."""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

WIDTH = 1440
CONTRACT = "sunbiz-daily-corporate-filings-v3"
LIMIT = 5_000_000
DOCUMENT = re.compile(rb"[A-Z0-9]{6,12}")


def inspect_record(line):
    ending = b"\r\n" if line.endswith(b"\r\n") else b"\n"
    if not line.endswith(ending) or len(line) != WIDTH + len(ending):
        return None, "width_or_framing"
    document = line[:12].strip(b" ")
    if not DOCUMENT.fullmatch(document):
        return None, "document_number"
    # Bytes outside the projection can contain accented names. Store projected
    # status and filing type as bytes without assuming a name-field encoding.
    return (document.decode("ascii"), line[204:205], line[205:220]), None


def stage_daily(source, database):
    artifact = source.name
    if not re.fullmatch(r"[0-9]{8}c\.txt", artifact):
        raise ValueError("Expected a daily corporate filings filename")
    db = sqlite3.connect(database)
    try:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS filing_manifest (
                artifact TEXT PRIMARY KEY, sha256 TEXT NOT NULL, receipt TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS filing_observations (
                artifact TEXT, source_line INTEGER, document TEXT, raw_status BLOB,
                filing_type BLOB, PRIMARY KEY (artifact, source_line)
            );
            CREATE TABLE IF NOT EXISTS filing_quarantine (
                artifact TEXT, source_line INTEGER, reason TEXT, row_sha256 TEXT,
                PRIMARY KEY (artifact, source_line)
            );
        """)
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT sha256, receipt FROM filing_manifest WHERE artifact=?",
                           (artifact,)).fetchone()
        digest = hashlib.sha256()
        total = size = 0
        statuses = Counter()
        framing = Counter()
        rejects = Counter()
        with source.open("rb") as stream:
            for line in iter(lambda: stream.readline(LIMIT - size + 1), b""):
                size += len(line)
                if size > LIMIT:
                    raise ValueError("Daily filing artifact exceeds byte budget")
                digest.update(line)
                if prior:
                    continue
                total += 1
                fields, reason = inspect_record(line)
                if reason:
                    rejects[reason] += 1
                    db.execute("INSERT INTO filing_quarantine VALUES (?, ?, ?, ?)",
                               (artifact, total, reason, hashlib.sha256(line).hexdigest()))
                else:
                    framing["CRLF" if line[WIDTH:] == b"\r\n" else "LF"] += 1
                    raw_status = fields[1]
                    statuses[raw_status.hex()] += 1
                    db.execute("INSERT INTO filing_observations VALUES (?, ?, ?, ?, ?)",
                               (artifact, total, *fields))
        sha256 = digest.hexdigest()
        if prior:
            if prior[0] != sha256:
                raise ValueError("Published artifact name has different bytes")
            receipt = json.loads(prior[1])
            if receipt["contract"] != CONTRACT:
                raise ValueError("Existing receipt uses an older contract. Restage in a fresh database.")
            return {**receipt, "replay": True}
        if not total:
            raise ValueError("Daily filing artifact is empty")
        receipt = {
            "contract": CONTRACT,
            "source": "https://sftp.floridados.gov/",
            "artifact": f"doc/cor/{artifact}",
            "sha256": sha256,
            "bytes": size,
            "records": total,
            "accepted": sum(statuses.values()),
            "accepted_record_framing": dict(framing),
            "raw_status_hex_counts": dict(statuses),
            "quarantined": dict(rejects),
            "commercial_release_authorized": False,
        }
        db.execute("INSERT INTO filing_manifest VALUES (?, ?, ?)",
                   (artifact, sha256, json.dumps(receipt, sort_keys=True)))
        db.commit()
        return {**receipt, "replay": False}
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(stage_daily(args.source, args.database), indent=2))


if __name__ == "__main__":
    main()
