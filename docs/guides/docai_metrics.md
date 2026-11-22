# `tools/docai_metrics.py`

## Purpose

Score a frozen synthetic document corpus using an independent JSON interface.
The tool reads labels and predictions, verifies original/reference integrity,
and reports exact values, citations, coverage, abstentions, reported acceptance
errors, elapsed time and cost. It neither extracts documents nor calls a provider.
Its report is evidence for independent review, not a ticket transition.

## Inputs and public functions

`validate_corpus(corpus)` validates the `br.docai-corpus.v1` manifest.
`verify_corpus(corpus, root)` additionally checks source/reference SHA-256 and
every gold quote against UTF-8 reference text. Relative artifacts must stay
inside `root`; traversal, external symlinks and artifacts over 8 MB are rejected.
The v1 interface permits only synthetic originals.

`corpus_fingerprint(corpus)` hashes finite canonical UTF-8 JSON with sorted keys
and compact separators. It binds labels, splits, hashes and scope, independent
of file indentation. `evaluate(corpus, predictions, split="holdout")` validates
and scores the independent prediction envelope, but does not read artifacts.
Its integrity status is therefore `not_checked_by_pure_scorer`. `load_json(path)`
rejects duplicate JSON keys, nonfinite JSON constants, and files over 32 MB.

The `br.docai-predictions.v1` envelope includes `corpus_id`, `corpus_sha256`,
`scope`, and `documents`. Each document identifies `document_id`,
`processing_status` (`complete`, `partial`, `needs_ocr`, `unsupported`, or `error`),
and `fields`. A field uses:

```json
{
  "field": "total_cents",
  "decision": "propose",
  "canonical_value": "125000",
  "span": {
    "page": 1,
    "text_sha256": "698de26d12a53468eb135d4d3498917fa7599a05c14ea2a768629784869b747b",
    "start": 166,
    "end": 174,
    "quote": "1,250.00"
  },
  "review_decision": "pending"
}
```

This example is the first development fixture. Runtime cents are exact integers;
an evaluation adapter stringifies them without converting through floating point.
Dates are canonical ISO strings. The scorer compares exact values without fixing
case, spaces, formatting or units. A citation must equal an allowed page hash,
Unicode-codepoint range and quote. Correct values with wrong citations fail
grounded correctness.

For `decision="abstain"` or `"error"`, value/span must be null or absent and the
review decision cannot be accepted. Missing output is counted as missing, not
as an abstention. Review decisions default to pending; accepted/rejected are
reported observations only. The scorer does not authenticate them. Confidence
fields are rejected rather than interpreted as correctness probabilities.

Optional document fields `latency_ms` and `review_ms` are observed finite,
nonnegative numbers, at most 1e12 milliseconds. Unknown values are null or absent.
`reported_cost_usd` is an unsigned fixed-point decimal string with at most 12
decimal places and value at most 1e12 USD; exponents and floats are rejected.
Unknown cost stays null. Aggregate observations state their sample counts.

## Running it

From the repository root, score an existing real prediction artifact:

```bash
python tools/docai_metrics.py \
  --corpus tests/fixtures/docai/manifest.json \
  --predictions /tmp/docai-run/predictions.json \
  --split holdout \
  --output /tmp/docai-holdout-report.json
```

The output path must be new; existing reports are never overwritten. Omit
`--output` to write JSON to standard output. Exit 0 means the report was generated;
exit 2 means an invalid input, hash mismatch or file error. Exit 0 is not a quality
pass. The default holdout split prevents development cases from inflating its
denominator. `--split all` provides the full transparent inventory; unknown IDs
or duplicate fields fail rather than being silently dropped.

The [native runner guide](evaluate_docai_native.md) describes obtaining predictions
from the real local native reader and invoice candidate function. Never construct
an implementation accuracy report by copying gold labels into predictions.

## Reading the result

The `br.docai-metrics.v1` report contains explicit counts and a
`{numerator, denominator, value}` object for each rate. Zero denominators produce
`null`. Field-slot precision/recall are distinct from exact value precision/recall.
`processing_status_counts` reports native document errors separately from
`counts.errors`, which counts field-level error decisions. Span fidelity is
distinct from value correctness. Required abstention accuracy
does not excuse low answer coverage. All proposals, including unsupported fields,
affect precision. Claimed accepted answers with wrong values or spans count as
false accepts, including unregistered accepted fields.

See the [evaluation policy](../validation/docai-evaluation-policy.md) for all
formula definitions, declared scope, evidence minimums and zero-false-accept
criteria. Calibration is explicitly `not_evaluated`; usage and review inputs
are not independently observed by this pure scorer.

## Runtime and limitations

Only Python standard-library code is required for scoring. It runs on CPU and
imports no parser, application, R, CUDA or provider client. Bounded string/hash
comparisons and small reductions do not justify GPU transfer/startup overhead.
Future large batches require measured profiling and parity against this reference.
R diagnostics remain a later typed, versioned validation track.

The checked-in nine-document corpus tests a narrow native contract. Its scores
cannot establish general invoice accuracy, production readiness, a live NVIDIA
connection, review identity, or capacity for the household-scale goal. Tests and
their independent numerical references are described in
[`test_docai_metrics.md`](test_docai_metrics.md).
