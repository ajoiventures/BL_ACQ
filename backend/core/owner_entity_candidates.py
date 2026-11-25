"""Retain entity candidates and dated title observations for independent review."""
from datetime import date
import re


def name_key(label):
    return tuple(re.findall(r"[^\W_]+", label.casefold()))


def reconcile(parcel_id, assessor_name, filings, title_observations, *, cutoff):
    day = date.fromisoformat(cutoff)
    if not parcel_id or not assessor_name:
        raise ValueError("Parcel ID and assessor label are required")

    def validate(row):
        if not row["source_ref"] or date.fromisoformat(row["observed_date"]) > day:
            raise ValueError("Evidence is missing or unavailable at cutoff")

    candidates = []
    ids = set()
    for row in filings:
        validate(row)
        key = row["document_id"]
        if not key or key in ids:
            raise ValueError("Expected distinct registry document IDs")
        ids.add(key)
        if name_key(assessor_name) and name_key(row["entity_name"]) == name_key(assessor_name):
            candidates.append({"document_id": key, "match": "NORMALIZED_NAME_CANDIDATE",
                               "source_ref": row["source_ref"], "observed_date": row["observed_date"]})
    instruments = []
    for row in title_observations:
        validate(row)
        if row["parcel_id"] != parcel_id or not row["instrument_id"]:
            raise ValueError("Title evidence must identify the parcel and instrument")
        if row["kind"] not in {"DEED", "MORTGAGE", "SATISFACTION"}:
            raise ValueError("Unknown title instrument kind")
        instruments.append({key: row[key] for key in ("parcel_id", "instrument_id", "kind", "source_ref", "observed_date")})
        instruments[-1]["review_status"] = "REVIEW_REQUIRED"
    return {
        "parcel_id": parcel_id, "cutoff": cutoff,
        "candidates": sorted(candidates, key=lambda row: row["document_id"]),
        "candidate_state": ("UNRESOLVED" if not candidates else "ONE_NAME_CANDIDATE"
                            if len(candidates) == 1 else "MULTIPLE_NAME_CANDIDATES"),
        "instruments": sorted(instruments, key=lambda row: (row["observed_date"], row["instrument_id"])),
        "accepted_owner_id": None, "signing_authority": "UNKNOWN", "mortgage_status": "UNKNOWN",
    }
