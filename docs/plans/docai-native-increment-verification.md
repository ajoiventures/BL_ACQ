# Doc AI native increment: implementation and verification

Date: November 22, 2026. Scope: local document engine and synchronous review
application. This record does not certify a live AI connection, production
deployment, authenticated multiuser service or organizational ticket closure.

## Delivered result

The first native path runs from an original document through the preserved
filing interface, a source-bound extraction, six declared invoice fields,
explicit review/correction and accepted export. It uses ordinary Python and
SQLite without model inference. The builder swarm remained outside the runtime.

The public [synthetic accepted example](../../data/docai/accepted_invoice_demo.json)
was produced by the actual `demo` command. It retains the synthetic marker,
original SHA-256, exact quotations, typed values, parser configuration, extraction
pages, actual CPU backend and automated synthetic review reasons. The actor is
`synthetic-demo-runner`, and `execution_authority` is `none`.

| Synthetic invoice field | Observed typed value |
| --- | --- |
| vendor | Example Mechanical Services |
| invoice_number | SYN-INV-001 |
| invoice_date | 2026-11-20 |
| due_date | 2026-12-15 |
| total_cents / currency | 125000 / USD |
| Source quote for amount | `1,250.00` |

Normal new proposals remain pending. The demo's explicitly automated review
steps are confined to the bundled synthetic original; they do not represent a
person approving a real invoice. See the [CLI guide](../guides/run_docai.md) and
[mechanics guide](../guides/document_application.md) for manual operation.

## Reuse and ownership evidence

The initial local baseline was commit
`12df530eaa1e3ae73f620d71c326075de1b31c91`, whose tree
`42fe36afc14efd46fa441f76c50c6ee7b95980ec` matched published PR15 baseline
`99d9fef31535767c89aec399815b8956c9f820b8`. The
[dated audit](../architecture/docai-current-state.md) records the execution
decision and old filing/ticket/model source hashes. No private routing data,
organizational archive or application database was imported.

Three bounded builders separately owned contracts, native intake and evaluation.
The integrator owned vault/application composition, documentation and plan
integration. A builder other than the relevant implementation author reviewed
native source identity, review/version behavior and metric arithmetic/provenance.
These are local development review records; they are not authenticated SW-13
transitions in the existing PROJECT_INTERNAL tracker.

The review found and resolved three concrete implementation gaps: a revised
amount label was initially missed by ambiguity detection; an accepted older
source remained exportable after a successor; and the evaluation fingerprints
initially omitted the newly separated invoice engine. Regression cases or
independent reruns cover each correction. Mixed PDF image/Form content now
receives an explicit partial native-coverage result.

## Native corpus evaluation

The retained artifacts come from an actual native reader and candidate-parser
run, followed by separate holdout rescoring. They include original/page hashes,
source code hashes, configuration, processing status and observed timing:

- [Full report](../../data/docai/native-baseline-20261122/report.json)
- [Pending predictions](../../data/docai/native-baseline-20261122/predictions.json)
- [Execution and source fingerprints](../../data/docai/native-baseline-20261122/execution.json)
- [Separate designated holdout report](../../data/docai/native-baseline-20261122/holdout-report.json)

| Measure | Observed result |
| --- | ---: |
| Original documents / original-and-reference artifacts | 9 / 11 |
| Explicit field decisions / labels | 54 / 54 |
| Expected processing statuses | 9 / 9 |
| Exact proposed values | 26 / 26 |
| Correct proposal spans | 26 / 26 |
| Answerable values recovered with correct evidence | 26 / 32 = **81.25%** |
| Correct required abstentions | 22 / 22 |
| CSV answerable fields not proposed | **6** |
| False proposals / missing outputs / unexpected fields | 0 / 0 / 0 |
| Reviewed accepted fields in the evaluation | **0** |

The native statuses were six complete, one malformed-PDF error, one OCR-needed
scan and one partial bounded read. The evaluator preserves all six unsupported
CSV field misses in the recall denominator. It does not fabricate reviewed
acceptances. Zero false accepts with zero accepted fields is not evidence of
review safety; review/export invariants have their own application tests.

The four-document designated holdout separately produced 12/12 exact grounded
answers and 12/12 required abstentions. It is tiny, patterned and visible in the
repository. It is not a blinded sample or a population accuracy estimate.
The [predeclared evaluation policy](../validation/docai-evaluation-policy.md)
states the scope, split, thresholds, denominators and future provider-quality
requirements. The corpus canonical JSON SHA-256 is
`f313e2d6599680333afa2a4d188f0dd9603765be16e309829b0405653d8a4378`.

