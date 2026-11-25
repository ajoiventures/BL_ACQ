"""Aggregate the pinned Orange final assessment roll by official Orlando tax districts."""
import argparse
from collections import Counter
import csv
from hashlib import file_digest
from io import TextIOWrapper
import json
from pathlib import Path
from zipfile import ZipFile

COUNTY_RECEIPT = Path("docs/economic-development/orange-county-reported-housing-comparator.json")
RATE_CHART = "https://ocpaimages.ocpafl.org/api/Content/GetContentDynamicFile?contentFileID=418587"
ORLANDO_CODES = {
    "ORL07", "ORL08", "ORL13", "ORL22", "ORL25", "ORL26", "ORL27",
    "ORL28", "ORL36", "ORL71", "ORL77", "ORL78", "ORL88", "ORL89",
    "ORL90", "ORL91", "ORL92", "ORL93", "ORL94", "ORL95",
}


def summarize(path):
    county = json.loads(COUNTY_RECEIPT.read_bytes())
    with path.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    if digest != county["roll_archive_sha256"]:
        raise ValueError("Orange final roll differs from the pinned county release")
    counts, numeric, units = Counter(), Counter(), Counter()
    county_count = 0
    with ZipFile(path) as archive, archive.open(county["roll_member"]) as rows:
        for row in csv.DictReader(TextIOWrapper(rows, encoding="cp1252", newline="")):
            county_count += 1
            code = row["TAX_AUTH_CD"]
            if code.startswith("ORL") and code not in ORLANDO_CODES:
                raise ValueError(f"Unmapped Orlando authority: {code}")
            if code not in ORLANDO_CODES:
                continue
            counts[code] += 1
            value = row["NO_RES_UNTS"].strip()
            if value.isascii() and value.isdecimal():
                numeric[code] += 1
                units[code] += int(value)
    if county_count != county["parcel_denominator"]:
        raise ValueError("Orange final roll denominator differs from the county receipt")
    return {
        "place_id": "US-FL-ORLANDO",
        "assessment_year": county["assessment_year"],
        "roll_archive_sha256": digest,
        "roll_member": county["roll_member"],
        "authority_chart": RATE_CHART,
        "parcel_denominator": sum(counts.values()),
        "parcels_with_numeric_values": sum(numeric.values()),
        "parcels_without_numeric_values": sum(counts.values()) - sum(numeric.values()),
        "reported_unit_sum": sum(units.values()),
        "districts": {
            code: {"parcels": count, "numeric_parcels": numeric[code],
                   "unknown_parcels": count - numeric[code], "reported_units": units[code]}
            for code, count in sorted(counts.items())
        },
        "scope": "Whole parcels whose tax authority is listed under Orlando in the 2026 rate chart. Tax jurisdiction differs from a geometric clipping. Vacancy, occupancy and lawful units are unknown.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roll", type=Path)
    print(json.dumps(summarize(parser.parse_args().roll), indent=2))
