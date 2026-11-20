"""Screen a grid of resale and stress assumptions on CPU or an NVIDIA GPU."""

import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import replace
import hashlib
from importlib.metadata import PackageNotFoundError, distribution
import json
import os
from time import perf_counter
from typing import Literal

from pilot.underwriting import Economics, purchase_limits


def wheel_file(package, filename):
    wheel = distribution(package)
    return next(wheel.locate_file(item) for item in wheel.files or () if item.name == filename)


@contextmanager
def cuda_runtime():
    """Expose the separate NVIDIA wheel directories to the Windows DLL loader."""
    if os.name != "nt" or os.environ.get("CUDA_PATH"):
        yield
        return
    try:
        root = wheel_file("nvidia-cuda-runtime-cu12", "cuda_runtime.h").parent.parent
        compiler = wheel_file("nvidia-cuda-nvrtc-cu12", "nvrtc64_120_0.dll").parent
    except (PackageNotFoundError, StopIteration) as exc:
        raise RuntimeError("Install the CUDA requirements or point CUDA_PATH to a CUDA 12 toolkit") from exc

    saved_path = os.environ.get("PATH")
    with ExitStack() as loaders:
        for directory in (compiler, root / "bin"):
            loaders.enter_context(os.add_dll_directory(str(directory)))
        os.environ["CUDA_PATH"] = str(root)
        os.environ["PATH"] = os.pathsep.join((str(compiler), str(root / "bin"), saved_path or ""))
        try:
            yield
        finally:
            os.environ.pop("CUDA_PATH", None)
            if saved_path is None:
                os.environ.pop("PATH", None)
            else:
                os.environ["PATH"] = saved_path


def screen(
    terms: Economics,
    resale_values: list[int],
    stress_values: list[int],
    backend: Literal["cpu", "cuda"] = "cpu",
) -> list[list[int]]:
    """Return downside ceilings in cents, in resale-major matrix order."""
    purchase_limits(terms)
    if any(type(value) is not int or not 0 <= value <= 10**14 for value in resale_values):
        raise ValueError("Resale assumptions must be integer cents from 0 through 10^14")
    if any(type(value) is not int or not 0 <= value <= 10_000 for value in stress_values):
        raise ValueError("Stress assumptions must be integer basis points")
    if not resale_values or not stress_values or len(resale_values) * len(stress_values) > 2_000_000:
        raise ValueError("Screen between 1 and 2,000,000 assumptions per call")
    costs = terms.renovation_cents + terms.carrying_cents + terms.stress_extra_cents + terms.stress_profit_cents
    if not 0 <= costs <= 10**14:
        raise ValueError("Combined scenario costs exceed the supported cents range")

    if backend == "cpu":
        return [
            [int(purchase_limits(replace(terms, resale_cents=resale, stress_price_drop_bps=stress))["downside"])
             for stress in stress_values]
            for resale in resale_values
        ]
    if backend != "cuda":
        raise ValueError("Backend must be cpu or cuda")

    # Broadcast a column of resale assumptions against a row of stress rates.
    # Stay in integer cents and round at the same two steps as the CPU oracle.
    with cuda_runtime():
        import cupy as cp

        resale = cp.asarray(resale_values, dtype=cp.int64)[:, None]
        retained = 10_000 - cp.asarray(stress_values, dtype=cp.int64)[None, :]
        stressed = resale * retained // 10_000
        net = stressed * (10_000 - terms.selling_bps) // 10_000
        # The device-to-host copy also waits for the CUDA work to finish.
        return (net - costs).get().tolist()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--compare", action="store_true", help="Check the complete result against the CPU oracle")
    parser.add_argument("--repeat", type=int, default=1, help="Measure first-call and warmed timings")
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10:
        parser.error("--repeat must be between 1 and 10")
    terms = Economics(
        resale_cents=45_000_000, renovation_cents=3_200_000, carrying_cents=1_200_000,
        selling_bps=600, stress_price_drop_bps=1000, stress_extra_cents=1_000_000,
        base_profit_cents=7_500_000, stress_profit_cents=2_000_000, financing_cap_cents=28_000_000,
    )
    resale = list(range(30_000_001, 60_000_001, 60_000))
    stress = list(range(0, 2500, 5))
    timings = []
    for _ in range(args.repeat):
        start = perf_counter()
        result = screen(terms, resale, stress, args.backend)
        timings.append(round(perf_counter() - start, 4))
    parity = args.compare and result == screen(terms, resale, stress)
    if args.compare and not parity:
        raise SystemExit("The scenario results disagree with the CPU calculation")
    print(json.dumps({
        "backend": args.backend,
        "scenarios": len(resale) * len(stress),
        "seconds_per_run": timings,
        "sha256": hashlib.sha256(json.dumps(result, separators=(",", ":")).encode()).hexdigest(),
        "cpu_parity_checked": parity,
    }))


if __name__ == "__main__":
    main()
