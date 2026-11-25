"""Match observed Orange sales to same-unit nearby sales on CPU or CUDA."""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
import math
from pathlib import Path
from time import perf_counter

import numpy as np

from backend.core.acquisition_batch import FIELDS, backend, screen, summarize
from backend.core.acquisition_source_gate import Purpose, route
from backend.core.state_parcel_research import orange_id_candidate

MAX_TRANSFERS = 1000
MAX_DISTANCE_METRES = 5000
BLOCK_ROWS = 64
EARTH_METRES = 6_371_008.8


def load_rows(path, expected_digest):
    with path.open("rb") as handle:
        data = handle.read(2_000_001)
    if len(data) > 2_000_000 or hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError(f"input size or digest mismatch: {path.name}")
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))


def observed_transfers(inventory, sales, centroids):
    parcel = {r["PARCEL_ID"]: r for r in inventory}
    if len(parcel) != len(inventory):
        raise ValueError("duplicated final-roll parcel")
    by_id = defaultdict(list)
    for position in centroids:
        by_id[position["PARCEL"]].append(position)
    transfers = [r for r in sales if r["spatial_economic_cohort"] == "1"]
    if not 0 < len(transfers) <= MAX_TRANSFERS:
        raise ValueError("unexpected transfer count")
    if len({r["CLERK_NO"] for r in transfers}) != len(transfers):
        raise ValueError("duplicate transfer")
    observations = []
    exclusions = Counter()
    for sale in sorted(transfers, key=lambda row: (row["PARCEL_ID"], row["CLERK_NO"])):
        pid = sale["PARCEL_ID"]
        roll = parcel[pid]
        county_id = orange_id_candidate(pid)
        units = int(roll["NO_RES_UNTS"])
        price = int(sale["SALE_PRC"])
        if (county_id != roll["ALT_KEY"] or units not in (2, 3, 4) or not 0 < price <= 10**10
                or (roll["CO_NO"], roll["ASMNT_YR"], roll["FILE_T"]) != ("58", "2026", "R")
                or sale["QUAL_CD"] not in {"01", "02"} or sale["VI_CD"] != "I"
                or sale["MULTI_PAR_SAL"] or sale["SAL_CHG_CD"] or not sale["CLERK_NO"]):
            raise ValueError("sale or parcel outside the observed cohort contract")
        matches = by_id[county_id]
        if len(matches) != 1:
            exclusions["missing_centroid" if not matches else "multiple_gis_features"] += 1
            continue
        feature = matches[0]
        if not feature["LATITUDE"] or not feature["LONGITUDE"]:
            exclusions["invalid_centroid"] += 1
            continue
        lat, lon = float(feature["LATITUDE"]), float(feature["LONGITUDE"])
        if not (math.isfinite(lat) and math.isfinite(lon) and 28 < lat < 29 and -82 < lon < -80):
            exclusions["invalid_centroid"] += 1
            continue
        observations.append({
            "parcel_key": "12095:" + county_id, "source_parcel_id": pid,
            "sale_id": sale["CLERK_NO"], "sale_month": sale["SALE_YR"] + "-" + sale["SALE_MO"],
            "sale_price_dollars": price, "reported_units": units,
            "county_feature_id": feature["OBJECTID"], "lat": lat, "lon": lon,
            "assessment_land_use": roll["DOR_UC"], "decision": "HOLD",
        })
    if not observations:
        raise ValueError("no sales with unambiguous county centroids")
    return observations, dict(exclusions)


