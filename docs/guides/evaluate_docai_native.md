# `tools/evaluate_docai_native.py`

## Purpose

Run the actual native document reader and strict invoice candidate grammar against
the frozen synthetic corpus, then translate their output into the independent
metrics interface. The runner preserves runtime provenance and unsupported field
coverage. Archive, human review and accepted export require separate application
tests. No AI or OCR service is invoked.

## Run and artifacts

From the repository root:

```bash
python tools/evaluate_docai_native.py \
  --corpus tests/fixtures/docai/manifest.json \
  --split all \
  --output-dir /tmp/docai-run
```

The output directory must be new. The corpus defaults to the checked-in manifest
and the split defaults to `all`. `development` and `holdout` restrict execution
and scoring to that fixed split. An empty selected split is an error.

| Artifact | Contents |
| --- | --- |
| `predictions.json` | `br.docai-predictions.v1` values, spans, abstentions, observed latency, pending review status |
| `report.json` | Independent metrics, explicit denominators, processing-status counts, integrity checks and limitations |
| `execution.json` | Original identity, extraction runs, candidates, parser/configuration versions, code hashes and timing basis |

Re-score the measured output without repeating extraction:

```bash
python tools/docai_metrics.py \
  --corpus tests/fixtures/docai/manifest.json \
  --predictions /tmp/docai-run/predictions.json \
  --split holdout
```

Exit 0 means artifacts were written, not that quality passed or a ticket closed.
Input/output validation errors return 2. Unexpected runtime exceptions fail
visibly and never become successful abstentions. A failed write can leave an
incomplete new directory; retain it as failure evidence and use a new path.

## Engine and scoring boundary

`evaluate_native(corpus, root, split="all")` verifies the synthetic-only manifest,
source/reference hashes and gold quotes. It builds a document from identity,
class, original hash and byte count, then calls
`extract_document(path, document, run_id, limits=...)`. The native reader rechecks
source identity. `invoice_candidates` receives only the actual document and
extraction through the application interface. Its grammar lives in
`pilot/document_invoice.py`.

Gold values and citations are never passed to those production functions. Exact
integer cents become canonical strings without floating point; text and dates
remain unchanged. A proposal must have one native candidate and one source span.
Duplicate candidates or incompatible types fail instead of choosing an answer.
Absent candidates produce explicit abstentions for the six declared fields.
Unexpected fields remain visible to the scorer.

A handled malformed original retains document status `error` and its structured
errors in `execution.json`, while unsupported facts are abstained. A runtime
exception is a failed evaluation. The actual configured limits, parser versions,
source text and truncation evidence remain in each extraction record.

All emitted review decisions are pending. Human review time and operating cost
are unknown and remain null. The runner supports only synthetic originals and
`native_invoice_contract_v1`; it reads sources without moving them or creating a
product vault. Provider/model metadata must be absent.

## Reproducibility and timing

Execution evidence binds the corpus fingerprint and hashes of the runner,
scorer, application interface, invoice engine, contracts, native adapter and
filing implementation. Source hashes are checked before and after execution;
changes require a fresh run. Corpus integrity is checked again afterward.
Run IDs and UTC timestamps identify actual invocations, so artifacts are
deliberately not byte-identical between runs.

`time.perf_counter` measures each native extraction plus candidate generation,
including any parser-worker startup. It excludes corpus verification, metrics
conversion and report I/O. OS cache state is uncontrolled. These are local
observations, not a cold/warm benchmark or a production latency/throughput claim.

The metrics run on CPU; the native PDF reader needs the installed `pypdf`
dependency. Nothing is downloaded. CUDA and R require separately measured future
work. The [policy](../validation/docai-evaluation-policy.md) predeclares 26 of 32
answerable fields within the initial label grammar and 22 required abstentions.
The six CSV candidate misses stay in aggregate recall.

Run the [integration checks](test_docai_evaluation.md) with:

```bash
python -m unittest tests.test_docai_metrics tests.test_docai_evaluation -v
```
