"""Measure a full rerun after a discarded Orange research comparison result."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from tools.rehearse_orange_full_geometry_sales import load_full_geometry_observations
from tools.run_orange_observed_spatial_economic import compare_nearby


def benchmark(docs):
    observations, exclusions, coverage, fdor, county, pins, _, _ = load_full_geometry_observations(docs)
    if exclusions or not observations:
        raise ValueError("Research observations did not reconcile")
    reference, _ = compare_nearby(observations, "cpu_reference")

    def timed(engine, attempts):
        start = perf_counter()
        for _ in range(attempts):
            output, _ = compare_nearby(observations, engine)
        elapsed = (perf_counter() - start) * 1000
        if output != reference:
            raise ValueError(f"{engine} replay did not match CPU reference")
        return elapsed

    timing = {}
    for engine in ("cpu_reference", "cuda"):
        timed(engine, 1)
        first_times, replay_times = [], []
        for i in range(9):
            for attempts in ((1, 2) if i % 2 == 0 else (2, 1)):
                (first_times if attempts == 1 else replay_times).append(timed(engine, attempts))
        timing[engine] = {
            "one_attempt_ms_median": median(first_times),
            "two_attempts_ms_median": median(replay_times),
            "paired_retry_overhead_ms_median": median(
                replay - single for single, replay in zip(first_times, replay_times)
            ),
            "one_attempt_samples_ms": first_times,
            "two_attempt_samples_ms": replay_times,
        }
    return {
        "contract": "orange-observed-full-retry-benchmark/1",
        "geometry_covered_parcels": coverage,
        "fdor_geometry_sha256": fdor["sha256"],
        "county_supplement_sha256": county["county_geoparquet_sha256"],
        "sales_sha256": pins["parcel-sales.csv"],
        "real_transfers": len(reference),
        "result_sha256": hashlib.sha256(json.dumps(reference, sort_keys=True).encode()).hexdigest(),
        "scenario": "Discard the first completed comparison result and recompute from the same in-memory observations.",
        "timing_scope": "Warm comparison calls, including device transfers and readback. Excludes source preparation, worker scheduling, and persistence.",
        "cpu_cuda_exact": True,
        "commercial_admissions": 0,
        "timing": timing,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    receipt = benchmark(args.docs)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(receipt, output, indent=2)
        output.write("\n")
    print(receipt["real_transfers"], {k: v["paired_retry_overhead_ms_median"] for k,v in receipt["timing"].items()})
