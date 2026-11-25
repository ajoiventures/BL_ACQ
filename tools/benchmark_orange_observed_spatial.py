"""Measure warm CPU and CUDA comparison on the pinned observed cohort."""
import argparse
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from backend.core.acquisition_batch import backend
from tools.run_orange_observed_spatial_economic import compare_nearby, load_rows, observed_transfers


def measure_pool_peak(cp, rows, reference):
    """Measure live pooled bytes independently of timed runs."""
    pool = cp.cuda.MemoryPool()

    class PeakHook(cp.cuda.MemoryHook):
        name = "OrangeObservedPeak"

        def __init__(self):
            self.live = {}
            self.current = 0
            self.peak = 0

        def malloc_postprocess(self, *, pmem_id, mem_size, **kwargs):
            if pmem_id:
                self.live[pmem_id] = mem_size
                self.current += mem_size
                self.peak = max(self.peak, self.current)

        def free_postprocess(self, *, pmem_id, **kwargs):
            self.current -= self.live.pop(pmem_id, 0)

    hook = PeakHook()
    with cp.cuda.using_allocator(pool.malloc), hook:
        results, _ = compare_nearby(rows, "cuda")
        cp.cuda.get_current_stream().synchronize()
    if results != reference or not hook.peak or hook.current != pool.used_bytes():
        raise ValueError("Instrumented CUDA run did not reconcile")
    return {
        "peak_live_pool_bytes": hook.peak,
        "pool_reserved_bytes_after": pool.total_bytes(),
        "scope": "CuPy pool only; excludes CUDA context and allocations outside the pool",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.evidence
    pins = json.loads((root / "spatial-input-digests.json").read_bytes())
    rows, _ = observed_transfers(
        load_rows(args.inventory, pins["official_final_roll_inventory.csv"]),
        load_rows(root / "parcel-sales.csv", pins["parcel-sales.csv"]),
        load_rows(root / "county-centroids.csv", pins["county-centroids.csv"]),
    )
    cp = backend("cuda")
    reference, _ = compare_nearby(rows, "cpu_reference")
    warm, _ = compare_nearby(rows, "cuda")
    if reference != warm:
        raise ValueError("warm-up backend disagreement")
    repetitions = {name: [] for name in ("cpu_reference", "cuda")}
    for _ in range(7):
        for name, samples in repetitions.items():
            start = perf_counter()
            results, detail = compare_nearby(rows, name)
            duration = perf_counter() - start
            if reference != results:
                raise ValueError("timed backend disagreement")
            samples.append({"wall_s": duration, **detail})
    report = {
        "rows": len(rows), "input_sha256": pins,
        "median_wall_s": {name: median(s["wall_s"] for s in samples) for name, samples in repetitions.items()},
        "runs": repetitions, "measured_scope": "warm end-to-end comparison after CSV parse",
        "cuda_pool_cached_bytes_after": cp.get_default_memory_pool().total_bytes(),
        "cuda_driver": cp.cuda.runtime.driverGetVersion(),
        "cuda_runtime": cp.cuda.runtime.runtimeGetVersion(), "cupy": cp.__version__,
        "cupy_pool_measurement": measure_pool_peak(cp, rows, reference),
        "actual_peak_device_memory_measured": False,
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(report["median_wall_s"])


if __name__ == "__main__":
    main()
