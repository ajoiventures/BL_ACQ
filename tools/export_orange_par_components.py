"""Build a bounded Orange 2?4 unit geometry exchange from the pinned FDOR PAR archive."""

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import tracemalloc
import zipfile

from pyproj import CRS, Transformer
import pyarrow as pa
import pyarrow.parquet as pq
import shapefile
from shapely import from_wkb, to_wkb
from shapely.geometry import MultiPolygon, shape
from shapely.ops import transform

BATCH = 256
STEM = "orange_2026Ppar"
EXTENSIONS = ("prj", "shp", "shx", "dbf")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def export(archive, docs, output):
    evidence = docs / "source-contract-review/orange-fdor-gis.json"
    verified = json.loads(evidence.read_bytes())
    arc_sha = digest(archive)
    if arc_sha != verified["archive_sha256"]:
        raise ValueError("FDOR archive digest mismatch")
    final_roll = docs / "orange-final-roll/official_final_roll_inventory.csv"
    roll_sha = digest(final_roll)
    pins = json.loads((docs / "orange-sales-spatial/spatial-input-digests.json").read_bytes())
    if roll_sha != pins[final_roll.name]:
        raise ValueError("Final roll digest mismatch")
    with final_roll.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    targets = {r["PARCEL_ID"]: r for r in rows}
    if not 0 < len(targets) == len(rows) <= 12_000 or any(
        r["NO_RES_UNTS"] not in ("2", "3", "4") or (r["CO_NO"], r["ASMNT_YR"]) != ("58", "2026")
        for r in rows
    ):
        raise ValueError("Unexpected final-roll inventory")
    output.mkdir(parents=True, exist_ok=True)
    parquet = output / "orange-2-to-4-par-components-v1.parquet"
    if parquet.exists():
        raise FileExistsError(parquet)
    observed = Counter()
    invalid = []
    expected = {}
    batch = []
    with tempfile.TemporaryDirectory(dir=output) as work, zipfile.ZipFile(archive) as zipped:
        path = Path(work)
        members = {i["name"]: i for i in verified["members"]}
        for ext in EXTENSIONS:
            name = f"{STEM}.{ext}"
            member = zipped.getinfo(name)
            pin = members[name]
            if member.file_size != pin["bytes"] or f"{member.CRC:08x}" != pin["crc32"]:
                raise ValueError(f"FDOR member mismatch: {name}")
            with zipped.open(member) as src, (path / name).open("wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
        crs = CRS.from_wkt((path / f"{STEM}.prj").read_text(encoding="ascii"))
        if not crs.is_projected or any(axis.unit_name != "US survey foot" for axis in crs.axis_info):
            raise ValueError("FDOR projected CRS or units unavailable")
        target_crs = CRS.from_epsg(2236)
        project = Transformer.from_crs(crs, target_crs, always_xy=True).transform
        geo = {"version": "1.0.0", "primary_column": "geometry",
               "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["MultiPolygon"],
                                        "crs": target_crs.to_json_dict()}}}
        schema = pa.schema([
            ("state_parcel_id", pa.string()), ("county_parcel_id", pa.string()),
            ("fdor_shape_index", pa.int64()), ("reported_units", pa.int8()),
            ("component_area_us_survey_sqft", pa.float64()), ("geometry", pa.binary()),
        ], metadata={b"geo": json.dumps(geo).encode("utf-8")})
        with shapefile.Reader(str(path / STEM)) as layer, pq.ParquetWriter(parquet, schema) as writer:
            for record in layer.iterRecords(fields=["PARCELNO"]):
                pid = record[0]
                if pid not in targets:
                    continue
                observed[pid] += 1
                source_shape = layer.shape(record.oid)
                if source_shape.shapeType not in {shapefile.POLYGON, shapefile.POLYGONZ, shapefile.POLYGONM}:
                    invalid.append({"parcel_id": pid, "shape_index": record.oid, "reason": "non_polygon"})
                    continue
                geom = transform(project, shape(source_shape.__geo_interface__))
                if geom.geom_type == "Polygon":
                    geom = MultiPolygon([geom])
                if geom.is_empty or not geom.is_valid or geom.area <= 0:
                    invalid.append({"parcel_id": pid, "shape_index": record.oid, "reason": "invalid_geometry"})
                    continue
                roll = targets[pid]
                raw = to_wkb(geom)
                row = {"state_parcel_id": pid, "county_parcel_id": roll["ALT_KEY"],
                       "fdor_shape_index": record.oid, "reported_units": int(roll["NO_RES_UNTS"]),
                       "component_area_us_survey_sqft": geom.area, "geometry": raw}
                expected[record.oid] = (pid, roll["ALT_KEY"], row["reported_units"], geom.area,
                                         hashlib.sha256(raw).digest())
                batch.append(row)
                if len(batch) == BATCH:
                    writer.write_table(pa.Table.from_pylist(batch, schema=schema))
                    batch.clear()
            if batch:
                writer.write_table(pa.Table.from_pylist(batch, schema=schema))

    file = pq.ParquetFile(parquet)
    assert json.loads(file.schema_arrow.metadata[b"geo"]) == geo
    seen = set()
    for block in file.iter_batches(batch_size=BATCH):
        for row in block.to_pylist():
            oid = row["fdor_shape_index"]
            geom = from_wkb(row["geometry"])
            assert geom.is_valid and oid not in seen
            assert expected[oid] == (row["state_parcel_id"], row["county_parcel_id"], row["reported_units"],
                                     geom.area, hashlib.sha256(row["geometry"]).digest())
            assert row["component_area_us_survey_sqft"] == geom.area
            seen.add(oid)
    assert seen and seen == expected.keys()
    missing = sorted(targets.keys() - observed.keys())
    repeated = {p: count for p, count in sorted(observed.items()) if count > 1}
    assert sum(observed.values()) == len(seen) + len(invalid)
    return {"contract": "orange-fdor-par-component-exchange/1", "source_archive_sha256": arc_sha,
            "final_roll_sha256": roll_sha, "target_parcels": len(targets),
            "distinct_exact_parcels": len(observed), "rows": len(seen), "row_groups": file.num_row_groups,
            "epsg": 2236, "source_crs_wkt": crs.to_wkt(), "output_dimensions": "XY", "area_units": "US survey square feet", "missing_parcels": missing,
            "repeated_parcel_components": repeated, "quarantined_shapes": invalid,
            "file": parquet.name, "sha256": digest(parquet), "release_authorized": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "docs", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    tracemalloc.start()
    result = export(args.archive, args.docs, args.output)
    result["peak_python_traced_bytes"] = tracemalloc.get_traced_memory()[1]
    with (args.output / "orange-par-component-exchange.json").open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    print(result["target_parcels"], result["rows"], len(result["quarantined_shapes"]))
