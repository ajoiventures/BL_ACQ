"""Measure bounded spatial joins against pinned public parcel polygons."""
import argparse
from pathlib import Path
import hashlib
import json
from time import perf_counter

import numpy as np
import shapely
from shapely import STRtree

from tools.rehearse_orange_full_geometry_sales import load_geometry_components

BATCH = 10_000


def verify(docs, count, batch_size=BATCH):
    if type(batch_size) is not int or not 1 <= batch_size <= BATCH:
        raise ValueError(f"Batch size must be between 1 and {BATCH}")
    parts, _, _, fdor, county, _, _ = load_geometry_components(docs)
    polys = np.asarray([shapely.union_all(parts[key]) for key in sorted(parts)], dtype=object)
    if not np.all(shapely.is_valid(polys)):
        raise ValueError("Invalid source parcel geometry")
    points = shapely.point_on_surface(polys)
    missing = shapely.Point(-1, -1)
    tree = STRtree(polys)
    sample = list(range(0, len(points), 127))
    for idx in sample:
        brute = set(np.flatnonzero(shapely.intersects(points[idx], polys)))
        if set(tree.query(points[idx], predicate="intersects")) != brute:
            raise ValueError("Spatial index disagrees with scan")
    if len(tree.query(missing, predicate="intersects")):
        raise ValueError("Synthetic missing point intersects a parcel")
    dig = hashlib.sha256()
    matches = multiple = misses = peak_pairs = 0
    started = perf_counter()
    for start in range(0, count, batch_size):
        ordinals = np.arange(start, min(count, start + batch_size))
        expected = np.where(ordinals % 4 == 0, 0, ordinals % len(points))
        absent = ordinals % 17 == 0
        queries = points[expected].copy()
        queries[absent] = missing
        positions, polygons = tree.query(queries, predicate="intersects")
        if np.any(absent[positions]):
            raise ValueError("Unmatched fixture point returned a hit")
        owner_hits = polygons == expected[positions]
        if int(owner_hits.sum()) != int((~absent).sum()):
            raise ValueError("Expected source parcel did not match")
        per_query = np.bincount(positions, minlength=len(queries))
        misses += int(np.count_nonzero(per_query == 0))
        multiple += int(np.count_nonzero(per_query > 1))
        matches += len(positions)
        peak_pairs = max(peak_pairs, len(positions))
        order = np.lexsort((polygons, positions))
        pairs = np.column_stack((positions[order] + start, polygons[order])).astype("<i8", copy=False)
        dig.update(pairs.tobytes())
    return dict(workload_rows=count, source_polygons=len(polys), query_batch_limit=batch_size,
                index_verified_against_full_scan_for=len(sample), confirmed_missing=misses,
                spatial_join_pairs=matches, queries_with_multiple_hits=multiple, max_pairs_in_batch=peak_pairs,
                elapsed_s=perf_counter()-started, result_sha256=dig.hexdigest(), crs="EPSG:2236",
                fdor_sha256=fdor["sha256"], county_sha256=county["county_geoparquet_sha256"],
                engine="CPU Shapely STRtree", geos=shapely.geos_version_string,
                scope="Repeated representative-point queries and synthetic misses. No independent acceptance or parcel eligibility.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--count",type=int,choices=(2_000_000,5_000_000,10_000_000),default=2_000_000)
    parser.add_argument("--batch-size", type=int, default=BATCH)
    args=parser.parse_args()
    result=verify(args.docs,args.count,args.batch_size)
    with args.output.open("x",encoding="utf-8") as out:
        json.dump(result,out,indent=2)
        out.write("\n")
    print(result)
