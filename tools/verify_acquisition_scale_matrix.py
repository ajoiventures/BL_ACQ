"""Measure bounded numeric scale with identical CPU and CUDA synthetic inputs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import perf_counter
import json
from pathlib import Path
import subprocess

from backend.core.acquisition_batch import backend
from tools.run_acquisition_batch import benchmark

SIZES = (1_000, 10_000, 100_000, 2_000_000, 5_000_000, 10_000_000)
BATCH = 100_000


def verify_pair(cpu, gpu, count):
    if cpu["counts"] != gpu["counts"] or cpu["batch_result_sha256"] != gpu["batch_result_sha256"]:
        raise ValueError("backend results disagree")
    for report in (cpu, gpu):
        end = 0
        for part in report["receipts"]:
            if part["start"] != end or not 0 < part["end_exclusive"] - end <= BATCH:
                raise ValueError("invalid batch coverage")
            end = part["end_exclusive"]
        if end != count:
            raise ValueError("incomplete batch coverage")
    for left, right in zip(cpu["receipts"], gpu["receipts"], strict=True):
        for key in ("start", "end_exclusive", "input_sha256", "result_sha256"):
            if left[key] != right[key]:
                raise ValueError(f"batch parity failure for {key}")


def concurrent_pair(count):
    references = [benchmark(count, BATCH, "cpu_reference", eligible)
                  for eligible in (False, True)]
    ready = Barrier(2)
    cp = backend("cuda")
    device_id = cp.cuda.Device().id

    def run(eligible):
        with cp.cuda.Device(device_id):
            stream = cp.cuda.Stream(non_blocking=True)
            first, last = cp.cuda.Event(), cp.cuda.Event()
            with stream:
                ready.wait(timeout=15)
                start = perf_counter()
                first.record(stream)
                report = benchmark(count, BATCH, "cuda", eligible)
                last.record(stream)
                last.synchronize()
                end = perf_counter()
            return start, end, report, stream.ptr, cp.cuda.get_elapsed_time(first, last)

    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs = [executor.submit(run, eligible) for eligible in (False, True)]
        results = [job.result() for job in jobs]
    for reference, (_, _, result, _, _) in zip(references, results, strict=True):
        verify_pair(reference, result, count)
    if len({row[3] for row in results}) != 2 or any(row[4] <= 0 for row in results):
        raise ValueError("CUDA stream event measurements did not reconcile")
    overlap = min(row[1] for row in results) - max(row[0] for row in results)
    if overlap <= 0:
        raise ValueError("No overlap observed between concurrent worker calls")
    return {
        "rows_per_worker": count,
        "worker_call_overlap_s": overlap,
        "worker_call_span_s": max(row[1] for row in results) - min(row[0] for row in results),
        "parity": True,
        "distinct_nonblocking_streams": True,
        "cuda_event_scope": "Per-stream elapsed interval including idle time; kernel overlap not measured",
        "workers": [
            {"cohort": result["synthetic_case_mix"], "elapsed_s": result["elapsed_s"],
             "output_sha256": result["batch_result_sha256"], "counts": result["counts"],
             "cuda_stream_elapsed_ms": elapsed_ms}
            for _, _, result, _, elapsed_ms in results
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--concurrent", action="store_true", help="Also verify two overlapping CUDA worker calls")
    args = parser.parse_args()
    cp = backend("cuda")
    for name in ("cpu_reference", "cuda"):
        benchmark(1_000, BATCH, name)
    device = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
        check=True, capture_output=True, text=True, timeout=15,
    ).stdout.strip()
    report = {"hardware": device, "cupy": cp.__version__, "batch_limit": BATCH, "runs": [],
              "independent_acceptance": False, "scope": "Synthetic numeric worker only"}
    for count in SIZES:
        for eligible in (False, True):
            cpu = benchmark(count, BATCH, "cpu_reference", eligible)
            gpu = benchmark(count, BATCH, "cuda", eligible)
            verify_pair(cpu, gpu, count)
            if eligible and cpu["counts"]["eligible"] != count:
                raise ValueError("eligible synthetic cohort incomplete")
            report["runs"].append({"rows": count, "cohort": cpu["synthetic_case_mix"],
                                   "parity": True, "cpu": cpu, "cuda": gpu,
                                   "cuda_cached_pool_bytes_after_run": cp.get_default_memory_pool().total_bytes()})
            print(count, cpu["synthetic_case_mix"], round(cpu["elapsed_s"], 4), round(gpu["elapsed_s"], 4))
    if args.concurrent:
        report["concurrent_cuda_worker_calls"] = [concurrent_pair(count) for count in SIZES[:4]]
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)


if __name__ == "__main__":
    main()
