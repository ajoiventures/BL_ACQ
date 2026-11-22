# Black River engineering preferences

## CUDA utilization

Standing user instruction, November 22, 2026: **"Remember always code to maximize the utilization of CUDA."**

For new or modified computational features, treat efficient CUDA execution as
a default design requirement. Structure independent deals, scenarios,
simulations and parameter searches as vectorized batches. Preserve financial
dependencies and calculation order within each case.

Maximize useful GPU work through suitable batch sizes, memory layout,
device-resident data, reduced host/device transfers and reusable allocations.
Bound memory and arithmetic ranges and chunk large workloads safely. Profile
the complete workload, including transfers and synchronization. Optimize
measured throughput and latency; a utilization percentage alone is not a
performance claim. Explain any computational stage retained on CPU.

Preserve financial semantics and required precision. Keep a readable CPU
reference and verify accelerated results with exact equality or explicitly
justified numerical tolerances. Do not enable reduced precision or altered
rounding solely to increase speed.

Make the execution backend visible. An explicitly requested CUDA run must
report unavailable hardware or an execution failure instead of silently
falling back to CPU. Report the actual device, workload, numeric precision,
comparison baseline and cold/warm timing basis with benchmark claims. Never
claim CUDA execution or a speedup that was not measured on a real GPU.

Keep formulas, intermediate traces and a small-case learning path inspectable.
GPU acceleration should extend the user's control over the model.

See [the CUDA architecture decision](docs/architecture/cuda-screening.md) for
current implementation scope and the [screening guide](docs/guides/cuda_screen.md)
for the existing CPU/CUDA comparison command.
