"""Simulation of externally paid service invoices, reviewed by entity."""

from collections import defaultdict
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Service:
    entity: str
    service_id: str
    authorized_by: str
    completion_ref: str


@dataclass(frozen=True)
class Invoice:
    entity: str
    invoice_id: str
    service_id: str
    amount_cents: int
    document_ref: str
    prepared_by: str
    reviewed_by: str


@dataclass(frozen=True)
class Receipt:
    entity: str
    invoice_id: str
    receipt_id: str
    amount_cents: int
    settlement_ref: str
    prepared_by: str
    reviewed_by: str


@dataclass(frozen=True)
class Entry:
    entity: str
    event_id: str
    invoice_id: str
    debit: str
    credit: str
    amount_cents: int
    evidence: str
    prepared_by: str
    reviewed_by: str


def _validate(record):
    for key, value in asdict(record).items():
        if key == "amount_cents":
            continue
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError("A nonblank, unpadded identifier is required")
    if isinstance(record, (Invoice, Receipt)):
        if type(record.amount_cents) is not int or record.amount_cents <= 0:
            raise ValueError("Amount must be positive integer cents")
        if record.prepared_by.casefold() == record.reviewed_by.casefold():
            raise ValueError("An independent reviewer is required")


class Ledger:
    """Accrual entries debit receivables on invoice and clear them on verified receipt."""

    def __init__(self):
        self._services = {}
        self._invoices = {}
        self._receipts = {}
        self._settled = set()
        self._invoiced_services = set()
        self._service_and_invoice_refs = set()
        self._settlement_refs = set()
        self._entries = []

    @staticmethod
    def _replay(records, key, event):
        if key not in records:
            return False
        if records[key] != event:
            raise ValueError("Conflicting replay of an existing record")
        return True

    def approve_service(self, service: Service):
        _validate(service)
        key = (service.entity, service.service_id)
        if self._replay(self._services, key, service):
            return
        if service.completion_ref in self._settlement_refs:
            raise ValueError("A receipt cannot also evidence service completion")
        self._services[key] = service
        self._service_and_invoice_refs.add(service.completion_ref)

    def post_invoice(self, invoice: Invoice):
        _validate(invoice)
        key = (invoice.entity, invoice.invoice_id)
        if self._replay(self._invoices, key, invoice):
            return
        service_key = (invoice.entity, invoice.service_id)
        if service_key not in self._services or service_key in self._invoiced_services:
            raise ValueError("Invoice requires an approved, completed, unbilled service in this entity")
        if invoice.document_ref in self._settlement_refs:
            raise ValueError("A receipt cannot also evidence an invoice")
        self._entries.append(Entry(invoice.entity, invoice.invoice_id, invoice.invoice_id,
                                   "receivable", "service_income", invoice.amount_cents,
                                   invoice.document_ref, invoice.prepared_by, invoice.reviewed_by))
        self._invoices[key] = invoice
        self._invoiced_services.add(service_key)
        self._service_and_invoice_refs.add(invoice.document_ref)

    def post_receipt(self, receipt: Receipt):
        _validate(receipt)
        key = (receipt.entity, receipt.receipt_id)
        if self._replay(self._receipts, key, receipt):
            return
        invoice_key = (receipt.entity, receipt.invoice_id)
        invoice = self._invoices.get(invoice_key)
        if invoice is None or invoice_key in self._settled:
            raise ValueError("Receipt requires an open invoice in the same entity")
        if receipt.amount_cents != invoice.amount_cents:
            raise ValueError("Receipt differs from the full invoice amount")
        if (receipt.settlement_ref in self._service_and_invoice_refs or
                receipt.settlement_ref in self._settlement_refs):
            raise ValueError("Distinct, unused settlement evidence is required")
        self._entries.append(Entry(receipt.entity, receipt.receipt_id, receipt.invoice_id,
                                   "cash", "receivable", receipt.amount_cents,
                                   receipt.settlement_ref, receipt.prepared_by, receipt.reviewed_by))
        self._receipts[key] = receipt
        self._settled.add(invoice_key)
        self._settlement_refs.add(receipt.settlement_ref)

    def report(self) -> dict:
        by_entity = {entity: {"cash": 0, "receivable": 0, "service_income": 0}
                     for entity, _ in sorted(self._services)}
        for entry in self._entries:
            balances = by_entity[entry.entity]
            balances[entry.debit] += entry.amount_cents
            balances[entry.credit] += entry.amount_cents if entry.credit == "service_income" else -entry.amount_cents
        combined = {account: sum(row[account] for row in by_entity.values())
                    for account in ("cash", "receivable", "service_income")}
        invoice_states = [{"entity": entity, "invoice_id": invoice_id,
                           "state": "settled" if (entity, invoice_id) in self._settled else "open"}
                          for entity, invoice_id in sorted(self._invoices)]
        # Compare posted balances with an independent sum of the accepted source records.
        expected = defaultdict(lambda: {"cash": 0, "receivable": 0, "service_income": 0})
        for invoice in self._invoices.values():
            expected[invoice.entity]["service_income"] += invoice.amount_cents
            expected[invoice.entity]["receivable"] += invoice.amount_cents
        for receipt in self._receipts.values():
            expected[receipt.entity]["cash"] += receipt.amount_cents
            expected[receipt.entity]["receivable"] -= receipt.amount_cents
        reconciled = all(balances == expected[entity] for entity, balances in by_entity.items())
        return {"entity_balances_cents": by_entity, "consolidated_cents": combined,
                "reconciled": reconciled, "invoices": invoice_states,
                "entries": [asdict(entry) for entry in self._entries]}
