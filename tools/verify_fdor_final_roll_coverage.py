"""Verify aggregate coverage from a bounded FDOR county final assessment roll."""

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile

from backend.core.acquisition_source_gate import Purpose, route


REQUIRED = {"CO_NO", "PARCEL_ID", "FILE_T", "ASMNT_YR", "NO_RES_UNTS", "NO_BULDNG"}
ENCODING = "cp1252"


def audit(archive, *, member, dor_code, county_fips, year, source_url, large_county=False, release='final', use_classes=False, identity_digests=False):
    release_code = {"final": "F", "preliminary": "P"}[release]
    # The expanded profile covers the largest published county files while
    # keeping both archive expansion and retained identities bounded.
    archive_limit, member_limit, row_limit = (
        (70_000_000, 700_000_000, 1_400_000) if large_county
        else (50_000_000, 300_000_000, 650_000)
    )
    if not 0 < archive.stat().st_size <= archive_limit:
        raise ValueError("Archive size exceeds diagnostic limit")
    if not re.fullmatch(r"12[0-9]{3}", county_fips) or not re.fullmatch(r"[0-9]{2}", dor_code):
        raise ValueError("Expected Florida FIPS and DOR county identifiers")
    gate = route("FDOR", Purpose.COMMERCIAL_RESEARCH)
    if gate["data_release_authorized"]:
        raise ValueError("Expected a quarantined roll diagnostic")
    with archive.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    seen = set()
    unit_counts = Counter()
    building_counts = Counter()
    roll_use_counts = Counter()
    target_use_counts = Counter()
    normalized_rows = hashlib.sha256()
    alternate_keys = Counter()
    missing_alternate_keys = 0
    with ZipFile(archive) as zipped:
        if member is None:
            pattern = re.compile(rf"NAL{re.escape(dor_code)}{release_code}{re.escape(year)}[0-9]{{2}}(?:VAB[0-9]*)?\.csv", re.IGNORECASE)
            candidates = [entry for entry in zipped.infolist() if pattern.fullmatch(entry.filename)]
            if len(candidates) != 1:
                raise ValueError("Expected one unambiguous county final-roll member")
            member = candidates[0].filename
        info = zipped.getinfo(member)
        if not 0 < info.file_size <= member_limit:
            raise ValueError("Roll member size exceeds diagnostic limit")
        with zipped.open(info) as raw, io.TextIOWrapper(raw, encoding=ENCODING, newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            fields = reader.fieldnames or []
            required = REQUIRED | ({"DOR_UC"} if use_classes or identity_digests else set())
            if identity_digests:
                required.add("ALT_KEY")
            if not required <= set(fields) or len(set(fields)) != len(fields):
                raise ValueError("Unexpected roll layout")
            for row in reader:
                if (len(seen) >= row_limit or None in row or None in row.values()
                        or (row["CO_NO"], row["ASMNT_YR"], row["FILE_T"]) != (dor_code, year, "R")):
                    raise ValueError(f"Invalid roll scope at row {reader.line_num}")
                key = row["PARCEL_ID"].strip()
                if not key or key in seen:
                    raise ValueError(f"Missing or duplicate parcel identity at row {reader.line_num}")
                seen.add(key)
                use = None
                if use_classes or identity_digests:
                    use = row["DOR_UC"].strip()
                    if not use:
                        use = "missing"
                    elif not re.fullmatch(r"[0-9]{1,3}", use):
                        raise ValueError(f"Unexpected DOR use code at row {reader.line_num}")
                    else:
                        use = use.zfill(3)
                    roll_use_counts[use] += 1
                units = row["NO_RES_UNTS"].strip()
                if units not in {"2", "3", "4"}:
                    continue
                unit_counts[units] += 1
                if use_classes:
                    target_use_counts[use] += 1
                buildings = row["NO_BULDNG"].strip()
                if buildings and (not buildings.isascii() or not buildings.isdecimal()):
                    raise ValueError(f"Invalid building count at row {reader.line_num}")
                building_counts[buildings or "missing"] += 1
                if identity_digests:
                    alternate = row["ALT_KEY"].strip()
                    if alternate:
                        alternate_keys[alternate] += 1
                    else:
                        missing_alternate_keys += 1
                    # An ALT_KEY is an observation. Keep the primary namespace
                    # based on the roll parcel ID, even when alternates collide.
                    normalized = [f"{county_fips}:{key}", use, int(units),
                                  int(buildings) if buildings else None, alternate or None]
                    normalized_rows.update((json.dumps(normalized, ensure_ascii=False) + "\n").encode("utf-8"))
    if not seen:
        raise ValueError("Final roll contains no parcels")
    report = {
        "contract": "br-fdor-final-roll-coverage/1", "source_url": source_url,
        "archive_sha256": archive_hash, "archive_bytes": archive.stat().st_size,
        "member": member, "member_crc32": f"{info.CRC:08x}", "member_bytes": info.file_size,
        "encoding": ENCODING, "schema_sha256": hashlib.sha256(json.dumps(fields).encode()).hexdigest(),
        "release": release, "county_fips": county_fips, "dor_code": dor_code, "assessment_year": int(year),
        "distinct_roll_parcels": len(seen), "reported_2_to_4_total": sum(unit_counts.values()),
        "reported_residential_unit_buckets": dict(sorted(unit_counts.items())),
        "reported_building_count_buckets_for_targets": dict(sorted(building_counts.items())),
        "source_gate": gate, "verified_lawful_units": 0, "production_admissions": 0,
    }
    if use_classes:
        report["source_reported_use_code_counts"] = dict(sorted(roll_use_counts.items()))
        report["reported_2_to_4_by_use_code"] = dict(sorted(target_use_counts.items()))
    if identity_digests:
        report["identity_diagnostic"] = {
            "scope": "IN_MEMORY_TARGET_NORMALIZATION",
            "primary_namespace": "CENSUS_COUNTY_FIPS:FDOR_PARCEL_ID",
            "ordered_normalized_target_sha256": normalized_rows.hexdigest(),
            "distinct_observed_alternate_keys": len(alternate_keys),
            "targets_missing_alternate_key": missing_alternate_keys,
            "repeated_alternate_keys": sum(count > 1 for count in alternate_keys.values()),
            "targets_with_repeated_alternate_key": sum(count for count in alternate_keys.values() if count > 1),
            "alternate_keys_used_for_identity_merges": 0,
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--member")
    parser.add_argument("--dor-code", required=True)
    parser.add_argument("--county-fips", required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--release", choices=("final", "preliminary"), default="final")
    parser.add_argument("--identity-digests", action="store_true")
    parser.add_argument("--use-classes", action="store_true")
    parser.add_argument("--large-county", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = vars(parser.parse_args())
    output = args.pop("output")
    report = audit(**args)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
