"""Regression cases for qualification, purchase ceilings, approval and accounting."""

from dataclasses import replace
from datetime import timedelta
import unittest

from pilot.ledger import Invoice, Ledger, Receipt, Service
from pilot.scenario import deal_fixture, run_scenario
from pilot.underwriting import Approval, purchase_limits, qualify, underwrite


class DealTests(unittest.TestCase):
    def setUp(self):
        self.c, self.e, self.day = deal_fixture()

    def packet(self, candidate=None, economics=None, approval=None, bid=23_500_000):
        return underwrite(candidate or self.c, economics or self.e, bid, self.day, "analyst", approval)

    def test_three_binding_limits_and_ties(self):
        for economics, binding, ceiling in [
            (self.e, ["base"], 23_500_000),
            (replace(self.e, stress_profit_cents=3_000_000), ["downside"], 23_240_000),
            (replace(self.e, financing_cap_cents=22_000_000), ["financing"], 22_000_000),
            (replace(self.e, financing_cap_cents=23_500_000), ["base", "financing"], 23_500_000),
        ]:
            with self.subTest(binding=binding):
                packet = self.packet(economics=economics)
                self.assertEqual(packet["ceiling_cents"], ceiling)
                self.assertEqual(packet["binding_limits"], binding)
        self.assertEqual(purchase_limits(self.e)["downside"], 24_240_000)
        self.assertEqual(self.packet(bid=23_500_001)["state"], "review_required")
        self.assertIsNone(self.packet(economics=replace(self.e, financing_cap_cents=None))["ceiling_cents"])
        self.assertEqual(self.packet(economics=replace(self.e, resale_cents=1))["state"], "review_required")

    def test_evidence_scope_freshness_and_coverage(self):
        good = qualify(self.c, self.day)
        self.assertEqual(good["state"], "eligible")
        for substitute in (lambda row: replace(row, subject="other-deal"),
                           lambda row: replace(row, observed=self.day + timedelta(days=1)),
                           lambda row: replace(row, expires=self.day - timedelta(days=1)),
                           lambda row: replace(row, confirmed=False), lambda row: replace(row, source="")):
            candidate = replace(self.c, evidence=tuple(substitute(e) if e.kind == "financing" else e
                                                       for e in self.c.evidence))
            self.assertEqual(qualify(candidate, self.day)["state"], "review_required")
        same_sale = tuple(replace(e, reference="same-sale") if e.kind == "closed_comp" else e
                          for e in self.c.evidence)
        for candidate in (replace(self.c, evidence=same_sale), replace(self.c, longitude=190),
                          replace(self.c, latitude=float("nan")), replace(self.c, property_family="unknown")):
            self.assertEqual(self.packet(candidate)["state"], "review_required")

    def test_packet_bound_independent_approval(self):
        draft = self.packet()
        self.assertEqual(draft["state"], "awaiting_manual_review")
        approval = Approval("reviewer", draft["packet_digest"], self.day)
        self.assertEqual(self.packet(approval=approval)["state"], "bid_ready_simulation")
        for altered in (replace(approval, reviewer="Analyst "), replace(approval, packet_digest="old"),
                        replace(approval, reviewed_on=self.day - timedelta(days=1))):
            self.assertEqual(self.packet(approval=altered)["state"], "awaiting_manual_review")
        self.assertEqual(self.packet(approval=approval, bid=23_499_999)["state"], "awaiting_manual_review")
        self.assertEqual(self.packet(approval=approval, economics=replace(self.e, carrying_cents=1))["state"],
                         "awaiting_manual_review")
        for change in ({"landlocked": True}, {"surviving_liens_cents": None}, {"wetlands_bps": 5001},
                       {"evidence": tuple(e for e in self.c.evidence if e.kind != "title")}):
            self.assertEqual(self.packet(replace(self.c, **change), approval=approval)["state"], "review_required")
        self.assertEqual(self.packet(replace(self.c, wetlands_bps=5000))["state"], "awaiting_manual_review")


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.invoice = Invoice("property", "I1", "S1", 1000, "bill-proof", "preparer", "reviewer")
        self.receipt = Receipt("property", "I1", "R1", 1000, "bank-proof", "preparer", "reviewer")
        self.service = Service("property", "S1", "manager", "done-proof")

    def test_approval_invoice_receipt_and_replay(self):
        with self.assertRaises(ValueError):
            self.ledger.post_invoice(self.invoice)
        self.ledger.approve_service(self.service)
        self.ledger.post_invoice(self.invoice)
        self.ledger.post_invoice(self.invoice)
        open_report = self.ledger.report()
        self.assertEqual(open_report["invoices"][0]["state"], "open")
        self.assertEqual(open_report["consolidated_cents"]["cash"], 0)
        for bad in (replace(self.receipt, settlement_ref="bill-proof"),
                    replace(self.receipt, reviewed_by="PREPARER"),
                    replace(self.receipt, entity="other"), replace(self.receipt, amount_cents=999)):
            with self.subTest(receipt=bad), self.assertRaises(ValueError):
                self.ledger.post_receipt(bad)
        self.assertEqual(self.ledger.report(), open_report)
        self.ledger.post_receipt(self.receipt)
        self.ledger.post_receipt(self.receipt)
        paid_report = self.ledger.report()
        self.assertTrue(paid_report["reconciled"])
        self.assertEqual(paid_report["invoices"][0]["state"], "settled")
        self.assertEqual(len(paid_report["entries"]), 2)
        for bad in (replace(self.receipt, amount_cents=950), replace(self.receipt, receipt_id="R2")):
            with self.assertRaises(ValueError):
                self.ledger.post_receipt(bad)
        self.assertEqual(self.ledger.report(), paid_report)

    def test_four_entities_consolidate_and_share_no_receipt(self):
        report = run_scenario()["ledger"]
        self.assertEqual(len(report["entity_balances_cents"]), 4)
        self.assertEqual(report["consolidated_cents"],
                         {"cash": 205_000, "receivable": 80_000, "service_income": 285_000})
        self.assertTrue(report["reconciled"])
        for entity in ("first", "second"):
            self.ledger.approve_service(replace(self.service, entity=entity))
            self.ledger.post_invoice(replace(self.invoice, entity=entity))
        self.ledger.post_receipt(replace(self.receipt, entity="first"))
        with self.assertRaises(ValueError):
            self.ledger.post_receipt(replace(self.receipt, entity="second"))

    def test_evidence_cannot_change_role_across_entities_in_either_order(self):
        self.ledger.approve_service(self.service)
        self.ledger.post_invoice(self.invoice)
        extra = replace(self.service, entity="other", completion_ref="other-delivery")
        self.ledger.approve_service(extra)
        self.ledger.post_invoice(replace(self.invoice, entity="other", document_ref="other-bill"))
        opened = self.ledger.report()
        for ref in ("other-delivery", "other-bill"):
            with self.subTest(ref=ref), self.assertRaises(ValueError):
                self.ledger.post_receipt(replace(self.receipt, settlement_ref=ref))
        self.assertEqual(self.ledger.report(), opened)
        self.ledger.post_receipt(self.receipt)
        third = replace(self.service, entity="third", completion_ref="third-delivery")
        with self.assertRaises(ValueError):
            self.ledger.approve_service(replace(third, completion_ref=self.receipt.settlement_ref))
        self.ledger.approve_service(third)
        paid = self.ledger.report()
        with self.assertRaises(ValueError):
            self.ledger.post_invoice(replace(self.invoice, entity="third", document_ref=self.receipt.settlement_ref))
        self.assertEqual(self.ledger.report(), paid)
        self.ledger.post_invoice(replace(self.invoice, entity="third", document_ref="third-bill"))


if __name__ == "__main__":
    unittest.main()
