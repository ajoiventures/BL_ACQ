# Inspect native extraction mechanics

[document_native.py](../../pilot/document_native.py) adapts the existing
[filing implementation](../../filing/inbox.py) to the shared
[Doc AI contract](document_contracts.md). Its public interface is:

```python
extract_document(path, document, run_id, *, limits=None)
```

`path` points to the archived original. `document` is a validated `br.docai.v1`
document record carrying tenant/domain/subject/case identity, version, source
reference, SHA-256, byte count and received time. `run_id` identifies this
execution. `limits` contains explicit overrides of the shared defaults. The
result is a validated extraction dictionary, suitable for the application to
store and then use when proposing source-linked candidates.

## Follow one execution

1. Validate and detach the supplied document and limits using the shared
   contract module. Unknown fields, invalid types and unbounded native execution
   settings fail before parsing.
2. Read bounded regular-file bytes and bind parsing to their actual SHA-256 and
   byte count. PDF/DOCX subprocesses receive those same bytes on stdin; they do
   not reopen a mutable source path.
3. Retain exact Unicode page text within byte and character budgets. Record its
   SHA-256 without newline normalization or replacement characters. Page spans
   in later candidates use Unicode code-point offsets into this retained text.
4. Compare the observed source hash and byte count against document identity.
   Any mismatch raises `ValueError`; it cannot produce a falsely bound run.
5. Record the native parser/Python version, optional pypdf version, configuration
   digest, UTC start/finish timestamps, coverage and structured errors. The
   configuration digest includes limits, worker memory/time bounds and encoding.
   Return the shared validator's normalized extraction record.

Metadata, format errors and source bytes are separate concerns. An unreadable
or unstable source, an unsafe path or an invalid document record raises an input
error. A readable, identified source with an unsupported or broken format
returns a structured run, preserving its original identity for review.

## Supported text projections

| Reader | Page meaning | Coverage and remaining limits |
| --- | --- | --- |
| TXT, MD, CSV | One logical text page | Strict UTF-8 text, exact retained newlines. CSV is text only; there is no spreadsheet formula or column-type interpretation. Invalid bytes fail, and a truncated terminal multibyte code point is omitted without replacement. |
| DOCX | One logical body-text page | Bounded UTF-8 `word/document.xml`, joined in XML text order. DTD/entity declarations fail. Main XML outside the byte limit returns partial. Headers, footnotes, comments, embedded media and recognized nontext objects make coverage partial; visual layout is not reconstructed. |
| Native PDF | Physical PDF pages | pypdf native text, physical numbering and retained page hashes. Page/text budgets, blank pages among text pages and image/Form XObjects make coverage partial. No image decode, visual interpretation or OCR is claimed. |
| PDF without native text | Physical PDF pages | `needs_ocr`, blank retained text and incomplete coverage when the full bounded page range is read. A page-limited scan remains partial because later pages were not examined. Blank and image-only pages are conservatively held together. |
| PNG/JPEG/TIFF signature | One logical input item | `needs_ocr` after signature recognition only. Image validity and physical image/page counts are not decoded. A bad signature is a distinct error. |
| Other suffixes | No extracted pages | `unsupported` with `UNSUPPORTED_FORMAT`. Originals can still be archived. |

`complete` means the declared native text projection finished within known
limits. It does not prove semantic correctness, field completeness, visual
fidelity, source authenticity or a document's legal/financial effect. A fully
read invoice missing its due date remains complete text extraction; the field
layer must abstain. This module contains no field inference and does not
implement all twelve registered document-class extractors.

## Bounds and statuses

| Limit | Default | Native operational ceiling |
| --- | ---: | ---: |
| Input bytes | 16,777,216 | 16,777,216 |
| Retained text UTF-8 bytes across pages | 150,000 | 512,000 |
| Pages | 5 | 100 |
| Characters per retained page | 20,000 | 512,000 |
| Uncompressed DOCX main XML bytes | 2,000,000 | 2,000,000 |

The hard input limit rejects intake before an unbounded read or archive write.
A lower declared input limit returns `error/INPUT_LIMIT_EXCEEDED` after the
bounded original is identified. Text-byte and character limits both apply;
`max_text_bytes=150000` alone does not increase the 20,000-character default.
For PDF/DOCX, `processed_bytes` measures the source buffer submitted/read by the
reader, while `complete`, `truncated`, page counts and notes describe the text
actually covered. It must not be read as an OCR or visual-coverage percentage.

PDF/DOCX workers use a ten-second parent timeout, ten-second OS CPU-time limit
and 512 MiB address-space limit. Resource-limit setup must succeed; unavailable
confinement fails explicitly. A native worker is a bounded ordinary process,
not an AI agent or a complete malicious-document sandbox. Constrained inputs,
optional parser updates and production containment still require release review.

`partial` retains usable source text with a coverage explanation. `needs_ocr`
returns no claimed readable text. `unsupported` returns no pages. `error`
distinguishes `INVALID_UTF8`, `MALFORMED_DOCX`, `MALFORMED_PDF`,
`DEPENDENCY_MISSING`, `ENCRYPTED_PDF`, `PROCESSING_TIMEOUT`, resource/memory
failures and input-size failures. Safe error messages omit document content.

## Runtime and provider boundary

The implementation is ordinary Python and reports `method=native`,
`backend=cpu`, with null provider/model/API/raw-response fields. CPU execution is
appropriate for bounded file I/O, hashing, XML/PDF traversal and short string
operations. There is no parallel numerical workload that would justify CUDA
transfers in this increment, and no CUDA benchmark is claimed. Later batched
OCR/model work can use the separate measured NVIDIA adapter. R analysis remains
a separate typed validation consumer, not a prerequisite for native intake.

TXT/MD/CSV use the Python standard library. DOCX adds standard-library ZIP/XML
parsing. Native PDF declares the optional exact pin `pypdf==6.21.4` in
[requirements-docai.txt](../../requirements-docai.txt); the actual parser version
is recorded in each successful PDF parser load. The observed verification
runtime was Python 3.12.14 on Linux. Package pinning does not imply vulnerability
certification or support across other runtime versions.

Run the [native checks](test_docai_native.md) and the application/corpus checks
before promoting the increment. No provider connection, model download,
production deployment or organizational data migration is established by a
successful native run.
