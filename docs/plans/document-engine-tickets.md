# Document engine builder tickets and roadmap

## Scope correction — November 22, 2026

This earlier 84-capability evidence/acquisition build plan is retained with
its original IDs, completion evidence and estimates. The active Doc AI
workstream is [the corrected Doc AI plan](docai-ticket-plan.md). Its provider
readiness milestone does not depend on completing this entire plan.
The [swarm-library crosswalk](../../config/swarm-library-extension.json)
registers the builder procedures in the existing organization; it does not
create a second swarm runtime or ticket authority.

The retained historical plan is [config/build-ticket-plan.json](../../config/build-ticket-plan.json). It contains 14 epics and 84 tickets, one for each capability in [the builder catalog](../../config/builder-skills.json). This page explains the plan; consult the JSON for current statuses, exact acceptance criteria, deliverables, resource needs and completion evidence.

## Scope and delivery meaning

Build deterministic evidence and probability engines, then join them through an inspectable application layer. Operator interfaces and authorized integrations follow stable contracts. NVIDIA/assistive AI comes later; product-runtime agents are a further deferred phase. The swarm and the offline scheduler are development tools.

The two-million-U.S.-household goal, including immigrants, is a future scale hypothesis. The plan requires an initial segment and incentive/payer hypothesis, consent and permitted-purpose boundaries, localization/accessibility, representative load, and unit economics before expansion. Professional financial rigor is a validation target, not an institutional-readiness claim.

Target paths describe intended deliverables. A path's appearance in this plan does not establish that it exists or that the ticket is complete. The plan is not a batch of externally created GitHub issues.

The [initial segment and incentive hypothesis](initial-pilot-hypothesis.md)
proposes a bounded first customer and validation path. The
[build verification record](document-engine-verification.md) reconciles the
current 20 completed, 59 planned and five deferred tickets. Partial working
behavior is recorded separately from completion of a broader capability.

## Resource manager and scheduling rules

| Resource | Current planning capacity | Meaning |
| --- | ---: | --- |
| Worker agent | 3 | Bounded implementation or validation workers |
| Reserved integrator | 1 | Architecture, coordination, integration and reviewed completion |
| CUDA device | 0 | Hardware execution/parity/benchmark tickets remain resource-blocked |
| R runtime | 0 | Actual R execution and environment-lock verification remain resource-blocked |

Physical CPU count, hardware model and production capacity are not assumed. Each ticket consumes exactly one worker or one integrator, plus any required CUDA/R resources. One ticket at a time may occupy each named builder owner/lane. File and ancestor-directory write-scope overlaps must serialize.

The offline scheduler is `tools/schedule_builder_work.py`. Its CLI contract is:

    python tools/schedule_builder_work.py --plan config/build-ticket-plan.json

An optional new output path may be supplied with `--output`. The scheduler validates the dependency graph, phases, resource demands, estimates and ownership conflicts. It produces a relative build schedule and blocked/deferred report. It does not launch agents, run tests, send messages, call model services, or operate the product.

All duration estimates below are assumptions about active builder effort, with low/high ranges retained in JSON. They are not observed agent speed, calendar bookings, service-level commitments or promised completion dates. Dependencies, phase gates and actual resource availability take precedence over urgency.

A completed status is an assertion supported by recorded evidence; the scheduler cannot independently verify it. Failed work returns to its owner for rework, preserving the failure and affected dependencies. Mark unavailable or unexecuted paths explicitly rather than treating them as passed.

## Roadmap and phase gates

