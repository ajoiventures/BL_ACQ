# Architecture decision · CUDA for underwriting sensitivity

**Status** Implemented for the synthetic pilot on November 20, 2026.

## Standing engineering preference · November 22, 2026

The user requires code to maximize productive CUDA utilization. The repository
[agent instructions](../../AGENTS.md) make this a default design requirement
for new and modified computational features. The architecture agent carries
the same instruction.

Expose parallelism across independent deals, scenarios and simulations; retain
ordered dependencies within a case. Batch work, reuse device allocations, keep
intermediate data on the GPU, reduce transfers and profile realistic complete
workloads. Preserve financial precision and compare with a readable CPU
reference. Explicit CUDA requests must report failure or unavailable hardware
rather than silently change backends. Any acceleration claim needs actual
device, workload and timing evidence.

This follows NVIDIA's emphasis on profiling, parallel workloads, transfer cost
and device-resident intermediate data in its
[CUDA Best Practices Guide](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/).
Useful end-to-end performance and correct results are the optimization targets.

**Current scope remains explicit:** the synthetic underwriting screen below has
a CUDA backend. The linked corporate statement, DCF and acquisition-finance
engines currently run on CPU; a batched CUDA implementation for those modules
is future work. Recording this preference does not claim that migration or a
new benchmark has been completed.

## R integration requirement · November 22, 2026

The user also requires R in the stack. This is an architecture addition; no R
runtime, bridge, model, package environment or GPU benchmark is implemented by
this decision.

| Responsibility | Intended owner and role |
| --- | --- |
| Financial and transaction rules | Shared Python services remain authoritative for financial calculations, evidence, offer versions, permissions and state transitions. |
| Research and diagnostics | R supports econometrics, time-to-event analysis, sensitivity, uncertainty, model diagnostics and explicitly independent reference calculations. |
| Parallel calculation | Existing Python/CuPy CUDA batches are the first integration target. R torch is an optional route for workloads suited to GPU tensors. |
| Reports | R and Quarto can produce reproducible acquisition briefs, model diagnostics and negotiation-outcome reports from versioned results. |
| Data exchange | Use a declared, typed schema over a batch call or Arrow/Parquet artifacts, with source and model versions attached. |

For the proposed negotiation engine, R can examine observed offer responses,
time to agreement and failed closings, compare candidate statistical models,
and validate uncertainty. Rejected, withdrawn, expired and still-open cases
need explicit treatment. An acceptance estimate requires suitable outcome
data, a stated observation cutoff and calibration evidence. An R research
result cannot itself establish seller consent, an effective contract or a
completed acquisition.

The initial integration target is R calling a single shared Python/CUDA batch
through [reticulate](https://rstudio.github.io/reticulate/articles/calling_python.html).
Select the intended Python environment explicitly; retain Python objects when
automatic conversion would create unnecessary host copies. Ordinary R arrays
and data frames do not thereby become GPU-resident. Keep repeated computation
inside the backend and transfer the required results at the boundary.

Validate money types and supported ranges, missing values, units, currency,
time zones, IDs, and [array orientation/indexing](https://rstudio.github.io/reticulate/articles/arrays.html).
Do not silently narrow cents to R's ordinary integer type or convert arbitrary
64-bit monetary values through floating point. Validate a small known case
across the boundary before making throughput claims. Independent R validation
must not introduce a second conflicting operational definition of a formula.

[Arrow for R](https://arrow.apache.org/docs/r/) supports typed columnar exchange,
including Parquet and Arrow IPC. Exchange schemas and conversion checks remain
application responsibilities. For suitable tensor workloads,
[torch for R](https://torch.mlverse.org/technical/tensors/) can explicitly place
tensors on a CUDA device; select a supported runtime combination from the
[installation guidance](https://torch.mlverse.org/docs/articles/installation).
Neither route makes every R package GPU-accelerated.

When implementing the first R component, record its packages with
[renv](https://rstudio.github.io/renv/articles/renv.html), pin the paired Python
environment, and verify the selected backend. Explicit CUDA requests must fail
clearly when unavailable. Financial parity, complete workload timings and
actual device evidence remain required. [Quarto's R support](https://quarto.org/docs/computations/r.html)
is the intended reproducible reporting route, not an already deployed report.

## Context

A single deal decision uses a handful of conservative price calculations. A sensitivity exercise can ask the same question for hundreds of thousands of combinations of resale value and stress. The Windows development workstation has an NVIDIA GPU. The browser, CI and other developer machines need a reproducible path on CPU.

## Decision

Keep the scalar integer-cent calculation in [underwriting](../../pilot/underwriting.py). The [scenario screen](../../pilot/cuda_screen.py) can evaluate a grid of resale assumptions and stress rates on CPU or CUDA. CUDA broadcasts the two axes, computes in signed 64-bit integers and rounds down at each of the same stages as the reference. Bounded inputs limit both device memory and overflow. Copying the completed matrix back to the host waits for the device work. Explicit CUDA runs can compare every result to the CPU and fail on a mismatch.

The screen returns indicative downside ceilings. The application decides bid readiness from the complete underwriting packet, including the base case, downside, financing, current evidence and human review. The browser and storage do not need a CUDA runtime. Install GPU dependencies only for the screening task.

## Trade-offs and verification

Using only the scalar calculation would remove GPU setup while giving up the batch accelerator. Requiring CUDA for every decision would add launch latency and hardware dependence to small cases. The optional batch architecture keeps the decision path portable and gives the workstation a repeatable way to measure benefit on larger grids.

Verify parity with `code-map.cmd cuda`. Use `--repeat 3` with the direct command from the [screening guide](../guides/cuda_screen.md) to compare first-call and warm timings. Measure representative grid sizes before using elapsed time as a product claim. The current comparator is the scalar reference and includes host result conversion.

One Windows run on the RTX 5070 Ti Laptop GPU matched all 250,000 cells. The first GPU call took 0.404 seconds and the next two took about 0.009 seconds each. Three scalar CPU calls took 0.959–0.969 seconds each. These measurements describe the synthetic grid on this machine.
