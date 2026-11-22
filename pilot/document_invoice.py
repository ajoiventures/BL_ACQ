"""Deterministic invoice label grammar producing unreviewed document claims.

Only the declared exact labels are supported. Unknown layouts, synonyms and
semantic contradictions require review or a later parser, never a guessed value.
"""
from datetime import date
from decimal import Decimal
import re

from pilot.document_contracts import SCHEMA_VERSION, canonical_json, sha256_text, validate_candidate


LABELS = {"vendor": "Vendor", "invoice_number": "Invoice", "invoice_date": "Invoice date",
          "due_date": "Due date", "total_cents": "Total due", "currency": "Currency"}


def invoice_candidates(document, extraction):
    """One exact label per field, strict typed values, no inferred currency."""
    if document["document_class"] != "MEP_INVOICE" or extraction["method"] != "native" or extraction["status"] != "complete":
        return []
    found = {}
    for field, label in LABELS.items():
        pattern = re.compile(r"^" + re.escape(label) + r":[ \t]*(?P<value>[^\r\n]*?)[ \t]*\r?$", re.MULTILINE)
        # A qualified/revised occurrence is an ambiguity signal even when it
        # does not satisfy the supported exact-label grammar. This is a
        # conservative lexical check, not general contradiction detection.
        mentions = re.compile(r"\b" + re.escape(label) + r"[ \t]*:", re.IGNORECASE)
        if sum(len(mentions.findall(page["text"])) for page in extraction["pages"]) != 1:
            continue
        matches = [(page, match) for page in extraction["pages"] for match in pattern.finditer(page["text"])]
        if len(matches) == 1 and matches[0][1].group("value").strip():
            found[field] = matches[0]
    currency = found.get("currency")
    currency = currency[1].group("value") if currency else None
    if currency is not None and not re.fullmatch(r"[A-Z]{3}", currency):
        currency = None
    candidates = []
    for field, (page, match) in found.items():
        quote = match.group("value")
        value, value_type = quote, "text"
        if field in {"invoice_date", "due_date"}:
            try:
                if date.fromisoformat(quote).isoformat() != quote:
                    continue
            except ValueError:
                continue
            value_type = "date"
        elif field == "total_cents":
            if currency is None or not re.fullmatch(r"(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)\.[0-9]{2}", quote):
                continue
            value = int(Decimal(quote.replace(",", "")) * 100)
            if value > (1 << 63) - 1:
                continue
            value_type = "money_cents"
        elif field == "currency" and currency is None:
            continue
        if len(quote) > 4000:
            continue
        span = {"page": page["page"], "text_sha256": page["text_sha256"],
                "start": match.start("value"), "end": match.end("value"), "quote": quote}
        candidate = {"schema_version": SCHEMA_VERSION,
                     "claim_id": "claim-" + sha256_text(canonical_json([extraction["run_id"], field, value, span]))[:40],
                     "document_id": document["document_id"], "document_version": document["version"],
                     "run_id": extraction["run_id"], "context": document["context"], "field": field,
                     "value_type": value_type, "value": value, "unit": "cents" if value_type == "money_cents" else None,
                     "currency": currency if value_type == "money_cents" else None, "method": "native",
                     "spans": [span], "confidence": None, "created_at": extraction["finished_at"],
                     "proposed_by": "native.invoice.labels.v1", "supersedes_claim_id": None}
        candidates.append(validate_candidate(candidate, document, extraction))
    return candidates
