# Read and control the Doc AI record contracts

[document_contracts.py](../../pilot/document_contracts.py) is the deterministic
boundary for the new document product. It validates data and returns detached
Python dictionaries. It does not open a source file, fetch a URL, execute a model,
authenticate an actor or write a review. The record schema version is
`br.docai.v1`.

The [structural JSON Schema](../../schemas/docai/records.schema.json),
[class registry](../../schemas/docai/document-classes.json) and
[validated example bundle](../../schemas/docai/examples.json) make the interface
inspectable. The Python validators additionally enforce relationships that a
single-record JSON Schema cannot establish: matching source hashes and contexts,
chronology, page coverage and exact evidence slices.

## The four records

| Record and entry point | What it establishes | What it does not establish |
| --- | --- | --- |
| `validate_document(record)` | Source identity, declared byte hash/count, class, version, receipt time and document-neutral context | That the bytes at a URI match the declaration, or that the source is true |
| `validate_extraction(record, document)` | A processing run tied to that source/version, truthful-shaped provenance, bounded page text, hashes and explicit coverage | That the processor actually ran as declared, or that every relevant fact was extracted |
| `validate_candidate(record, document, extraction)` | A typed field proposal tied to exact text slices from that run | Correct interpretation of those slices, approval, or a probability of a real-world outcome |
| `validate_review(record, candidate)` | An accept/reject event tied to one candidate and its source/run identity | Authentication, reviewer authority or persistence of append-only history |

Every validator returns a copy and raises `ValueError` for invalid input. No
validator silently changes a type, ignores an unknown field, or upgrades an
unsupported version. Callers retain the validated result; they must not mutate
it after inserting it into immutable storage.

## Trace the mechanics in order

Start at `validate_context`, then read the four public validators in their source
order. The helpers above them implement exact scalar types, bounded JSON,
identifiers, SHA-256, dates and UTC. `CLASS_FIELDS` supplies the explicit field
contracts; `DOCUMENT_CLASSES` contains those twelve names plus `UNKNOWN`.

The context is `{tenant_id, domain, subject_id, case_id}`. Domain is exactly
`commercial`, `family` or `civic`. `case_id` may be omitted and normalizes to
`None`. The other three identifiers are required. A family service invoice can
therefore belong to a household subject without creating an acquisition deal.
Context travels unchanged from document to extraction, candidate and review.
Matching text IDs are a consistency boundary; the application must still enforce
who can access that tenant and domain.

A `document_id` identifies a particular source version. Version one has no
predecessor. A later version needs a different `document_id` and an explicit
`predecessor_document_id`. The storage layer must check that the predecessor
exists and belongs to the same authorized history. Optional `asset_links`
associate a source with known parcels, properties, accounts, organizations or
work items; this module does not create those assets.

Document metadata preserves the source URI, title, MIME type, raw-byte hash,
byte count, UTC receipt time and `synthetic` or `supplied` source status. The URI
must use HTTP(S), `fixture://` or `local://`, contain no whitespace or userinfo,
and avoid credential query parameters recognized by the validator. A URI is a
reference, not an instruction to fetch. The intake/storage code must hash the
actual bytes and compare them with the declared metadata. An empty source can
be registered with byte count zero so its processing failure remains visible.

## Time, hashing and offsets

Input timestamps use an explicit UTC `Z` suffix, with seconds and optionally
one through six fractional digits. The returned form has six fractional digits,
for example `2026-11-22T12:00:00.000000Z`. Convert an aware UTC datetime with
`.isoformat().replace("+00:00", "Z")` before validation. Dates are exact
`YYYY-MM-DD` calendar dates. Extraction cannot precede intake, a candidate cannot
precede its extraction completion, and a review cannot precede its candidate.

There are three different measurements:

| Measurement | Meaning |
| --- | --- |
| `content_sha256` and `byte_count` | Hash and size of the original source bytes |
| `pages[].text_sha256` | Hash of that page's exact UTF-8 encoded extracted text |
| `spans[].start` and `end` | Zero-based Unicode code-point offsets in the extracted page; end is exclusive |

Do not normalize whitespace, line endings or Unicode after hashing page text.
If a transformation is needed, preserve it as a distinct processing result with
its own configuration, hashes and run identity. An emoji is one Python string
code point and several UTF-8 bytes; byte offsets cannot substitute for string
slice offsets.

```python
from pilot.document_contracts import sha256_text

text = "🏠 Total: USD 125.00\n"
start = text.index("125.00")
span = {
    "page": 1,
    "text_sha256": sha256_text(text),
    "start": start,
    "end": start + len("125.00"),
    "quote": "125.00",
}
assert text[span["start"]:span["end"]] == span["quote"]
```

The validator checks every candidate's one through sixteen spans against the
supplied extraction. A valid quote proves where the proposed value came from.
It does not prove that a parser interpreted the amount, date or party correctly;
the parser's tests and the review workflow address that separate question.

## Coverage is explicit

An extraction records its method, processor/version, configuration hash,
backend, timestamps, pages, errors and coverage. All five limit keys are required:

| Limit | Default | Meaning |
| --- | ---: | --- |
| `max_input_bytes` | 16,777,216 | Native input-size budget |
| `max_text_bytes` | 150,000 | Aggregate retained UTF-8 page-text budget |
| `max_pages` | 5 | Retained page budget |
| `max_chars_per_page` | 20,000 | Code-point budget per retained page |
| `max_xml_bytes` | 2,000,000 | XML expansion/read budget for relevant readers |

The limits bound a processing attempt; they are not a claim that every file of
that size is supported. `processed_bytes` and `total_pages` can be `None` when
unknown. `page_basis` distinguishes logical text pages from physical PDF pages.
The page count must equal the represented page array, and retained text cannot
exceed either the page-character or aggregate UTF-8 budget.