| Wave | Phase | Objective | Exit condition |
| --- | --- | --- | --- |
| W0 | foundation | Confirm product boundary, current code, first segment/incentive hypothesis, shared contracts and work breakdown. | Versioned contracts and an acyclic plan with explicit acceptance and resource needs. |
| W1 | builder_tooling | Operate the offline ready queue, resource planner, file-ownership rules and builder handoffs. | Scheduler rejects invalid plans and reports blocked resources without launching agents. |
| W2 | engine | Build and verify evidence records, financial semantics and conditional probability calculations. | Meaningful positive and negative cases reconcile with independent references; CUDA limitations are explicit. |
| W3 | application | Join reviewed document inputs to underwriting through explicit bindings and stale-input holds. | Synthetic quote changes recompute the right fields; unresolved evidence and changed live-counter terms withhold adjusted decisions. |
| W4 | validation | Verify default non-AI behavior, source integrity, exact arithmetic, typed R exchange and actual execution status. | CPU evidence is recorded; actual R and GPU validation remain blocked until their runtimes exist. |
| W5 | release | Package the bounded local demonstration, recovery evidence and honest capability status. | Required local release checks pass and residual limitations are stated. |
| W6 | presentation | Add an operator review interface, accessibility, localization and source-to-number navigation. | Observed operator workflow, stale-evidence behavior and supported-screen accessibility checks. |
| W7 | integration | Add authorized live sources, complete historical outcomes and measured operating economics. | Source permissions, identity, ingestion replay, unit economics and representative capacity are validated. |
| W8 | assistive_ai | Later add NVIDIA parsing/OCR, embedding/reranking and evidence-grounded assistance. | Version/hardware compatibility, extraction/retrieval quality, permissions, costs and review boundary are independently verified. |
| W9 | runtime_agents | Evaluate separately whether bounded product agents are justified. | Explicit scope, permissions, tools, budgets, stop conditions, monitoring and rollback are implemented and validated. |

Phase gates are additional dependencies in the JSON, not merely headings. Independent work can overlap when those gates, resources, and write ownership permit it. Presentation, live integration, assistive AI, and product-agent phases are outside the default enabled phase set.

## Ticket state and quality

States are `planned`, `in_progress`, `completed`, `blocked`, and `deferred`. Completed dependencies satisfy a prerequisite. Deferred, explicitly blocked, unavailable-resource and unmet-data work cannot silently become executable. In-progress estimates represent assumed remaining effort from relative minute zero.

The current implementation increment is evaluated through actual code and tests. No ticket is completed solely because a builder reports confidence. Acceptance includes a material success/failure path, source provenance, appropriate precision, and truthful runtime status.

## Epic tickets

Priority 0 is highest. Every row has its full acceptance, inputs, outputs, dependencies, write scopes and planning range in the canonical JSON. The concise acceptance excerpt below is for navigation; it does not replace the full criterion.

### BR-BUILD-E01 — Black River Product Builder

Skill: `br-build-product`. Owner: `architect_integrator`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-001 | **Record the product and builder boundary.** The ordinary product path runs without an LLM, autonomous agent, or NVIDIA model service; later AI is explicitly disabled. | None | 15 min |
| BR-BUILD-002 | **Inventory existing engines and gaps.** Reuse working finance, ledger, storage, and workflow modules; distinguish source-reviewed, executed, and planned behavior. | BR-BUILD-001 | 25 min |
| BR-BUILD-003 | **Decompose a bounded product increment.** Select an initial segment using service need, geography, obtainable evidence, and delivery capacity; state the participant incentive, payer, revenue/cost hypothesis, and validation measure. Every work item has… | BR-BUILD-002 | 30 min |
| BR-BUILD-004 | **Specify shared contracts before implementation.** IDs, currency, units, dates, null semantics, rounding, and error behavior are explicit and can be validated without AI. | BR-BUILD-003 | 30 min |
| BR-BUILD-005 | **Dispatch and integrate builder work.** Concurrent builders have bounded ownership; dependencies and conflicts are resolved sequentially by the integrator. | BR-BUILD-004, BR-BUILD-080, BR-BUILD-082 | 15 min |
| BR-BUILD-006 | **Reconcile delivery claims against evidence.** No planned capability, unavailable R/CUDA execution, or future AI service is reported as deployed. | BR-BUILD-005, BR-BUILD-066, BR-BUILD-077 | 30 min |

### BR-BUILD-E02 — Black River Evidence Engine Builder

