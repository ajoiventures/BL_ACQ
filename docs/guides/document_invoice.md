# Native invoice field engine

[Source](../../pilot/document_invoice.py) · [Contract guide](document_contracts.md)

`invoice_candidates(document, extraction)` implements one deterministic grammar
for `MEP_INVOICE`. It requires a complete native extraction and recognizes the
exact labels `Vendor:`, `Invoice:`, `Invoice date:`, `Due date:`, `Currency:` and
`Total due:`. CSV cell/table interpretation, arbitrary layout, synonyms, OCR and
general semantic invoice understanding are not implemented here.

The engine first counts matching label mentions, including qualified or revised
labels. Repeated mentions cause field abstention. It then takes one exact value
slice, records its Unicode code-point offsets and page-text SHA-256, and validates
the typed candidate against its document and extraction run. This conservative
lexical ambiguity check does not detect every possible contradiction.

Dates require canonical ISO `YYYY-MM-DD`. Currency must be explicit uppercase
three-letter text. Amounts require a nonnegative ordinary decimal with exactly
two fractional digits and valid optional thousands grouping. `Decimal` converts
the amount to signed-64-bit-range integer cents without rounding. Unsupported
numeric forms and overflow abstain. There is no assumed currency or probability
of correctness. The resulting method is `native`, confidence is null, and every
candidate remains pending review.

To understand the operation, inspect `tests/fixtures/docai/invoice_native.txt`:
`Total due: 1,250.00` yields integer `125000`, unit `cents`, currency `USD`, and
the exact quote `1,250.00`. Inspect the corresponding candidate span and its
extraction page. The contract proves exact citation and type binding; a reviewer
must still verify that the normalized value is supported by the quotation.

CPU execution is intentional: this bounded grammar is I/O, strings and exact
scalar validation. No CUDA work or speedup is claimed. Later page inference and
large numerical/evaluation batches have separate profiling and parity gates.

Verification: `python -m unittest tests.test_docai_application` plus
`python -m unittest tests.test_docai_evaluation`. The development ambiguity case
is a regression control, not independent evidence of general invoice accuracy.
