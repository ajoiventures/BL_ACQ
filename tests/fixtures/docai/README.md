# Synthetic Doc AI invoice fixtures

These are original fictional test materials authored for this repository. No
private document, real customer identity, invoice, provider output or external
source was copied. Every rendered invoice says it is synthetic and not payable.
The CSV is a synthetic table; the malformed control is deliberately not a valid
PDF. Test materials follow the repository's source usage terms and must not be
presented as real financial records.

The initial declared class is `MEP_INVOICE`; this corpus does not establish a
general invoice reader, OCR model or deployed service. Ground truth in
`manifest.json` is independent of implementation predictions. Each original and
reference has a SHA-256, and every answer has an exact page/offset/quote span.
Money labels use string integer cents and dates use ISO dates. Text is UTF-8 with
LF line endings; offsets count Unicode codepoints, not UTF-8 bytes.

| ID | Split | Original | Case | Native status |
| --- | --- | --- | --- | --- |
| DOC-SYN-001 | Development | `invoice_native.txt` | Six simple labeled fields | complete |
| DOC-SYN-002 | Development | `invoice_table.csv` | Native CSV table; candidate grammar challenge | complete |
| DOC-SYN-003 | Development | `invoice_ambiguous.txt` | Conflicting totals and ambiguous date convention | complete |
| DOC-SYN-004 | Development | `malformed.pdf` | Missing document objects/page tree | error; MALFORMED_PDF |
| DOC-SYN-005 | Development | `invoice_missing.txt` | Complete source bytes, missing due date and amount | complete |
| DOC-SYN-105 | Holdout | `invoice_holdout.txt` | Unicode vendor and labeled values | complete |
| DOC-SYN-106 | Holdout | `invoice_native.pdf` | Native labeled fields plus a visible line-item table | complete |
| DOC-SYN-107 | Holdout | `invoice_scan.pdf` | Raster-only page, no hidden native text | needs_ocr |
| DOC-SYN-108 | Holdout | `invoice_over_limit.txt` | Invoice fields lie beyond the 150,000-byte read limit | partial |

There are nine originals, 54 field labels, 32 answerable values and 22 required
abstentions. The five development documents contain 20 answers and 10 abstention
labels; the four holdout documents contain 12 of each. The CSV has six known gold
values even though the initial label grammar cannot propose them. Preserve those
misses in the reported coverage denominator.

The PDFs were authored with ReportLab on a letter page. The native PDF uses
Courier text and a monospaced line-item table. Its reference text was authored
from the intended lines and checked against native extraction; a visual blank
gap is not an extra text line. The scan contains one raster image authored from
fictional text and no hidden PDF text. Its separate `.reference.txt` file is the
synthetic authoring transcript, **not an OCR result**. All scan labels intentionally
require native abstention. A future OCR/provider-quality evaluation needs another
versioned scope and truth definition.

The over-limit original is retained in full. Run it with the manifest's
`read_limits` override, including `max_text_bytes=150000`; other configured native
limits are recorded by the extractor. It is different from `invoice_missing.txt`,
whose entire source can be read but still lacks facts.

The fixed holdout is repository-visible and highly patterned. Do not optimize
code to those values and then claim independent validation. If it informs tuning,
retain it as development evidence and create/version a new holdout. Do not move
related versions of a source between splits or silently repair a released label.

Corpus version: `br-docai-native-invoices-001`, v1. Canonical manifest fingerprint:
`f313e2d6599680333afa2a4d188f0dd9603765be16e309829b0405653d8a4378`.
The canonical fingerprint ignores JSON indentation; it binds all manifest labels
and metadata. Original/reference hashes bind the actual files.

Run `python -m unittest tests.test_docai_metrics -v` from the repository root to
check hashes, quote locations, fixed splits, explicit cents, Unicode offsets,
and independently calculated scorer behavior. The PDF text/image check runs
when PyMuPDF is available and reports a skip otherwise. Visual render inspection
was performed separately; test success does not imply production quality.

See the [evaluation policy](../../../docs/validation/docai-evaluation-policy.md)
for thresholds, denominators, small-sample limits and the later AI boundary.