Skill: `br-build-evidence-engine`. Owner: `evidence_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-007 | **Register immutable document identity.** Duplicate IDs cannot replace different content; malformed hashes and missing provenance are rejected. | BR-BUILD-004 | 60 min |
| BR-BUILD-008 | **Preserve source locations and units.** Page references are valid for the source type; money is not silently converted between dollars and cents. | BR-BUILD-007 | 45 min |
| BR-BUILD-009 | **Represent versions and supersession.** Old sources remain reproducible; a later upload alone does not silently erase previously reviewed evidence. | BR-BUILD-007 | 75 min |
| BR-BUILD-010 | **Record named review decisions.** Candidate claims cannot self-approve; review cannot silently alter the source value or deal binding. | BR-BUILD-008 | 60 min |
| BR-BUILD-011 | **Apply time and conflict validity.** Future or expired evidence cannot enter the projection; two incompatible accepted current values remain a blocker. | BR-BUILD-009, BR-BUILD-010 | 75 min |
| BR-BUILD-012 | **Project accepted inputs with provenance.** Wrong-deal, ambiguous, unreviewed, or incompatible-unit claims cannot become financial inputs; the projection is reproducible. | BR-BUILD-011 | 45 min |

### BR-BUILD-E03 — Black River Document Workflow Builder

Skill: `br-build-document-workflows`. Owner: `evidence_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-013 | **Define intake manifests and duplicate behavior.** Reprocessing identical input is idempotent; corrupt or unsupported files remain visible without guessed content. | BR-BUILD-007 | 40 min |
| BR-BUILD-014 | **Normalize candidate extraction results.** The envelope preserves raw values and provenance; absent fields remain missing and do not become zero. | BR-BUILD-008, BR-BUILD-004 | 40 min |
| BR-BUILD-015 | **Reconcile financial document fields.** Totals, period alignment, units, and source conflicts are checked with declared rules and no invented balancing amounts. | BR-BUILD-014, BR-BUILD-019 | 60 min |
| BR-BUILD-016 | **Build the review application service.** Only valid state transitions create reviews; unresolved source conflicts cannot bypass the evidence engine. | BR-BUILD-015, BR-BUILD-010 | 60 min |
| BR-BUILD-017 | **Map reviewed fields into model inputs.** Only permitted fields and scenarios are changed; evidence values never silently replace probability assumptions. | BR-BUILD-016, BR-BUILD-012 | 60 min |
| BR-BUILD-018 | **Propagate evidence changes to downstream decisions.** A changed material input cannot reuse an approval for an old packet; the old result remains inspectable. | BR-BUILD-017, BR-BUILD-033 | 60 min |

### BR-BUILD-E04 — Black River Financial Engine Builder

