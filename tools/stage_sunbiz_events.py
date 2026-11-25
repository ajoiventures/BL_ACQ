"""Stage Sunbiz corporate events as immutable observations, without registry updates."""

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from contextlib import closing
from io import BytesIO
from pathlib import Path

from .stage_sunbiz_filings import DOCUMENT

DEFINITION = "https://dos.sunbiz.org/data-definitions/cor.html"
WIDTH = 662
LIMIT = 5_000_000


def stage(source, database):
    if not re.fullmatch(r"[0-9]{8}ce\.txt", source.name):
        raise ValueError("Expected a daily corporate events filename")
    with source.open("rb") as stream:
        payload = stream.read(LIMIT + 1)
    if not 0 < len(payload) <= LIMIT:
        raise ValueError("Event artifact is empty or exceeds byte budget")
    digest = hashlib.sha256(payload).hexdigest()
    with closing(sqlite3.connect(database)) as db, db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS event_manifest
                (artifact TEXT PRIMARY KEY, sha256 TEXT NOT NULL, receipt TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS event_observation
                (artifact TEXT, line INTEGER, document TEXT, sequence INTEGER,
                 code BLOB, effective_raw BLOB, filed_raw BLOB, row_sha256 TEXT,
                 PRIMARY KEY (artifact, line));
            CREATE TABLE IF NOT EXISTS event_quarantine
                (artifact TEXT, line INTEGER, reason TEXT, row_sha256 TEXT,
                 PRIMARY KEY (artifact, line));
        """)
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT sha256, receipt FROM event_manifest WHERE artifact=?",
                           (source.name,)).fetchone()
        if prior:
            if prior[0] != digest:
                raise ValueError("Published event artifact name has different bytes")
            return {**json.loads(prior[1]), "replay": True}
        rejected = Counter()
        accepted = 0
        for number, line in enumerate(BytesIO(payload), start=1):
            row_hash = hashlib.sha256(line).hexdigest()
            document = line[:12].strip(b" ")
            sequence = line[12:17].strip(b" ")
            reason = None
            if line[WIDTH:] not in (b"\n", b"\r\n"):
                reason = "width_or_framing"
            elif not DOCUMENT.fullmatch(document):
                reason = "document_number"
            elif not sequence.isdigit():
                reason = "event_sequence"
            if reason:
                rejected[reason] += 1
                db.execute("INSERT INTO event_quarantine VALUES (?,?,?,?)",
                           (source.name, number, reason, row_hash))
                continue
            db.execute("INSERT INTO event_observation VALUES (?,?,?,?,?,?,?,?)",
                       (source.name, number, document.decode("ascii"), int(sequence),
                        line[17:37], line[77:85], line[85:93], row_hash))
            accepted += 1
        receipt = dict(definition=DEFINITION, source="https://sftp.floridados.gov/",
                       artifact=f"doc/cor/events/{source.name}", sha256=digest,
                       accepted=accepted, quarantined=dict(rejected), bytes=len(payload),
                       registry_updates=0, commercial_release_authorized=False)
        db.execute("INSERT INTO event_manifest VALUES (?,?,?)",
                   (source.name, digest, json.dumps(receipt, sort_keys=True)))
        return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    print(json.dumps(stage(args.source, args.database), indent=2))
