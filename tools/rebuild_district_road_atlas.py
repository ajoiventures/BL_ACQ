"""Rebuild editable local-frame district road models from pinned atlas source URLs."""
import argparse
import csv
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
from urllib.request import urlopen
import zipfile

import pyproj
import rhino3dm as rhino
import shapefile
from shapely.geometry import LineString, box
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site_academy/atlas-seed.csv"
HALF_WIDTH_M = 1000


def load_roads(url, cache):
    filename = url.rsplit("/", 1)[-1]
    if not re.fullmatch(r"https://www2\.census\.gov/geo/tiger/TIGER2024/ROADS/tl_2024_12[0-9]{3}_roads\.zip", url):
        raise ValueError(f"Unexpected road source: {url}")
    path = cache / filename
    if not path.exists():
        with urlopen(url, timeout=35) as response:
            data = response.read(50_000_001)
        if len(data) > 50_000_000 or not zipfile.is_zipfile(io.BytesIO(data)):
            raise ValueError(f"Invalid road archive: {filename}")
        path.write_bytes(data)
    data = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        stem = filename.removesuffix(".zip")
        with shapefile.Reader(shp=io.BytesIO(archive.read(stem + ".shp")),
                              shx=io.BytesIO(archive.read(stem + ".shx")),
                              dbf=io.BytesIO(archive.read(stem + ".dbf"))) as reader:
            crs = pyproj.CRS.from_wkt(archive.read(stem + ".prj").decode())
            roads = [(shape.points, list(shape.parts), shape.bbox) for shape in reader.iterShapes()]
    return crs, roads, hashlib.sha256(data).hexdigest()


def build(rows, output, cache):
    crs, roads, digest = load_roads(rows[0]["County GIS source"], cache)
    records = []
    footprint = box(-HALF_WIDTH_M, -HALF_WIDTH_M, HALF_WIDTH_M, HALF_WIDTH_M)
    for row in rows:
        lon = float(row["Center longitude"])
        lat = float(row["Center latitude"])
        local = pyproj.CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m")
        project = pyproj.Transformer.from_crs(crs, local, always_xy=True)
        inverse = pyproj.Transformer.from_crs(local, crs, always_xy=True)
        search = inverse.transform_bounds(*footprint.bounds, densify_pts=11)
        model = rhino.File3dm()
        model.Settings.ModelUnitSystem = rhino.UnitSystem.Meters
        model.Strings["district"] = row["District"]
        model.Strings["source_url"] = row["County GIS source"]
        model.Strings["source_sha256"] = digest
        model.Strings["local_crs_wkt"] = local.to_wkt()
        model.Strings["source_crs_wkt"] = crs.to_wkt()
        count = 0
        for points, parts, bounds in roads:
            if bounds[2] < search[0] or bounds[0] > search[2] or bounds[3] < search[1] or bounds[1] > search[3]:
                continue
            for start, end in zip(parts, parts[1:] + [len(points)]):
                if end - start < 2:
                    continue
                clipped = transform(project.transform, LineString(points[start:end])).intersection(footprint)
                lines = clipped.geoms if hasattr(clipped, "geoms") else [clipped]
                for line in lines:
                    if line.geom_type != "LineString" or line.length <= 0:
                        continue
                    model.Objects.AddPolyline([rhino.Point3d(x, y, 0) for x, y in line.coords])
                    count += 1
        district = Path(row["Profile"]).parent.name
        path = output / (district + ".3dm")
        if not count or not model.Write(str(path), 7):
            raise RuntimeError(f"No editable model written for {district}")
        reopened = rhino.File3dm.Read(str(path))
        assert len(reopened.Objects) == count
        assert reopened.Settings.ModelUnitSystem == rhino.UnitSystem.Meters
        assert reopened.Strings["source_sha256"] == digest
        records.append({"district": row["District"], "id": district, "file": path.name, "curves": count,
                        "center_lon_lat": [lon, lat], "source_url": row["County GIS source"],
                        "source_sha256": digest, "model_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--cache", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.cache.mkdir(parents=True, exist_ok=True)
    groups = {}
    with SOURCE.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len({row["Profile"] for row in rows}) == 66
    for row in rows:
        groups.setdefault(row["County GIS source"], []).append(row)
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(build, group, args.output, args.cache) for group in groups.values()]
        results = [row for future in futures for row in future.result()]
    assert len(results) == 66
    (args.output / "manifest.json").write_text(json.dumps({
        "source_inventory_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "model_units": "metres", "clip_half_width_m": HALF_WIDTH_M,
        "scope": "Editable road context around listed centers. District boundaries and survey accuracy are unverified.",
        "districts": sorted(results, key=lambda row: row["id"]),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Verified {len(results)} models from {len(groups)} county road archives.")


if __name__ == "__main__":
    main()
