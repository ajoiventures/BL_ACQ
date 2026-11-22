"""Document input changes must preserve provenance, policy and probability semantics."""

from copy import deepcopy
import csv
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pilot.document_offer_layer import evaluate_with_evidence, export_r_review
from tools.run_document_offer import renovation_bindings, run_demo


ROOT = Path(__file__).resolve().parents[1]


def packet_fixture():
    return json.loads((ROOT/"data/offer_probability/duplex.json").read_text())


class ReviewedProjection:
    """A deliberately small public-contract double; real SQLite is used by run_demo."""
    def __init__(self, value=5_500_000, *, currency="USD", provenance=True):
        self.value, self.currency, self.provenance = value, currency, provenance

    def project_inputs(self, deal_id, as_of, *, required_fields):
        return {"state": "ready", "deal_id": deal_id, "as_of": as_of, "illustrative": True,
                "facts": {field: {"value": self.value, "value_type": "money_cents", "unit": "cents",
                                  "currency": self.currency, "provenance": [{"claim_id": "test-claim"}] if self.provenance else []}
                          for field in required_fields}}


class DocumentOfferLayerTests(unittest.TestCase):
    def test_complete_workflow_without_network_or_ai_credentials(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "NVIDIA_API_KEY": "", "ANTHROPIC_API_KEY": ""}), \
                patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            report = run_demo()
        stages = report["stages"]
        for key in ("unreviewed", "revision_pending"):
            self.assertEqual(stages[key]["status"], "evidence_review_required")
            self.assertIsNone(stages[key]["after_evidence"])
        old = {o["id"]: o for o in stages["original_reviewed"]["after_evidence"]["offers"]}
        new = {o["id"]: o for o in stages["revision_reviewed"]["after_evidence"]["offers"]}
        self.assertEqual(old["B"]["baseline_profit_cents"], 4_700_000)
        self.assertEqual(old["B"]["expected_profit_given_close_cents"], 3_670_000)
        self.assertEqual(new["B"]["baseline_profit_cents"], 2_700_000)
        self.assertEqual(new["B"]["expected_profit_given_close_cents"], 1_670_000)
        self.assertEqual(new["B"]["probability_loss_given_close"], .30)
        self.assertFalse(any(o["policy_passed"] for o in new.values()))
        for stage in stages.values():
            self.assertFalse(stage["execution_allowed"])
            self.assertFalse(stage["ai_enabled"])
            self.assertFalse(stage["runtime_agents_enabled"])

    def test_explicit_scenario_buffers_and_input_immutability(self):
        packet = packet_fixture(); original = deepcopy(packet)
        bindings = renovation_bindings(packet); before = deepcopy(bindings)
        report = evaluate_with_evidence(ReviewedProjection(), packet, bindings)
        self.assertEqual(packet, original)
        self.assertEqual(bindings, before)
        changes = {c["record_id"]: c for c in report["changes"]}
        self.assertEqual(changes["baseline"]["analyst_offset_cents"], 0)
        self.assertEqual(changes["slow_costlier"]["analyst_offset_cents"], 1_000_000)
        self.assertEqual(changes["severe"]["analyst_offset_cents"], 2_000_000)
        self.assertTrue(all(c["delta_cents"] == 2_000_000 for c in changes.values()))
        old = report["baseline"]["offers"][2]["event_tree"]
        new = report["after_evidence"]["offers"][2]["event_tree"]
        # Only economics changed: the current action's acquisition probability did not.
        self.assertEqual(old["probability_acquisition"], new["probability_acquisition"])

    def test_probability_and_policy_targets_are_rejected(self):
        packet = packet_fixture()
        for group, identity, key in (("offer", "B", "agreement_bp"), ("global", None, "required_profit_cents"),
                                     ("scenario", "baseline", "weight_bp"), ("global", None, "closing_given_agreement_bp")):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "whitelisted"):
                evaluate_with_evidence(ReviewedProjection(), packet, [
                    {"field": "any", "group": group, "record_id": identity, "key": key, "offset_cents": 0}])

    def test_changed_live_counter_terms_hold_the_whole_projection(self):
        packet = packet_fixture()
        report = evaluate_with_evidence(ReviewedProjection(50_700_000), packet, [
            {"field": "counter_price", "group": "offer", "record_id": "C", "key": "price_cents", "offset_cents": 0}])
        self.assertIsNone(report["after_evidence"])
        self.assertEqual(report["application_blockers"][0]["code"], "live_counter_terms_changed")
        self.assertEqual(report["changes"], [])

    def test_changed_new_offer_terms_require_probability_revalidation(self):
        packet = packet_fixture()
        for identity in ("A", "B"):
            for key, value in (("price_cents", 50_700_000), ("incremental_timing_cents", 500_000)):
                with self.subTest(offer=identity, key=key):
                    report = evaluate_with_evidence(ReviewedProjection(value), packet, [
                        {"field": "changed_terms", "group": "offer", "record_id": identity,
                         "key": key, "offset_cents": 0}])
                    self.assertIsNone(report["after_evidence"])
                    self.assertEqual(report["application_blockers"][0]["code"], "offer_probability_context_changed")
                    self.assertEqual(report["changes"], [])

    def test_economic_changes_hold_externally_estimated_probabilities(self):
        packet = packet_fixture()
        packet["probability_basis"] = "external_estimate"
        packet["probability_reference"] = "external-model/version-1/input-context-1"
        report = evaluate_with_evidence(ReviewedProjection(), packet, renovation_bindings(packet))
        self.assertIsNone(report["after_evidence"])
        self.assertEqual(report["application_blockers"][0]["code"], "external_probability_context_changed")
        self.assertEqual(report["changes"], [])

    def test_synthetic_evidence_cannot_lose_its_illustrative_label(self):
        packet = packet_fixture()
        packet["illustrative"] = False
        report = evaluate_with_evidence(ReviewedProjection(), packet, renovation_bindings(packet))
        self.assertFalse(report["baseline"]["illustrative"])
        self.assertTrue(report["illustrative"])
        self.assertTrue(report["after_evidence"]["illustrative"])

    def test_currency_type_provenance_and_bounds_fail_closed(self):
        packet = packet_fixture(); bindings = renovation_bindings(packet)
        for source in (ReviewedProjection(currency="EUR"), ReviewedProjection(True), ReviewedProjection(1.25),
                       ReviewedProjection(provenance=False), ReviewedProjection(-1), ReviewedProjection(10**12+1)):
            with self.subTest(source=vars(source)), self.assertRaises(ValueError):
                evaluate_with_evidence(source, packet, bindings)

    def test_duplicate_unknown_and_malformed_bindings_are_rejected(self):
        packet = packet_fixture(); bindings = renovation_bindings(packet)
        bad = [[], [bindings[0], bindings[0]], [dict(bindings[0], record_id="missing")],
               [dict(bindings[0], offset_cents=True)], [dict(bindings[0], key=[])],
               [dict(bindings[0], extra="not_allowed")]]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate_with_evidence(ReviewedProjection(), packet, value)

    def test_r_exchange_preserves_exact_strings_and_unknowns(self):
        report = run_demo()["stages"]["revision_reviewed"]
        with TemporaryDirectory() as directory:
            path = Path(directory)/"exchange"
            manifest = export_r_review(report, path)
            self.assertFalse(manifest["R_executed"])
            with (path/"offer_review.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 10)
            b = next(r for r in rows if r["case"] == "after_evidence" and r["offer_id"] == "B")
            self.assertEqual(b["mean_profit_cents_numerator"], "1670000")
            self.assertEqual(b["mean_profit_cents_denominator"], "1")
            self.assertTrue(all(r["ev_cents_numerator"] == "" for r in rows if r["offer_id"] == "A"))
            with self.assertRaises(FileExistsError):
                export_r_review(report, path)

    def test_r_exchange_rejects_unreviewed_or_tampered_reports(self):
        demo = run_demo()
        with TemporaryDirectory() as directory:
            for report in (demo["stages"]["unreviewed"], deepcopy(demo["stages"]["revision_reviewed"])):
                report["currency"] = "EUR"
                with self.assertRaises(ValueError):
                    export_r_review(report, Path(directory)/"rejected")
                self.assertFalse((Path(directory)/"rejected").exists())


if __name__ == "__main__":
    unittest.main()
