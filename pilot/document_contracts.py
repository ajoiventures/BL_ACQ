"""Strict, document-neutral Doc AI records, with no provider or storage effects.

All public validators return detached JSON-safe dictionaries. Source text stays
unchanged; spans use Unicode code-point offsets into a SHA-256-bound text page.
These CPU validation rules do not authenticate actors, establish source truth,
execute a model, or replace the existing acquisition evidence schema.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import re
from urllib.parse import parse_qsl, urlsplit


SCHEMA_VERSION = "br.docai.v1"
MAX_RECORD_BYTES = 4 * 1024 * 1024
MAX_INTEGER = (1 << 63) - 1
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FIELD = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
DOMAINS = frozenset({"commercial", "family", "civic"})
METHODS = frozenset({"native", "manual", "provider"})
EXTRACTION_STATUSES = frozenset({"complete", "partial", "needs_ocr", "unsupported", "error", "disabled"})
VALUE_TYPES = frozenset({"text", "date", "integer", "money_cents", "basis_points", "decimal", "boolean"})
DEFAULT_LIMITS = {"max_input_bytes": 16 * 1024 * 1024, "max_text_bytes": 150000,
                  "max_pages": 5, "max_chars_per_page": 20000, "max_xml_bytes": 2000000}

# A registered field contract is not an implemented extractor. Only the narrow
# declared invoice grammar in document_invoice has native field extraction.
CLASS_FIELDS = {
    "LEASE": {"tenant": "text", "landlord": "text", "property_reference": "text",
              "start_date": "date", "end_date": "date", "monthly_rent_cents": "money_cents",
              "security_deposit_cents": "money_cents", "currency": "text", "renewal_notice_days": "integer"},
    "TITLE_OE": {"owner": "text", "parcel_reference": "text", "effective_date": "date", "liens_count": "integer"},
    "NOTE_COLLATERAL": {"borrower": "text", "lender": "text", "principal_cents": "money_cents",
                        "currency": "text", "interest_rate_basis_points": "basis_points", "maturity_date": "date", "collateral_reference": "text"},
    "NOTE_TAPE_ROLL": {"loan_reference": "text", "borrower": "text", "unpaid_balance_cents": "money_cents",
                       "currency": "text", "next_due_date": "date", "status": "text"},
    "ZONING_COMP_PLAN": {"jurisdiction": "text", "parcel_reference": "text", "zoning_district": "text",
                         "future_land_use": "text", "effective_date": "date"},
    "SURVEY_PLAT": {"survey_reference": "text", "parcel_reference": "text", "survey_date": "date",
                    "surveyor": "text", "area_square_feet": "decimal"},
    "PERMIT_CODE_LIEN": {"jurisdiction": "text", "permit_reference": "text", "parcel_reference": "text",
                         "status": "text", "issued_date": "date", "amount_cents": "money_cents", "currency": "text"},
    "INSURANCE_COI": {"insured": "text", "insurer": "text", "policy_number": "text",
                      "effective_date": "date", "expiration_date": "date", "coverage_cents": "money_cents", "currency": "text"},
    "MEP_INVOICE": {"vendor": "text", "invoice_number": "text", "invoice_date": "date", "due_date": "date",
                    "subtotal_cents": "money_cents", "tax_cents": "money_cents", "total_cents": "money_cents", "currency": "text"},
    "TAX_TRIM_TDT": {"taxpayer": "text", "parcel_reference": "text", "tax_year": "integer",
                     "assessed_value_cents": "money_cents", "tax_due_cents": "money_cents", "currency": "text", "due_date": "date"},
    "VALUATION_OM": {"property_reference": "text", "valuation_date": "date", "asking_price_cents": "money_cents",
                     "noi_cents": "money_cents", "currency": "text", "capitalization_rate_basis_points": "basis_points"},
    "PROBATE_CLOSING": {"estate": "text", "case_reference": "text", "property_reference": "text",
                        "closing_date": "date", "gross_proceeds_cents": "money_cents", "net_proceeds_cents": "money_cents", "currency": "text"},
}
DOCUMENT_CLASSES = frozenset(CLASS_FIELDS) | {"UNKNOWN"}


def _json_value(value, depth=0):
    if depth > 16:
        raise ValueError("Record nesting exceeds contract limit")
    if value is None or type(value) in {str, bool, int}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Non-finite numbers are not JSON contract values")
        return
    if type(value) is list:
        for item in value:
            _json_value(item, depth + 1)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item, depth + 1)
        return
    raise ValueError("Contract values must use exact JSON object/array/scalar types")


def canonical_json(record):
    """Deterministic finite JSON; no type coercion of tuples, Decimal or objects."""
    _json_value(record)
    try:
        serialized = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        if len(serialized.encode("utf-8")) > MAX_RECORD_BYTES:
            raise ValueError("Record exceeds serialized contract size limit")
        return serialized
    except (TypeError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ValueError("Record is not valid bounded UTF-8 JSON") from exc


def sha256_text(text):
    if type(text) is not str:
        raise ValueError("Text must be a string")
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeError as exc:
        raise ValueError("Text must encode as UTF-8") from exc


def _object(record, required, optional=(), name="record"):
    if type(record) is not dict or set(record) - set(required) - set(optional) or set(required) - set(record):
        raise ValueError(f"{name} has unknown or missing fields")
    return json.loads(canonical_json(record))


def _version(record):
    if record["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported Doc AI schema_version")


def _text(value, name, maximum=2000, empty=False):
    if type(value) is not str or len(value) > maximum or (not empty and not value.strip()):
        raise ValueError(f"{name} must be bounded {'possibly empty ' if empty else 'nonempty '}text")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError(f"{name} must encode as UTF-8") from exc
    return value


def _id(value, name):
    if type(value) is not str or not _ID.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _hash(value, name):
    if type(value) is not str or not _SHA.fullmatch(value):
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _int(value, name, low=0, high=MAX_INTEGER):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an exact integer in [{low}, {high}]")
    return value


def _choice(value, choices, name):
    if type(value) is not str or value not in choices:
        raise ValueError(f"Unknown {name}")
    return value


def _boolean(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} must be a Boolean")
    return value


def _date(value):
    if type(value) is not str:
        raise ValueError("Date must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("Date must be canonical YYYY-MM-DD")
    return value


def _utc(value, name):
    if type(value) is not str or not _UTC.fullmatch(value):
        raise ValueError(f"{name} must be an explicit UTC ISO timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"Invalid {name}") from exc
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _uri(value, name):
    _text(value, name, 2048)
    try:
        parsed = urlsplit(value)
        query_keys = {key.casefold() for key, _ in parse_qsl(parsed.query)}
    except ValueError as exc:
        raise ValueError(f"Invalid {name}") from exc
    secrets = {"token", "access_token", "api_key", "key", "signature", "sig", "x-amz-signature"}
    if any(char.isspace() or ord(char) < 32 for char in value) or parsed.scheme not in {"http", "https", "fixture", "local"} or not parsed.netloc or parsed.username or parsed.password or query_keys & secrets:
        raise ValueError(f"{name} must be a credential-free HTTP(S), fixture or local reference")
    return value


def validate_context(record):
    """Require tenant, purpose/domain and subject independently of financial deals."""
    r = _object(record, {"tenant_id", "domain", "subject_id"}, {"case_id"}, "context")
    _id(r["tenant_id"], "tenant_id")
    _id(r["subject_id"], "subject_id")
    _choice(r["domain"], DOMAINS, "domain")
    r.setdefault("case_id", None)
    if r["case_id"] is not None:
        _id(r["case_id"], "case_id")
    return r


def validate_document(record):
    required = {"schema_version", "document_id", "context", "version", "source_uri", "title", "media_type",
                "document_class", "content_sha256", "byte_count", "received_at", "source_status"}
    r = _object(record, required, {"predecessor_document_id", "asset_links"}, "document")
    _version(r)
    _id(r["document_id"], "document_id")
    r["context"] = validate_context(r["context"])
    _int(r["version"], "version", 1, 1000000)
    _uri(r["source_uri"], "source_uri")
    _text(r["title"], "title", 500)
    if type(r["media_type"]) is not str or not re.fullmatch(r"[a-z0-9][a-z0-9.+-]*/[a-z0-9][a-z0-9.+-]*", r["media_type"]):
        raise ValueError("media_type must be a lowercase MIME type without parameters")
    _choice(r["document_class"], DOCUMENT_CLASSES, "document_class")
    _hash(r["content_sha256"], "content_sha256")
    _int(r["byte_count"], "byte_count", 0)
    r["received_at"] = _utc(r["received_at"], "received_at")
    _choice(r["source_status"], {"synthetic", "supplied"}, "source_status")
    r.setdefault("predecessor_document_id", None)
    if r["predecessor_document_id"] is not None:
        _id(r["predecessor_document_id"], "predecessor_document_id")
        if r["predecessor_document_id"] == r["document_id"] or r["version"] == 1:
            raise ValueError("A predecessor must be another document ID at a later version")
    elif r["version"] > 1:
        raise ValueError("A later document version requires an explicit predecessor")
    r.setdefault("asset_links", [])
    if type(r["asset_links"]) is not list or len(r["asset_links"]) > 100:
        raise ValueError("asset_links must be a bounded array")
    links = []
    for link in r["asset_links"]:
        link = _object(link, {"kind", "id"}, name="asset_link")
        _choice(link["kind"], {"parcel", "property", "account", "organization", "work_item"}, "asset kind")
        _id(link["id"], "asset link ID")
        if link in links:
            raise ValueError("Duplicate asset link")
        links.append(link)
    r["asset_links"] = links
    return r


def validate_limits(record):
    r = _object(record, set(DEFAULT_LIMITS), name="limits")
    for key, value in r.items():
        _int(value, key, 1, 1024 * 1024 * 1024 if key != "max_pages" else 1000)
    return r


def _same_identity(r, document):
    _id(r["document_id"], "document_id")
    _int(r["document_version"], "document_version", 1, 1000000)
    r["context"] = validate_context(r["context"])
    if (r["document_id"], r["document_version"], r["context"]) != (document["document_id"], document["version"], document["context"]):
        raise ValueError("Record identity, version or context does not match document")


def validate_extraction(record, document):
    document = validate_document(document)
    required = {"schema_version", "run_id", "document_id", "document_version", "context", "source_sha256", "method",
                "processor", "processor_version", "provider", "model", "model_version", "api_version", "configuration_sha256",
                "raw_response", "backend", "started_at", "finished_at", "status", "coverage", "pages", "errors"}
    r = _object(record, required, {"device", "precision"}, "extraction")
    _version(r)
    _same_identity(r, document)
    _id(r["run_id"], "run_id")
    _hash(r["source_sha256"], "source_sha256")
    if r["source_sha256"] != document["content_sha256"]:
        raise ValueError("Extraction source hash does not match document")
    _choice(r["method"], METHODS, "method")
    for key in ("processor", "processor_version"):
        _text(r[key], key, 200)
    _hash(r["configuration_sha256"], "configuration_sha256")
    _choice(r["backend"], {"cpu", "cuda", "remote", "none"}, "backend")
    _choice(r["status"], EXTRACTION_STATUSES, "extraction status")
    r["started_at"] = _utc(r["started_at"], "started_at")
    r["finished_at"] = _utc(r["finished_at"], "finished_at")
    if r["finished_at"] < r["started_at"] or r["started_at"] < document["received_at"]:
        raise ValueError("Extraction timestamps precede intake or run start")
    for key in ("provider", "model", "model_version", "api_version", "device", "precision"):
        r.setdefault(key, None)
        if r[key] is not None:
            _text(r[key], key, 200)
    if r["raw_response"] is not None:
        raw = _object(r["raw_response"], {"source_uri", "sha256"}, name="raw_response")
        _uri(raw["source_uri"], "raw response reference")
        _hash(raw["sha256"], "raw response hash")
        r["raw_response"] = raw
    provider_fields = (r["provider"], r["model"], r["model_version"], r["api_version"])
    if r["method"] != "provider" and (any(v is not None for v in provider_fields) or r["raw_response"] is not None):
        raise ValueError("Native/manual extraction cannot disguise provider provenance")
    if r["method"] == "provider" and r["status"] not in {"disabled", "error"}:
        if any(v is None for v in provider_fields) or r["raw_response"] is None:
            raise ValueError("Provider output requires exact provider/model/API and raw-response provenance")
    if r["backend"] == "cuda" and (r["device"] is None or r["precision"] is None):
        raise ValueError("CUDA execution requires device and precision metadata")

    coverage = _object(r["coverage"], {"input_bytes", "processed_bytes", "total_pages", "processed_pages",
                                      "complete", "truncated", "page_basis", "limits", "notes"}, name="coverage")
    _int(coverage["input_bytes"], "input_bytes")
    if coverage["input_bytes"] != document["byte_count"]:
        raise ValueError("Coverage input byte count must match document")
    if coverage["processed_bytes"] is not None:
        _int(coverage["processed_bytes"], "processed_bytes", 0, coverage["input_bytes"])
    if coverage["total_pages"] is not None:
        _int(coverage["total_pages"], "total_pages", 0, 1000000)
    _int(coverage["processed_pages"], "processed_pages", 0, 1000)
    _boolean(coverage["complete"], "complete")
    _boolean(coverage["truncated"], "truncated")
    _choice(coverage["page_basis"], {"logical", "physical"}, "page_basis")
    coverage["limits"] = validate_limits(coverage["limits"])
    if type(coverage["notes"]) is not list or len(coverage["notes"]) > 100:
        raise ValueError("Coverage notes must be a bounded array")
    for note in coverage["notes"]:
        _text(note, "coverage note", 1000)
    if type(r["pages"]) is not list or len(r["pages"]) > coverage["limits"]["max_pages"]:
        raise ValueError("Pages must be a bounded array within the configured page limit")
    previous = 0
    for page in r["pages"]:
        _object(page, {"page", "text", "text_sha256"}, name="text page")
        _int(page["page"], "page", 1, 1000000)
        if page["page"] <= previous or (coverage["total_pages"] is not None and page["page"] > coverage["total_pages"]):
            raise ValueError("Page numbers must be unique, increasing and within source coverage")
        previous = page["page"]
        _text(page["text"], "page text", coverage["limits"]["max_chars_per_page"], empty=True)
        _hash(page["text_sha256"], "page text hash")
        if sha256_text(page["text"]) != page["text_sha256"]:
            raise ValueError("Page text hash mismatch")
    if coverage["processed_pages"] != len(r["pages"]):
        raise ValueError("Processed page count must equal represented text-page count")
    if sum(len(page["text"].encode("utf-8")) for page in r["pages"]) > coverage["limits"]["max_text_bytes"]:
        raise ValueError("Retained page text exceeds the declared aggregate UTF-8 byte limit")
    if coverage["total_pages"] is not None and coverage["processed_pages"] > coverage["total_pages"]:
        raise ValueError("Processed pages exceed total pages")
    if type(r["errors"]) is not list or len(r["errors"]) > 100:
        raise ValueError("Errors must be a bounded array")
    for error in r["errors"]:
        _object(error, {"code", "message", "page"}, name="processing error")
        _id(error["code"], "error code")
        _text(error["message"], "error message", 1000)
        if error["page"] is not None:
            _int(error["page"], "error page", 1, 1000000)
    if r["status"] == "complete":
        if not coverage["complete"] or coverage["truncated"] or r["errors"] or coverage["processed_bytes"] != coverage["input_bytes"] or coverage["total_pages"] is None or coverage["processed_pages"] != coverage["total_pages"]:
            raise ValueError("Complete extraction requires complete known coverage without truncation or errors")
        if coverage["input_bytes"] > coverage["limits"]["max_input_bytes"]:
            raise ValueError("Complete extraction cannot exceed its declared input-size limit")
    elif coverage["complete"]:
        raise ValueError("Only complete status may assert complete coverage")
    if r["status"] == "partial" and not (coverage["truncated"] or coverage["notes"] or r["errors"]):
        raise ValueError("Partial extraction must explain its missing coverage")
    if r["status"] == "needs_ocr" and any(page["text"].strip() for page in r["pages"]):
        raise ValueError("needs_ocr is reserved for input with no native readable text")
    if r["status"] in {"unsupported", "disabled"} and r["pages"]:
        raise ValueError("Unsupported or disabled processing cannot return extracted pages")
    if r["status"] in {"unsupported", "error", "needs_ocr", "disabled"} and not r["errors"] and not coverage["notes"]:
        raise ValueError("Unavailable processing must have an explicit reason")
    if r["status"] == "disabled" and (r["backend"] != "none" or coverage["processed_bytes"] not in (0, None) or coverage["processed_pages"]):
        raise ValueError("Disabled processing cannot claim execution")
    if r["status"] in {"complete", "partial"} and r["backend"] == "none":
        raise ValueError("Returned extraction output requires an actual backend label")
    r["coverage"] = coverage
    return r


def validate_candidate(record, document, extraction):
    document = validate_document(document)
    extraction = validate_extraction(extraction, document)
    required = {"schema_version", "claim_id", "document_id", "document_version", "run_id", "context", "field",
                "value_type", "value", "unit", "currency", "method", "spans", "confidence", "created_at", "proposed_by"}
    r = _object(record, required, {"supersedes_claim_id"}, "candidate")
    _version(r)
    _same_identity(r, document)
    _id(r["claim_id"], "claim_id")
    _id(r["run_id"], "run_id")
    _id(r["proposed_by"], "proposed_by")
    if r["run_id"] != extraction["run_id"] or extraction["status"] not in {"complete", "partial"}:
        raise ValueError("Candidate must refer to the supplied usable extraction run")
    if type(r["field"]) is not str or not _FIELD.fullmatch(r["field"]):
        raise ValueError("Invalid candidate field name")
    _choice(r["value_type"], VALUE_TYPES, "value_type")
    fields = CLASS_FIELDS.get(document["document_class"])
    if fields is None:
        raise ValueError("UNKNOWN document class remains quarantined until classified")
    if fields.get(r["field"]) != r["value_type"]:
        raise ValueError("Candidate field/type is not registered for this document class")
    _choice(r["method"], METHODS, "candidate method")
    if r["method"] != "manual" and r["method"] != extraction["method"]:
        raise ValueError("Candidate method cannot disguise the extraction method")
    if r["unit"] is not None:
        _text(r["unit"], "unit", 64)
    if r["currency"] is not None and (type(r["currency"]) is not str or not re.fullmatch(r"[A-Z]{3}", r["currency"])):
        raise ValueError("Currency must be an explicit uppercase three-letter code")
    kind, value = r["value_type"], r["value"]
    if kind in {"integer", "money_cents", "basis_points"}:
        _int(value, "value", -MAX_INTEGER, MAX_INTEGER)
    elif kind == "boolean":
        _boolean(value, "value")
    elif kind == "date":
        _date(value)
    elif kind == "decimal":
        if type(value) is not str or len(value) > 100 or not _DECIMAL.fullmatch(value):
            raise ValueError("Decimal value must be a bounded plain decimal string")
        if value.startswith("-") and Decimal(value) == 0:
            raise ValueError("Negative zero is not a canonical decimal value")
        if r["unit"] is None:
            raise ValueError("A decimal measurement requires an explicit unit")
    else:
        _text(value, "value", 4000)
    if kind == "money_cents":
        if r["currency"] is None or r["unit"] != "cents":
            raise ValueError("Money requires integer cents, currency and unit=cents")
    elif r["currency"] is not None:
        raise ValueError("Only money_cents values carry the currency attribute")
    if kind == "basis_points" and r["unit"] != "basis_points":
        raise ValueError("Rates require explicit basis_points units")
    if kind in {"date", "text", "boolean"} and r["unit"] is not None:
        raise ValueError("Text/date/Boolean values have no numeric unit")
    if r["field"] == "currency" and not re.fullmatch(r"[A-Z]{3}", r["value"]):
        raise ValueError("Currency field must be a three-letter uppercase code")
    if r["confidence"] is not None:
        if r["method"] != "provider" or type(r["confidence"]) not in {int, float} or not math.isfinite(r["confidence"]) or not 0 <= r["confidence"] <= 1:
            raise ValueError("Only provider candidates may carry a finite [0,1] provider score")
    r["created_at"] = _utc(r["created_at"], "created_at")
    if r["created_at"] < extraction["finished_at"]:
        raise ValueError("Candidate predates extraction completion")
    r.setdefault("supersedes_claim_id", None)
    if r["supersedes_claim_id"] is not None:
        _id(r["supersedes_claim_id"], "supersedes_claim_id")
        if r["supersedes_claim_id"] == r["claim_id"]:
            raise ValueError("A candidate cannot supersede itself")
    if type(r["spans"]) is not list or not 1 <= len(r["spans"]) <= 16:
        raise ValueError("Candidates require one through sixteen source spans")
    pages = {page["page"]: page for page in extraction["pages"]}
    seen = set()
    for span in r["spans"]:
        _object(span, {"page", "text_sha256", "start", "end", "quote"}, name="source span")
        _int(span["page"], "span page", 1, 1000000)
        page = pages.get(span["page"])
        if page is None:
            raise ValueError("Source span does not belong to an extracted page")
        _hash(span["text_sha256"], "span text hash")
        _int(span["start"], "span start", 0, len(page["text"]))
        _int(span["end"], "span end", span["start"] + 1, len(page["text"]))
        _text(span["quote"], "span quote", 4000)
        if span["text_sha256"] != page["text_sha256"] or page["text"][span["start"]:span["end"]] != span["quote"]:
            raise ValueError("Source span must quote the exact hash-bound text slice")
        key = (span["page"], span["start"], span["end"])
        if key in seen:
            raise ValueError("Duplicate source span")
        seen.add(key)
    return r


def validate_review(record, candidate):
    """Validate review shape/binding; caller must validate the candidate first.

    Storage/application owns identity authentication, authorization, append-only
    persistence, prior-review lookup and independence. Actor text is not proof.
    """
    required = {"schema_version", "review_id", "claim_id", "document_id", "document_version", "run_id",
                "context", "actor", "decision", "reason", "reviewed_at"}
    r = _object(record, required, {"supersedes_review_id"}, "review")
    _version(r)
    if type(candidate) is not dict or candidate.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Review requires a previously validated candidate")
    _object(candidate, {"schema_version", "claim_id", "document_id", "document_version", "run_id", "context", "field",
                        "value_type", "value", "unit", "currency", "method", "spans", "confidence", "created_at", "proposed_by"},
            {"supersedes_claim_id"}, "review target candidate")
    for key in ("review_id", "claim_id", "document_id", "run_id", "actor"):
        _id(r[key], key)
    _int(r["document_version"], "document_version", 1, 1000000)
    r["context"] = validate_context(r["context"])
    for key in ("claim_id", "document_id", "document_version", "run_id", "context"):
        if r[key] != candidate.get(key):
            raise ValueError("Review identity or context does not match candidate")
    _choice(r["decision"], {"accept", "reject"}, "review decision")
    _text(r["reason"], "review reason", 2000)
    r["reviewed_at"] = _utc(r["reviewed_at"], "reviewed_at")
    created = _utc(candidate.get("created_at"), "candidate created_at")
    if r["reviewed_at"] < created:
        raise ValueError("Review predates candidate")
    r.setdefault("supersedes_review_id", None)
    if r["supersedes_review_id"] is not None:
        _id(r["supersedes_review_id"], "supersedes_review_id")
        if r["supersedes_review_id"] == r["review_id"]:
            raise ValueError("A review cannot supersede itself")
    return r
