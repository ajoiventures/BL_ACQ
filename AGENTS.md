# Black River engineering preferences

## Builder swarm and product runtime

Standing user instruction, November 22, 2026: the swarm builds the product;
the AI layer comes later. Development agents may inspect, implement and test
the software within their assigned scopes. Their roles and installed builder
skills are development tools, not agents running inside the product.

Build in this order: deterministic domain engines; application services and
versioned interfaces; review interfaces; optional document-AI adapters; and
only later, separately specified bounded runtime agents. The current engine
and application layer must operate without an LLM, NVIDIA inference service,
model download, API credential or network dependency. CUDA numerical kernels
are ordinary compute and do not make the financial engine an AI system.

Treat the NVIDIA document-AI integration as a future provider interface.
Current manual/native inputs remain explicit. A future model may propose
candidate claims; it may not self-verify evidence, overwrite financial policy,
manufacture calibrated outcome probabilities or advance transaction status.
Keep provider scores separate from evidence validity and event probabilities.

Make build status precise: specified, implemented, tested and deployed are
different. State which checks and runtimes actually ran. Builder configuration
must not imply that product agents or NVIDIA services have been deployed.

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

## R, Python and CUDA

Standing user instruction, November 22, 2026: **"Include R."**

Include R in the architecture for statistical research, econometrics,
time-to-event analysis, uncertainty and model diagnostics, independent
validation, and reproducible analytical reports. Apply these capabilities to
property economics, offer outcomes and negotiation-to-closing research when
the necessary evidence exists. Do not invent calibrated acceptance or closing
probabilities from an unvalidated score.

Keep the operational workflow and authoritative financial rules in the shared
Python services. R should call those calculations through a versioned batch
interface rather than establish a conflicting production formula set. Small
independent R reference calculations are useful for validation and learning.
Evaluate reticulate for calling the Python/CUDA backend, typed Arrow/Parquet
artifacts for data exchange, and R torch for suitable GPU tensor workloads.
Ordinary R code does not become CUDA code merely because R is in the stack.

Carry deal/offer/scenario IDs, source and model versions, currency, units,
time zones and explicit numeric types across every interface. Preserve integer
cents and rounding; check conversion ranges, missing values and array order.
Keep computational batches on the GPU where practical and return only the
required outputs. The CUDA visibility, parity and benchmarking requirements
above apply equally to R-originated work.

When adding an executable R component, pin its packages with renv, bind the
intended Python environment explicitly, and record the tested runtime/GPU
compatibility. R integration is currently an architecture requirement, not an
implemented or benchmarked runtime. See the R section in the
[CUDA architecture decision](docs/architecture/cuda-screening.md).
