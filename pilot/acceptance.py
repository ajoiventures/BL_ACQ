"""Run one synthetic deal through acquisition, settlement and SQLite recovery."""
from contextlib import closing
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from .contracts import Evidence
from .founder_service import RECORD, SCOPE, mutate, prepare, read_record
from .ledger import Invoice, Ledger, Receipt, Service
from .storage import Store


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def approved_packet(store):
    """Only the independently reviewed, approved revision can authorize this simulation."""
    require(store.get_deal(RECORD) is not None, "Deal not found")
    snapshot = read_record(store.connection, "founder")
    require(snapshot["underwriting"]["state"] == "bid_ready_simulation", "Deal requires current approval")
    require([(e["actor"], e["action"]) for e in snapshot["events"]] ==
            [("reviewer", "review"), ("founder", "approve")], "Missing independent decision trail")
    approvals = [d for d in store.decisions_for(RECORD) if d.outcome == "approve"]
    evidence = {item.evidence_id: item for item in store.evidence_for(RECORD)}
    # The reviewed version is resolved through the durable FK, not a second underwriting run.
    digest = snapshot["underwriting"]["packet_digest"]
    matching = [a for a in approvals if a.evidence_id in evidence
                and json.loads(evidence[a.evidence_id].value).get("packet_digest") == digest]
    require(len(matching) == 1, "Approval evidence differs from the active underwriting revision")
    return matching[0], digest


def record_service_events(store, approval, digest):
    """Create four entity-level service fixtures for the same approved deal handling."""
    for entity, amount, paid in (("commercial", 125_000, True), ("property", 30_000, False),
                                 ("family", 50_000, False), ("client", 80_000, True)):
        identity = f"{approval.deal_id}/{entity}"
        job = identity + "/service"
        bill = identity + "/invoice"
        receipt = identity + "/receipt"
        records = [
            ("service", Service(entity, job, "founder", identity + "/delivery-doc"), job),
            ("invoice", Invoice(entity, bill, job, amount, bill + "-doc", "bookkeeper", "controller"), bill),
        ]
        if paid:
            records.append(("receipt", Receipt(entity, bill, receipt, amount, receipt + "-doc",
                                               "bookkeeper", "controller"), receipt))
        for kind, record, identifier in records:
            source = record.completion_ref if kind == "service" else (
                record.document_ref if kind == "invoice" else record.settlement_ref)
            payload = {"approval_decision_id": approval.decision_id, "approved_packet_digest": digest,
                       "record": asdict(record)}
            store.save(Evidence(identifier, approval.deal_id, kind, source, "2026-11-20",
                                json.dumps(payload, sort_keys=True)))


def reconcile(store, approval, digest):
    """Rebuild the accounting result solely from the persisted source events in order."""
    ledger = Ledger()
    handlers = {"service": (Service, ledger.approve_service), "invoice": (Invoice, ledger.post_invoice),
                "receipt": (Receipt, ledger.post_receipt)}
    for item in store.evidence_for(approval.deal_id):
        if item.kind not in handlers:
            continue
        payload = json.loads(item.value)
        require((payload["approval_decision_id"], payload["approved_packet_digest"]) ==
                (approval.decision_id, digest), "Accounting evidence references a different approval")
        event_type, post = handlers[item.kind]
        post(event_type(**payload["record"]))
    report = ledger.report()
    require(report["reconciled"] and len(report["entity_balances_cents"]) == 4,
            "Expected balanced statements for four entities")
    require(len(report["invoices"]) == 4 and sum(i["state"] == "settled" for i in report["invoices"]) == 2,
            "Expected two settled and two outstanding service invoices")
    require(report["consolidated_cents"] ==
            {"cash": 205_000, "receivable": 80_000, "service_income": 285_000},
            "Ledger amounts differ from the synthetic service contracts")
    return report


def settle(store):
    with store.transaction():
        approval, digest = approved_packet(store)
        task_id = approval.decision_id + "/settlement"
        queued = store.enqueue(task_id, RECORD, "approved-service-settlement")
        if queued.state == "completed":
            return task_id, reconcile(store, approval, digest)
        task = store.claim(request_id=task_id)
        require(task is not None and task.task_id == task_id, "Approved settlement task was not claimed")
        record_service_events(store, approval, digest)
        report = reconcile(store, approval, digest)
        store.complete(task, "Independent service and receipt entries reconciled")
    return task_id, report


def recovery_snapshot(store, settlement_task):
    """Capture record and receipt data independently of the SQLite file representation."""
    approval, digest = approved_packet(store)
    return {
        "deal": store.get_deal(RECORD), "evidence": store.evidence_for(RECORD),
        "decisions": store.decisions_for(RECORD), "ledger": reconcile(store, approval, digest),
        "intake_history": store.history("orchard-intake"), "settlement_history": store.history(settlement_task),
        "founder": {name: [tuple(row) for row in store.connection.execute(f"SELECT * FROM {name} ORDER BY rowid")]
                   for name in ("founder_drafts", "founder_actions", "founder_receipts")},
    }


def acceptance(directory):
    original = Path(directory) / "pilot.sqlite3"
    restored = Path(directory) / "restored.sqlite3"
    if original.exists() or restored.exists():
        raise FileExistsError("Use a fresh directory for the acceptance run")
    prepare(original)
    with Store(original, scope=SCOPE, actor="pilot-intake") as store:
        store.enqueue("orchard-intake", RECORD, "qualification")
        task = store.claim(request_id="orchard-intake-poll")
        require(task is not None and task.task_id == "orchard-intake", "Intake task was not claimed")
        store.complete(task, "Synthetic intake evidence reviewed")

    for actor, action, version in (("reviewer", "draft", 0), ("reviewer", "review", 0),
                                   ("founder", "approve", 1)):
        with Store(original, scope=SCOPE, actor=actor) as store:
            snapshot = read_record(store.connection, actor)
            body = {"request_id": "pilot-" + action, "scope": SCOPE, "record": RECORD,
                    "action": action, "note": "Synthetic pilot evidence checked",
                    "evidence": snapshot["evidence"], "version": version}
            response = mutate(store, actor, body)
            if action == "draft":
                require(response["draft"]["version"] == 1, "Draft checkpoint was not persisted")
            else:
                require(len(response["events"]) == version + 1, "Unexpected decision count")

    with Store(original, scope=SCOPE, actor="pilot-reconciler") as store:
        settlement_task, ledger = settle(store)
        before = recovery_snapshot(store, settlement_task)
    with closing(sqlite3.connect(original)) as source, closing(sqlite3.connect(restored)) as target:
        source.backup(target)
        require(target.execute("PRAGMA integrity_check").fetchone() == ("ok",), "Backup integrity check failed")
        require(not target.execute("PRAGMA foreign_key_check").fetchall(), "Restored evidence has broken links")
    with Store(restored, scope=SCOPE, actor="founder") as store:
        after = recovery_snapshot(store, settlement_task)
        require(before == after, "Restored workflow differs from the original")
        # Replay the final request after restart to prove its receipt survived backup.
        require(mutate(store, "founder", body) == response, "Restored approval receipt differs")
        require(recovery_snapshot(store, settlement_task) == after, "Receipt replay changed the restored history")
    return {"mode": "synthetic", "deal": RECORD, "review_events": len(after["decisions"]),
            "settled_invoices": sum(i["state"] == "settled" for i in ledger["invoices"]),
            "reconciled": ledger["reconciled"], "restored": True}


if __name__ == "__main__":
    with TemporaryDirectory() as directory:
        print(json.dumps(acceptance(directory), sort_keys=True))
