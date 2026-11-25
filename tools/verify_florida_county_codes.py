"""Join the official FDOR county number table to Census 2026 county GEOIDs."""
import argparse
import csv
import io
from pathlib import Path
import re
import zipfile

from pypdf import PdfReader


def normalize(name):
    name = name.removesuffix(" County")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def crosswalk(fdor, census):
    text = PdfReader(fdor).pages[0].extract_text()
    section = text.split("County Numbers\n", 1)[1].split("\n:", 1)[0]
    pairs = re.findall(r"^([A-Za-z. ]+?) ([0-9]{2})\s*$", section, re.MULTILINE)
    codes = {number: name for name, number in pairs}
    if len(pairs) != 67 or set(codes) != {str(n) for n in range(11, 78)}:
        raise ValueError("FDOR source did not yield exactly its 67 county numbers")
    with zipfile.ZipFile(census) as archive:
        member = archive.getinfo("2026_Gaz_counties_national.txt")
        if member.file_size > 2_000_000:
            raise ValueError("unexpected Census source size")
        with archive.open(member) as stream:
            florida = [row for row in csv.DictReader(
                io.TextIOWrapper(stream, encoding="utf-8-sig", newline=""), delimiter="|"
            ) if row["USPS"] == "FL"]
    by_name = {normalize(row["NAME"]): row for row in florida}
    if len(florida) != 67 or len(by_name) != 67:
        raise ValueError("expected 67 distinct Census Florida counties")
    matched = []
    for code, name in sorted(codes.items()):
        label = "miamidade" if name == "Dade" else normalize(name)
        county = by_name.get(label)
        if not county or not re.fullmatch(r"12[0-9]{3}", county["GEOID"]):
            raise ValueError(f"missing Florida Census GEOID for {name}")
        matched.append((code, name, county["GEOID"], county["NAME"]))
    if len({row[2] for row in matched}) != 67:
        raise ValueError("county code crosswalk is not one to one")
    return matched


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fdor", "census", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    rows = crosswalk(args.fdor, args.census)
    with args.output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("fdor_county_code", "fdor_county_label", "census_county_geoid", "census_county_name"))
        writer.writerows(rows)
    print(f"{len(rows)} one-to-one county mappings")


if __name__ == "__main__":
    main()
