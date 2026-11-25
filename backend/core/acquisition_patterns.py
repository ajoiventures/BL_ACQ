"""Deterministic pattern screening; no legal, financial or send authorization.

CPU reference over supplied evidence projections. Authentication/acceptance remain
with the existing evidence and Academy services. This module never accepts facts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
import sqlite3
from typing import Any

VERSION = "acquisition-patterns/1"
RULE_SCHEMA_VERSION = 1
FIELD_TYPES = {
    "reviewed_research_unit_count": ("number", "dwelling_unit"),
    "contiguous_upland_acres": ("number", "acre"),
    "lot_coverage_ratio": ("number", "ratio"),
    "hotel_distance_miles": ("number", "mile"),
    "annual_cash_after_reserves_usd": ("number", "USD"),
    "active_hotel_license_count": ("number", "count"),
    "owner_name_match_count": ("number", "count"),
    "entity_status": ("string", "category"),
    "legal_access_confirmed": ("boolean", "boolean"),
    "utility_capacity_confirmed": ("boolean", "boolean"),
    "title_authority_confirmed": ("boolean", "boolean"),
    "zoning_use_confirmed": ("boolean", "boolean"),
    "source_identity_reconciled": ("boolean", "boolean"),
    "flood_overlay_present": ("boolean", "boolean"),
    "wetlands_overlay_present": ("boolean", "boolean"),
    "loan_balloon_present": ("boolean", "boolean"),
    "packet_version_changed": ("boolean", "boolean"),
}
EVIDENCE_BINDING_KEYS = {"subject_id", "domain", "denominator", "geography_revision", "source_revision_sha256"}
OPS = {"eq", "ne", "lt", "lte", "gt", "gte"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _scalar(value: Any, kind: str) -> Any:
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise ValueError("Expected a finite number")
        try:
            n = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError("Invalid number") from exc
        if not n.is_finite():
            raise ValueError("Expected a finite number")
        return n
    if kind == "boolean" and type(value) is not bool:
        raise ValueError("Expected boolean")
    if kind == "string" and not isinstance(value, str):
        raise ValueError("Expected string")
    return value


def validate_predicate(node: dict, depth: int = 0, _budget: list[int] | None = None) -> None:
    _budget = [1024] if _budget is None else _budget
    _budget[0] -= 1
    if _budget[0] < 0:
        raise ValueError("Predicate node limit")
    if not isinstance(node, dict) or depth > 12:
        raise ValueError("Invalid predicate or nesting limit")
    groups = set(node) & {"all", "any", "not"}
    if groups:
        if len(node) != 1 or len(groups) != 1:
            raise ValueError("One group operator required")
        op = next(iter(groups))
        children = [node[op]] if op == "not" else node[op]
        if not isinstance(children, list) or not 1 <= len(children) <= 64:
            raise ValueError("Invalid predicate group")
        for child in children:
            validate_predicate(child, depth + 1, _budget)
        return
    if set(node) != {"field", "op", "value", "unit"}:
        raise ValueError("Invalid leaf keys")
    if node["field"] not in FIELD_TYPES or node["op"] not in OPS:
        raise ValueError("Unsupported field or operator")
    kind, unit = FIELD_TYPES[node["field"]]
    if node["unit"] != unit:
        raise ValueError("Predicate unit mismatch")
    if kind != "number" and node["op"] not in {"eq", "ne"}:
        raise ValueError("Ordering requires a numeric field")
    _scalar(node["value"], kind)


@dataclass(frozen=True)
class Evaluation:
    value: bool | None
    reasons: tuple[str, ...] = ()


def _evaluate(node: dict, facts: dict, as_of: date, bindings: dict) -> Evaluation:
    if "not" in node:
        result = _evaluate(node["not"], facts, as_of, bindings)
        return Evaluation(None if result.value is None else not result.value, result.reasons)
    for group in ("all", "any"):
        if group in node:
            children = [_evaluate(c, facts, as_of, bindings) for c in node[group]]
            values = [c.value for c in children]
            if group == "all":
                result = False if False in values else None if None in values else True
            else:
                result = True if True in values else None if None in values else False
            return Evaluation(result, tuple(dict.fromkeys(r for c in children for r in c.reasons)))
    field = node["field"]
    fact = facts.get(field)
    if not isinstance(fact, dict) or fact.get("value") is None:
        return Evaluation(None, (field + ":missing",))
    if fact.get("review_status") != "ACCEPTED" or not fact.get("evidence_id"):
        return Evaluation(None, (field + ":unaccepted_or_unsourced",))
    if field in bindings and fact.get("binding") != bindings[field]:
        return Evaluation(None, (field + ":evidence_binding_mismatch",))
    if "available_from" in fact:
        try:
            available_from = date.fromisoformat(fact["available_from"])
        except (TypeError, ValueError):
            return Evaluation(None, (field + ":invalid_availability_date",))
        if available_from > as_of:
            return Evaluation(None, (field + ":not_yet_available",))
    if not fact.get("valid_from"):
        return Evaluation(None, (field + ":missing_effective_date",))
    try:
        valid_from = date.fromisoformat(fact["valid_from"])
        valid_to = date.fromisoformat(fact["valid_to"]) if fact.get("valid_to") else None
    except (TypeError, ValueError):
        return Evaluation(None, (field + ":invalid_effective_date",))
    if valid_from > as_of or (valid_to and (valid_to <= as_of or valid_to <= valid_from)):
        return Evaluation(None, (field + ":outside_effective_interval",))
    kind, unit = FIELD_TYPES[field]
    if fact.get("unit") != unit:
        return Evaluation(None, (field + ":unit_mismatch",))
    try:
        left, right = _scalar(fact["value"], kind), _scalar(node["value"], kind)
    except ValueError:
        return Evaluation(None, (field + ":type_mismatch",))
    op = node["op"]
    result = {"eq": lambda: left == right, "ne": lambda: left != right,
              "lt": lambda: left < right, "lte": lambda: left <= right,
              "gt": lambda: left > right, "gte": lambda: left >= right}[op]()
    return Evaluation(result)


def evaluate_predicate(node: dict, facts: dict, as_of: str, *, bindings: dict | None = None) -> Evaluation:
    validate_predicate(node)
    if not isinstance(facts, dict):
        raise ValueError("Facts must be an evidence projection")
    return _evaluate(node, facts, date.fromisoformat(as_of), bindings or {})


def validate_rule(rule: dict) -> None:
    required = {"schema_version", "pattern_id", "version", "taxonomy_path", "kind", "lifecycle",
                "jurisdictions", "tracks", "effective_from", "effective_to",
                "predicate", "source_refs", "title"}
    if not required <= set(rule):
        raise ValueError("Incomplete rule snapshot")
    if type(rule["schema_version"]) is not int or rule["schema_version"] != RULE_SCHEMA_VERSION:
        raise ValueError("Unsupported rule schema version")
    if not isinstance(rule["pattern_id"], str) or not rule["pattern_id"].strip():
        raise ValueError("Pattern identity required")
    if type(rule["version"]) is not int or rule["version"] < 1:
        raise ValueError("Positive integer version required")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*(\.[A-Z][A-Z0-9_]*){3}", rule["taxonomy_path"]):
        raise ValueError("Four uppercase taxonomy labels required")
    if rule["kind"] not in {"HYPOTHESIS", "REVIEW_CHECK", "POLICY", "LEGAL_REQUIREMENT"}:
        raise ValueError("Unknown rule kind")
    if rule["lifecycle"] not in {"DRAFT", "REVIEWED", "RETIRED"}:
        raise ValueError("Unknown lifecycle")
    for field in ("jurisdictions", "tracks", "source_refs"):
        if not isinstance(rule[field], list) or not rule[field] or any(not isinstance(v, str) or not v for v in rule[field]):
            raise ValueError(field + " must be a nonempty string list")
    begin = date.fromisoformat(rule["effective_from"])
    end = date.fromisoformat(rule["effective_to"]) if rule["effective_to"] else None
    if end and end <= begin:
        raise ValueError("Invalid rule interval")
    claim = rule.get("book_claim")
    if claim is not None:
        if (not isinstance(claim, dict)
                or set(claim) != {"claim_id", "source_sha256", "disposition"}
                or not isinstance(claim["claim_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}", claim["claim_id"])
                or not isinstance(claim["source_sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", claim["source_sha256"])
                or not isinstance(claim["disposition"], str)
                or claim["disposition"] not in {"UNRESOLVED", "ILLUSTRATIVE", "CONTRADICTED", "METHOD_ONLY"}):
            raise ValueError("Invalid book claim provenance")
    book_method_reference = any(
        re.fullmatch(r"(?:urn:black-river:book-method:)?BM-[0-9a-f]{16}", ref.strip())
        for ref in rule["source_refs"]
    )
    illustrative_reference = any(
        ref.strip().startswith("urn:black-river:acquisition-academy:illustrative-program-policy:")
        for ref in rule["source_refs"]
    )
    if claim is not None or book_method_reference or illustrative_reference:
        if rule["lifecycle"] == "REVIEWED" or rule["kind"] == "LEGAL_REQUIREMENT":
            raise ValueError("Book claim evidence and illustrative references can only support research or a retired snapshot")

    validate_predicate(rule["predicate"])
    bindings = rule.get("evidence_bindings", {})
    if not isinstance(bindings, dict):
        raise ValueError("Evidence bindings must be a field map")
    for field, binding in bindings.items():
        if (field not in FIELD_TYPES or not isinstance(binding, dict)
                or set(binding) != EVIDENCE_BINDING_KEYS
                or any(not isinstance(value, str) or not value.strip() for value in binding.values())
                or binding["domain"] != "COMMERCIAL"
                or not re.fullmatch(r"[0-9a-f]{64}", binding["source_revision_sha256"])):
            raise ValueError("Invalid Commercial evidence binding")


def screen_rule(rule: dict, facts: dict, *, jurisdiction: str, track: str,
                as_of: str, similarity: float | None = None) -> dict:
    """Screen a frozen snapshot; matching NEVER authorizes a real-world action."""
    validate_rule(rule)
    when = date.fromisoformat(as_of)
    if similarity is not None and (isinstance(similarity, bool) or not isinstance(similarity, (int, float))
                                   or not -1 <= similarity <= 1):
        raise ValueError("Similarity must be finite and in [-1, 1]")
    applicable = jurisdiction in rule["jurisdictions"] and track in rule["tracks"]
    current = date.fromisoformat(rule["effective_from"]) <= when and (
        not rule["effective_to"] or when < date.fromisoformat(rule["effective_to"]))
    result = Evaluation(None)
    if not applicable:
        status = "NOT_APPLICABLE"
    elif not current or rule["lifecycle"] == "RETIRED":
        status = "INACTIVE"
    else:
        result = evaluate_predicate(rule["predicate"], facts, as_of, bindings=rule.get("evidence_bindings"))
        if result.value is None:
            status = "NEEDS_EVIDENCE"
        elif result.value is False:
            status = "NO_MATCH"
        elif rule["lifecycle"] == "DRAFT":
            status = "DRAFT_MATCH_REVIEW"
        else:
            status = "MATCH_REVIEW"
    input_snapshot = {"facts": facts, "jurisdiction": jurisdiction, "track": track, "as_of": as_of}
    return {"pattern_id": rule["pattern_id"], "pattern_version": rule["version"],
            "rule_sha256": digest(rule), "input_sha256": digest(input_snapshot),
            "rule_snapshot": json.loads(canonical(rule)),
            "input_snapshot": json.loads(canonical(input_snapshot)),
            "taxonomy_path": rule["taxonomy_path"], "status": status,
            "predicate_value": result.value, "reasons": list(result.reasons),
            "similarity_for_retrieval_only": similarity, "backend": "CPU_REFERENCE",
            "evaluator_version": VERSION, "external_authority": False,
            "financial_authority": False, "legal_determination": False}


class DecisionReceipts:
    """Local append-only receipts, not a source-acceptance or approval service.

    SQL triggers and chain checks protect normal access. An OS/database owner can
    replace storage, so this is not externally anchored or tamper-proof storage.
    """
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, timeout=15)
        self.db.row_factory = sqlite3.Row
        self.initialize(self.db)

    @staticmethod
    def initialize(db):
        db.executescript("""
          CREATE TABLE IF NOT EXISTS acquisition_pattern_versions(
            pattern_id TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
            body TEXT NOT NULL, content_hash TEXT NOT NULL,
            PRIMARY KEY(pattern_id,version));
          CREATE TRIGGER IF NOT EXISTS acquisition_version_no_update
          BEFORE UPDATE ON acquisition_pattern_versions
          BEGIN SELECT RAISE(ABORT,'append-only version'); END;
          CREATE TRIGGER IF NOT EXISTS acquisition_version_no_delete
          BEFORE DELETE ON acquisition_pattern_versions
          BEGIN SELECT RAISE(ABORT,'append-only version'); END;
          CREATE TABLE IF NOT EXISTS acquisition_pattern_receipts(
            sequence INTEGER PRIMARY KEY, operation_id TEXT UNIQUE NOT NULL,
            body TEXT NOT NULL, prior_hash TEXT NOT NULL, receipt_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
          CREATE TRIGGER IF NOT EXISTS acquisition_receipt_no_update
          BEFORE UPDATE ON acquisition_pattern_receipts
          BEGIN SELECT RAISE(ABORT,'append-only receipt'); END;
          CREATE TRIGGER IF NOT EXISTS acquisition_receipt_no_delete
          BEFORE DELETE ON acquisition_pattern_receipts
          BEGIN SELECT RAISE(ABORT,'append-only receipt'); END;
        """)

    def register_version(self, rule: dict) -> str:
        """Retain a snapshot without granting it reviewed/active authority."""
        validate_rule(rule)
        body, content_hash = canonical(rule), digest(rule)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self._register_locked(self.db, rule, body, content_hash)
        return content_hash

    @staticmethod
    def _register_locked(db, rule: dict, body: str, content_hash: str) -> None:
        old = db.execute("SELECT body FROM acquisition_pattern_versions WHERE pattern_id=? AND version=?",
                              (rule["pattern_id"], rule["version"])).fetchone()
        if old and old["body"] != body:
            raise ValueError("Pattern version already exists with different content")
        if not old:
            db.execute("INSERT INTO acquisition_pattern_versions VALUES(?,?,?,?)",
                            (rule["pattern_id"], rule["version"], body, content_hash))

    @staticmethod
    def _validated_result(payload: dict) -> dict:
        result = payload.get("result", payload)
        if not isinstance(result, dict) or not isinstance(result.get("rule_snapshot"), dict) or not isinstance(result.get("input_snapshot"), dict):
            raise ValueError("A complete rule evaluation receipt is required")
        inputs = result["input_snapshot"]
        if set(inputs) != {"facts", "jurisdiction", "track", "as_of"}:
            raise ValueError("Invalid input snapshot")
        expected = screen_rule(result["rule_snapshot"], inputs["facts"],
                               jurisdiction=inputs["jurisdiction"], track=inputs["track"],
                               as_of=inputs["as_of"], similarity=result.get("similarity_for_retrieval_only"))
        if canonical(expected) != canonical(result):
            raise ValueError("Receipt differs from deterministic evaluation")
        return result

    def append(self, operation_id: str, payload: dict) -> dict:
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return self.append_locked(self.db, operation_id, payload)

    @classmethod
    def append_locked(cls, db, operation_id: str, payload: dict) -> dict:
        """Append to an existing write transaction."""
        if not db.in_transaction:
            raise ValueError("A caller-owned write transaction is required")
        if not isinstance(operation_id, str) or not operation_id.strip() or not isinstance(payload, dict):
            raise ValueError("Operation ID and payload required")
        body = canonical(payload)
        old = db.execute("SELECT * FROM acquisition_pattern_receipts WHERE operation_id=?",
                              (operation_id,)).fetchone()
        if old:
            if old["body"] != body:
                raise ValueError("Operation ID conflicts with previous payload")
            return dict(old)
        # An exact historical retry is a read of a retained operation, not
        # a new execution under today's schema. New operations validate.
        result = cls._validated_result(json.loads(body))
        rule = result["rule_snapshot"]
        cls._register_locked(db, rule, canonical(rule), digest(rule))
        previous = db.execute("SELECT receipt_hash FROM acquisition_pattern_receipts ORDER BY sequence DESC LIMIT 1").fetchone()
        prior = previous[0] if previous else "GENESIS"
        receipt_hash = digest({"operation_id": operation_id, "body": body, "prior_hash": prior})
        db.execute("INSERT INTO acquisition_pattern_receipts(operation_id,body,prior_hash,receipt_hash) VALUES(?,?,?,?)",
                        (operation_id, body, prior, receipt_hash))
        return dict(db.execute("SELECT * FROM acquisition_pattern_receipts WHERE operation_id=?",
                                    (operation_id,)).fetchone())


    def verify(self) -> bool:
        prior = "GENESIS"
        for row in self.db.execute("SELECT * FROM acquisition_pattern_receipts ORDER BY sequence"):
            expected = digest({"operation_id": row["operation_id"], "body": row["body"], "prior_hash": prior})
            if row["prior_hash"] != prior or row["receipt_hash"] != expected:
                return False
            try:
                payload = json.loads(row["body"])
                result = payload.get("result", payload)
                rule = result["rule_snapshot"]
                if digest(rule) != result["rule_sha256"] or digest(result["input_snapshot"]) != result["input_sha256"]:
                    return False
                saved = self.db.execute("SELECT body,content_hash FROM acquisition_pattern_versions WHERE pattern_id=? AND version=?",
                                        (rule["pattern_id"], rule["version"])).fetchone()
                if not saved or saved["body"] != canonical(rule) or saved["content_hash"] != digest(rule):
                    return False
            except (ValueError, KeyError, TypeError):
                return False
            prior = row["receipt_hash"]
        return True

    def close(self) -> None:
        self.db.close()
