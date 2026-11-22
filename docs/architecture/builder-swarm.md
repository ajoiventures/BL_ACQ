# Black River builder swarm

## Decision and scope

The existing swarm supplies the development team used to build Doc AI. Its agents inspect
requirements, implement code, challenge assumptions, test behavior, and hand
changes to an integrator. They are not processes inside the acquisition product.

A skill is a reusable development procedure. An agent is a temporary worker
assigned a bounded task and the relevant skills. An engine is executable
processing, workflow or numerical code. An application layer coordinates engines and
records. None of these definitions requires a product LLM or autonomous agent.

The native/manual document path remains useful without inference. Build the
provider contract and disabled/fake-adapter tests alongside the document core;
connect one real provider at a bounded readiness milestone. Any later product
agent runtime is a further, separate decision. Builders are not document
processing workers inside the product.

The [Doc AI plan](../plans/docai-ticket-plan.md) is the active workstream.
The [source audit](docai-current-state.md) distinguishes existing filing,
evidence, local-model client code and missing integration. Preserve the
previous acquisition/evidence increment as a downstream demonstration.
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

## Extend the existing organization

BR-SWARM-001 and BR-SWARM-SKILLS-001 retain L1–L4 ownership, SW-00
coordination, SW-13 independent review, SK-01–35 and the existing specialist
roster. The [library extension](../../config/swarm-library-extension.json)
maps the 14 procedural builder skills into that organization. It preserves
domain Academy collections; it does not replace them.

The audited organizational code already contains a PROJECT_INTERNAL ticket
register in `backend/core/tickets.py` and a reviewed artifact workflow in
`site_academy/runner.py`. Adapt those interfaces after compatibility review.
The business simulation in `backend/core/swarm.py` uses underwriting and
settlement states and is not the engineering ticket state machine. Audited
snapshots have no verified deployment identity; do not treat a folder name as
the canonical running service.

## Four reusable task profiles

| Role | Owns | Required handoff |
| --- | --- | --- |
| Product architect and integrator — L1/L2, SW-00 | Doc AI boundary, shared contracts, work allocation and integration | Source revision, integrated result and precise status |
| Evidence and workflow engineer — L2, L4/SW-09 | Intake, document identity, claims, review, connectors and provider contracts | Reproducible evidence history and blocking cases |
| Financial and compute engineer — L2/L3, SW-04/SW-05 | Downstream financial consumers, probability, precision and suitable CUDA batches | Worked calculation, backend behavior and numeric limits |
| Validation and release engineer — SW-13 review | Independent evidence checks, evaluation, recovery and release evidence | Observed successes/failures and unexecuted paths |

The current resource profile allows three worker agents plus one reserved
integrator. The four roles describe responsibilities; a role is not a
permanent runtime, employee, paid subscription, or claim of unlimited
concurrency. A worker can take successive bounded tasks after handing off its
previous work.

## Skills and capability coverage

[The builder catalog](../../config/builder-skills.json) defines 14 reusable
skills and 84 granular capabilities. Each capability records its input,
output, acceptance criterion, dependencies, and a delivery-state field.
A catalog entry is a specification. The personal procedures have been
installed separately; that does not implement their 84 capabilities or prove
a runtime is connected.

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
| `br-build-ai-adapters` | Design provider interfaces now; implement and evaluate a selected optional backend at its readiness gate |
| `br-build-release-operations` | Package, recover, observe, and stage actual capabilities |
| `br-coordinate-builder-resources` | Maintain the DAG, resource plan, write ownership, estimates, and roadmap |

The [earlier ticket plan](../plans/document-engine-tickets.md) preserves the
84-capability work breakdown and its evidence. It is not the Doc AI critical
path. The [active plan](../plans/docai-ticket-plan.md) maps document work to
existing BR-ENG requirements and BR-T commitments. Installing a builder skill
does not start any product service or agent.

## Coordination and scheduling

The active [machine-readable work breakdown](../../config/docai-ticket-plan.json)
contains status, owner, priority, dependencies, phase gates, assumption-based
duration, required resources, file write scopes, deliverables, and acceptance
criteria for every child item. BR-ENG-MASTER-001 remains the requirements
authority; existing PROJECT_INTERNAL BR-T records retain execution status and
reviewed closure. A scheduler snapshot is an advisory projection, not a second
ticket database. Crosswalk IDs and revisions rather than overwriting history.

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
3. Keep CUDA and R execution capacity at zero until those environments are
   actually available. Source design and fake/HTTP-client tests need no local
   GPU. Hosted inference needs an authorized endpoint and budget; self-hosted
   inference needs compatible measured runtime capacity. Split those tasks.
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

The first Doc AI workflow must preserve originals and receipts, report native
extraction completeness, reject malformed provider output, retain page/span
provenance, and require independent acceptance of candidate claims. Retried
jobs must not create duplicate document facts; changed requests reusing an
idempotency key must fail visibly. Reviewers must see missing pages, failed
extractions and conflicting values. Live-provider gates also require version,
endpoint/auth, allowed-data, timeout, cost and evaluation evidence.

The retained acquisition-consumer demonstration has separate checks:

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

Stabilize the smallest document and review contracts while building the
disabled provider seam in parallel. Deliver native intake-to-review, then a
bounded selected-provider evaluation. Provider production enablement follows
measured quality and operational evidence. Financial expansion, household
scale, optional retrieval and R research do not gate first extraction.
Product agents, if ever justified, need a separate validated execution and
authority design.

See [engine and layer contracts](document-engine-layers.md) and the
[R exchange guide](../guides/r-evidence-validation.md).