Skill: `br-build-financial-engine`. Owner: `quant_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-019 | **Define monetary and time conventions.** Boolean, nonfinite, missing, overflow, and incompatible currency/unit inputs fail explicitly. | BR-BUILD-004 | 40 min |
| BR-BUILD-020 | **Implement the complete cost bridge.** Every cost is counted once; refundable deposits and unspent reserves are distinguished from consumed expenses. | BR-BUILD-019 | 60 min |
| BR-BUILD-021 | **Calculate scenario economics.** Dependencies within each case are preserved; acquisition cash, terminal profit, and dated returns are labeled separately. | BR-BUILD-020 | 60 min |
| BR-BUILD-022 | **Calculate binding investment limits.** The strictest applicable constraint is visible; higher seller acceptance never silently relaxes a financial rule. | BR-BUILD-021 | 60 min |
| BR-BUILD-023 | **Extend financing and valuation coherently.** Loan proceeds and principal repayments reconcile; IRR/NPV claims require correctly dated cash-flow definitions. | BR-BUILD-020 | 120 min |
| BR-BUILD-024 | **Reconcile modeled and realized cash.** A billed amount is not a cash receipt; corrections preserve original postings and use explicit adjusting evidence. | BR-BUILD-021, BR-BUILD-012 | 120 min |

### BR-BUILD-E05 — Black River Probability Engine Builder

Skill: `br-build-probability-engine`. Owner: `quant_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-025 | **Define outcome events and conditioning.** Every probability has a denominator and horizon; an existing live counter is distinguished from a fresh offer. | BR-BUILD-004 | 45 min |
| BR-BUILD-026 | **Enumerate a joint economic distribution.** Weights sum to one; dependencies between sale prices and costs are represented jointly rather than silently assumed independent. | BR-BUILD-025, BR-BUILD-021 | 60 min |
| BR-BUILD-027 | **Compute terminal pursuit value.** Branches are mutually exclusive and exhaustive; failed-pursuit costs are deducted once and unknown acceptance stays unknown. | BR-BUILD-026 | 60 min |
| BR-BUILD-028 | **Apply conditional risk policies.** Conditional and unconditional criteria are never interchanged; discrete chance boundaries are checked directly. | BR-BUILD-027, BR-BUILD-022 | 60 min |
| BR-BUILD-029 | **Evaluate decision sensitivity and continuation limits.** Assumption ranges are not confidence intervals; grid-cell counts are not probabilities that a strategy is best; multi-round claims require transitions. | BR-BUILD-028 | 60 min |
| BR-BUILD-030 | **Design and validate empirical probability models.** Use only information available at prediction time; handle pending/censored cases and related-deal leakage; no calibrated claim without evaluation evidence. | BR-BUILD-025, BR-BUILD-058 | 180 min |

### BR-BUILD-E06 — Black River Deal Workflow Builder

Skill: `br-build-deal-workflow`. Owner: `evidence_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-031 | **Define independent qualification dimensions.** Passing one dimension never substitutes for the evidence needed by another. | BR-BUILD-012 | 45 min |
| BR-BUILD-032 | **Define event-driven transaction stages.** Extraction and inference cannot directly advance agreement, closing, ownership, or cash-settlement status. | BR-BUILD-031 | 60 min |
| BR-BUILD-033 | **Bind decisions to exact evidence packets.** Changed material inputs invalidate the prior review; scope, role, and review separation are checked. | BR-BUILD-032, BR-BUILD-022 | 60 min |
| BR-BUILD-034 | **Make retries and concurrency safe.** Concurrent or repeated requests cannot duplicate a financial effect or silently approve a stale revision. | BR-BUILD-033 | 60 min |
| BR-BUILD-035 | **Separate proposals from externally consequential actions.** A builder or simulation cannot send offers, sign documents, move funds, or claim ownership without a separately authorized execution path. | BR-BUILD-033 | 45 min |
| BR-BUILD-036 | **Track completion, operation, exit, and reinvestment.** Only independently evidenced receipts become realized cash; living-expense or reinvestment allocations preserve obligations and reserves. | BR-BUILD-034, BR-BUILD-024 | 120 min |

### BR-BUILD-E07 — Black River CUDA Compute Builder

Skill: `br-build-cuda-compute`. Owner: `quant_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-037 | **Identify useful computational parallelism.** Parallelize independent cases; preserve within-case financial order; retain tiny or irregular control work on CPU with reasons. | BR-BUILD-021, BR-BUILD-026 | 45 min |
| BR-BUILD-038 | **Define bounded batch interfaces.** Shape, length, identifiers, finite values, overflow and maximum allocation are checked before execution. | BR-BUILD-037, BR-BUILD-004 | 45 min |
| BR-BUILD-039 | **Implement reusable GPU execution.** Avoid per-record transfers and repeated model/kernel initialization; explicit CUDA failures never silently become CPU execution. | BR-BUILD-038 | 75 min |
| BR-BUILD-040 | **Verify numeric and decision parity.** Money and eligibility decisions match declared semantics; tolerance is meaningful in currency units and tested at policy boundaries. | BR-BUILD-039, BR-BUILD-062 | 90 min; needs CUDA |
| BR-BUILD-041 | **Measure complete workload performance.** Every speedup names hardware, workload, precision, baseline, warmup and transfer scope; no speedup is inferred from utilization alone. | BR-BUILD-040 | 120 min; needs CUDA |
| BR-BUILD-042 | **Integrate acceleration across callers.** R and application callers invoke the same financial backend; results report actual execution and have stable case ordering. | BR-BUILD-038, BR-BUILD-044 | 90 min; needs CUDA + R |