def compare_nearby(observations, backend_name):
    xp = backend(backend_name)
    synchronize = xp.cuda.get_current_stream().synchronize if backend_name == "cuda" else lambda: None
    start = perf_counter()
    ids = {key: index for index, key in enumerate(sorted({r["parcel_key"] for r in observations}))}
    parcels = xp.asarray([ids[r["parcel_key"]] for r in observations], dtype=xp.int64)
    units = xp.asarray([r["reported_units"] for r in observations], dtype=xp.int64)
    price = xp.asarray([r["sale_price_dollars"] for r in observations], dtype=xp.int64)
    month = xp.asarray([int(r["sale_month"].replace("-", "")) for r in observations], dtype=xp.int64)
    lat = xp.radians(xp.asarray([r["lat"] for r in observations], dtype=xp.float64))
    lon = xp.radians(xp.asarray([r["lon"] for r in observations], dtype=xp.float64))
    synchronize()
    loaded = perf_counter()
    unit_price = price * 100 // units
    output = []
    missing = MAX_DISTANCE_METRES + 1
    for offset in range(0, len(observations), BLOCK_ROWS):
        part = slice(offset, offset + BLOCK_ROWS)
        lat_delta = lat[part, None] - lat
        lon_delta = lon[part, None] - lon
        hav = (xp.sin(lat_delta / 2)**2
               + xp.cos(lat[part, None]) * xp.cos(lat) * xp.sin(lon_delta / 2)**2)
        metres = xp.rint(2 * EARTH_METRES * xp.arcsin(xp.sqrt(xp.clip(hav, 0, 1)))).astype(xp.int64)
        valid = ((units[part, None] == units) & (parcels[part, None] != parcels)
                 & (month < month[part, None]) & (metres <= MAX_DISTANCE_METRES))
        distance = xp.where(valid, metres, missing)
        nearest = xp.argmin(distance, axis=1)
        closest = xp.min(distance, axis=1)
        output.append(xp.stack((unit_price[part], nearest, closest, unit_price[nearest]), axis=1))
    packed = xp.concatenate(output)
    synchronize()
    computed = perf_counter()
    rows = xp.asnumpy(packed) if backend_name == "cuda" else packed
    ended = perf_counter()
    compared = []
    for row, (amount, nearest, distance, comparable_amount) in zip(observations, rows):
        found = int(distance) != missing
        compared.append({
            **row, "observed_sale_cents_per_reported_unit": int(amount),
            "nearest_same_unit_sale_id": observations[int(nearest)]["sale_id"] if found else None,
            "rounded_distance_metres": int(distance) if found else None,
            "comparable_sale_cents_per_reported_unit": int(comparable_amount) if found else None,
        })
    return compared, {
        "backend": backend_name, "transfer_or_setup_s": loaded - start,
        "compute_s": computed - loaded, "copy_or_read_s": ended - computed,
        "max_distance_metres": MAX_DISTANCE_METRES, "batch_rows": BLOCK_ROWS,
    }


def run(path, inventory_path, input_digests):
    filenames = ("official_final_roll_inventory.csv", "parcel-sales.csv", "county-centroids.csv")
    inventory, sales, centroids = [
        load_rows(file, input_digests[name])
        for file, name in zip((inventory_path, path / filenames[1], path / filenames[2]), filenames)
    ]
    gates = [route(key, Purpose.COMMERCIAL_RESEARCH) for key in ("FDOR", "COUNTY_GIS")]
    if any(g["disposition"] != "HOLD" or g["data_release_authorized"] for g in gates):
        raise ValueError("unexpected source gate for research evidence")
    observations, exclusions = observed_transfers(inventory, sales, centroids)
    outputs = {}
    timing = {}
    numeric = {}
    for name in ("cpu_reference", "cuda"):
        outputs[name], timing[name] = compare_nearby(observations, name)
        arrays = {key: np.full(len(observations), -1, dtype=np.int64) for key in FIELDS}
        arrays["reported_units"] = np.array([r["reported_units"] for r in observations], dtype=np.int64)
        result, _ = screen(arrays, name)
        numeric[name] = result
    if outputs["cpu_reference"] != outputs["cuda"] or any(
        not np.array_equal(numeric["cpu_reference"][key], numeric["cuda"][key])
        for key in numeric["cpu_reference"]
    ):
        raise ValueError("CPU and CUDA outputs disagree")
    return {
        "contract": "br-orange-observed-sales-spatial/1", "exact_cpu_cuda_parity": True,
        "input_sha256": input_digests, "source_gates": gates, "excluded_sales": exclusions,
        "transfers_processed": len(observations),
        "distinct_parcels": len({row["parcel_key"] for row in observations}),
        "matched_nearby_sales": sum(row["nearest_same_unit_sale_id"] is not None for row in outputs["cuda"]),
        "timing": timing, "acquisition_screen": summarize(numeric["cuda"]),
        "production_admissions": 0, "records": outputs["cuda"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    pins = json.loads((args.evidence / "spatial-input-digests.json").read_bytes())
    result = run(args.evidence, args.inventory, pins)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k not in {"records", "source_gates"}}, indent=2))


if __name__ == "__main__":
    main()
