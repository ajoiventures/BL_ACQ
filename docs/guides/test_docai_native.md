# Verify native source identity and coverage

[test_docai_native.py](../../tests/test_docai_native.py) exercises real temporary
archive folders, SQLite receipts and bounded parser subprocesses. Run from the
repository root:

```bash
python -m unittest tests.test_docai_native -v
```

Install the optional [PDF dependency](../../requirements-docai.txt) to execute
the PDF coverage cases. Those cases skip explicitly without pypdf. The missing
dependency check always launches an isolated Python interpreter with site
packages disabled, proving the unavailable-dependency result without modifying
the active environment.

## Meaningful failure cases

The tests change the original after snapshot creation and verify that the
archived bytes/hash still describe the captured original. They replay exact
duplicates, preserve historical receipt rows and timestamps, recover a missing
receipt after an interruption, and reject both archive-content and receipt-hash
conflicts without overwriting them.

Route traversal and symlink tests exercise source, root, route folder, archived
target and database paths. A long Unicode filename retains its suffix within
filesystem byte limits. A sparse source exceeding 16 MiB is rejected before it
can acquire a receipt. These are local filesystem checks, not authentication or
hostile same-UID race tests.

Text checks verify exact UTF-8/LF retention and page hashes, truncation at
multibyte boundaries, independent character limits, invalid UTF-8 abstention,
empty files, unsupported formats, declared input bounds and source-identity
mismatches. DOCX checks cover body text, unexamined extra parts, malformed ZIP
or XML, DTD/entity rejection and XML-size limits.

PDF checks cover malformed structure, blank pages, physical page budgets,
native text and an image-only synthetic scan. A constructed PDF with both
native invoice text and an embedded image must be partial, with an explicit
unexamined-XObject coverage note. Timeouts and bad worker exits retain distinct
structured errors. Signature-only image handling cannot assert decoded image
validity or complete coverage.

The independently authored [synthetic corpus](../../tests/fixtures/docai/manifest.json)
adds declared native-reference and held-out application evaluation. Its golden
fields are not created by this parser. Passing these native tests alone does
not certify arbitrary PDFs, all registered document classes, OCR, review
authority, financial correctness, production safety or household-scale capacity.
See [the extraction mechanics](document_native.md) and
[filing history contract](../../filing/README.md) for their exact boundaries.
