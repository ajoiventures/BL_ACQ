# Document vault and review engine

[Source](../../pilot/document_vault.py) · [Application guide](document_application.md)

`DocumentVault` composes the existing `EvidenceStore` connection and transaction
manager. It adds neutral `br_docai_*` tables without modifying the old financial
tables or requiring a fictitious deal ID. The context is tenant, domain, subject
and optional case. Every query and stored request is bound to that context.

## Follow one state transition

`add_bundle` validates the document, extraction and candidates, then stores them
atomically with the filing receipt. All candidates start without a review.
`review` checks the document revision, source version, proposer label and any
prior decision before appending the new decision. `correct` appends a cited
manual candidate; supersession preserves its predecessor and removes that
predecessor from the current accepted projection.

`inspect` derives current accepted fields from immutable records. Pending or
conflicting required fields hold export. A newly proposed correction holds the
old accepted value immediately. `accepted_export` requires all six initial
invoice fields, complete extraction coverage and matching amount/currency.
Exports also contain every referenced extraction run, including parser/version,
configuration hash, actual backend and source text. A source successor holds the older source's current export, review and correction;
history remains inspectable. A successor also advances the predecessor revision,
and version forks are rejected.

Records and idempotency responses have SQLite update/delete prevention triggers.
These are application integrity controls, not tamper-proof storage against the
database owner. Request hashes bind the actor and payload, so an exact retry
returns its original response, while a changed reason, actor or payload fails.
Revision checks prevent a stale operator snapshot from accepting a later state.

## Authority and incomplete work

This first implementation trusts the local OS user and caller-supplied actor
labels. Distinct labels are not authenticated independent people. Service ACLs,
revocation, retention, deletion propagation, multiuser access and complete source
family lifecycle remain BR-DOC-004 work. A provider has no route to write a
review; ordinary trusted code remains capable of calling the review API.

The original file lives under the preserved filing archive. The application
rehashes it before inspection, review and export. SQLite and filesystem changes
are not one distributed transaction: filing may succeed before bundle storage.
The tested retry recovers that local failure. Durable leased jobs and outbox
recovery remain BR-DOC-006. The storage version table rejects unknown versions;
there is no destructive migration of existing financial evidence.

Verification: `python -m unittest tests.test_docai_application` and the existing
`tests.test_document_evidence` regressions. Read the tests to see stale reviews,
payload replay, exact source spans, context isolation, version supersession and
failed-transaction recovery exercised directly.
