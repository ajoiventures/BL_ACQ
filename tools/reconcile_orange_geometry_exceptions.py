"""Reconcile bounded Orange geometry gaps against roll flags and county features."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from backend.core.state_parcel_research import orange_id_candidate


def observed_change(code, year):
    if not code:
        return None
    match = re.fullmatch(r"([12])(0[1-9]|1[0-2])([0-9]{2})", code)
    if match is None or int(match[3]) != year % 100:
        raise ValueError("unexpected parcel split/combine code")
    return {"change": {"1": "split", "2": "combine"}[match[1]],
            "source_month": f"{year}-{match[2]}", "raw_code": code}


def verify_response(directory, name):
    path = directory / f"{name}.json"
    raw = path.read_bytes()
    receipt = json.loads((directory / f"{name}.receipt.json").read_bytes())
    if receipt["sha256"] != hashlib.sha256(raw).hexdigest() or receipt["bytes"] != len(raw):
        raise ValueError(f"source receipt mismatch: {name}")
    return [f["attributes"] for f in json.loads(raw)["features"]]


def run(directory):
    def read(name):
        return json.loads((directory / name).read_bytes())

    selected = read("gis-exception-input.json")
    roll = {row["PARCEL_ID"]: row for row in read("nal-six-projection.json")}
    by_county, by_state = defaultdict(list), defaultdict(list)
    for row in verify_response(directory, "county_live"):
        by_county[row["PARCEL"]].append(row)
    for row in verify_response(directory, "state_live"):
        if (row["CO_NO"], row["ASMNT_YR"]) != (58, 2026):
            raise ValueError("unexpected state source scope")
        by_state[row["PARCEL_ID"]].append(row)

    classifications = Counter()
    output = []
    if len({r["state_id"] for r in selected}) != len(selected) or len(selected) > 100:
        raise ValueError("duplicate or excessive exception cohort")
    for row in selected:
        source, county = row["state_id"], row["county_id"]
        if orange_id_candidate(source) != county:
            raise ValueError("county ID crosswalk mismatch")
        records = by_county[county]
        change = None
        if not row["archive_shapes"]:
            official = roll[source]
            if official["ALT_KEY"] != county or official["NO_RES_UNTS"] != row["nal_units"]:
                raise ValueError("final NAL row inconsistent with selected gap")
            change = observed_change(official["PAR_SPLT"], 2026)
            identity_agrees = len(records) == 1 and (
                records[0]["SEC_TWN_RNG"].replace("-", "") == source
                and records[0]["SITUS"].strip().upper() == official["PHY_ADDR1"].strip().upper()
            )
            if not identity_agrees:
                disposition = "current_county_identity_unconfirmed"
            elif change and change["change"] == "split":
                disposition = "same_id_in_current_county_gis_with_roll_split_flag"
            else:
                disposition = "same_id_in_current_county_gis"
        elif row["archive_shapes"] == 2 and len(records) == 2 and (
            {c["NC_FLAG"] for c in records} == {1, 2}
            and all(c["SEC_TWN_RNG"].replace("-", "") == source for c in records)
        ):
            disposition = "retained_one_identity_with_two_county_features"
        else:
            disposition = "feature_repeat_unresolved"
        classifications[disposition] += 1
        output.append({
            **row, "disposition": disposition, "nal_change_observation": change,
            "state_service_feature_count": len(by_state[source]),
            "county_features": [
                {"object_id": r["OBJECTID"], "component_flag": r["NC_FLAG"]}
                for r in sorted(records, key=lambda item: item["OBJECTID"])
            ],
            "lineage_verified": False, "lawful_units": None, "production_admitted": False,
        })
    return {"assessment_year": 2026, "county_fips": "12095",
            "dispositions": dict(classifications), "rows": output,
            "scope": "One assessment identity per county ID; archive observations preserved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run(args.evidence)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(report["dispositions"])


if __name__ == "__main__":
    main()
