"""Rehearse nearby-sale comparison against the complete Orange geometry inventory."""
import argparse
import hashlib
import json
from pathlib import Path

from pyproj import Transformer
import pyarrow.parquet as pq
from shapely import from_wkb
from shapely.ops import unary_union

from backend.core.acquisition_batch import backend
from backend.core.acquisition_source_gate import Purpose, route
from tools.benchmark_orange_observed_spatial import measure_pool_peak
from tools.run_orange_observed_spatial_economic import compare_nearby, load_rows, observed_transfers


def pinned(path, expected):
    with path.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != expected:
            raise ValueError(f"Source revision mismatch: {path.name}")
    return path


def load_geometry_components(docs):
    spatial = docs / "orange-sales-spatial"
    exchange = docs / "fdor-geometry-exceptions"
    fdor = json.loads((exchange / "orange-par-component-exchange.json").read_bytes())
    county = json.loads((exchange / "orange-county-gap-exchange.json").read_bytes())
    pins = json.loads((spatial / "spatial-input-digests.json").read_bytes())
    inventory_name = "official_final_roll_inventory.csv"
    inventory = load_rows(docs / "orange-final-roll" / inventory_name, pins[inventory_name])
    by_state = {row["PARCEL_ID"]: row["ALT_KEY"] for row in inventory}
    components = {}
    county_keys = set()
    sources = [
        (fdor["file"], fdor["sha256"], "FDOR_PAR", fdor["rows"]),
        ("orange-county-gap-components-v1.parquet", county["county_geoparquet_sha256"],
         "OCPA_GAP_SUPPLEMENT", county["county_gap_rows"]),
    ]
    for filename, sha, source, expected_rows in sources:
        file = pq.ParquetFile(pinned(exchange / filename, sha))
        if file.metadata.num_rows != expected_rows:
            raise ValueError("Component count differs from source receipt")
        for batch in file.iter_batches(batch_size=256, columns=["state_parcel_id", "county_parcel_id", "geometry"]):
            for row in batch.to_pylist():
                pid = row["state_parcel_id"]
                if by_state.get(pid) != row["county_parcel_id"]:
                    raise ValueError("Component does not match the final-roll crosswalk")
                if source == "OCPA_GAP_SUPPLEMENT":
                    if pid in components:
                        raise ValueError("County supplement overlaps FDOR coverage")
                    county_keys.add(pid)
                components.setdefault(pid, []).append(from_wkb(row["geometry"]))
    if components.keys() != by_state.keys() or county_keys != set(fdor["missing_parcels"]):
        raise ValueError("Geometry sources do not cover the pinned inventory")

    return components, county_keys, by_state, fdor, county, pins, inventory


def load_full_geometry_observations(docs):
    components, county_keys, by_state, fdor, county, pins, inventory = load_geometry_components(docs)
    sales = load_rows(docs / "orange-sales-spatial" / "parcel-sales.csv", pins["parcel-sales.csv"])
    project = Transformer.from_crs(2236, 4326, always_xy=True)
    selected = {row["PARCEL_ID"] for row in sales if row["spatial_economic_cohort"] == "1"}
    points = []
    for pid in sorted(selected):
        anchor = unary_union(components[pid]).representative_point()
        lon, lat = project.transform(anchor.x, anchor.y)
        points.append({"PARCEL": by_state[pid], "OBJECTID": None, "LATITUDE": lat, "LONGITUDE": lon})
    observations, exclusions = observed_transfers(inventory, sales, points)
    for row in observations:
        row["point_source"] = "OCPA_GAP_SUPPLEMENT" if row["source_parcel_id"] in county_keys else "FDOR_PAR"
    return observations, exclusions, len(components), fdor, county, pins, inventory, sales


def run(docs):
    spatial = docs / "orange-sales-spatial"
    observations, exclusions, coverage, fdor, county, pins, inventory, sales = load_full_geometry_observations(docs)
    cpu, cpu_timing = compare_nearby(observations, "cpu_reference")
    cuda, cuda_timing = compare_nearby(observations, "cuda")
    if cpu != cuda or exclusions:
        raise ValueError("Orange research comparison did not reconcile")
    gates = [route(name, Purpose.COMMERCIAL_RESEARCH) for name in ("FDOR", "COUNTY_GIS")]
    if any(gate["disposition"] != "HOLD" or gate["data_release_authorized"] for gate in gates):
        raise ValueError("Unexpected research source gate")
    cp = backend("cuda")
    pool_memory = measure_pool_peak(cp, observations, cpu)
    device = cp.cuda.Device()
    properties = cp.cuda.runtime.getDeviceProperties(device.id)
    device_name = properties["name"]
    if isinstance(device_name, bytes):
        device_name = device_name.decode("utf-8")
    county_points = load_rows(spatial / "county-centroids.csv", pins["county-centroids.csv"])
    baseline, baseline_exclusions = observed_transfers(inventory, sales, county_points)
    baseline_result, _ = compare_nearby(baseline, "cpu_reference")
    by_sale = {row["sale_id"]: row for row in cuda}
    baseline_ids = {row["sale_id"] for row in baseline_result}
    same_pool, _ = compare_nearby(
        [row for row in observations if row["sale_id"] in baseline_ids], "cpu_reference"
    )
    same_pool_by_sale = {row["sale_id"]: row for row in same_pool}
    changed = []
    for row in baseline_result:
        current = by_sale[row["sale_id"]]
        before = row["nearest_same_unit_sale_id"]
        after = current["nearest_same_unit_sale_id"]
        same_pool_comparable = same_pool_by_sale[row["sale_id"]]["nearest_same_unit_sale_id"]
        if len({before, after, same_pool_comparable}) > 1:
            changed.append({"sale_id": row["sale_id"], "source_parcel_id": row["source_parcel_id"],
                            "county_point_comparable": before, "polygon_point_comparable": after,
                            "polygon_point_same_pool_comparable": same_pool_comparable})
    sensitivity = {
        "county_point_input_sha256": pins["county-centroids.csv"],
        "baseline_exclusions": baseline_exclusions,
        "common_sales": len(baseline_ids),
        "polygon_only_sales": sorted(set(by_sale) - baseline_ids),
        "comparable_changes": changed,
        "scope": "Comparison of point methods and the additional polygon-only sale in the comparable pool.",
    }
    return {
        "contract": "orange-full-geometry-sales-rehearsal/1",
        "geometry_covered_parcels": coverage,
        "fdor_source_sha256": fdor["sha256"], "county_supplement_sha256": county["county_geoparquet_sha256"],
        "sales_sha256": pins["parcel-sales.csv"], "transfers_processed": len(cuda),
        "nearby_sales_matched": sum(row["nearest_same_unit_sale_id"] is not None for row in cuda),
        "county_gap_sales_processed": sum(row["point_source"] == "OCPA_GAP_SUPPLEMENT" for row in cuda),
        "cpu_cuda_exact": True, "commercial_admissions": 0,
        "source_gates": gates, "point_method_sensitivity": sensitivity,
        "timing": {"cpu": cpu_timing, "cuda": cuda_timing},
        "cuda_pool_memory": pool_memory,
        "cuda_device": {
            "name": device_name, "physical_device_bytes": device.mem_info[1],
            "driver_api_version": cp.cuda.runtime.driverGetVersion(),
            "runtime_api_version": cp.cuda.runtime.runtimeGetVersion(),
            "cupy": cp.__version__,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    receipt = run(args.docs)
    with args.output.open("x", encoding="utf-8") as out:
        json.dump(receipt, out, indent=2)
    print(receipt)
