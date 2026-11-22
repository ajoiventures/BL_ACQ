# Trace a document into a reviewed model input

[document_evidence.py](../../pilot/document_evidence.py) is a deterministic,
standard-library evidence engine. The build-time swarm created this code; the
product does not contain an AI agent, OCR model, network client, or seller action.

## Data flow

1. Open `EvidenceStore(path, actor="named-operator", scope="commercial")`.
2. Call `register_document(metadata, content=bytes)`. The engine calculates
   SHA-256, archives the supplied bytes, and stores immutable version metadata.
   It never fetches `source_uri`. Source dates and document identity are assertions
   supplied by the calling application; hashing does not prove source truth.
3. Add a typed manual or native-JSON claim with `add_claim`. Each claim names its
   deal, document, field, value/type/unit/currency, page, location, raw supporting
   text, entry date, and method. A normalized bounding box is optional. Money is
   integer USD cents. A number of dollars is not silently converted into cents.
4. Record an explicit named decision through `review_claim`. Reviews are
   append-only, accept/reject decisions with dates, expiry, and a reason. The
   connection's actor supplies reviewer identity. Authentication and authority
   checks belong to the application; the engine records the review assertion.
5. Call `project_inputs(deal_id, as_of, required_fields=(...))`. Read the flat
   `values`, the typed `facts` with complete provenance, `states`, and `blockers`.
   Bind only the allowed fields to the financial engine. A `ready` projection
   means the requested evidence checks passed; it is not transaction approval.

The projection includes a digest, scope, business date, `illustrative`, explicit
CPU backend, and `product_ai_enabled=False`. Each `facts[field]` contains
`value`, `value_type`, `unit`, `currency`, and a `provenance` list. Provenance
includes document and claim IDs, content hash, version, page/location, raw text,
method, review ID, reviewer, review date, and synthetic-source status.

## Revision and conflict behavior

Document families start at version 1 and advance one version at a time, naming
the prior document. Dates cannot move backward. A successor effective as of the
analysis date suppresses the prior document. If the new document has no candidate
for a previously used field, `successor_missing_claim` blocks reuse of the old
amount. A new pending claim also blocks reuse. Review the new claim explicitly.

Two current accepted values that disagree block their field. Equal typed values
may combine supporting provenance. Rejecting one conflicting claim appends a
decision and permits the other accepted value to project. A later review is
evaluated only from its declared review date. An expired latest review never
reactivates an earlier acceptance. Expired or policy-stale documents block use.
`max_age_days` is optional and must be specified by the consuming policy.

As-of projection uses declared business dates, including received, effective,
entry, and review dates. Each immutable row additionally records `recorded_at`
in UTC. This pilot is not a complete bitemporal or authenticated document system;
backfilled assertions are not automatically proof of what was known historically.

## Synthetic quote example

[duplex_quote.json](../../data/document_evidence/duplex_quote.json) contains
explicitly synthetic quote revisions of $35,000 and $55,000 for
`BR-DEMO-DUPLEX-001`. `ingest_bundle` atomically imports their source text and
candidate claims. It imports zero reviews. Approving the first claim can produce
the original input before November 22, 2026; the new effective revision blocks
that input on November 22 until the second claim is reviewed. Both source bytes
and review histories remain intact. The application layer decides how a new
base quote changes its scenario assumptions.

## Later AI boundary

`CandidateProvider` describes a candidate-only adapter. `NativeJsonProvider`
accepts a bounded claims object. `DisabledAIProvider` always raises an explicit
error. NVIDIA services can later propose candidates through an adapter contract;
they must not write review decisions, set closing status, or bypass source checks.
Scores for extraction or retrieval are not seller-acceptance probabilities.

## Execution and limitations

SQLite transactions, ordered histories, content hashing, and small typed record
checks remain on CPU. They are metadata and consistency operations; GPU transfer
would add overhead without parallel numerical work. The financial engine can
batch the projected inputs separately on CUDA. No GPU throughput is claimed here.

The local pilot limits each document to 16 MiB and each projected deal to 10,000
documents/claims and 100,000 reviews. Projection obtains a serialized snapshot
with writers. Native bundles carry UTF-8 source text; direct registration accepts
opaque bytes, including PDFs, without reading their contents. File format parsing,
malware scanning, authentication, tenant policy, document OCR and production-scale
object storage are application/deployment responsibilities outside this module.

Run `python -m unittest tests.test_document_evidence` from the repository root.
The [test guide](test_document_evidence.md) describes the meaningful cases.
