"""Immutable valuation snapshots and idempotent receipts in the pilot database."""

from datetime import datetime, timezone
import hashlib
import json
import re

from .contracts import Evidence
from .valuation_layer import evaluate


SCHEMA = """
CREATE TABLE IF NOT EXISTS valuation_runs (
 scope TEXT NOT NULL, run_id TEXT NOT NULL, deal_id TEXT NOT NULL, asset_id TEXT NOT NULL,
 packet_digest TEXT NOT NULL, model_version TEXT NOT NULL, created_at TEXT NOT NULL,
 created_by TEXT NOT NULL, link_type TEXT NOT NULL, request_json TEXT NOT NULL, report_json TEXT NOT NULL,
 PRIMARY KEY(scope,run_id), UNIQUE(scope,packet_digest));
CREATE INDEX IF NOT EXISTS valuation_deal_runs ON valuation_runs(scope,deal_id,created_at);
CREATE TABLE IF NOT EXISTS valuation_receipts (
 scope TEXT NOT NULL, actor TEXT NOT NULL, request_id TEXT NOT NULL, packet_digest TEXT NOT NULL,
 run_id TEXT NOT NULL, PRIMARY KEY(scope,actor,request_id),
 FOREIGN KEY(scope,run_id) REFERENCES valuation_runs(scope,run_id));
"""


class Conflict(ValueError):
    """An idempotency key or canonical identity was reused inconsistently."""


def initialize(connection):
    connection.executescript(SCHEMA)


def _stored_run(row):
    """Verify stored request identity without recomputing historical valuation."""
    try:
        request = json.loads(row["request_json"])
        report = json.loads(row["report_json"])
        if not isinstance(request, dict) or not isinstance(report, dict):
            raise ValueError("Stored snapshots must be objects")
        digest = hashlib.sha256(json.dumps(
            {"model_version": row["model_version"], "request": request},
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode()).hexdigest()
        # Also reject nonfinite values in report metadata/results, but retain the
        # historical result rather than rerunning today's model or source policy.
        json.dumps(report, allow_nan=False)
        consistent = (
            digest == row["packet_digest"] == report["packet_digest"]
            and row["run_id"] == "VR-" + digest[:24]
            and row["model_version"] == report["model_version"]
            and row["deal_id"] == request["deal_id"] == report["deal_id"]
            and row["asset_id"] == request["asset_id"] == report["asset_id"]
            and request == report["request"]
            and request["schema_version"] == report["schema_version"]
            and request["model_type"] == report["model_type"]
            and request["as_of"] == report["as_of"]
            and request.get("currency", "USD") == report["currency"]
        )
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise Conflict("Stored valuation snapshot is malformed or inconsistent") from exc
    if not consistent:
        raise Conflict("Stored valuation request digest or identity mismatch")
    return {"run_id": row["run_id"], "packet_digest": row["packet_digest"],
            "created_at": row["created_at"], "created_by": row["created_by"],
            "link_type": row["link_type"], "request": request, "report": report}


def _check_deal_identity(store, deal_id, asset_id):
    """One deal keeps one asset even before a canonical parcel deal exists."""
    deal = store.get_deal(deal_id)
    if deal and deal.parcel_id != asset_id:
        raise Conflict("The asset ID disagrees with the existing deal's permanent parcel identity")
    previous = store.connection.execute(
        "SELECT DISTINCT asset_id FROM valuation_runs WHERE scope=? AND deal_id=?",
        (store.scope, deal_id),
    ).fetchall()
    if any(row["asset_id"] != asset_id for row in previous):
        raise Conflict("The asset ID disagrees with this research deal's saved permanent identity")
    return deal


def save_run(store, request_id, packet):
    if store.scope != "commercial":
        raise PermissionError("Valuation research belongs to the commercial workspace")
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{8,80}", request_id):
        raise ValueError("A valid request_id is required")
    report = evaluate(packet)
    digest = report["packet_digest"]
    run_id = "VR-" + digest[:24]
    # Persist the evaluator's frozen copy, not a caller-owned dictionary that
    # could be changed between evaluation and the write transaction.
    frozen_request = report["request"]
    with store.transaction():
        deal = _check_deal_identity(store, report["deal_id"], report["asset_id"])
        prior = store.connection.execute(
            "SELECT packet_digest,run_id FROM valuation_receipts WHERE scope=? AND actor=? AND request_id=?",
            (store.scope, store.actor, request_id),
        ).fetchone()
        if prior and prior["packet_digest"] != digest:
            raise Conflict("This operation ID is already bound to another valuation")
        if prior:
            saved = get_run(store, prior["run_id"])
            if saved is None or saved["packet_digest"] != digest or saved["run_id"] != run_id:
                raise Conflict("Stored operation receipt disagrees with its valuation")
            return saved
        existing = store.connection.execute(
            "SELECT * FROM valuation_runs WHERE scope=? AND (run_id=? OR packet_digest=?)",
            (store.scope, run_id, digest),
        ).fetchall()
        if len(existing) > 1:
            raise Conflict("Stored valuation identities are inconsistent")
        if existing:
            saved = _stored_run(existing[0])
            if saved["packet_digest"] != digest or saved["run_id"] != run_id:
                raise Conflict("Valuation run ID conflicts with another request digest")
        else:
            link_type = "existing_parcel_deal" if deal else "research_deal"
            created_at = datetime.now(timezone.utc).isoformat()
            store.connection.execute(
                """INSERT INTO valuation_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (store.scope, run_id, report["deal_id"], report["asset_id"], digest, report["model_version"],
                 created_at, store.actor, link_type,
                 json.dumps(frozen_request, sort_keys=True, allow_nan=False),
                 json.dumps(report, sort_keys=True, allow_nan=False)),
            )
            saved = get_run(store, run_id)
        if deal:
            store.save(Evidence("valuation-" + digest, deal.deal_id, "valuation",
                                "Black River valuation research packet " + saved["report"]["model_version"],
                                saved["report"]["as_of"],
                                json.dumps(saved["report"], sort_keys=True, allow_nan=False)))
        store.connection.execute(
            "INSERT INTO valuation_receipts VALUES (?,?,?,?,?)",
            (store.scope, store.actor, request_id, digest, run_id),
        )
        return saved


def get_run(store, run_id):
    row = store.connection.execute(
        "SELECT * FROM valuation_runs WHERE scope=? AND run_id=?", (store.scope, run_id)
    ).fetchone()
    if row is None:
        return None
    return _stored_run(row)


def list_runs(store):
    rows = store.connection.execute(
        "SELECT * FROM valuation_runs WHERE scope=? ORDER BY rowid DESC LIMIT 100", (store.scope,)
    ).fetchall()
    result = []
    for row in rows:
        snapshot = _stored_run(row)
        report = snapshot["report"]
        result.append({"run_id": row["run_id"], "deal_id": row["deal_id"], "asset_id": row["asset_id"],
                       "created_at": row["created_at"], "created_by": row["created_by"],
                       "packet_digest": row["packet_digest"], "model_version": row["model_version"],
                       "model_type": report["model_type"], "as_of": report["as_of"],
                       "status": report["decision"]["status"],
                       "adjusted_value": report["decision"]["adjusted_value"]})
    return result
