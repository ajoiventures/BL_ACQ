# Local Doc AI application

[Source](../../pilot/document_application.py) · [CLI guide](run_docai.md)

This is the first working local document increment. It combines the preserved
filing interface, the native parser, neutral document contracts and the review
engine. The builder swarm supplies development work and review outside this
runtime. No model provider or product agent is loaded.

## Reconstruct one document's mechanics

1. `DocumentApplication.ingest` calls `filing.file_document`. The original bytes
   are retained and a compatible four-field filing receipt is returned.
2. The application hashes the archived original. A stable context/content/class
   identity identifies this first source version. A repeated intake returns the
   existing run and reviews instead of recreating them.
3. `extract_document` records real native parsing, limits, pages, source hash,
   applied configuration, coverage and structured errors. A scan needs OCR;
   partial extraction remains partial.
4. `invoice_candidates` proposes the six explicitly supported invoice fields.
   The engine owns all parsing and monetary conversion rules. Proposed fields
   contain exact source spans and no acceptance decision.
5. `DocumentVault` stores the bundle atomically. The application's inspection
   result exposes source identity, original receipt, extracted pages, candidates,
   review history, revision, accepted fields and export holds.
6. Review supplies an actor label, decision, reason, unique request ID and the
   inspected revision. Stale writes or changed request replay fail. A manual
   correction is a new cited candidate and needs another actor label to review.
7. Export rechecks original integrity and current review state, then produces
   `br.docai-accepted.v1`. It retains source status, source spans, referenced extraction records, reviews and
   explicit `execution_authority: none`.

For the bundled synthetic invoice, the six typed values are:

| Field | Value |
| --- | --- |
| vendor | Example Mechanical Services |
| invoice_number | SYN-INV-001 |
| invoice_date | 2026-11-20 |
| due_date | 2026-12-15 |
| total_cents | 125000 |
| currency | USD |

No field is accepted during normal intake. `demo` is an explicitly automated
synthetic demonstration that exercises review transitions; it does not claim a
person reviewed a real invoice. `source_status: synthetic` survives export.

## Current scope and controls

The app is synchronous and single-user. Use a private runtime directory outside
the source tree. Contexts receive separate archive/database directories; the
vault also scopes every query. Actor labels and context arguments remain trusted
local inputs, not login or network authorization. Authentication, ACLs,
revocation and retention belong to later service work. Do not expose this CLI
directly as an unauthenticated web endpoint.

Native TXT/Markdown/CSV/DOCX/PDF text extraction and structured failures are
separate from field grammar support. The twelve class contracts are registered;
only the narrow invoice field grammar and six-field accepted-export policy are
implemented. Unknown classes can archive and extract but cannot propose or
export accepted fields through this policy.

The current CLI registers independent source versions as version 1. The vault
supports validated successor records and protects current exports from stale
predecessors; a complete user-facing version-family/reprocess workflow remains
future work. Repeating intake with a different parser limit preserves the
original run; it is not a reprocessing command.

The engine rejects changed or missing originals at review/export. The local OS
owner can still alter files or the database. There is no immutable object-store,
malware-sandbox or hostile multiuser filesystem claim. New directories request
mode 0700; existing directory ownership/permissions are the operator's boundary.

Durable work registration, leases, cancellation, retries and an outbox are still
BR-DOC-006. This successful synchronous path is partial evidence for BR-DOC-008
and Gate A, not completion of their broader service/authority/recovery criteria.

The provider contract already has honest provider/model/API/run metadata,
coverage and raw-response references. NVIDIA Parse is the selected future
adapter target in `config/docai-provider-target.json`; no selected service client,
live endpoint, credential, model download or invocation is established. R and
CUDA remain separate measured extension tracks. CPU work here is bounded file
I/O, exact parsing, hashing and SQLite transactions.
