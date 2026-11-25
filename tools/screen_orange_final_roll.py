"""Run the 2026 Orange final-roll cohort through the local acquisition screen."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np

from backend.core.acquisition_batch import FIELDS, screen, summarize
from backend.core.acquisition_source_gate import Purpose, route
from backend.core.state_parcel_research import orange_id_candidate

MAX_ROWS = 12_000
INPUT_FIELDS = {
    "PARCEL_ID", "CO_NO", "ASMNT_YR", "FILE_T", "NO_RES_UNTS", "DOR_UC",
    "JV", "NO_BULDNG", "LND_SQFOOT", "TOT_LVG_AREA", "ACT_YR_BLT",
    "PHY_ADDR1", "ALT_KEY", "state_comparison",
}


def load_final_roll(path, expected_sha256, expected_rows):
    if not 0 < expected_rows <= MAX_ROWS:
        raise ValueError("expected row count exceeds intake limit")
    with Path(path).open("rb") as stream:
        raw = stream.read(2_000_001)
    if len(raw) > 2_000_000 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("inventory size or digest mismatch")
    gate = route("FDOR", Purpose.COMMERCIAL_RESEARCH)
    if gate["disposition"] != "HOLD" or gate["data_release_authorized"]:
        raise ValueError("unexpected disposition for the quarantined diagnostic")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""), strict=True)
        if set(reader.fieldnames or ()) != INPUT_FIELDS or len(reader.fieldnames) != len(INPUT_FIELDS):
            raise ValueError("unexpected inventory schema")
        records = {}
        for row in reader:
            if len(records) >= expected_rows or None in row or None in row.values():
                raise ValueError("invalid or excess inventory row")
            if (row["CO_NO"], row["ASMNT_YR"], row["FILE_T"]) != ("58", "2026", "R"):
                raise ValueError("inventory scope mismatch")
            if row["NO_RES_UNTS"] not in {"2", "3", "4"}:
                raise ValueError("invalid reported residential units")
            buildings = row["NO_BULDNG"]
            if buildings and (not buildings.isascii() or not buildings.isdecimal()):
                raise ValueError("invalid reported building count")
            county_id = orange_id_candidate(row["PARCEL_ID"])
            if row["ALT_KEY"] != county_id:
                raise ValueError("published alternate parcel ID disagrees with the county key")
            key = "12095:" + county_id
            if key in records:
                raise ValueError(f"duplicate parcel key: {key}")
            records[key] = {
                "parcel_key": key,
                "source_parcel_id": row["PARCEL_ID"],
                "source_reported_units": int(row["NO_RES_UNTS"]),
                "source_reported_buildings": int(buildings) if buildings else None,
                "source_use_code": row["DOR_UC"],
                "source_situs": row["PHY_ADDR1"],
                "legal_units": None,
                "decision": "HOLD",
            }
    except (csv.Error, UnicodeDecodeError) as exc:
        raise ValueError("invalid inventory CSV encoding or syntax") from exc

    if len(records) != expected_rows:
        raise ValueError("inventory count mismatch")

    return gate, [records[key] for key in sorted(records)]


def prepare(path, expected_sha256, expected_rows, backend_name):
    gate, records = load_final_roll(path, expected_sha256, expected_rows)
    ordered = [{key: value for key, value in r.items() if key != "source_situs"} for r in records]
    arrays = {field: np.full(len(ordered), -1, dtype=np.int64) for field in FIELDS}
    arrays["reported_units"] = np.array(
        [record["source_reported_units"] for record in ordered], dtype=np.int64
    )
    values, diagnostics = screen(arrays, backend_name)
    return {
        "contract": "br-orange-final-roll-screen/1",
        "source_gate": gate,
        "inventory_sha256": expected_sha256,
        "county_fips": "12095",
        "assessment_year": 2026,
        "diagnostics": diagnostics,
        "screen": summarize(values),
        "screen_field_sha256": {
            field: hashlib.sha256(array.tobytes()).hexdigest()
            for field, array in sorted(values.items())
        },
        "decisions": dict(Counter(record["decision"] for record in ordered)),
        "production_admissions": 0,
        "records": ordered,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory")
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--backend", choices=("cpu_reference", "cuda"), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = prepare(args.inventory, args.sha256, args.rows, args.backend)
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
