"""Financial and event-tree acceptance checks for the non-AI probability engine."""

from copy import deepcopy
from fractions import Fraction
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from pilot.offer_probability import batch_expected_values, evaluate_packet
from pilot.underwriting import Economics, purchase_limits


FIXTURE = Path(__file__).resolve().parents[1] / "data" / "offer_probability" / "duplex.json"


def case():
    return json.loads(FIXTURE.read_text())


def indexed(report):
    return {offer["id"]: offer for offer in report["offers"]}


def exact(record):
    return Fraction(int(record["numerator"]), int(record["denominator"]))


class OfferProbabilityChecks(unittest.TestCase):
    def test_independently_calculated_duplex(self):
        report = evaluate_packet(case())
        rows = indexed(report)
        self.assertEqual(report["ranked_research_candidates"], ["D", "B", "E"])
        self.assertEqual([rows[x]["baseline_profit_cents"] for x in "AEBDC"],
                         [5500000, 5000000, 4700000, 4500000, 4200000])
        self.assertEqual([rows[x]["expected_profit_given_close_cents"] for x in "AEBDC"],
                         [4470000, 3970000, 3670000, 3470000, 3170000])
        self.assertEqual([rows[x]["event_tree"]["expected_net_cents_per_attempt"] for x in "EBDC"],
                         [787375, 1342525, 1850925, 2619500])
        self.assertEqual(rows["C"]["decision_state"], "policy_rejected")
        self.assertEqual(rows["A"]["decision_state"], "policy_rejected")
        self.assertEqual(rows["D"]["event_tree"]["probability_acquisition"], 0.5525)
        self.assertEqual(rows["D"]["event_tree"]["probability_acquire_and_meet_floor"], 0.38675)
        self.assertEqual(rows["C"]["probability_floor_given_close"], 0.2)
        self.assertFalse(report["runtime_agents_enabled"])
        self.assertFalse(report["execution"]["ai_runtime_used"])
        self.assertEqual(report["decision_scope"], "research_only")
        self.assertFalse(report["probabilities_validated_by_engine"])
        json.dumps(report, allow_nan=False)

    def test_terminal_totals_and_costs_are_not_double_counted(self):
        for row in evaluate_packet(case())["offers"]:
            if row["event_tree"] is None:
                continue
            tree = row["event_tree"]
            self.assertEqual(sum(exact(b["probability_exact"]) for b in tree["branches"]), 1)
            self.assertEqual(tree["branches"][0]["total_net_cash_cents"], -50000)
            self.assertEqual(tree["branches"][1]["total_net_cash_cents"], -500000)
            self.assertEqual(sum(exact(b["probability_exact"])*b["total_net_cash_cents"] for b in tree["branches"]),
                             exact(tree["expected_net_cents_per_attempt_exact"]))

    def test_policy_mean_and_chance_are_not_baseline_policy(self):
        for mode in ("expected_conditional", "chance_conditional"):
            packet = case()
            packet["policy"]["mode"] = mode
            self.assertEqual(evaluate_packet(packet)["ranked_research_candidates"], [])
        packet = case()
        packet["policy"].update(mode="chance_conditional", required_floor_probability_bp=7000)
        self.assertEqual(evaluate_packet(packet)["ranked_research_candidates"], ["D", "B", "E"])

    def test_exact_ceiling_and_discrete_chance_boundary(self):
        report = evaluate_packet(case())
        ceiling = next(c for c in report["price_ceilings"] if c["closing_days"] == 60)
        self.assertEqual(ceiling["baseline_floor_price_cents"], 50700000)
        self.assertEqual(ceiling["expected_conditional_floor_price_cents"], 49670000)
        self.assertEqual(ceiling["chance_floor_price_cents"], 46750000)
        self.assertEqual(ceiling["all_modeled_scenarios_floor_price_cents"], 40450000)
        for price, expected in ((46750000, 0.95), (46750001, 0.70)):
            packet = case()
            packet["offers"][2]["price_cents"] = price
            self.assertEqual(indexed(evaluate_packet(packet))["B"]["probability_floor_given_close"], expected)

    def test_distinct_timing_cost_packages_have_distinct_ceilings(self):
        packet = case()
        packet["offers"][2]["incremental_timing_cents"] += 100000
        report = evaluate_packet(packet)
        ceiling = next(c for c in report["price_ceilings"] if c["incremental_timing_cents"] == 400000)
        self.assertEqual(ceiling["expected_conditional_floor_price_cents"], 49570000)
        self.assertEqual(indexed(report)["B"]["baseline_profit_cents"], 4600000)

    def test_unknown_probabilities_are_not_zero_or_invented(self):
        packet = case()
        packet["policy"]["required_closing_days"] = None
        report = evaluate_packet(packet)
        self.assertEqual(indexed(report)["A"]["decision_state"], "probability_unknown")
        self.assertIsNone(indexed(report)["A"]["event_tree"])
        packet["closing_given_agreement_bp"] = None
        report = evaluate_packet(packet)
        self.assertTrue(all(r["event_tree"] is None for r in report["offers"]))
        self.assertEqual(report["ranked_research_candidates"], [])

    def test_offer_specific_conditional_closing_override(self):
        packet = case()
        packet["offers"][2]["closing_given_agreement_bp"] = 10000
        self.assertEqual(indexed(evaluate_packet(packet))["B"]["event_tree"]["expected_net_cents_per_attempt"], 1624000)
        packet["offers"][2]["closing_given_agreement_bp"] = None
        self.assertIsNone(indexed(evaluate_packet(packet))["B"]["event_tree"])

    def test_event_boundary_cases(self):
        for agreement, closing, expected in ((0, 10000, -50000), (10000, 0, -500000), (10000, 10000, 3670000)):
            packet = case()
            packet["offers"][2]["agreement_bp"] = agreement
            packet["offers"][2]["closing_given_agreement_bp"] = closing
            self.assertEqual(indexed(evaluate_packet(packet))["B"]["event_tree"]["expected_net_cents_per_attempt"], expected)

    def test_live_counter_requires_explicit_premise(self):
        packet = case()
        c = packet["offers"][-1]
        for key in ("exact_terms", "authorized", "still_open", "effectively_accepted"):
            bad = deepcopy(packet)
            bad["offers"][-1]["counter_premise"][key] = False
            with self.assertRaises(ValueError):
                evaluate_packet(bad)
        c["agreement_bp"] = 6500
        with self.assertRaises(ValueError):
            evaluate_packet(packet)
        packet = case()
        packet["offers"][2]["counter_premise"] = dict(packet["offers"][-1]["counter_premise"])
        with self.assertRaises(ValueError):
            evaluate_packet(packet)

    def test_fee_rounding_matches_existing_underwriting(self):
        packet = case()
        packet["selling_cost_bp"] = 500
        packet["scenarios"][1]["resale_cents"] = 100001
        row = indexed(evaluate_packet(packet))["B"]
        terms = Economics(resale_cents=100001, renovation_cents=3500000+1150000+1500000,
                          carrying_cents=1800000+300000, selling_bps=500, stress_price_drop_bps=0,
                          stress_extra_cents=0, base_profit_cents=0, stress_profit_cents=0, financing_cap_cents=None)
        self.assertEqual(row["baseline_profit_cents"], purchase_limits(terms)["base"]-50500000)

    def test_fractional_cents_are_preserved_and_price_ceiling_floors(self):
        packet = case()
        for key in ("selling_cost_bp", "buyer_closing_cents", "spent_additional_allowance_cents",
                    "no_agreement_total_loss_cents", "agreement_no_close_total_loss_cents"):
            packet[key] = 0
        packet["required_profit_cents"] = 1
        packet["scenarios"] = [dict(id="baseline", weight_bp=5000, resale_cents=2, renovation_cents=0, carry_cents=0),
                               dict(id="strong", weight_bp=5000, resale_cents=3, renovation_cents=0, carry_cents=0)]
        packet["offers"] = [dict(id="tiny", kind="new_offer", price_cents=1, closing_days=60,
                                 incremental_timing_cents=0, agreement_bp=3333, closing_given_agreement_bp=6667)]
        report = evaluate_packet(packet)
        row = report["offers"][0]
        self.assertEqual(exact(row["expected_profit_given_close_cents_exact"]), Fraction(3, 2))
        self.assertEqual(exact(row["event_tree"]["expected_net_cents_per_attempt_exact"]),
                         Fraction(3333,10000)*Fraction(6667,10000)*Fraction(3,2))
        self.assertEqual(report["price_ceilings"][0]["expected_conditional_floor_price_cents"], 1)
        self.assertEqual(exact(report["price_ceilings"][0]["expected_conditional_unrounded_price_cents_exact"]), Fraction(3,2))

    def test_packet_is_immutable_and_revision_changes_digest(self):
        packet = case()
        original = deepcopy(packet)
        report = evaluate_packet(packet)
        self.assertEqual(packet, original)
        packet["scenarios"][1]["renovation_cents"] += 2000000
        changed = evaluate_packet(packet)
        self.assertNotEqual(report["input_sha256"], changed["input_sha256"])
        self.assertEqual(indexed(changed)["B"]["baseline_profit_cents"], 2700000)

    def test_exact_json_integers_survive_cross_language_transport(self):
        packet = case()
        packet["offers"][2].update(agreement_bp=3333, closing_given_agreement_bp=6667)
        packet["scenarios"][0]["resale_cents"] = 999999999991
        report = json.loads(json.dumps(evaluate_packet(packet)))
        fraction = indexed(report)["B"]["event_tree"]["expected_net_cents_per_attempt_exact"]
        self.assertIsInstance(fraction["numerator"], str)
        self.assertIsInstance(fraction["denominator"], str)
        self.assertGreater(abs(int(fraction["numerator"])), 2**53)
        self.assertEqual(report["exact_integer_encoding"], "base10_strings")

    def test_external_estimate_is_not_a_calibration_certificate(self):
        packet = case()
        packet["probability_basis"] = "external_estimate"
        with self.assertRaises(ValueError):
            evaluate_packet(packet)
        packet["probability_reference"] = "external-model-run-123"
        self.assertFalse(evaluate_packet(packet)["probabilities_validated_by_engine"])

    def test_invalid_packet_types_ranges_schema_and_ids(self):
        modifications = [
            ("schema_version", "2"), ("currency", "EUR"), ("as_of", "2026-02-30"),
            ("timezone", "Unknown/Zone"), ("selling_cost_bp", True),
            ("selling_cost_bp", 10001), ("buyer_closing_cents", 1.5),
            ("required_profit_cents", -1), ("closing_given_agreement_bp", float("nan")),
            ("illustrative", "yes"), ("deal_id", "bad id"), ("offers", []),
            ("scenarios", []), ("provenance", ""),
        ]
        for key, value in modifications:
            with self.subTest(field=key):
                packet = case(); packet[key] = value
                with self.assertRaises(ValueError):
                    evaluate_packet(packet)
        for packet in ({}, {**case(), "unrecognized": 1}, {**case(), 1: "non-string-key"}):
            with self.assertRaises(ValueError):
                evaluate_packet(packet)
        for collection in ("scenarios", "offers"):
            packet = case(); packet[collection].append(deepcopy(packet[collection][0]))
            with self.assertRaises(ValueError):
                evaluate_packet(packet)
        packet = case(); packet["scenarios"][0]["weight_bp"] -= 1
        with self.assertRaises(ValueError):
            evaluate_packet(packet)

    def test_explicit_cuda_failure_never_falls_back(self):
        for unknown in (False, True):
            packet = case()
            if unknown:
                packet["closing_given_agreement_bp"] = None
            with patch("pilot.offer_probability._cuda_backend", side_effect=RuntimeError("CUDA unavailable")):
                with self.assertRaisesRegex(RuntimeError, "CUDA unavailable"):
                    evaluate_packet(packet, backend="cuda")
        with self.assertRaises(ValueError):
            evaluate_packet(case(), backend="auto")


