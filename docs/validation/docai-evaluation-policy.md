# Doc AI evaluation policy: native invoice contract v1

Declared on 2026-11-22 for BR-DOC-003, before the native corpus evaluation and
before any live provider result. This policy defines local evidence requirements;
it does not close a ticket, authenticate a reviewer, or activate a provider.

## Scope and baseline

The initial use case is an explicitly declared `MEP_INVOICE` that proceeds from
native text to source-linked candidate fields, human review and accepted export.
The six scored fields are `vendor`, `invoice_number`, `invoice_date`, `due_date`,
`total_cents` and `currency`. Registered classes and fields outside this list are
not supported by this evaluation. A readable PDF or CSV does not by itself prove
that its fields can be interpreted.

The baseline is the local native reader plus the application's strict invoice
label grammar, with AI and OCR disabled. The parser must preserve original bytes
and page text. The candidate grammar supports unique `Vendor:`, `Invoice:`,
`Invoice date:`, `Due date:`, `Total due:` and `Currency:` labels. It must abstain
on missing or conflicting values. The CSV fixture is deliberately a field-coverage
challenge outside that initial candidate grammar; its six known values remain in
the overall denominator. Do not remove it to improve an aggregate score.

The nine-document corpus has 54 labels: **32 answerable values and 22 required
abstentions**. Of the 32 answers, 26 occur in the declared label grammar and six
in the CSV challenge. A hypothetical correct narrow grammar therefore has
26/32 overall grounded value recall, or 81.25%, while retaining a visible coverage
gap. This is a predeclared scope calculation, not a measured result.

## Fixed corpus and split

The manifest is [`tests/fixtures/docai/manifest.json`](../../tests/fixtures/docai/manifest.json),
with corpus ID `br-docai-native-invoices-001`, version `1`, scope
`native_invoice_contract_v1`, and canonical JSON SHA-256
`f313e2d6599680333afa2a4d188f0dd9603765be16e309829b0405653d8a4378`.
See the [fixture README](../../tests/fixtures/docai/README.md) for file identities
and authoring provenance.

| Split | Documents | Answerable labels | Required abstentions | Intended use |
| --- | ---: | ---: | ---: | --- |
| Development | 5 | 20 | 10 | Implementation feedback and known adverse examples |
| Holdout | 4 | 12 | 12 | A separately reported fixed verification set |
| All | 9 | 32 | 22 | Full inventory and transparent coverage accounting |

The holdout is repository-visible, small and highly patterned. It is not blinded
or a statistically independent sample of real invoices. Builders must not tune
to its labels or choose only successful cases after viewing results. If holdout
labels inform a change, preserve this result as development evidence and version
a genuinely new held-out set before making an independent quality claim. Related
versions of one original must stay in one split. These originals have different
source hashes; shared synthetic grammar is still a source of correlation.

Gold canonical values were authored independently of parser output. Gold spans
refer to independently authored reference page text, checked against actual bytes
and native PDF text. No prediction is copied into gold. Correcting a released
label requires a new corpus version and fingerprint plus an explanation; it must
not silently rewrite earlier evaluation results.

## Processing and abstention controls

| Case | Expected native status | Required field behavior |
| --- | --- | --- |
| Plain labeled text; labeled native PDF | `complete` | Propose only exact supported values with exact page spans |
| CSV table | `complete` | Preserve readable text; report unsupported candidate coverage honestly |
| Conflicting totals or an ambiguous date | `complete` | Abstain on the conflicting/ambiguous fields |
| Fully read original with absent fields | `complete` | Abstain on missing fields; do not claim a byte-coverage failure |
| Malformed PDF | `error` with `MALFORMED_PDF` | No invented fields; retain the structured error |
| Image-only PDF | `needs_ocr` | No native-text fields; a transcript is not OCR evidence |
| Original exceeding the declared read limit | `partial` | No complete-source claims or proposals from an unseen tail |

The byte-limit case declares `max_text_bytes=150000`; all invoice labels occur
after that point. Other native limits, including a per-page character cap, remain
visible in the actual extraction. Its complete original bytes remain in the
corpus. The incomplete-looking small original is a separate case whose native
read is complete.

An explicit field `abstain` is different from an omitted output, and a field
`error` is different from either. Missing documents/fields stay in denominators.
Provider experiments must use a separately versioned scope and appropriate image
truth labels: this native contract intentionally expects no OCR answers on scans.
It must not be used to penalize successful, authorized OCR as though those native
abstention labels described provider quality.

## Predeclared evidence and acceptance criteria

The evaluation foundation requires all nine originals, all 54 labels, valid
original/reference hashes, checked quotes, unchanged split/fingerprint, and the
independent scorer arithmetic/adverse-input tests. This establishes an evaluation
instrument, not application performance.

For a narrow native grammar quality claim, independently review the exact code
revision, configuration and full report against all of these criteria:

1. Report all nine processing results and all 54 field decisions, with **zero
   missing documents, missing fields, and unexpected fields**. Expected native
   statuses must match 9/9; structured error codes need separate extraction tests.