The retained run observed about 620 ms summed extraction-plus-candidate wall
time for nine originals. This excludes archive/review/report I/O; parser startup
and OS cache were uncontrolled. It is not a service latency, throughput or CUDA
benchmark. Human review time and operating cost remain null. No confidence score
or calibrated probability is asserted.

Reproduce with a new output directory:

```bash
python tools/evaluate_docai_native.py --output-dir /tmp/br-docai-evaluation --split all
python tools/docai_metrics.py --corpus tests/fixtures/docai/manifest.json --predictions /tmp/br-docai-evaluation/predictions.json --split holdout --output /tmp/br-docai-evaluation/holdout-report.json
```

## Executed checks

The focused Doc AI verification ran **96 tests successfully**: 17 contract,
23 native parser, 19 application and 37 metrics/evaluation tests. Its cases
include malformed files, missing PDF dependency, bounded worker time/memory,
invalid UTF-8, partial coverage, exact Unicode citations, stale review revisions,
changed-payload retry, context filtering, corrupt originals, source/candidate
supersession, transaction rollback/retry and independent scorer arithmetic.

```bash
python -m unittest tests.test_docai_contracts tests.test_docai_native tests.test_docai_application tests.test_docai_metrics tests.test_docai_evaluation -q
```

The full repository acceptance runner and final guide/metadata checks are
recorded in the integration result section below. A check that cannot run or
fails remains a failed/unverified gate; a passing native subset cannot substitute
for an unrelated browser or production release requirement.

## Ticket and capability status

The updated [24-child plan](docai-ticket-plan.md) records local completion for
BR-DOC-001, 002, 003 and 005. BR-DOC-004 and 008 contain tested partial evidence
and remain planned for their unfulfilled criteria. Four completed planning
children are not four closed canonical tickets.

The next three dependency-ready workers are L1 on vault ACL/retention work
(004), L4 on durable intake jobs (006), and L2 on the disabled provider seam and
mock contract (007). The regenerated remaining schedule reserves one separate
integrator, with three worker slots and no declared CUDA/R runtime capacity.
Its point simulation is 750 relative minutes for the schedulable remainder,
with a 560-minute critical-path lower bound and 480–1,360 minute low/high
assumption scenarios. These are estimates, not delivery commitments.

Gate A remains open: the CLI trusts the local OS user and supplied actor labels;
it has no authenticated service ACL, revocation/retention workflow, durable
leased job/outbox service or complete operational release. Its native text
support is separate from its one narrow invoice field grammar. Twelve class
registries do not establish twelve working extractors.

NVIDIA Parse is a selected future adapter target, recorded with documentation
version and owner in [the target configuration](../../config/docai-provider-target.json).
The generic seam, selected real client, authenticated endpoint and actual model
runtime remain unimplemented or unverified. AI/model downloads/live calls and
production activation remain disabled. Gates B/C/D have not passed. No R or
CUDA execution, model-quality claim or two-million-household capacity test was
performed. No financial transaction or negotiation authority was introduced.

## Integration result

The assembled `tools/check_pilot.py` runner was executed with the pinned local
check dependencies. Observed results were:

| Check | Result |
| --- | --- |
| Configured Ruff fatal-error subset, including filing | Passed |
| Existing mypy scope | Passed; three previously typed modules |
| Reporting suite | 9 tests passed |
| Pilot suite, including the 96 Doc AI cases | 315 passed; 1 real-CUDA test skipped; 316 discovered |
| Tool suite | 1 test passed |
| Source guides and Markdown links | 86 maintained source/config files, 123 Markdown files; zero errors |
| Synthetic recovery | Reconciled and restored; two review events and two settled synthetic invoices |
| Founder browser replay | Failed before assertions: Chromium could not create its process-singleton socket (`Operation not permitted`) |
| Valuation browser replay | Not reached because the sequential runner stopped at that launch failure |

Thus the full release gate is **not passed**. No browser assertion result is
invented and no weakened launch configuration substitutes for the blocked test.
The native command has no browser interface. The PR remains a draft; production
and hosted CI acceptance are separate requirements.

The [structured check record](../../data/docai/increment-checks.json) binds source
and test file hashes to these observations. The retained corpus source hashes
match the final native evaluation source. Final text formatting was followed by
a fresh native corpus run and focused Doc AI regression run; the quality counts
were unchanged. PDF fixtures are stored as binary Git artifacts to preserve
their original bytes and cross-reference offsets. The synthetic demo was rerun with a
fixed demonstration actor and self-contained referenced extraction records.
The remaining plan was revalidated and its exact file/canonical hashes are
recorded in the generated plan. Final publication also checks that the Git tree
created remotely matches the reviewed local tree before conditionally updating
the existing draft branch.
