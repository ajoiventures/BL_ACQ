"""Deterministic document evidence, review history, and typed input projection.

This CPU/SQLite engine archives supplied bytes and manually entered or native-JSON
claims. It does not fetch documents, perform OCR, call AI, or authorize a deal.
Declared business dates support as-of replay; recorded_at separately records when
this application received each record. This is not a complete bitemporal system.
"""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
import sqlite3
from typing import Protocol
from urllib.parse import urlsplit


SCHEMA_VERSION = "1.0"
MAX_CONTENT_BYTES = 16 * 1024 * 1024
MAX_RECORDS_PER_DEAL = 10000
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
SCOPES = {"commercial", "family", "civic"}
VALUE_TYPES = {"money_cents", "integer", "basis_points", "text", "boolean", "date"}


def _text(value, name, maximum=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonempty text up to {maximum} characters")
    return value


def _id(value, name):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _date(value, name, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name} must be YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return value


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _object(record, allowed, required, name):
    if not isinstance(record, dict):
        raise ValueError(f"{name} must be an object")
    if set(record) - allowed or required - set(record):
        raise ValueError(f"{name} has unknown or missing fields")
    if record.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError(f"Unsupported {name} schema_version")


def _canonical(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)


class CandidateProvider(Protocol):
    """Future adapters may propose claims; they never write review decisions."""
    name: str

    def candidate_claims(self, payload: dict) -> list[dict]: ...


class NativeJsonProvider:
    name = "native_json"

    def candidate_claims(self, payload):
        if not isinstance(payload, dict) or set(payload) != {"claims"}:
            raise ValueError("Native JSON provider accepts a claims object only")
        if not isinstance(payload["claims"], list) or len(payload["claims"]) > MAX_RECORDS_PER_DEAL:
            raise ValueError("claims must be a bounded array")
        # Round-trip also rejects non-JSON values; validation happens at add_claim.
        result = json.loads(_canonical(payload["claims"]))
        for claim in result:
            if not isinstance(claim, dict) or claim.get("method") != "native_json":
                raise ValueError("Native JSON candidates must declare method=native_json")
        return result


class DisabledAIProvider:
    name = "ai_disabled"

    def candidate_claims(self, payload):
        raise RuntimeError("Product AI extraction is disabled; supply manual or native JSON candidates")


class EvidenceStore:
    """One trusted application actor and scope per connection; no authentication UI.

    Authentication/authorization belong to the calling application. Use a distinct
    connection per thread. Named reviews are recorded attestations, not proof that
    a source is truthful or that a transaction has legally completed.
    """
    def __init__(self, db_path, *, actor, scope="commercial"):
        self.actor = _text(actor, "actor", 200)
        if not isinstance(scope, str) or scope not in SCOPES:
            raise ValueError("Unknown evidence scope")
        self.scope, self._savepoint = scope, 0
        self.connection = sqlite3.connect(db_path, timeout=10, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA foreign_keys=ON")
            self._migrate()
        except BaseException:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.connection.close()

    @contextmanager
    def transaction(self):
        if self.connection.in_transaction:
            self._savepoint += 1
            name = f"document_operation_{self._savepoint}"
            self.connection.execute(f"SAVEPOINT {name}")
            try:
                yield
            except BaseException:
                self.connection.execute(f"ROLLBACK TO {name}")
                raise
            finally:
                self.connection.execute(f"RELEASE {name}")
            return
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def _migrate(self):
        with self.transaction():
            self.connection.execute("CREATE TABLE IF NOT EXISTS br_document_evidence_versions(version INTEGER PRIMARY KEY)")
            versions = [r[0] for r in self.connection.execute("SELECT version FROM br_document_evidence_versions ORDER BY version")]
            if versions not in ([], [1]):
                raise ValueError("Unsupported document evidence storage version")
            if versions:
                return
            self.connection.execute("""CREATE TABLE br_documents(
                scope TEXT NOT NULL, document_id TEXT NOT NULL, deal_id TEXT NOT NULL,
                family_id TEXT NOT NULL, version INTEGER NOT NULL, record_json TEXT NOT NULL,
                content BLOB NOT NULL, recorded_at TEXT NOT NULL,
                PRIMARY KEY(scope,document_id), UNIQUE(scope,deal_id,document_id),
                UNIQUE(scope,deal_id,family_id,version))""")
            self.connection.execute("""CREATE TABLE br_document_claims(
                scope TEXT NOT NULL, claim_id TEXT NOT NULL, deal_id TEXT NOT NULL,
                document_id TEXT NOT NULL, field TEXT NOT NULL, record_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL, PRIMARY KEY(scope,claim_id),
                UNIQUE(scope,deal_id,claim_id),
                FOREIGN KEY(scope,deal_id,document_id) REFERENCES br_documents(scope,deal_id,document_id))""")
            self.connection.execute("""CREATE TABLE br_document_reviews(
                seq INTEGER PRIMARY KEY, scope TEXT NOT NULL, review_id TEXT NOT NULL,
                deal_id TEXT NOT NULL, claim_id TEXT NOT NULL, reviewed_on TEXT NOT NULL,
                record_json TEXT NOT NULL, recorded_at TEXT NOT NULL,
                UNIQUE(scope,review_id),
                FOREIGN KEY(scope,deal_id,claim_id) REFERENCES br_document_claims(scope,deal_id,claim_id))""")
            self.connection.execute("CREATE INDEX br_document_claim_deal ON br_document_claims(scope,deal_id,field)")
            self.connection.execute("CREATE INDEX br_document_review_claim ON br_document_reviews(scope,deal_id,claim_id,reviewed_on,seq)")
            for table in ("br_documents", "br_document_claims", "br_document_reviews"):
                for action in ("UPDATE", "DELETE"):
                    self.connection.execute(f"""CREATE TRIGGER {table}_{action.lower()}_immutable
                        BEFORE {action} ON {table} BEGIN
                        SELECT RAISE(ABORT,'Document evidence history is append-only'); END""")
            self.connection.execute("INSERT INTO br_document_evidence_versions VALUES(1)")

    @staticmethod
    def _recorded_at():
        return datetime.now(timezone.utc).isoformat()

    def _record(self, table, id_column, identity, deal_id=None):
        # Table and column names are private constants, never user input.
        sql = f"SELECT record_json FROM {table} WHERE scope=? AND {id_column}=?"
        args = [self.scope, identity]
        if deal_id is not None:
            sql += " AND deal_id=?"
            args.append(deal_id)
        row = self.connection.execute(sql, args).fetchone()
        return json.loads(row[0]) if row else None

    def get_document(self, document_id, *, deal_id):
        return self._record("br_documents", "document_id", _id(document_id, "document_id"), _id(deal_id, "deal_id"))

    def document_content(self, document_id, *, deal_id):
        row = self.connection.execute("SELECT content FROM br_documents WHERE scope=? AND document_id=? AND deal_id=?",
                                      (self.scope, _id(document_id, "document_id"), _id(deal_id, "deal_id"))).fetchone()
        if row is None:
            raise ValueError("Document does not belong to this deal and scope")
        return bytes(row[0])

    def register_document(self, metadata, *, content):
        required = {"document_id", "deal_id", "family_id", "version", "source_uri", "title",
                    "received_on", "effective_on", "expires_on", "page_count", "illustrative"}
        allowed = required | {"schema_version", "supersedes_document_id", "sha256"}
        _object(metadata, allowed, required, "document")
        if not isinstance(content, bytes) or not 1 <= len(content) <= MAX_CONTENT_BYTES:
            raise ValueError("content must be 1 to 16777216 supplied bytes")
        record = dict(metadata)
        for key in ("document_id", "deal_id", "family_id"):
            _id(record[key], key)
        _integer(record["version"], "version", 1, 1000000)
        _integer(record["page_count"], "page_count", 1, 100000)
        _text(record["title"], "title", 1000)
        uri = urlsplit(_text(record["source_uri"], "source_uri", 2048))
        if uri.scheme not in {"http", "https", "fixture", "local"} or not uri.netloc or uri.username or uri.password:
            raise ValueError("source_uri must be a credential-free HTTP(S), fixture, or local reference")
        for key in ("received_on", "effective_on"):
            _date(record[key], key)
        _date(record["expires_on"], "expires_on", nullable=True)
        if record["expires_on"] is not None and record["expires_on"] < record["effective_on"]:
            raise ValueError("Document expiry precedes its effective date")
        if type(record["illustrative"]) is not bool:
            raise ValueError("illustrative must be a Boolean")
        sha = hashlib.sha256(content).hexdigest()
        if "sha256" in record and record["sha256"] != sha:
            raise ValueError("Supplied content does not match sha256")
        record.update(schema_version=SCHEMA_VERSION, sha256=sha, registered_by=self.actor,
                      byte_count=len(content), supersedes_document_id=record.get("supersedes_document_id"))
        with self.transaction():
            existing = self._record("br_documents", "document_id", record["document_id"])
            if existing is not None:
                if {k: v for k, v in existing.items() if k != "registered_by"} != {k: v for k, v in record.items() if k != "registered_by"}:
                    raise ValueError("Conflicting document replay; append a new document version")
                return existing
            latest_row = self.connection.execute("SELECT record_json FROM br_documents WHERE scope=? AND deal_id=? AND family_id=? ORDER BY version DESC LIMIT 1",
                (self.scope, record["deal_id"], record["family_id"])).fetchone()
            latest = json.loads(latest_row[0]) if latest_row else None
            if latest is None:
                if record["version"] != 1 or record["supersedes_document_id"] is not None:
                    raise ValueError("A document family starts at version 1 without a predecessor")
            elif (record["version"] != latest["version"]+1
                  or record["supersedes_document_id"] != latest["document_id"]
                  or record["received_on"] < latest["received_on"]
                  or record["effective_on"] < latest["effective_on"]):
                raise ValueError("New document must follow the same deal/family's latest version and dates")
            self.connection.execute("INSERT INTO br_documents VALUES(?,?,?,?,?,?,?,?)",
                (self.scope, record["document_id"], record["deal_id"], record["family_id"], record["version"],
                 _canonical(record), content, self._recorded_at()))
        return record

    def add_claim(self, candidate):
        required = {"claim_id", "deal_id", "document_id", "field", "value", "value_type", "unit",
                    "currency", "page", "location", "raw_text", "entered_on", "method"}
        _object(candidate, required | {"schema_version", "bbox"}, required, "claim")
        record = dict(candidate)
        for key in ("claim_id", "deal_id", "document_id", "field"):
            _id(record[key], key)
        kind, value = _text(record["value_type"], "value_type", 40), record["value"]
        _text(record["unit"], "unit", 40)
        if kind not in VALUE_TYPES:
            raise ValueError("Unsupported value_type")
        if kind == "money_cents":
            _integer(value, "money cents", -10**12, 10**12)
            if record["unit"] != "cents" or record["currency"] != "USD":
                raise ValueError("Money claims require unit=cents and currency=USD")
        else:
            if record["currency"] is not None:
                raise ValueError("Nonmonetary claims must have currency=null")
            if kind == "integer":
                _integer(value, "integer value", -10**12, 10**12)
                if record["unit"] not in {"days", "count", "months", "years"}:
                    raise ValueError("Integer claim unit is unsupported")
            elif kind == "basis_points":
                _integer(value, "basis points", 0, 10000)
                if record["unit"] != "bps":
                    raise ValueError("Basis point claims require unit=bps")
            elif kind == "text":
                _text(value, "text value", 4000)
                if record["unit"] != "text":
                    raise ValueError("Text claims require unit=text")
            elif kind == "boolean":
                if type(value) is not bool or record["unit"] != "boolean":
                    raise ValueError("Boolean claims require a Boolean and unit=boolean")
            elif kind == "date":
                _date(value, "date value")
                if record["unit"] != "date":
                    raise ValueError("Date claims require unit=date")
        _integer(record["page"], "page", 1, 100000)
        _text(record["location"], "location", 1000)
        _text(record["raw_text"], "raw_text", 8000)
        _date(record["entered_on"], "entered_on")
        if not isinstance(record["method"], str) or record["method"] not in {"manual", "native_json"}:
            raise ValueError("AI extraction is disabled; use manual or native_json")
        bbox = record.get("bbox")
        if bbox is not None and (not isinstance(bbox, list) or len(bbox) != 4
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in bbox)
                or not bbox[0] < bbox[2] or not bbox[1] < bbox[3]):
            raise ValueError("bbox must be normalized [left,top,right,bottom] with positive area")
        record.update(schema_version=SCHEMA_VERSION, bbox=bbox, entered_by=self.actor)
        with self.transaction():
            document = self.get_document(record["document_id"], deal_id=record["deal_id"])
            if document is None:
                raise ValueError("Document does not belong to this deal and scope")
            if record["page"] > document["page_count"] or record["entered_on"] < document["received_on"]:
                raise ValueError("Claim page or entered date is inconsistent with its document")
            existing = self._record("br_document_claims", "claim_id", record["claim_id"])
            if existing is not None:
                if {k: v for k, v in existing.items() if k != "entered_by"} != {k: v for k, v in record.items() if k != "entered_by"}:
                    raise ValueError("Conflicting claim replay; append a new claim")
                return existing
            self.connection.execute("INSERT INTO br_document_claims VALUES(?,?,?,?,?,?,?)",
                (self.scope, record["claim_id"], record["deal_id"], record["document_id"], record["field"],
                 _canonical(record), self._recorded_at()))
        return record

    def review_claim(self, review_id, claim_id, *, deal_id, decision, reviewed_on, expires_on, reason):
        for value, name in ((review_id, "review_id"), (claim_id, "claim_id"), (deal_id, "deal_id")):
            _id(value, name)
        if not isinstance(decision, str) or decision not in {"accept", "reject"}:
            raise ValueError("decision must be accept or reject")
        _date(reviewed_on, "reviewed_on")
        _date(expires_on, "review expires_on", nullable=True)
        if expires_on is not None and expires_on < reviewed_on:
            raise ValueError("Review expiry precedes review date")
        record = {"schema_version": SCHEMA_VERSION, "review_id": review_id, "claim_id": claim_id,
                  "deal_id": deal_id, "decision": decision, "reviewed_on": reviewed_on,
                  "expires_on": expires_on, "reason": _text(reason, "reason", 4000), "reviewer": self.actor}
        with self.transaction():
            claim = self._record("br_document_claims", "claim_id", claim_id, deal_id)
            if claim is None:
                raise ValueError("Claim does not belong to this deal and scope")
            if reviewed_on < claim["entered_on"]:
                raise ValueError("Review predates the claim")
            existing = self._record("br_document_reviews", "review_id", review_id)
            if existing is not None:
                if existing != record:
                    raise ValueError("Conflicting review replay; append a new review")
                return existing
            latest = self.connection.execute("SELECT reviewed_on FROM br_document_reviews WHERE scope=? AND claim_id=? ORDER BY reviewed_on DESC,seq DESC LIMIT 1",
                (self.scope, claim_id)).fetchone()
            if latest is not None and reviewed_on < latest[0]:
                raise ValueError("New review must not backdate the existing review history")
            self.connection.execute("INSERT INTO br_document_reviews(scope,review_id,deal_id,claim_id,reviewed_on,record_json,recorded_at) VALUES(?,?,?,?,?,?,?)",
                (self.scope, review_id, deal_id, claim_id, reviewed_on, _canonical(record), self._recorded_at()))
        return record

    def review_history(self, claim_id, *, deal_id):
        _id(claim_id, "claim_id"); _id(deal_id, "deal_id")
        return [json.loads(row[0]) for row in self.connection.execute(
            "SELECT record_json FROM br_document_reviews WHERE scope=? AND claim_id=? AND deal_id=? ORDER BY reviewed_on,seq",
            (self.scope, claim_id, deal_id))]

    def project_inputs(self, deal_id, as_of, *, required_fields=(), max_age_days=None):
        """Project currently reviewed, nonconflicting values; never fill absent data.

        A current pending/stale candidate blocks its field until resolved. Equal
        accepted values may share provenance. A newer effective family version
        suppresses the old version even when the successor has no claims yet.
        Expiring a rejection never restores a previous acceptance.
        """
        # The pilot serializes the snapshot with concurrent writers. This avoids
        # mixing old documents with newer review records halfway through a read.
        with self.transaction():
            return self._project_inputs(deal_id, as_of, required_fields, max_age_days)

    def _project_inputs(self, deal_id, as_of, required_fields, max_age_days):
        _id(deal_id, "deal_id"); _date(as_of, "as_of")
        if not isinstance(required_fields, (tuple, list)) or len(required_fields) > 1000:
            raise ValueError("required_fields must be a bounded list or tuple")
        for field in required_fields:
            _id(field, "required field")
        if len(set(required_fields)) != len(required_fields):
            raise ValueError("Duplicate required fields")
        if max_age_days is not None:
            _integer(max_age_days, "max_age_days", 0, 36500)
        docs = [json.loads(r[0]) for r in self.connection.execute("SELECT record_json FROM br_documents WHERE scope=? AND deal_id=? ORDER BY family_id,version LIMIT ?",
                (self.scope, deal_id, MAX_RECORDS_PER_DEAL+1))]
        claims = [json.loads(r[0]) for r in self.connection.execute("SELECT record_json FROM br_document_claims WHERE scope=? AND deal_id=? ORDER BY claim_id LIMIT ?",
                  (self.scope, deal_id, MAX_RECORDS_PER_DEAL+1))]
        if len(docs) > MAX_RECORDS_PER_DEAL or len(claims) > MAX_RECORDS_PER_DEAL:
            raise ValueError("Projection exceeds bounded pilot record count")
        review_rows = self.connection.execute(
            "SELECT record_json FROM br_document_reviews WHERE scope=? AND deal_id=? AND reviewed_on<=? ORDER BY reviewed_on,seq LIMIT ?",
            (self.scope, deal_id, as_of, MAX_RECORDS_PER_DEAL*10+1)).fetchall()
        if len(review_rows) > MAX_RECORDS_PER_DEAL*10:
            raise ValueError("Projection exceeds bounded pilot review count")
        latest_reviews = {}
        for row in review_rows:
            review = json.loads(row[0])
            latest_reviews[review["claim_id"]] = review
        indexed = {d["document_id"]: d for d in docs}
        active = {}
        for d in docs:
            if d["received_on"] <= as_of and d["effective_on"] <= as_of:
                active[d["family_id"]] = d
        visible = [c for c in claims if c["entered_on"] <= as_of]
        states, accepted, blocked = [], {}, {}
        current_fields = {}
        for c in visible:
            d = indexed[c["document_id"]]
            current = active.get(d["family_id"])
            if current and current["document_id"] == d["document_id"]:
                current_fields.setdefault(d["family_id"], set()).add(c["field"])
        for c in visible:
            d = indexed[c["document_id"]]
            latest = active.get(d["family_id"])
            review = latest_reviews.get(c["claim_id"])
            state, reason = "pending", "No review is effective as of this date"
            blocking = True
            if d["received_on"] > as_of or d["effective_on"] > as_of:
                state, reason, blocking = "not_yet_effective", "Document is not available/effective as of this date", False
            elif latest["document_id"] != d["document_id"]:
                state, reason, blocking = "superseded", "A newer effective document version exists", False
                if c["field"] not in current_fields.get(d["family_id"], set()):
                    blocked.setdefault(c["field"], []).append({"code": "successor_missing_claim", "claim_id": c["claim_id"],
                        "document_id": latest["document_id"], "reason": "Newer document has no current candidate for the old field"})
            elif review and review["expires_on"] is not None and review["expires_on"] < as_of:
                state, reason = "review_expired", "The latest review expired; previous decisions are not revived"
            elif review and review["decision"] == "reject":
                state, reason, blocking = "rejected", review["reason"], False
            elif d["expires_on"] is not None and d["expires_on"] < as_of:
                state, reason = "source_expired", "The current source document expired"
            elif max_age_days is not None and (date.fromisoformat(as_of)-date.fromisoformat(d["received_on"])).days > max_age_days:
                state, reason = "source_stale", "The current source exceeds the declared age policy"
            elif review and review["decision"] == "accept":
                state, reason, blocking = "accepted", review["reason"], False
                accepted.setdefault(c["field"], []).append((c, d, review))
            states.append({"claim_id": c["claim_id"], "document_id": d["document_id"], "field": c["field"],
                           "state": state, "reason": reason, "review_id": review["review_id"] if review else None})
            if blocking:
                blocked.setdefault(c["field"], []).append({"code": state, "claim_id": c["claim_id"],
                                                         "document_id": d["document_id"], "reason": reason})
        facts = {}
        for field, candidates in accepted.items():
            keys = {_canonical({k: c[k] for k in ("value", "value_type", "unit", "currency")}) for c, _, _ in candidates}
            if len(keys) > 1:
                blocked.setdefault(field, []).append({"code": "conflict", "claim_ids": [c["claim_id"] for c, _, _ in candidates],
                                                      "reason": "Current accepted claims disagree on value, type, unit or currency"})
                for state in states:
                    if state["field"] == field and state["state"] == "accepted":
                        state.update(state="conflict", reason="Current accepted claims disagree")
            if field in blocked:
                continue
            c = candidates[0][0]
            provenance = [{"claim_id": c0["claim_id"], "document_id": doc["document_id"], "sha256": doc["sha256"],
                           "document_version": doc["version"], "source_uri": doc["source_uri"],
                           "page": c0["page"], "location": c0["location"], "bbox": c0["bbox"],
                           "raw_text": c0["raw_text"], "method": c0["method"], "review_id": r["review_id"],
                           "reviewer": r["reviewer"], "reviewed_on": r["reviewed_on"], "illustrative": doc["illustrative"]}
                          for c0, doc, r in candidates]
            facts[field] = {**{k: c[k] for k in ("value", "value_type", "unit", "currency")}, "provenance": provenance}
        for field in required_fields:
            if field not in facts and field not in blocked:
                blocked[field] = [{"code": "missing", "reason": "No current accepted claim supplies this required field"}]
        blockers = [{"field": f, **issue} for f in sorted(blocked) for issue in blocked[f]]
        material = {"schema_version": SCHEMA_VERSION, "deal_id": deal_id, "scope": self.scope,
                    "as_of": as_of, "values": {f: v["value"] for f, v in facts.items()}, "facts": facts,
                    "states": states, "blockers": blockers, "required_fields": list(required_fields),
                    "max_age_days": max_age_days, "state": "review_required" if blockers or not facts else "ready",
                    "illustrative": any(doc["illustrative"] for doc in docs), "backend": "cpu",
                    "product_ai_enabled": False, "date_semantics": "declared business dates; recorded_at is retained separately"}
        return {**material, "projection_digest": hashlib.sha256(_canonical(material).encode()).hexdigest()}

    def ingest_bundle(self, bundle):
        """Atomically ingest supplied document bytes/claims; never import reviews."""
        if not isinstance(bundle, dict) or set(bundle) != {"schema_version", "documents", "claims"} or bundle["schema_version"] != SCHEMA_VERSION:
            raise ValueError("Bundle requires schema_version, documents, claims; review imports are not allowed")
        if any(not isinstance(bundle[k], list) or len(bundle[k]) > MAX_RECORDS_PER_DEAL for k in ("documents", "claims")):
            raise ValueError("Bundle collections must be bounded lists")
        with self.transaction():
            documents = []
            for item in bundle["documents"]:
                if not isinstance(item, dict) or set(item) != {"metadata", "content_utf8"} or not isinstance(item["content_utf8"], str):
                    raise ValueError("Each bundle document requires metadata and content_utf8")
                documents.append(self.register_document(item["metadata"], content=item["content_utf8"].encode("utf-8")))
            claims = [self.add_claim(c) for c in NativeJsonProvider().candidate_claims({"claims": bundle["claims"]})]
        return {"document_ids": [d["document_id"] for d in documents], "claim_ids": [c["claim_id"] for c in claims],
                "review_decisions_imported": 0, "product_ai_enabled": False}