| Status | Contract interpretation |
| --- | --- |
| `complete` | Known full byte/page coverage, no truncation or errors, and an actual backend label |
| `partial` | Usable retained text with an explicit truncation, note or error explaining missing coverage |
| `needs_ocr` | No readable native text; the current result must not invent text for an image |
| `unsupported` | Reader cannot handle this input; no extracted pages |
| `error` | Processing failed, with a retained reason |
| `disabled` | No processing execution; backend `none`, no pages, zero or unknown processed bytes |

The generic candidate contract allows exact spans from a partial extraction so a
separate manual workflow can review a known slice. The first native invoice
application deliberately has a stricter rule: automatic proposals require a
complete, unambiguous supported profile. Full text coverage alone does not mean
all six required invoice fields are present.

## Typed values and model metadata

Money uses exact Python integers in cents, `unit="cents"` and an explicit
three-letter uppercase currency. `12500` means 125.00 in that currency. Floats,
Booleans and the string `"12500"` are rejected for `money_cents`. Integer values
are bounded to `[-(2**63 - 1), 2**63 - 1]`. Basis points have an explicit
`basis_points` unit. Measured decimals use bounded plain decimal strings and a
unit; exponents, nonfinite values and negative zero are rejected. Text, dates
and Booleans have no numeric unit. A `currency` field is text such as `"USD"`;
its separate currency attribute is `None`.

`canonical_json` uses sorted keys, compact separators and UTF-8-preserving finite
JSON, with a four-MiB serialized record bound and a nesting bound. It is this
module's deterministic Python encoding, not a claim of compliance with an
external canonical-JSON standard. A JavaScript or R client must preserve integers
above `2**53` exactly; a later adapter may use a documented decimal-string
exchange without changing this runtime contract. No R execution or CUDA
acceleration is implemented here. These small provenance and validation steps
run on the CPU.

Extraction methods are `native`, `manual` or `provider`. Native/manual runs have
null provider, model, model version, API version and raw-response metadata.
Usable provider output requires those identifiers and a raw-response
`{source_uri, sha256}` reference. Disabled or failed provider attempts can retain
null metadata when no such output exists. The optional `device` and `precision`
fields are mandatory if a record declares a CUDA backend. These declarations
describe a future adapter; the contracts neither load CUDA nor establish a
provider connection.

A native/provider candidate must retain its extraction method. A manual
interpretation may cite an extraction, but the provider run identity remains
present. Only provider candidates can carry a finite `confidence` score between
zero and one. That score is neither acceptance nor a calibrated event
probability. Unknown properties such as `accepted`, `review` or provider-injected
decisions are rejected. No scalar field can bypass a separate review event.

## Review and correction responsibilities

A review contains an actor identifier, `accept` or `reject`, a nonempty reason,
UTC timestamp and exact candidate/document/version/run/context identity. It
cannot change the candidate's value. Correcting a value creates a new candidate
with `supersedes_claim_id`; changing a decision creates a new review with
`supersedes_review_id`. The shape validator rejects self-supersession.

The application and vault must authenticate the actor, authorize the context,
require any independent reviewer policy, verify that superseded IDs exist and
belong to the same history, and atomically enforce the expected current head.
The validator has no database or session and cannot do those things. In
particular, an arbitrary actor string is not proof of identity, and a structurally
valid review dictionary is not an approval until the authorized workflow accepts
and stores it. Pass a fully validated candidate to `validate_review`.

## Class scope and compatibility

The registry declares field contracts for `LEASE`, `TITLE_OE`,
`NOTE_COLLATERAL`, `NOTE_TAPE_ROLL`, `ZONING_COMP_PLAN`, `SURVEY_PLAT`,
`PERMIT_CODE_LIEN`, `INSURANCE_COI`, `MEP_INVOICE`, `TAX_TRIM_TDT`,
`VALUATION_OM` and `PROBATE_CLOSING`. `UNKNOWN` documents can register and
extract but remain held from candidate creation until explicitly classified.
Declared class fields are not evidence of twelve implemented parsers. This
increment's initial native field profile in
[document_invoice.py](../../pilot/document_invoice.py) is `native.invoice.labels.v1`: vendor,
invoice number, invoice date, due date, total cents and currency for a narrow
MEP invoice grammar. Parser coverage and extraction accuracy are measured
separately by the synthetic corpus.

The existing [financial evidence engine](../../pilot/document_evidence.py) and
its acquisition-specific `1.0` records retain their existing APIs. This module
does not migrate them or automatically translate one schema into the other. A
future explicit adapter must receive an authorized tenant/domain/subject/case
mapping, preserve source/version/run/claim/review links, convert units exactly,
and reject or hold unknown identities. It must not fabricate a deal identifier
for a household or civic document, discard a provider origin, or infer that an
old value was accepted merely because it exists. Export to an acquisition model
requires a deliberate, auditable mapping at that application's boundary.

## Try the complete example without a connection

Run from the repository root:

```bash
python - <<'PY'
import json
from pathlib import Path
from pilot.document_contracts import (
    validate_document, validate_extraction, validate_candidate, validate_review,
)

bundle = json.loads(Path("schemas/docai/examples.json").read_text())
document = validate_document(bundle["document"])
extraction = validate_extraction(bundle["extraction"], document)
candidate = validate_candidate(bundle["candidate"], document, extraction)
review = validate_review(bundle["review"], candidate)
print(document["context"], candidate["value"], review["decision"])
PY
```

This validates a synthetic family service invoice and one 12,500-cent claim. It
does not write an acceptance into a vault. Continue with the
[adverse-case test guide](test_docai_contracts.md) to see which changes fail and
why.