### BR-BUILD-E08 — Black River R Validation Builder

Skill: `br-build-r-validation`. Owner: `quality_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-043 | **Establish reproducible R and Python environments.** Do not fabricate a renv lock or successful run; record actual R/Python versions and independently verify restoration. | BR-BUILD-004 | 60 min; needs R |
| BR-BUILD-044 | **Define typed cross-language exchange.** Cents, nulls, IDs, dates/time zones and array order round-trip without lossy implicit conversion. | BR-BUILD-004, BR-BUILD-019 | 45 min |
| BR-BUILD-045 | **Implement small independent reference checks.** The check is independently expressed and executed; it does not become a competing authoritative production engine. | BR-BUILD-044, BR-BUILD-027 | 90 min; needs R |
| BR-BUILD-046 | **Evaluate calibration and economic forecast loss.** Out-of-sample evaluation excludes future information; uncertainty and thin samples remain explicit. | BR-BUILD-044, BR-BUILD-030 | 180 min; needs R |
| BR-BUILD-047 | **Model time-to-event and competing outcomes.** Pending cases are not mislabeled failures; competing outcomes and observation windows are represented explicitly. | BR-BUILD-044, BR-BUILD-058 | 180 min; needs R |
| BR-BUILD-048 | **Produce reproducible analytical reports.** Every result resolves to data and executable analysis; unexecuted R/CUDA paths are explicitly marked. | BR-BUILD-045, BR-BUILD-046, BR-BUILD-047 | 90 min; needs R |

### BR-BUILD-E09 — Black River Review Interface Builder

Skill: `br-build-review-interface`. Owner: `architect_integrator`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-049 | **Design the source-to-number trace.** An operator can explain one output and locate its source without relying on a generated narrative. | BR-BUILD-012, BR-BUILD-021 | 75 min |
| BR-BUILD-050 | **Display evidence conflicts and missingness.** Unknown, zero, rejected, expired and conflicting values remain visually and semantically distinct. | BR-BUILD-016 | 75 min |
| BR-BUILD-051 | **Expose investment policy controls.** Changing a control records a new input version and visibly changes the affected policy output; no hidden relaxation occurs. | BR-BUILD-028 | 75 min |
| BR-BUILD-052 | **Render complete offer and outcome comparisons.** Acquisition probability, conditional profit, joint target probability and per-attempt value are not conflated. | BR-BUILD-027 | 75 min |
| BR-BUILD-053 | **Implement usable and accessible interactions.** Primary workflows are legible and operable at supported sizes and with assistive access; declared locales preserve currency/date meaning, and comprehension is tested with intended users. No undocumented language… | BR-BUILD-049, BR-BUILD-050 | 90 min |
| BR-BUILD-054 | **Verify review and recalculation behavior.** The displayed result matches the actual service revision, and stale or unauthorized actions fail visibly. | BR-BUILD-051, BR-BUILD-052, BR-BUILD-033 | 90 min |

### BR-BUILD-E10 — Black River Data Connector Builder

Skill: `br-build-data-connectors`. Owner: `evidence_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-055 | **Define source access and permitted operations.** Record permitted access and purpose before ingestion; support the applicable consent/retention boundary. A read-only task does not acquire write authority; secrets never enter source control or diagnostic… | BR-BUILD-004 | 40 min |
| BR-BUILD-056 | **Read structured files without semantic loss.** Preserve original values, units, nulls and locations; malformed or unsupported cells remain errors rather than guessed values. | BR-BUILD-055, BR-BUILD-007 | 75 min |
| BR-BUILD-057 | **Resolve deal and entity identity explicitly.** Ambiguous matches never merge automatically; provenance and historical owner/version context remain visible. | BR-BUILD-056, BR-BUILD-009 | 120 min |
| BR-BUILD-058 | **Capture complete timestamped outcomes.** Retain unsuccessful and pending cases; preserve related-deal grouping and avoid selection bias from successful-only ingestion. | BR-BUILD-055, BR-BUILD-032 | 90 min |
| BR-BUILD-059 | **Implement incremental and idempotent ingestion.** Replay does not duplicate claims; partial failure does not advance the source cursor beyond committed work. | BR-BUILD-056 | 90 min |
| BR-BUILD-060 | **Version source and schema changes.** Changed schemas and source revisions cannot silently alter existing accepted inputs or historical model runs. | BR-BUILD-059, BR-BUILD-009 | 75 min |

