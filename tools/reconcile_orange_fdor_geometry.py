"""Reconcile Orange FDOR GIS IDs to the final NAL and publish aggregate coverage."""
import argparse
from collections import Counter
import csv
import io
import json
from pathlib import Path
import re
import struct
import zipfile

from tools.verify_orange_sales_and_sunbiz import digest


def nal_population(path):
    seen = set()
    targets = {}
    with zipfile.ZipFile(path) as archive:
        member = archive.getinfo("NAL58F202601.csv")
        if member.file_size > 300_000_000:
            raise ValueError("NAL exceeds limit")
        with archive.open(member) as handle:
            reader = csv.DictReader(io.TextIOWrapper(handle, encoding="cp1252", newline=""))
            for row in reader:
                pid = row["PARCEL_ID"]
                if (row["CO_NO"] != "58" or row["ASMNT_YR"] != "2026"
                        or not re.fullmatch(r"[0-9]{15}", pid) or pid in seen):
                    raise ValueError("unexpected roll identity")
                seen.add(pid)
                if row["NO_RES_UNTS"] in {"2", "3", "4"}:
                    targets[pid] = int(row["NO_RES_UNTS"])
    return seen, targets


def gis_population(path):
    with zipfile.ZipFile(path) as archive:
        info, = [i for i in archive.infolist() if i.filename.lower().endswith(".dbf")]
        with archive.open(info) as handle:
            header = handle.read(32)
            count, header_size, width = struct.unpack_from("<IHH", header, 4)
            if not (0 < count <= 1_000_000 and 32 < header_size <= 20_000 and 0 < width <= 10_000):
                raise ValueError("unexpected DBF dimensions")
            schema = handle.read(header_size - 32)
            fields = {}
            start = 1
            for offset in range(0, len(schema), 32):
                if schema[offset] == 13:
                    break
                field = schema[offset:offset + 32]
                name = field[:11].split(b"\0", 1)[0].decode("ascii")
                fields[name.upper()] = slice(start, start + field[16])
                start += field[16]
            if start != width or "PARCELNO" not in fields:
                raise ValueError("unexpected DBF parcel layout")
            ids = Counter()
            units = {}
            unit_conflicts = set()
            invalid_ids = deleted = 0
            for remaining in range(0, count, 8192):
                batch = min(8192, count - remaining)
                data = handle.read(width * batch)
                if len(data) != width * batch:
                    raise ValueError("truncated parcel layer")
                for offset in range(0, len(data), width):
                    record = data[offset:offset + width]
                    if record[0] == 42:
                        deleted += 1
                        continue
                    if record[0] != 32:
                        raise ValueError("invalid DBF record marker")
                    key = record[fields["PARCELNO"]].strip()
                    if not re.fullmatch(rb"[0-9]{15}", key):
                        invalid_ids += 1
                        continue
                    pid = key.decode("ascii")
                    ids[pid] += 1
                    if "NO_RES_UNT" in fields:
                        value = record[fields["NO_RES_UNT"]].strip().decode("ascii")
                        if pid in units and units[pid] != value:
                            unit_conflicts.add(pid)
                        units[pid] = value
            if handle.read() not in (b"", b"\x1a"):
                raise ValueError("unexpected bytes after DBF records")
    return count, deleted, invalid_ids, ids, units, unit_conflicts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("nal", "gis", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    nal, targets = nal_population(args.nal)
    count, deleted, invalid, gis, units, unit_conflicts = gis_population(args.gis)
    observed = gis.keys()
    overlaps = observed & targets.keys()
    report = {
        "nal_sha256": digest(args.nal), "gis_sha256": digest(args.gis),
        "county": "Orange", "exact_raw_key_pair": ["PARCELNO", "PARCEL_ID"],
        "nal_records": len(nal), "gis_records": count, "gis_deleted_rows": deleted,
        "gis_invalid_or_nonstandard_id_rows": invalid, "gis_distinct_exact_format_ids": len(gis),
        "gis_extra_rows_for_repeated_ids": sum(d - 1 for d in gis.values()),
        "matched_unique_ids": len(observed & nal), "nal_only_unique_ids": len(nal - observed),
        "gis_only_unique_ids": len(observed - nal), "nal_reported_2_to_4_parcels": len(targets),
        "nal_target_parcels_with_exact_gis_id": len(overlaps),
        "nal_target_parcels_missing_exact_gis_id": len(targets.keys() - observed),
        "nal_target_parcels_with_repeated_gis_id": sum(gis[x] > 1 for x in overlaps),
        "gis_unit_field_present": bool(units),
        "gis_target_parcels_with_internal_unit_disagreement": len(unit_conflicts & overlaps),
        "unmatched_raw_ids_published": False,
    }
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