@unittest.skipUnless(importlib.util.find_spec("numpy"), "Optional NumPy batch adapter is unavailable")
class ProbabilityBatchChecks(unittest.TestCase):
    def test_batch_order_boundaries_and_exact_reference(self):
        values = batch_expected_values([2500,4500,6500,10000,0], [8500]*5,
                                       [3970000,3670000,3470000,3170000,10],50000,500000)
        self.assertEqual(values.tolist(), [787375,1342525,1850925,2619500,-50000])

    def test_batch_rejects_malformed_data(self):
        cases = [([],[],[]), ([True],[8500],[1]), ([4500.0],[8500],[1]),
                 ([4500],[8500,8500],[1]), ([[4500]],[[8500]],[[1]]),
                 ([10001],[8500],[1]), ([4500],[8500],[float("inf")]),
                 ([4500],[8500],[True]), ([4500],[8500],[10**15])]
        for a,q,mean in cases:
            with self.subTest(agreement=a, closing=q, mean=mean):
                with self.assertRaises(ValueError):
                    batch_expected_values(a,q,mean,50000,500000)

    @unittest.skipUnless(os.environ.get("BLACK_RIVER_TEST_CUDA") == "1", "Real CUDA verification is opt-in")
    def test_real_cuda_parity(self):
        report = evaluate_packet(case(), backend="cuda")
        self.assertTrue(report["execution"]["cuda_executed"])
        self.assertLessEqual(report["execution"]["max_parity_difference_cents"], 0.01)


if __name__ == "__main__":
    unittest.main()
