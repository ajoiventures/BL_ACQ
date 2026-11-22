"""Local document records and review projection using the existing evidence DB.

This adapter composes EvidenceStore's transactions without changing its older
deal-specific tables. Context filters and actor labels are useful local controls,
not a network authentication or multi-tenant authorization service.
"""
from datetime import datetime, timezone
import hashlib
import json

from pilot.document_contracts import (
    SCHEMA_VERSION, canonical_json, validate_candidate, validate_context,
    validate_document, validate_extraction, validate_review,
)
from pilot.document_evidence import EvidenceStore


INVOICE_REQUIRED = ("vendor", "invoice_number", "invoice_date", "due_date", "total_cents", "currency")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


class DocumentVault:
    """One trusted OS application actor and document context per connection."""

    def __init__(self, path, *, context, actor):
        self.context = validate_context(context)
        self.context_key = canonical_json(self.context)
        self.actor = actor
        self.store = EvidenceStore(path, actor=actor, scope=self.context["domain"])
        self.connection = self.store.connection
        try:
            self._migrate()
        except BaseException:
            self.store.__exit__()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.store.__exit__(*exc)

    def _migrate(self):
        with self.store.transaction():
            self.connection.execute("""CREATE TABLE IF NOT EXISTS br_docai_versions(
                version INTEGER PRIMARY KEY)""")
            versions = [row[0] for row in self.connection.execute("SELECT version FROM br_docai_versions ORDER BY version")]
            if versions not in ([], [1]):
                raise ValueError("Unsupported neutral document storage version")
            if versions:
                return
            self.connection.execute("""CREATE TABLE br_docai_revisions(
                context TEXT NOT NULL, document_id TEXT NOT NULL, revision INTEGER NOT NULL,
                PRIMARY KEY(context, document_id))""")
            self.connection.execute("""CREATE TABLE br_docai_records(
                sequence INTEGER PRIMARY KEY, context TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('document','extraction','candidate','review','archive')),
                record_id TEXT NOT NULL, document_id TEXT NOT NULL, record_json TEXT NOT NULL,
                recorded_at TEXT NOT NULL, UNIQUE(context, kind, record_id),
                FOREIGN KEY(context, document_id) REFERENCES br_docai_revisions(context, document_id))""")
            self.connection.execute("CREATE INDEX br_docai_document_records ON br_docai_records(context,document_id,kind,sequence)")
            self.connection.execute("""CREATE TABLE br_docai_requests(
                context TEXT NOT NULL, request_id TEXT NOT NULL, request_sha256 TEXT NOT NULL,
                response_json TEXT NOT NULL, PRIMARY KEY(context, request_id))""")
            for table in ("br_docai_records", "br_docai_requests", "br_docai_versions"):
                for action in ("UPDATE", "DELETE"):
                    self.connection.execute(f"""CREATE TRIGGER {table}_{action.lower()}_immutable
                        BEFORE {action} ON {table} BEGIN
                        SELECT RAISE(ABORT,'Doc AI history is append-only'); END""")
            self.connection.execute("INSERT INTO br_docai_versions VALUES(1)")

    def _check_context(self, record):
        if record["context"] != self.context:
            raise ValueError("Record belongs to a different document context")

    def _insert(self, kind, identity, document_id, record):
        self.connection.execute(
            "INSERT INTO br_docai_records(context,kind,record_id,document_id,record_json,recorded_at) VALUES(?,?,?,?,?,?)",
            (self.context_key, kind, identity, document_id, canonical_json(record), utc_now()),
        )

    def _record(self, kind, identity):
        row = self.connection.execute(
            "SELECT record_json FROM br_docai_records WHERE context=? AND kind=? AND record_id=?",
            (self.context_key, kind, identity),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def _records(self, kind, document_id):
        return [json.loads(row[0]) for row in self.connection.execute(
            "SELECT record_json FROM br_docai_records WHERE context=? AND kind=? AND document_id=? ORDER BY sequence",
            (self.context_key, kind, document_id),
        )]

    def document(self, document_id):
        return self._record("document", document_id)

    def _successors(self, document_id):
        records = (json.loads(row[0]) for row in self.connection.execute(
            "SELECT record_json FROM br_docai_records WHERE context=? AND kind='document'",
            (self.context_key,),
        ))
        return [record for record in records if record["predecessor_document_id"] == document_id]

    def _require_current_source(self, document_id):
        if self._successors(document_id):
            raise ValueError("Source version is superseded; inspect and review its successor")

    def _require_document(self, document_id):
        record = self.document(document_id)
        if record is None:
            raise ValueError("Document is absent from this context")
        return record

    def revision(self, document_id):
        self._require_document(document_id)
        return self.connection.execute(
            "SELECT revision FROM br_docai_revisions WHERE context=? AND document_id=?",
            (self.context_key, document_id),
        ).fetchone()[0]

    def _check_revision(self, document_id, expected):
        if type(expected) is not int or expected != self.revision(document_id):
            raise ValueError("Stale or invalid document revision; inspect before changing review state")

    def _advance(self, document_id):
        self.connection.execute("UPDATE br_docai_revisions SET revision=revision+1 WHERE context=? AND document_id=?",
                                (self.context_key, document_id))
        return self.revision(document_id)

    def _request_hash(self, payload):
        return hashlib.sha256(canonical_json({"actor": self.actor, "context": self.context, "payload": payload}).encode()).hexdigest()

    def _replay(self, request_id, fingerprint):
        row = self.connection.execute("SELECT request_sha256,response_json FROM br_docai_requests WHERE context=? AND request_id=?",
                                      (self.context_key, request_id)).fetchone()
        if row is None:
            return None
        if row[0] != fingerprint:
            raise ValueError("Idempotency key was already used for a different request or actor")
        return json.loads(row[1])

    def _remember(self, request_id, fingerprint, result):
        self.connection.execute("INSERT INTO br_docai_requests VALUES(?,?,?,?)",
                                (self.context_key, request_id, fingerprint, canonical_json(result)))

    def add_bundle(self, document, extraction, candidates, *, archive):
        """Atomically register the first run and its unreviewed proposals."""
        document = validate_document(document)
        self._check_context(document)
        extraction = validate_extraction(extraction, document)
        if type(candidates) is not list or len(candidates) > 1000:
            raise ValueError("Candidates must be a bounded list")
        candidates = [validate_candidate(c, document, extraction) for c in candidates]
        if len({c["claim_id"] for c in candidates}) != len(candidates):
            raise ValueError("Duplicate claim identifier in intake")
        if type(archive) is not dict or set(archive) != {"destination", "file", "sha256", "reason"}:
            raise ValueError("Expected the existing filing receipt shape")
        if archive["sha256"] != document["content_sha256"] or any(type(v) is not str or not v for v in archive.values()):
            raise ValueError("Archive receipt must bind the original bytes")
        document_id = document["document_id"]
        with self.store.transaction():
            old = self.document(document_id)
            if old is not None:
                if old != document:
                    raise ValueError("A source version cannot be overwritten")
                raise ValueError("Document already exists; inspect or replay intake instead")
            predecessor = document["predecessor_document_id"]
            if predecessor is not None:
                prior = self._require_document(predecessor)
                if prior["version"] + 1 != document["version"]:
                    raise ValueError("Document predecessor does not establish the next version")
                if prior["document_class"] != document["document_class"]:
                    raise ValueError("Source versions must preserve the classified document family")
                self._require_current_source(predecessor)
                self._advance(predecessor)
            elif document["version"] != 1:
                raise ValueError("A later version requires its predecessor")
            self.connection.execute("INSERT INTO br_docai_revisions VALUES(?,?,0)", (self.context_key, document_id))
            self._insert("document", document_id, document_id, document)
            self._insert("archive", document_id, document_id, archive)
            self._insert("extraction", extraction["run_id"], document_id, extraction)
            for candidate in candidates:
                if candidate["supersedes_claim_id"] is not None:
                    raise ValueError("Initial intake cannot supersede an absent candidate")
                self._insert("candidate", candidate["claim_id"], document_id, candidate)
            self._advance(document_id)
            return self.inspect(document_id)

    def correct(self, candidate, *, expected_revision):
        """Append a cited manual candidate; preserve the superseded record."""
        payload = {"candidate": candidate, "expected_revision": expected_revision}
        fingerprint = self._request_hash(payload)
        if type(candidate) is not dict or type(candidate.get("claim_id")) is not str:
            raise ValueError("Correction requires a candidate claim_id")
        request_id = "candidate:" + candidate["claim_id"]
        with self.store.transaction():
            replay = self._replay(request_id, fingerprint)
            if replay is not None:
                return replay
            document = self._require_document(candidate.get("document_id"))
            run = self._record("extraction", candidate.get("run_id"))
            if run is None:
                raise ValueError("Correction extraction is absent from this context")
            candidate = validate_candidate(candidate, document, run)
            self._check_context(candidate)
            self._check_revision(document["document_id"], expected_revision)
            self._require_current_source(document["document_id"])
            if candidate["method"] != "manual" or candidate["proposed_by"] != self.actor:
                raise ValueError("A local correction must identify the current manual proposer")
            predecessor = candidate["supersedes_claim_id"]
            if predecessor is not None:
                old = self._record("candidate", predecessor)
                if old is None or old["document_id"] != document["document_id"] or old["field"] != candidate["field"]:
                    raise ValueError("Correction must supersede a candidate of this document and field")
                if any(c["supersedes_claim_id"] == predecessor for c in self._records("candidate", document["document_id"])):
                    raise ValueError("Candidate was already superseded")
            self._insert("candidate", candidate["claim_id"], document["document_id"], candidate)
            result = {"candidate": candidate, "revision": self._advance(document["document_id"])}
            self._remember(request_id, fingerprint, result)
            return result

    def review(self, claim_id, *, review_id, decision, reason, expected_revision, supersedes_review_id=None):
        payload = {"claim_id": claim_id, "review_id": review_id, "decision": decision, "reason": reason,
                   "expected_revision": expected_revision, "supersedes_review_id": supersedes_review_id}
        fingerprint = self._request_hash(payload)
        request_id = "review:" + str(review_id)
        with self.store.transaction():
            replay = self._replay(request_id, fingerprint)
            if replay is not None:
                return replay
            candidate = self._record("candidate", claim_id)
            if candidate is None:
                raise ValueError("Candidate is absent from this context")
            document_id = candidate["document_id"]
            self._check_revision(document_id, expected_revision)
            self._require_current_source(document_id)
            if self.actor == candidate["proposed_by"]:
                raise ValueError("A proposer label cannot also accept or reject its own candidate")
            if any(c["supersedes_claim_id"] == claim_id for c in self._records("candidate", document_id)):
                raise ValueError("Cannot review a superseded candidate")
            reviews = [r for r in self._records("review", document_id) if r["claim_id"] == claim_id]
            latest = reviews[-1] if reviews else None
            if supersedes_review_id != (latest["review_id"] if latest else None):
                raise ValueError("Review must explicitly supersede its current decision")
            record = validate_review({
                "schema_version": SCHEMA_VERSION, "review_id": review_id, "claim_id": claim_id,
                "document_id": document_id, "document_version": candidate["document_version"],
                "run_id": candidate["run_id"], "context": self.context, "actor": self.actor,
                "decision": decision, "reason": reason, "reviewed_at": utc_now(),
                "supersedes_review_id": supersedes_review_id,
            }, candidate)
            self._insert("review", review_id, document_id, record)
            result = {"review": record, "revision": self._advance(document_id)}
            self._remember(request_id, fingerprint, result)
            return result

    def inspect(self, document_id):
        """A transaction-consistent snapshot with every source/review record."""
        with self.store.transaction():
            document = self._require_document(document_id)
            candidates = self._records("candidate", document_id)
            reviews = self._records("review", document_id)
            latest = {r["claim_id"]: r for r in reviews}
            superseded = {c["supersedes_claim_id"] for c in candidates}
            fields = {}
            for candidate in candidates:
                if candidate["claim_id"] in superseded:
                    continue
                review = latest.get(candidate["claim_id"])
                fields.setdefault(candidate["field"], []).append({"candidate": candidate, "review": review})
            holds, accepted = [], {}
            successors = self._successors(document_id)
            if successors:
                holds.append("Source version is superseded by " + ", ".join(d["document_id"] for d in successors))
            if document["document_class"] != "MEP_INVOICE":
                holds.append("No accepted-export policy is implemented for this document class")
            required = INVOICE_REQUIRED if document["document_class"] == "MEP_INVOICE" else ()
            for field in sorted(set(fields) | set(required)):
                active = [item for item in fields.get(field, []) if not item["review"] or item["review"]["decision"] != "reject"]
                if len(active) != 1 or active[0]["review"] is None:
                    if field in required or active:
                        holds.append(f"{field}: missing, pending or conflicting candidate")
                    continue
                item = active[0]
                run = self._record("extraction", item["candidate"]["run_id"])
                if run["status"] != "complete":
                    holds.append(f"{field}: source extraction is incomplete")
                    continue
                accepted[field] = item
            if "total_cents" in accepted and "currency" in accepted:
                if accepted["total_cents"]["candidate"]["currency"] != accepted["currency"]["candidate"]["value"]:
                    holds.append("total_cents: currency conflicts with the reviewed currency field")
            return {"schema_version": SCHEMA_VERSION, "document": document,
                    "archive": self._record("archive", document_id), "revision": self.revision(document_id),
                    "extractions": self._records("extraction", document_id), "candidates": candidates,
                    "reviews": reviews, "accepted_fields": accepted, "holds": holds,
                    "ready_for_export": not holds, "identity_assurance": "trusted_local_os_actor_labels",
                    "provider_connection": "disabled", "product_agents": False}

    def accepted_export(self, document_id):
        snapshot = self.inspect(document_id)
        if not snapshot["ready_for_export"]:
            raise ValueError("Accepted export is held: " + "; ".join(snapshot["holds"]))
        document = snapshot["document"]
        used_runs = {item["candidate"]["run_id"] for item in snapshot["accepted_fields"].values()}
        return {"schema_version": "br.docai-accepted.v1", "document": document,
                "revision": snapshot["revision"], "fields": snapshot["accepted_fields"],
                "extractions": [run for run in snapshot["extractions"] if run["run_id"] in used_runs],
                "source_status": document["source_status"], "identity_assurance": snapshot["identity_assurance"],
                "execution_authority": "none", "exported_at": utc_now()}
