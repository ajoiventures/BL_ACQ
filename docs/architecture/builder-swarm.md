# Black River builder swarm

## Decision and scope

The swarm is the development team used to build the product. Its agents inspect
requirements, implement code, challenge assumptions, test behavior, and hand
changes to an integrator. They are not processes inside the acquisition product.

A skill is a reusable development procedure. An agent is a temporary worker
assigned a bounded task and the relevant skills. An engine is executable
business or numerical code. An application layer coordinates engines and
records. None of these definitions requires a product LLM or autonomous agent.

The default product path must run without NVIDIA inference, an LLM endpoint,
or an autonomous-agent scheduler. Document AI is a later optional provider
layer. Any later product-agent runtime is a further, separate decision.

This boundary applies to this acquisition and document-evidence increment.
Earlier portfolio descriptions of agent and review services remain broader
commercial possibilities; they do not establish an embedded runtime in this
increment. The [existing coverage map](capability-coverage.md) retains the
338-requirement master scope. This increment does not claim to complete it.

The future scale goal is two million U.S. households, including immigrants.
Choose an initial service segment, participant incentive, payer/revenue model,
and measurable customer-value hypothesis before expansion. Validate consent,
accessibility, localization, review workload, unit economics, and representative
capacity. The goal is not a measured capacity result. Wall Street-level rigor
remains a validation target, not an institutional-readiness claim.

## Four builder leaders

| Role | Owns | Required handoff |
| --- | --- | --- |
| Product architect and integrator | Business boundary, shared contracts, work allocation, application integration, review experience | Source revision, integrated result, conflict resolution, and precise status |
| Evidence and workflow engineer | Document identity, claims, review, accepted-input projection, source connectors, future provider interfaces | Reproducible evidence history, current projection, and blocking cases |
| Financial and compute engineer | Authoritative formulas, conditional probabilities, constraints, precision, CUDA batches | Worked calculation, test evidence, backend behavior, and numeric limits |
| Validation and release engineer | Independent references, R exchange, failure cases, recovery, release evidence | Observed successes/failures and unexecuted or unavailable paths |

The current resource profile allows three worker agents plus one reserved
integrator. The four roles describe responsibilities; a role is not a
permanent runtime, employee, paid subscription, or claim of unlimited
concurrency. A worker can take successive bounded tasks after handing off its
previous work.

## Skills and capability coverage

[The builder catalog](../../config/builder-skills.json) defines 14 reusable
skills and 84 granular capabilities. Each capability records its input,
output, acceptance criterion, dependencies, and a delivery-state field.
A catalog entry is a specification, not proof of implementation or proof
that a personal skill has been installed.

| Skill | Primary responsibility |
| --- | --- |
| `br-build-product` | Bound and integrate the product increment |
| `br-build-evidence-engine` | Preserve document identity, claims, reviews, and source-linked inputs |
| `br-build-document-workflows` | Join intake, reconciliation, review, and recalculation |
| `br-build-financial-engine` | Maintain financial rules, cost treatment, capital, and cash reconciliation |
| `br-build-probability-engine` | Define conditional outcomes, pursuit value, risk policies, and sensitivity |
| `br-build-deal-workflow` | Preserve independent qualification gates and transaction-state authority |
| `br-build-cuda-compute` | Implement bounded acceleration with CPU parity and measured hardware evidence |
| `br-build-r-validation` | Specify and later execute reproducible R research and independent checks |
| `br-build-review-interface` | Expose evidence, formulas, assumptions, and decisions clearly |
| `br-build-data-connectors` | Ingest authorized sources with identity, time, and schema lineage |
| `br-build-model-validation` | Challenge numerical, evidence, and runtime-boundary claims |
| `br-build-ai-adapters` | Define optional later NVIDIA and assistive AI interfaces |
| `br-build-release-operations` | Package, recover, observe, and stage actual capabilities |
| `br-coordinate-builder-resources` | Maintain the DAG, resource plan, write ownership, estimates, and roadmap |