### BR-BUILD-E11 — Black River Model Validation Builder

Skill: `br-build-model-validation`. Owner: `quality_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-061 | **Define claims and acceptance evidence.** Check actual product behavior, including a meaningful failure; avoid tests that merely repeat the implementation. | BR-BUILD-005 | 30 min |
| BR-BUILD-062 | **Construct independent numeric references.** Cost bridges, terminal mass, chance thresholds and policy decisions reconcile without circularly reusing the same function. | BR-BUILD-020, BR-BUILD-026 | 60 min |
| BR-BUILD-063 | **Challenge evidence and input integrity.** Unknown or invalid records cannot enter accepted-input projections or silently relax gates. | BR-BUILD-012, BR-BUILD-017 | 60 min |
| BR-BUILD-064 | **Check backend and language parity.** Unavailable hardware/runtime is an explicit limitation; no fallback or mocked execution is represented as a measured result. | BR-BUILD-039, BR-BUILD-044 | 120 min; needs CUDA + R |
| BR-BUILD-065 | **Verify the non-AI runtime boundary.** No LLM, NIM, autonomous-agent loop, or unapproved remote call is required by the default path. | BR-BUILD-001, BR-BUILD-017 | 45 min |
| BR-BUILD-066 | **Publish the validation and gap register.** Separate implemented, executed, reviewed, deferred and unavailable; agent consensus never substitutes for evidence. | BR-BUILD-061, BR-BUILD-062, BR-BUILD-063, BR-BUILD-065 | 45 min |

### BR-BUILD-E12 — Black River Future AI Adapter Builder

Skill: `br-build-ai-adapters`. Owner: `evidence_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-067 | **Define disabled optional provider contracts.** No model is installed, contacted, or made a runtime dependency just because the interface exists. | BR-BUILD-014, BR-BUILD-001 | 40 min |
| BR-BUILD-068 | **Pin NVIDIA service and hardware compatibility.** Do not mix the newer Parse /v1/parse API with older VLM chat-completions examples; GPU/VRAM compatibility must be observed. | BR-BUILD-067, BR-BUILD-037 | 90 min; needs CUDA; deferred phase |
| BR-BUILD-069 | **Evaluate assisted extraction against labeled documents.** Model outputs remain candidate claims; extraction score, evidence authority and deal-outcome probability stay separate. | BR-BUILD-068, BR-BUILD-063 | 180 min; needs CUDA; deferred phase |
| BR-BUILD-070 | **Build scoped retrieval and reranking.** Search cannot expose another scope's files; cited passages resolve to the exact document revision and location. | BR-BUILD-067, BR-BUILD-055 | 180 min; needs CUDA; deferred phase |
| BR-BUILD-071 | **Constrain assistive generation to accepted tools and evidence.** Generated prose cannot overwrite canonical amounts, approve a transaction, or silently modify investment policy. | BR-BUILD-069, BR-BUILD-070, BR-BUILD-035 | 120 min; needs CUDA; deferred phase |
| BR-BUILD-072 | **Evaluate any later product-agent runtime separately.** Builder-agent configuration never grants product autonomy; runtime agents remain disabled until the separate phase is explicitly implemented and validated. | BR-BUILD-071, BR-BUILD-076 | 180 min; needs CUDA; deferred phase |

