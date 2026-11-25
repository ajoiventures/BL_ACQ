"""Build an Orlando Census place comparator from 2020 BAF and 2024 LODES."""
from concurrent.futures import ThreadPoolExecutor
import csv
import gzip
from hashlib import sha256
from io import BytesIO, TextIOWrapper
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

BAF = "https://www2.census.gov/geo/docs/maps-data/data/baf2020/BlockAssign_ST12_FL.zip"
MEMBER = "BlockAssign_ST12_FL_INCPLACE_CDP.txt"
WORKSPACE = Path("docs/economic-development")


def download(url):
    limit = 20_000_000
    with urlopen(url, timeout=30) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Census download exceeded the byte limit")
    return data


def build():
    district = json.loads((WORKSPACE / "college-park-lodes-employment.json").read_bytes())
    modes = district["measures"]
    with ThreadPoolExecutor(max_workers=3) as executor:
        boundary, *files = executor.map(download, [BAF, *(item["source"] for item in modes.values())])
    with ZipFile(BytesIO(boundary)) as archive, archive.open(MEMBER) as member:
        blocks = set()
        for row in csv.DictReader(TextIOWrapper(member, encoding="utf-8"), delimiter="|"):
            if row["PLACEFP"] != "53000":
                continue
            block = row["BLOCKID"]
            if len(block) != 15 or not block.startswith("12") or not block.isdecimal() or block in blocks:
                raise ValueError("Invalid or repeated Orlando block ID")
            blocks.add(block)
    if not blocks:
        raise ValueError("No blocks assigned to Orlando")
    measures = {}
    for (mode, source), compressed in zip(modes.items(), files, strict=True):
        digest = sha256(compressed).hexdigest()
        if digest != source["source_sha256"]:
            raise ValueError(f"{mode} differs from the district source release")
        id_field = {"wac": "w_geocode", "rac": "h_geocode"}[mode]
        selected = {}
        with gzip.GzipFile(fileobj=BytesIO(compressed)) as stream:
            for row in csv.DictReader(TextIOWrapper(stream, encoding="utf-8", newline="")):
                block = row[id_field]
                if block in blocks:
                    if block in selected:
                        raise ValueError(f"Repeated {mode} row for {block}")
                    selected[block] = int(row["C000"])
        measures[mode] = {
            "jobs": sum(selected.values()),
            "blocks_with_source_rows": len(selected),
            "blocks_without_source_rows": len(blocks) - len(selected),
            "source": source["source"],
            "source_sha256": digest,
        }
    return {
        "place_id": "US-FL-ORLANDO",
        "census_place_fips": "1253000",
        "boundary_vintage": 2020,
        "boundary_source": BAF,
        "boundary_member": MEMBER,
        "boundary_archive_sha256": sha256(boundary).hexdigest(),
        "block_set_sha256": sha256("\n".join(sorted(blocks)).encode()).hexdigest(),
        "blocks": len(blocks),
        "employment_year": district["year"],
        "job_type": district["job_type"],
        "method": "Exact 2020 Census block assignment by incorporated place code",
        "limits": "2020 city geography. Subsequent annexations are outside this edition. District selections use a different boundary method. Job counts may include several jobs per person.",
        "measures": measures,
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
