# Offline builder work scheduler

`tools/schedule_builder_work.py` turns a versioned build ticket plan into a
deterministic proposed schedule. This is development tooling for the people and
agents building Black River. It does not spawn agents, run tickets, call an AI
service, access the network, deploy software or operate a property transaction.

The public Python entry point is:

```python
import json
from tools.schedule_builder_work import schedule_plan

with open("config/build-ticket-plan.json", encoding="utf-8") as source:
    report = schedule_plan(json.load(source))
```

From the repository root, inspect the report on standard output or save a new
JSON artifact:

```bash
python tools/schedule_builder_work.py --plan config/build-ticket-plan.json
python tools/schedule_builder_work.py --plan config/build-ticket-plan.json --output /tmp/br-builder-schedule-new.json
```

Choose a new output name for every saved report. The CLI refuses to overwrite an
existing file. The API does not mutate the supplied plan. `plan_sha256` records
the exact canonical JSON input, including descriptive metadata and list order.

## Input contract

The schema version is `br.build-ticket-plan.v1`. The supplied repository plan
contains 84 tickets across 14 epics; future revisions can add or revise tickets
without changing the scheduling algorithm. Inputs are bounded to 2,000 tickets
and 100,000 effective dependency edges. Extra descriptive metadata is allowed,
but it must serialize to finite JSON.

| Field | Meaning and validation |
| --- | --- |
| `resource_profile` | Exactly `agent_worker`, `integrator`, `cuda_device`, `r_runtime`, all nonnegative integers. Up to three workers and exactly one reserved integrator. These are declared capacities, not detected hardware. |
| `scheduling_policy.reserved_integrator` | Integer `1`; a worker cannot borrow this lane. |
| `scheduling_policy.enabled_phases` | Nonempty unique list of phase names present in the plan. Other phases are excluded from this run. |
| `scheduling_policy.estimate_basis` | Explicit explanation that durations are planning assumptions. |
| `scheduling_policy.phase_gates` | Optional map from phase to prerequisite ticket IDs. Gate dependencies are merged with each ticket's own dependencies. |
| `tickets[].id` | Unique stable identifier, up to 100 characters, using letters, digits, dots, underscores, colons or hyphens. |
| `title`, `owner`, `phase` | Nonempty text. Each named owner is one builder lane, with at most one active ticket. |
| `dependencies` | Unique known ticket IDs. Self dependencies, unknown IDs and cycles, including cycles created by phase gates, reject the plan. |
| `status` | `planned`, `in_progress`, `completed`, `blocked` or `deferred`. |
| `priority` | Integer 0–1,000; lower numbers come first. |
| `estimated_minutes` | Positive integer, at most 1,000,000. For an in-progress ticket, this means assumed remaining effort. |
| `required_resources` | Exactly one worker or one integrator, plus optional CUDA or R resources. Unknown resource names, negative values and Boolean numeric values reject the plan. |
| `write_scopes` | Relative repository paths or directory prefixes. An empty list declares no writes; `.` claims the whole repository. Absolute paths, traversal and globs are rejected. |
| `acceptance_criteria` | Nonempty list describing the required quality evidence. The planner does not execute or certify these checks. |
| `blockers` | Explicit unresolved conditions. A nonempty list holds work even when its status is `planned`. |

The current resource profile has three worker slots, one reserved integration
slot, zero CUDA devices and zero R runtimes. The four named owners in the current
plan are `evidence_builder`, `quant_builder`, `quality_builder` and
`architect_integrator`. Owner exclusivity applies in addition to pooled capacity.
Reassigning work requires an explicitly revised plan; spare pooled capacity does
not duplicate a named builder.

## Dependency, phase and quality gates

A completed ticket satisfies dependencies without consuming resources or adding
duration. Its own prerequisites must also be completed, and it cannot still
list unresolved blockers. An in-progress ticket must have all prerequisites
already completed, belong to an enabled phase and fit the currently declared
resources. Existing in-progress tickets reserve their lane and write scopes at
minute zero. Conflicting owner, resource or write claims reject the plan.

The plan's completion statuses are assertions supplied by its maintainer. The
planner does not infer completion from a file's existence or from a proposed end
time. Record independently verified acceptance evidence before changing a status
to `completed`. Likewise, the simulation assumes a predecessor will successfully
finish before its dependent begins; it does not grant a real release approval.

Tickets in disabled phases or with `deferred` status are listed as `excluded`.
Enabled tickets with missing resources, explicit blockers or blocked/excluded
prerequisites are listed as `blocked`. The report preserves reasons, including
the immediate dependency IDs responsible for propagated holds. A planned GPU
test with zero CUDA capacity remains blocked; its time is not included as though
it had run. A resource request exceeding a positive capacity is also held with
an `insufficient_resource_capacity` reason. Malformed resource declarations and
already-running overcommit are validation errors.

## Scheduling mechanics

The scheduler uses bounded list scheduling. At each relative time boundary it
releases finished work, finds dependency-ready tickets, and considers them in
this order:

1. Lower priority number.
2. Longer remaining dependency path.
3. Stable ticket ID.

It assigns only tickets that fit all current resource, owner and file ownership
constraints. If a higher-ranked ticket must wait, another eligible ticket can
use otherwise free capacity. Work is nonpreemptive: a proposed ticket holds its
resources until its assumed end time. The method is a transparent heuristic; it
does not claim to minimize the overall completion time.

File conflicts use normalized path components. `pilot/core` conflicts with
`pilot/core/file.py`; it does not conflict with `pilot/core2/file.py`. The tool
does not inspect files, follow symlinks or discover undeclared side effects.
Every writer must therefore declare its complete repository scope.

The algorithm stays on CPU because the workload is a small dependency graph
with branching, string ownership checks and event boundaries. CUDA transfer and
kernel work would not improve the correctness of this control task. CUDA
capacity is still modeled for relevant build tickets; probability batches and
other substantial numerical workloads retain their separate explicit CUDA
implementations. R execution tickets remain modeled resources, with no R
execution or compatibility claim made by this scheduler.

## Reading the report

The output schema is `br.builder-schedule.v1`. `dependency_ready_now` identifies
remaining schedulable tickets whose prerequisites are already complete.
`proposed_starts_at_zero` is the subset that can begin after current in-progress
reservations and allocation constraints are applied.

Each `scheduled` row gives its assumed start/end minute, resource requirements,
effective dependencies and write scopes. `dependency_ready_minute` and
`ready_wait_minutes` separate dependency waiting from later allocation waiting.
`wait_reasons` reports observed constraints with `values` containing resource
names for `resource_busy`, the owner name for `owner_busy`, or blocking ticket
IDs for `write_scope_conflict`. Several constraints can explain the same wait;
their durations should not be added together.

`resource_timeline` shows the active tickets and resource use at every scheduling
boundary. The `critical_path_lower_bound_minutes` and associated ticket chain
ignore resource, owner and write contention. They apply only to remaining
schedulable work, excluding blocked and future work. The
`estimated_makespan_minutes` includes modeled allocation contention for that
same subset. Neither value is the completion time for the entire roadmap when
blocked work remains. `current_enabled_scope_fully_schedulable` explicitly
indicates whether current enabled work is fully represented.

All times are relative planning estimates. They have no calendar start date,
availability calendar, interruption allowance, observed throughput model or
probability of meeting a delivery date. Reschedule after updating evidence,
statuses, durations, assignments or capacities. A schedule is not proof that a
build, a quality gate or a deployment has occurred.
