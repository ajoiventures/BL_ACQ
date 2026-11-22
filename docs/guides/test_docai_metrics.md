# `tests/test_docai_metrics.py`

## Purpose

Verify the Doc AI metrics interface independently of the production parser and
candidate extractor. This test file owns numerical reference checks and corpus
integrity checks, so parser output cannot define its own gold truth.

## Run

```bash
python -m unittest tests.test_docai_metrics -v
```

The suite uses Python's standard-library `unittest`. One optional fixture check
uses PyMuPDF (`fitz`) to confirm that the native PDF matches authored text and
the scanned PDF contains one image with no hidden text. That check is explicitly
skipped if PyMuPDF is unavailable; no dependency or model is downloaded.

## Evidence covered

The hand-authored two-document case has two answerable and two abstention labels.
Three proposals include one exact answer, one wrong date with a valid source span,
and one unsupported value marked accepted. The independently expected value
precision is 1/3, value recall 1/2, span fidelity 2/3 and critical false accepts 1.
Elapsed times 10 and 30 ms give a 20 ms mean; decimal costs 0.003 and 0.007 sum
exactly to 0.010. These expectations are literal calculations, not sums of the
scorer's own case output.

Additional cases exercise correct value/wrong citation, wrong canonical units,
missing output, all-abstention behavior, empty denominators, unexpected fields,
error/abstention separation, split leakage, duplicate identities/JSON keys,
bad spans, nonfinite or excessive usage, and rejected confidence fields.

Fixture checks bind nine original hashes, 54 labels, 32 answerable values, the
five/four fixed split and the canonical manifest fingerprint. Literal development
invoice offsets and Unicode byte/codepoint differences provide independent source
checks. Tampered originals, incorrect gold quotes, path traversal and an external
symlink are rejected. The CLI checks artifact verification, JSON output, error exit
status and refusal to overwrite an earlier report.

## Interpretation and limits

Passing these tests establishes scorer mechanics and fixture consistency. It does
not establish native extraction accuracy or safe real review/export behavior.
The separate [native evaluation tests](test_docai_evaluation.md) cover the runtime
adapter. The [evaluation policy](../validation/docai-evaluation-policy.md) governs
scope and acceptance. No live provider, CUDA, R, network, deployment or authentic
human review is performed by this suite.
