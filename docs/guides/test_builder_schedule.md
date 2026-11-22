# Validate the offline builder scheduler

Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_builder_schedule.py' -v
```

The tests use standard-library Python only. They construct small schedules with
independently stated expected times and also validate the repository's actual
ticket plan. No GPU, R runtime, AI model, credentials or network are required.

The cases cover three worker slots plus a reserved integration slot; one active
ticket per named owner; ancestor file-scope serialization; similar path names
that may run concurrently; a repository-wide write lock; phase gates; dependency
joins; critical path calculation; stable priority selection; and input order
independence of scheduling decisions. Timeline assertions check resources,
owner exclusivity, write conflicts and prerequisite completion across every
event boundary.

Blocked-work checks cover zero CUDA/R capacity, requests exceeding available
capacity, explicit unresolved prerequisites, deferred phases and propagation of
blocked or excluded dependencies. Status checks ensure completed work has a
consistent completed prerequisite closure and that in-progress work reserves
remaining effort without overcommitting resources, owners or write scopes.

Malformed inputs include unknown and cyclic dependencies, self dependencies,
cycles induced by phase gates, duplicate IDs, invalid phases/statuses, Boolean
or fractional integer fields, resource declarations, absolute/traversal/glob
paths and duplicate normalized scopes. Reports must remain finite JSON, inputs
must remain unchanged, and the plan digest must change when its input changes.

The CLI test creates a temporary plan, checks JSON on standard output, writes a
new schedule artifact, then repeats the write and verifies rejection with the
original bytes preserved. Temporary artifacts are removed after the test.

Passing these checks establishes the modeled scheduling behavior. It does not
measure builder throughput, run the scheduled acceptance criteria, validate
actual hardware availability or authorize a release. The real plan's reported
counts and estimated time can change as the maintainer updates completion
evidence and resource assumptions; the tests therefore validate invariants
instead of freezing that evolving plan to a delivery estimate.
