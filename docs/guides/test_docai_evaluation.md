# `tests/test_docai_evaluation.py`

## Purpose and command

Exercise the real native reader and invoice candidate engine through the
evaluation adapter, alongside the independent arithmetic tests in
[`test_docai_metrics.md`](test_docai_metrics.md).

```bash
python -m unittest tests.test_docai_evaluation -v
```

The suite uses the nine synthetic originals and installed native PDF parser.
It invokes no model, download or real review. Missing native PDF support fails
the integration expectation visibly instead of being reported as complete.

## Evidence covered

The predeclared narrow baseline requires 9/9 processing statuses, 54 explicit
decisions, 26 exact/cited proposals, 22 required abstentions and six CSV misses.
The denominator remains 32 answerable fields, yielding grounded recall 26/32.
Malformed PDF, image-only PDF, missing fields and configured truncation keep
distinct status and evidence.

Tests verify observed timing, parser/run/configuration identity, original hashes
and the invoice engine source hash. Reviews stay pending; unknown review time
and cost stay null. Changing a gold total in a detached test corpus from 125000
to 999 leaves the actual source-derived prediction at 125000 and creates a scored
error. This guards against manufacturing predictions from labels.

A bad original hash must stop before extraction, an unexpected runtime exception
must remain a failed run, and changing code during evaluation invalidates results.
Writing refuses to overwrite an earlier output directory. Re-scoring the measured
predictions through the independent CLI reproduces the holdout's 12 answers and
12 required abstentions.

## Limits

Count expectations bind this frozen corpus and narrow grammar. Later CSV support
needs reviewed new output and updated runtime scope; never change gold to fit
mistakes. The small repository-visible corpus does not establish general invoice
accuracy, production readiness, authenticated acceptance, CUDA or R execution.
Archive/review/export need independent application and vault tests. See the
[evaluation policy](../validation/docai-evaluation-policy.md).