The [ticket plan](../plans/document-engine-tickets.md) maps the 84 capabilities
one-to-one to development tickets. Personal skill installation is a separate
operation in the user's skill library. Installing a builder skill does not
start any product service or agent.

## Coordination and scheduling

The canonical [machine-readable plan](../../config/build-ticket-plan.json)
contains status, owner, priority, dependencies, phase gates, assumption-based
duration, required resources, file write scopes, deliverables, and acceptance
criteria for every ticket.

The offline scheduler is implemented at `tools/schedule_builder_work.py` with
`tests/test_builder_schedule.py`. Its scope is development planning: validate
the plan, expose ready work, reserve capacities, serialize conflicts, and
estimate relative start/finish times. It does not launch agents, contact
providers, change product states, or execute a ticket's tests.

Use the following operating rules:

1. Validate IDs, all dependency references, and the dependency-plus-phase-gate
   graph before dispatch. Reject cycles, unknown resources, or invalid estimates.
2. Reserve the integrator separately from the three worker slots. Assign each
   ticket exactly one worker or one integrator plus any declared special runtime.
   Treat each named owner as one builder lane, with at most one active ticket
   per owner; change assignments explicitly between planning runs.
3. Keep CUDA capacity and R runtime capacity at zero until those environments
   are actually available. A GPU or R ticket remains resource-blocked even if
   its source files can be reviewed.
4. Prevent overlapping write scopes from running concurrently. A directory
   scope overlaps its descendants. Coordinate shared edits through one owner.
5. Prioritize dependency-ready work using priority and the remaining critical
   path. Estimates are planning assumptions, not calendar promises or measured
   builder throughput.
6. Review actual evidence before marking a ticket completed. A scheduler can
   read a completion status; it cannot prove the assertion.
7. Return failed work to its owner with the failing artifact or trace. Preserve
   rework history and re-evaluate affected downstream assumptions.
8. Recompute the ready queue and roadmap after meaningful status or resource
   changes. Show blocked and deferred work explicitly.

## Dispatch contract

Each builder assignment must name:

- The operating problem and exact input/source revision.
- The engine or layer owned by the task.
- The allowed file write scope and shared-file coordination rule.
- The relevant skill and capability/ticket IDs.
- Required input/output contracts and the meaning of missing data.
- Success, failure, precision, and source-provenance acceptance checks.
- Prohibited runtime expansion, external writes, or real transaction actions.
- Required handoff evidence and remaining uncertainty.

Keep assignments narrow enough for a coherent implementation and review.
Parallelize independent implementation lanes; keep interface changes,
integration, reviews, approvals, and shared mutations sequential.

## Completion and quality gates

A high-quality handoff contains the changed files, the implemented behavior,
a reproducible invocation, meaningful check results, and limitations.
Inspect the emitted artifacts and independently reproduce material claims.
Reviewer consensus cannot replace source evidence or numerical validation.

For this increment, the minimum integration demonstration is:

- An unreviewed synthetic quote cannot alter underwriting.
- A reviewed $35,000 quote produces the original assumptions.
- A newer $55,000 quote remains blocked while its review is pending.
- Acceptance of the newer quote permits an explicitly bound recalculation.
- Stale, conflicting, wrong-deal, or malformed evidence remains a hold.
- A document binding cannot silently alter probabilities or investment policy.
- A changed live counter's terms cannot reuse its previous conditioning premise.
- No default run requires AI credentials or launches product agents.
- R and CUDA execution status is reported exactly as observed.

A failed critical gate returns the task for rework. Optional unavailable
runtime checks remain open with their resource requirement. They are never
converted into passes to make a release appear complete.

## Roadmap boundary

Engine core comes first, application composition second, and operator
presentation/API integration follows stable contracts. Later assistive AI
adapters may propose extracted claims or explanations through the same
review boundaries. Product agents, if ever justified, need a separate
validated execution and authority design.

See [engine and layer contracts](document-engine-layers.md) and the
[R exchange guide](../guides/r-evidence-validation.md).