2. Every proposed value and citation must be correct: value precision 1.0 and
   span fidelity 1.0 with nonzero proposal denominators. Recover all 26 answerable
   values in the predeclared label-grammar subset. Report the six CSV field misses
   separately and keep them in the overall 32-answer denominator.
3. Correctly abstain on all 22 required abstentions. Abstaining everywhere fails
   extraction coverage. Empty denominators or absent evidence never pass a rate
   threshold.
4. **Zero critical false accepts and zero false accepts of any field.** A correct
   value with a wrong/missing citation is a false accept if marked accepted.
   Unknown accepted fields also fail. This requirement applies even if an overall
   precision metric would otherwise round to 100%.
5. A native evaluation runner produces only pending proposals. Its zero accepted
   fields cannot prove review safety. Gate A needs separate actual review/export
   tests, including rejecting stale/cross-context or unsupported acceptance and
   tracing accepted values to the original. A synthetic scorer input claiming
   `accepted` is only reported test input, not an authenticated review record.
6. Record observed extraction-plus-candidate wall time and which processing
   methods actually ran. Missing human review time and unmeasured operating cost
   remain null. No latency, cost, deployment, or household-scale service level is
   certified from this bounded sample.

A broader claim covering the CSV candidate fields additionally requires 32/32
grounded answers with the same safety conditions. Failed or insufficient criteria
require rework or explicitly narrowed supported scope, not a changed denominator.
Scorer exit code zero means the report was validly produced; it is not a quality
pass or authority to transition the durable ticket.

## Metric definitions and denominator rules

The report exposes each rate's numerator and denominator alongside its value.
Let `P` be proposed fields, `A` answerable labels, `AP` proposals on answerable
field slots, `V` exactly correct values, `S` exact allowed spans, and `G` proposals
with both correct value and span. Unexpected fields are included in `P`.

| Metric | Definition | Meaning |
| --- | --- | --- |
| Field precision | `AP / P` | Proposal belongs to an answerable field slot; does not establish value correctness |
| Field recall | `AP / A` | Answerable field slots receiving a proposal |
| Exact value accuracy | `V / AP` | Value correctness conditional on a proposed answerable slot |
| Value precision | `V / P` | Exact correct values among every proposal, including unsupported fields |
| Value recall | `V / A` | Exact correct values among all answerable labels |
| Span fidelity | `S / P` | Proposal matches an allowed page/hash/offset/quote exactly |
| Grounded value recall | `G / A` | Both exact value and correct citation recovered |
| Required abstention accuracy | Correct abstentions / required abstention labels | Safe behavior on the predefined ambiguous/unreadable controls |
| Proposal coverage | Proposals on labeled fields / all labels | Amount proposed; a larger value alone is not better |
| Document reporting coverage | Reported documents / selected documents | Whether evaluated inputs were silently dropped |
| Processing status accuracy | Correct native statuses / selected documents | Complete/partial/error/OCR states reported truthfully |

All zero-denominator rates are JSON `null`, never 0 or 1. There is no tolerance,
fuzzy match, whitespace correction, date guessing or float conversion in the
scorer. Money is canonical string integer cents, such as `"125000"`, and dates
are ISO dates. Spans use Unicode codepoints, the complete reference page's SHA-256
and an exact quote. The CLI verifies original/reference artifacts before scoring;
the pure `evaluate` function deliberately does not read files and reports that
artifact integrity was not checked there.

Review time and extraction latency report observation counts, total, mean and
median over observed values only. They do not impute zero for absent observations.
Reported USD costs use exact fixed-point decimal strings. The scorer cannot infer
hardware/electricity, labor or API charges from a missing bill.

## Small samples, calibration and future provider evaluation

These nine synthetic documents test mechanics and known failure modes. They do
not estimate commercial invoice accuracy, population error, fraud detection,
institutional suitability or capacity for two million households. A field count
does not create 54 independent documents. No calibrated probabilities or
confidence intervals are asserted from this corpus.

Provider confidence, empirical field correctness, human acceptance, source
reliability, and deal/event probabilities remain separate quantities. This
scorer rejects confidence fields in prediction rows and reports calibration as
`not_evaluated`. It must never promote an unvalidated score into a probability.

Before a live provider experiment, declare a new provider-quality corpus/scope,
authorized sources, grouping/split method, exact provider/model/API/runtime
versions, baseline, field-level safety and coverage thresholds, minimum sample
and class/field coverage, review protocol, cost/time caps and stop rules. Preserve
failed/abstained runs. These preconditions plus the current connection gates are
required before viewing live outputs. This native policy grants no connection,
transfer, model download, or production permission.

Later calibration work needs appropriately labeled held-out probability-like
scores and sufficient independent observations. R may reproduce error rates and
diagnostics through a versioned, typed exchange carrying document/run/model IDs,
split, source hashes, exact units and missingness. An R design or exported file
is not an R execution. Pin and record the runtime before claiming those results.

The current scorer remains a readable CPU reference: fewer than a hundred label
comparisons and small summary reductions do not justify device transfer or GPU
startup. Future large inference/evaluation batches can be profiled for useful
CUDA execution with parity checks and actual hardware evidence. No CUDA, R,
model, network, or provider execution is performed by the metrics tool.
