"""Generate an exact-ID, ordered Sunbiz review receipt without applying updates."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile


def ordered_receipt(database, source, verification):
    with source.open('rb') as stream:
        source_data = stream.read(5_000_001)
    if not 0 < len(source_data) <= 5_000_000:
        raise ValueError("Event file exceeds the review budget")
    digest = hashlib.sha256(source_data).hexdigest()
    raw_lines = source_data.splitlines(keepends=True)
    verification_bytes = verification.read_bytes()
    verified = json.loads(verification_bytes)["records"]
    categories = {}
    for record in verified:
        key = record["document"]
        if key != record["displayed_document"] or key in categories:
            raise ValueError("Registry verification has ambiguous document identity")
        categories[key] = "TRADEMARK_EXCLUDED" if record["registry_aggregate_id"].startswith("trade-") else "REGISTRY_TYPE_REVIEW"
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        pinned = db.execute("SELECT sha256, receipt FROM event_manifest WHERE artifact=?", (source.name,)).fetchone()
        if pinned is None or pinned[0] != digest:
            raise ValueError("Staged source digest mismatch")
        rows = db.execute("""
            SELECT document, sequence, line, row_sha256 FROM event_observation
            WHERE artifact=? ORDER BY document, sequence, line
        """, (source.name,)).fetchall()

    if len(rows) != json.loads(pinned[1])["accepted"]:
        raise ValueError("Staged event count does not match the receipt")
    seen = set()
    items = []
    for document, sequence, line, row_hash in rows:
        if not 1 <= line <= len(raw_lines):
            raise ValueError("Event source line is out of range")
        raw = raw_lines[line - 1]
        if (hashlib.sha256(raw).hexdigest() != row_hash
                or raw[:12].strip(b" ").decode("ascii") != document
                or int(raw[12:17]) != sequence):
            raise ValueError("Event observation does not match exact source bytes")
        key = (document, sequence)
        if key in seen:
            raise ValueError("Ambiguous repeated document sequence")
        seen.add(key)
        items.append({"document": document, "sequence": sequence, "source_line": line,
                      "row_sha256": row_hash, "route": categories.get(document, "AWAIT_TYPE_REVIEW")})
    if set(categories) - {item["document"] for item in items}:
        raise ValueError("Registry evidence falls outside the staged artifact")
    return {
        "artifact": source.name, "artifact_sha256": digest,
        "registry_verification_sha256": hashlib.sha256(verification_bytes).hexdigest(),
        "rows": len(items), "documents": len({item["document"] for item in items}),
        "routes": dict(Counter(item["route"] for item in items)),
        "order_scope": "Sequence order within one retained artifact, for review only. Cross-artifact precedence is unresolved.",
        "commercial_release_authorized": False, "registry_updates": 0, "items": items,
    }


def add_type_evidence(receipt, snapshot, filings):
    """Attach exact-key raw type observations without interpreting filing codes."""
    keys = {item["document"] for item in receipt["items"]}
    evidence = {}
    inputs = {}
    for label, path, manifest_query, data_query in (
        ("snapshot", snapshot,
         "SELECT sha256 FROM snapshot_manifest ORDER BY sha256",
         "SELECT document, filing_type, sha256, member, source_line FROM snapshot_observations"),
        ("filings", filings,
         "SELECT artifact, sha256 FROM filing_manifest ORDER BY artifact",
         "SELECT document, filing_type, artifact, artifact, source_line FROM filing_observations"),
    ):
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            manifest = db.execute(manifest_query).fetchall()
            if not manifest:
                raise ValueError(f"No staged {label} manifest")
            inputs[label] = manifest
            manifest_ids = {row[0] for row in manifest}
            for document, filing_type, artifact, member, line in db.execute(data_query):
                if document not in keys:
                    continue
                if artifact not in manifest_ids:
                    raise ValueError("Type observation has no staged manifest")
                evidence.setdefault(document, []).append({
                    "source": label, "artifact": artifact, "member": member, "line": line,
                    "raw_filing_type_hex": filing_type.hex(),
                })

    code_rows = Counter()
    code_documents = {}
    for item in receipt["items"]:
        observations = sorted(evidence.get(item["document"], []),
                              key=lambda row: (row["source"], row["artifact"], row["member"], row["line"]))
        item["type_evidence"] = observations
        if item["route"] == "AWAIT_TYPE_REVIEW" and observations:
            codes = {row["raw_filing_type_hex"] for row in observations}
            if len(codes) == 1:
                item["route"] = "RAW_TYPE_REVIEW"
                code = next(iter(codes))
                code_rows[code] += 1
                code_documents.setdefault(code, set()).add(item["document"])
            else:
                item["route"] = "CONFLICTING_RAW_TYPES"
    receipt["raw_type_families"] = [
        {"raw_filing_type_hex": code, "rows": code_rows[code], "documents": len(code_documents[code])}
        for code in sorted(code_rows)
    ]
    receipt["routes"] = dict(Counter(item["route"] for item in receipt["items"]))
    receipt["type_evidence_source_manifests"] = inputs
    receipt["documents_with_raw_type_evidence"] = len(evidence)
    return receipt


def publish_receipt(path, receipt):
    """Replace the complete receipt only after the temporary file is flushed."""
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(receipt, stream, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("database", "source", "verification", "output"):
        parser.add_argument(field, type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--filings", type=Path)
    args = parser.parse_args()
    if (args.snapshot is None) != (args.filings is None):
        parser.error("--snapshot and --filings must be supplied together")
    inputs = (args.database, args.source, args.verification, args.snapshot, args.filings)
    if args.output.resolve() in {path.resolve() for path in inputs if path is not None}:
        raise ValueError("Output overlaps source evidence")
    receipt = ordered_receipt(args.database, args.source, args.verification)
    if args.snapshot is not None:
        receipt = add_type_evidence(receipt, args.snapshot, args.filings)
    publish_receipt(args.output, receipt)
    print(json.dumps({key: receipt[key] for key in ("rows", "documents", "routes", "registry_updates")}))


if __name__ == "__main__":
    main()
