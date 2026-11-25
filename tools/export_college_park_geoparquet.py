"""Convert the verified College Park GeoPackage into bounded GeoParquet batches."""
import argparse
import hashlib
import json
from contextlib import closing
from itertools import zip_longest
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from pyproj import CRS
import pyarrow as pa
import pyarrow.parquet as pq
from shapely import from_wkb

NAMES = ("county_parcel_id", "county_object_ids", "parcel_area_us_survey_sqft",
         "overlap_us_survey_sqft", "overlap_fraction", "geometry")
ENVELOPE_BYTES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}
BATCH = 128


def geometry(blob):
    if blob[:3] != b"GP\0" or blob[3] & 0x30:
        raise ValueError("Unexpected GeoPackage geometry header")
    flags = blob[3]
    endian = "little" if flags & 1 else "big"
    if int.from_bytes(blob[4:8], endian, signed=True) != 2236:
        raise ValueError("Unexpected feature CRS")
    raw = blob[8 + ENVELOPE_BYTES[(flags >> 1) & 7]:]
    g = from_wkb(raw)
    if g.is_empty or not g.is_valid or g.geom_type != "MultiPolygon":
        raise ValueError("Unexpected feature geometry")
    return raw


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_rows(db):
    return db.execute("""SELECT county_parcel_id,county_object_ids,parcel_area_us_survey_sqft,
                         overlap_us_survey_sqft,overlap_fraction,geom
                         FROM college_park ORDER BY county_parcel_id""")


def records(rows):
    for row in rows:
        yield dict(zip(NAMES, (*row[:-1], geometry(row[-1])), strict=True))


def publish(gpkg, gpkg_receipt, output):
    source = json.loads(gpkg_receipt.read_bytes())
    expected = source["outputs"]["GPKG"]
    if sha256(gpkg) != expected["sha256"]:
        raise ValueError("GeoPackage digest mismatch")
    geo = {"version": "1.0.0", "primary_column": "geometry",
           "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["MultiPolygon"],
                                    "crs": CRS.from_epsg(2236).to_json_dict()}}}
    schema = pa.schema(list(zip(NAMES, (pa.string(), pa.string(), pa.float64(),
                           pa.float64(), pa.float64(), pa.binary()), strict=True)),
                       metadata={b"geo": json.dumps(geo).encode("utf-8")})
    with TemporaryDirectory(prefix=".geoparquet-", dir=output.parent) as scratch:
        staged = Path(scratch) / output.name
        with closing(sqlite3.connect(gpkg.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.execute("BEGIN")
            if db.execute("SELECT srs_id,geometry_type_name FROM gpkg_geometry_columns").fetchall() != [(2236, "MULTIPOLYGON")]:
                raise ValueError("Unexpected GeoPackage geometry metadata")
            rows = source_rows(db)
            with staged.open("xb") as stream, pq.ParquetWriter(stream, schema, compression="zstd") as writer:
                while block := rows.fetchmany(BATCH):
                    writer.write_table(pa.Table.from_pylist(list(records(block)), schema=schema))
            with pq.ParquetFile(staged) as file:
                if file.schema_arrow != schema or json.loads(file.schema_arrow.metadata[b"geo"]) != geo:
                    raise ValueError("Unexpected GeoParquet schema or geometry metadata")
                observed = (row for batch in file.iter_batches(batch_size=BATCH) for row in batch.to_pylist())
                count = 0
                for count, (original, exported) in enumerate(
                        zip_longest(records(source_rows(db)), observed), start=1):
                    if original != exported:
                        raise ValueError(f"GeoParquet round-trip mismatch at row {count}")
                if count != expected["rows"]:
                    raise ValueError("GeoParquet row count mismatch")
                row_groups = file.num_row_groups
        digest = sha256(staged)
        output.hardlink_to(staged)
    return {"file": output.name, "rows": count, "row_groups": row_groups,
            "sha256": digest, "gpkg_source_sha256": expected["sha256"], "epsg": 2236,
            "geometry_field": "geometry", "arrow_version": pa.__version__}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("gpkg", "gpkg_receipt", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.gpkg, args.gpkg_receipt, args.output), indent=2))
