"""Validate official Orange County sales and a Sunbiz filing artifact."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

SDF_FIELDS = ("CO_NO", "PARCEL_ID", "ASMNT_YR", "ATV_STRT", "GRP_NO", "DOR_UC",
              "NBRHD_CD", "MKT_AR", "CENSUS_BK", "SALE_ID_CD", "SAL_CHG_CD", "VI_CD",
              "OR_BOOK", "OR_PAGE", "CLERK_NO", "QUAL_CD", "SALE_YR", "SALE_MO",
              "SALE_PRC", "MULTI_PAR_SAL", "RS_ID", "MP_ID", "STATE_PARCEL_ID")
SALE_OUTPUT = ("PARCEL_ID", "SALE_YR", "SALE_MO", "SALE_PRC", "QUAL_CD", "VI_CD",
               "MULTI_PAR_SAL", "SAL_CHG_CD", "CLERK_NO", "OR_BOOK", "OR_PAGE")
SDF_SOURCE = (
    "https://floridarevenue.com/property/dataportal/Documents/PTO%20Data%20Portal/"
    "Tax%20Roll%20Data%20Files/SDF/2026F/Orange%2058%20Final%20SDF%202026.zip"
)
SUNBIZ_LAYOUT = "https://dos.sunbiz.org/data-definitions/cor.html"
SUNBIZ_PORTAL = "https://sftp.floridados.gov/"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sales(path, targets, output):
    member = "SDF58F202601.csv"
    rows = []
    transfer_counts = Counter()
    months = Counter()
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo(member)
        if info.file_size > 20_000_000:
            raise ValueError("SDF member exceeds the Orange batch limit")
        with archive.open(info) as raw, io.TextIOWrapper(raw, encoding="cp1252", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != SDF_FIELDS:
                raise ValueError("unexpected SDF schema")
            for row in reader:
                if (None in row or None in row.values() or row["CO_NO"] != "58"
                        or row["ASMNT_YR"] != "2026" or row["SALE_YR"] not in {"2025", "2026"}
                        or not re.fullmatch(r"0[1-9]|1[0-2]", row["SALE_MO"])):
                    raise ValueError("unexpected SDF scope or structure")
                months[row["SALE_YR"] + "-" + row["SALE_MO"]] += 1
                if row["CLERK_NO"]:
                    transfer_counts[row["CLERK_NO"]] += 1
                if row["PARCEL_ID"] in targets:
                    rows.append({key: row[key] for key in SALE_OUTPUT})
    selected = []
    with (output / "parcel-sales.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, (*SALE_OUTPUT, "spatial_economic_cohort"))
        writer.writeheader()
        for row in rows:
            include = (
                row["VI_CD"] == "I" and row["QUAL_CD"] in {"01", "02"}
                and not row["MULTI_PAR_SAL"] and not row["SAL_CHG_CD"]
                and row["SALE_PRC"].isascii() and row["SALE_PRC"].isdigit()
                and int(row["SALE_PRC"]) > 0 and transfer_counts[row["CLERK_NO"]] == 1
            )
            writer.writerow({**row, "spatial_economic_cohort": int(include)})
            if include:
                selected.append(row)
    return {
        "url": SDF_SOURCE, "archive_sha256": digest(path), "archive_bytes": path.stat().st_size,
        "member": member, "member_bytes": info.file_size, "member_crc32": f"{info.CRC:08x}",
        "months": dict(sorted(months.items())), "total_rows": sum(months.values()),
        "target_join_rows": len(rows), "target_join_parcels": len({r["PARCEL_ID"] for r in rows}),
        "screen_sales": len(selected), "screen_parcels": len({r["PARCEL_ID"] for r in selected}),
        "ownership_link_verified": False, "commercial_release_authorized": False,
    }


def sunbiz(path):
    with path.open("rb") as stream:
        raw = stream.read(5_000_001)
    if len(raw) > 5_000_000:
        raise ValueError("Sunbiz sample exceeds byte budget")
    records = raw.splitlines()
    lengths = Counter(map(len, records))
    status = Counter()
    filing_types = Counter()
    identities = set()
    non_ascii = 0
    invalid = 0
    for record in records:
        non_ascii += not record.isascii()
        if len(record) != 1440 or not re.fullmatch(rb"[A-Z0-9]{6,12}", record[:12].strip()):
            invalid += 1
            continue
        identities.add(record[:12].strip())
        state = record[204:205].decode("ascii", errors="replace")
        status[state if state in {"A", "I"} else "other"] += 1
        filing_types[record[205:220].strip().decode("ascii", errors="replace")] += 1
    return {
        "layout_url": SUNBIZ_LAYOUT, "portal_url": SUNBIZ_PORTAL,
        "portal_artifact": "doc/cor/20261123c.txt", "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw), "records": len(records), "record_width_histogram": dict(lengths),
        "invalid_identity_or_width_records": invalid, "unique_document_ids": len(identities),
        "non_ascii_records": non_ascii, "status": dict(status), "filing_types": dict(filing_types),
        "layout": {"filing_record_width": 1440, "event_record_width": 662,
                   "document_number_start_and_length": [1, 12], "status_start_and_length": [205, 1],
                   "filing_type_start_and_length": [206, 15]},
        "quarterly_archive": {
            "portal_artifact": "doc/Quarterly/Cor/cordata.zip",
            "listed_modified": "2026-10-07 11:45:22 (portal display)",
            "listed_size_kb": 1751010, "bytes_verified": False,
        },
        "snapshot_population_verified": False, "commercial_release_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("sales", "sunbiz", "inventory", "output"):
        parser.add_argument("--" + flag, required=True, type=Path)
    args = parser.parse_args()
    with args.inventory.open(encoding="utf-8", newline="") as stream:
        targets = {row["PARCEL_ID"] for row in csv.DictReader(stream)}
    if not 0 < len(targets) <= 12_000:
        raise ValueError("inventory exceeds the Orange batch limit")
    report = {"sdf": sales(args.sales, targets, args.output), "sunbiz": sunbiz(args.sunbiz)}
    report["inventory_sha256"] = digest(args.inventory)
    with (args.output / "source-verification.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)


if __name__ == "__main__":
    main()
