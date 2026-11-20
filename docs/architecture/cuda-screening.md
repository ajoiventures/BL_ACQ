# Architecture decision · CUDA for underwriting sensitivity

**Status** Implemented for the synthetic pilot on November 20, 2026.

## Context

A single deal decision uses a handful of conservative price calculations. A sensitivity exercise can ask the same question for hundreds of thousands of combinations of resale value and stress. The Windows development workstation has an NVIDIA GPU. The browser, CI and other developer machines need a reproducible path on CPU.

## Decision

Keep the scalar integer-cent calculation in [underwriting](../../pilot/underwriting.py). The [scenario screen](../../pilot/cuda_screen.py) can evaluate a grid of resale assumptions and stress rates on CPU or CUDA. CUDA broadcasts the two axes, computes in signed 64-bit integers and rounds down at each of the same stages as the reference. Bounded inputs limit both device memory and overflow. Copying the completed matrix back to the host waits for the device work. Explicit CUDA runs can compare every result to the CPU and fail on a mismatch.

The screen returns indicative downside ceilings. The application decides bid readiness from the complete underwriting packet, including the base case, downside, financing, current evidence and human review. The browser and storage do not need a CUDA runtime. Install GPU dependencies only for the screening task.

## Trade-offs and verification

Using only the scalar calculation would remove GPU setup while giving up the batch accelerator. Requiring CUDA for every decision would add launch latency and hardware dependence to small cases. The optional batch architecture keeps the decision path portable and gives the workstation a repeatable way to measure benefit on larger grids.

Verify parity with `code-map.cmd cuda`. Use `--repeat 3` with the direct command from the [screening guide](../guides/cuda_screen.md) to compare first-call and warm timings. Measure representative grid sizes before using elapsed time as a product claim. The current comparator is the scalar reference and includes host result conversion.

One Windows run on the RTX 5070 Ti Laptop GPU matched all 250,000 cells. The first GPU call took 0.404 seconds and the next two took about 0.009 seconds each. Three scalar CPU calls took 0.959–0.969 seconds each. These measurements describe the synthetic grid on this machine.