### BR-BUILD-E13 — Black River Release Operations Builder

Skill: `br-build-release-operations`. Owner: `quality_builder`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-073 | **Package explicit runtime configuration.** Default operation needs no AI keys; secrets are external; installed capabilities and optional dependencies are visible. | BR-BUILD-004, BR-BUILD-067 | 45 min |
| BR-BUILD-074 | **Apply safe schema and data migrations.** A failed migration preserves recoverable prior data; historical evidence and decisions are not silently rewritten. | BR-BUILD-009, BR-BUILD-034 | 75 min |
| BR-BUILD-075 | **Verify backup, restore, and replay.** Backup existence alone does not count as recovery; restored identifiers, records and balances reconcile. | BR-BUILD-074, BR-BUILD-024 | 90 min |
| BR-BUILD-076 | **Observe workload, quality, and failures.** Logs omit secrets and private document bodies by default. Measure actual backend, queue latency, error/review rates, storage, throughput, and unit economics. A two-million-household capacity claim requires… | BR-BUILD-059, BR-BUILD-041 | 120 min |
| BR-BUILD-077 | **Run release gates and document limitations.** No unavailable R/CUDA/AI execution is claimed; failures stop the affected release path and remain explicitly described. | BR-BUILD-073, BR-BUILD-066 | 60 min |
| BR-BUILD-078 | **Stage production enablement by capability.** Builder skills do not start production agents. Enable providers and external actions only within their implemented, authorized boundaries. Expand from a validated initial segment using observed participant… | BR-BUILD-077, BR-BUILD-035 | 90 min |

### BR-BUILD-E14 — Black River Builder Resource Coordinator

Skill: `br-coordinate-builder-resources`. Owner: `architect_integrator`.

| Ticket | Work and acceptance focus | Dependencies | Estimate |
| --- | --- | --- | --- |
| BR-BUILD-079 | **Maintain the dependency graph and ready queue.** Reject missing dependencies and cycles; completed prerequisites satisfy dependencies and deferred/blocked work cannot become ready. | BR-BUILD-003 | 60 min |
| BR-BUILD-080 | **Allocate bounded builder and execution resources.** Never allocate more than three parallel workers and one integrator; zero CUDA or R capacity blocks tickets requiring those runtimes. | BR-BUILD-079 | 60 min |
| BR-BUILD-081 | **Schedule critical work with visible estimates.** Durations are labeled planning assumptions; estimates never become promised dates or fabricated performance measurements. | BR-BUILD-080 | 75 min |
| BR-BUILD-082 | **Prevent concurrent file-ownership conflicts.** Overlapping file or ancestor-directory write scopes cannot run concurrently; no builder may overwrite another's unintegrated work. | BR-BUILD-080 | 45 min |
| BR-BUILD-083 | **Enforce quality, rework and handoff gates.** A task becomes completed only after its own evidence is reviewed; rework preserves failure history and invalidates affected downstream assumptions. | BR-BUILD-082, BR-BUILD-061 | 30 min |
| BR-BUILD-084 | **Report roadmap and resource-blocked work.** Distinguish plan, active builders and actual runtime deployment; disclose AI deferral and resource shortages instead of pretending the full roadmap is complete. | BR-BUILD-081, BR-BUILD-083 | 30 min |

## Handoff required for each completed ticket

Record the source revision, exact changed paths, implemented behavior, meaningful check invocation and result, observed runtime/backend, unresolved limitations, reviewer, and linked acceptance evidence. For a dependency change or rework, identify downstream tickets whose previous assumptions need rechecking.

After an engine changes, rerun the checks that resolve its specific remaining risk and the required release gates. Do not add redundant tests merely to increase the count. A high-quality fast swarm limits work in progress, protects shared interfaces, and keeps a ready queue while blocked work awaits its actual resource or evidence.

See [builder coordination](../architecture/builder-swarm.md), [engine/layer contracts](../architecture/document-engine-layers.md), and [the R exchange guide](../guides/r-evidence-validation.md).
