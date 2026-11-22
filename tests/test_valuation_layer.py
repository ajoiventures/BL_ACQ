"""Policy invariants: evidence holds, denominator semantics, and immutable inputs."""

from copy import deepcopy
import unittest

from pilot.valuation_layer import evaluate


def request_fixture():
    return {
        "schema_version": "1.0", "deal_id": "valuation-test", "asset_id": "asset-test",
        "as_of": "2026-11-21", "model_type": "corporate_dcf", "currency": "USD",
        "assumptions": {"revenue": 100, "operating_margin": 1, "growth_rate": 0,
                        "target_margin": 1, "tax_rate": 0, "wacc": .10, "terminal_growth": 0,
                        "sales_to_capital": 2, "terminal_roic": .10, "years": 5,
                        "cash": 0, "non_operating_assets": 0, "debt": 0,
                        "debt_like_claims": 0, "units": 10},
        "market": {"price": 70, "as_of": "2026-11-21", "source_id": "price"},
        "policy": {"margin_of_safety": .30, "max_downside_probability": .35,
                   "max_source_age_days": 365, "max_quote_age_days": 7},
        "sources": [
            {"id": name, "title": "Verified test evidence", "url": "https://example.org/" + name,
             "observed_on": "2026-11-21", "verified": True, "kind": kind, "notes": "Test only"}
            for name, kind in [("inputs", "financials"), ("price", "quote"), ("gates", "qualification")]
        ],
        "input_source_ids": ["inputs"],
        "scenarios": [{"id": "unchanged", "label": "Unchanged operations", "probability": 1,
                       "shock": {}, "source_ids": ["inputs"]}],
        "qualification": {name: "confirmed" for name in ("buyable", "fundable", "sellable")},
        "qualification_source_ids": {name: ["gates"] for name in ("buyable", "fundable", "sellable")},
        "claims": [], "illustrative": False,
    }


class ValuationLayerTests(unittest.TestCase):
    def test_perpetuity_price_discount_and_upside_have_distinct_denominators(self):
        packet = request_fixture()
        original = deepcopy(packet)
        result = evaluate(packet)
        self.assertAlmostEqual(result["baseline"]["value_per_unit"], 100)
        self.assertAlmostEqual(result["decision"]["entry_ceiling"], 70)
        self.assertAlmostEqual(result["decision"]["discount_to_value"], .30)
        self.assertAlmostEqual(result["decision"]["upside"], 3 / 7)
        self.assertEqual(result["decision"]["status"], "review_candidate")
        self.assertFalse(result["decision"]["execution_allowed"])
        self.assertEqual(packet, original)

    def test_event_effect_and_safety_discount_are_separate(self):
        packet = request_fixture()
        packet["scenarios"] = [
            {"id": "base", "label": "Base", "probability": .5, "shock": {}, "source_ids": ["inputs"]},
            {"id": "event", "label": "Margin impairment", "probability": .5,
             "shock": {"long_term_margin_delta": -.2}, "source_ids": ["inputs"]},
        ]
        result = evaluate(packet)
        self.assertAlmostEqual(result["decision"]["adjusted_value"], 90)
        self.assertAlmostEqual(result["decision"]["entry_ceiling"], 63)
        self.assertAlmostEqual(result["decision"]["baseline_entry_reference"], 70)
        self.assertEqual(result["decision"]["status"], "watch")

    def test_small_valid_prices_do_not_bypass_entry_or_scenario_policy(self):
        packet = request_fixture()
        packet["assumptions"]["revenue"] = 1e-10
        packet["market"]["price"] = 1e-9
        result = evaluate(packet)
        decision = result["decision"]
        self.assertAlmostEqual(decision["market_price"] / decision["adjusted_value"], 10)
        self.assertEqual(decision["status"], "watch")
        self.assertEqual(decision["downside_probability"], 1)
        self.assertTrue(any("entry ceiling" in reason for reason in decision["reasons"]))

    def test_price_policy_is_invariant_under_economically_equivalent_scaling(self):
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            for price, status, downside in ((70, "review_candidate", 0),
                                             (71, "watch", 0), (110, "watch", 1)):
                with self.subTest(scale=scale, price=price):
                    packet = request_fixture()
                    packet["assumptions"]["revenue"] *= scale
                    packet["market"]["price"] = price * scale
                    decision = evaluate(packet)["decision"]
                    self.assertAlmostEqual(decision["adjusted_value"] / scale, 100)
                    self.assertAlmostEqual(decision["entry_ceiling"] / scale, 70)
                    self.assertEqual(decision["status"], status)
                    self.assertEqual(decision["downside_probability"], downside)

    def test_probability_weights_are_not_silently_normalized(self):
        packet = request_fixture()
        for probability in (.8, True, float("nan"), float("inf")):
            packet["scenarios"][0]["probability"] = probability
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                evaluate(packet)

    def test_missing_stale_future_and_unreviewed_sources_hold(self):
        mutations = [
            lambda p: p["market"].update(as_of=None),
            lambda p: p["market"].update(as_of="2026-10-01"),
            lambda p: p["market"].update(as_of="2026-11-22"),
            lambda p: p["sources"][0].update(verified=False),
            lambda p: p["sources"][0].update(observed_on="2022-10-31"),
            lambda p: p["sources"][0].update(issues=["Conflicting financial date"]),
            lambda p: p.update(illustrative=True),
        ]
        for mutate in mutations:
            packet = request_fixture()
            mutate(packet)
            with self.subTest(packet=packet):
                report = evaluate(packet)
                self.assertEqual(report["decision"]["status"], "hold")
                self.assertTrue(report["decision"]["reasons"])

    def test_independent_gates_need_separate_support(self):
        packet = request_fixture()
        packet["qualification_source_ids"]["fundable"] = []
        result = evaluate(packet)
        self.assertEqual(result["decision"]["qualification"]["fundable"]["status"], "unknown")
        self.assertEqual(result["decision"]["qualification"]["buyable"]["status"], "confirmed")
        self.assertEqual(result["decision"]["status"], "hold")

    def test_quote_source_kind_age_and_date_must_support_the_price(self):
        mutations = [
            (lambda p: p["sources"][1].update(kind="financials"), "identified as a quote"),
            (lambda p: p["sources"][1].update(observed_on="2026-10-01"), "quote-age policy"),
            (lambda p: p["sources"][1].update(observed_on="2026-11-20"), "later than its supporting"),
        ]
        for mutate, message in mutations:
            packet = request_fixture()
            mutate(packet)
            with self.subTest(message=message):
                result = evaluate(packet)
                self.assertEqual(result["decision"]["status"], "hold")
                self.assertTrue(any(message in issue for issue in result["evidence"]["issues"]))

    def test_exact_probability_policy_boundary_does_not_fail_from_roundoff(self):
        packet = request_fixture()
        packet["policy"]["max_downside_probability"] = .3
        packet["market"]["price"] = 50
        packet["scenarios"] = [
            {"id": "base", "label": "Base", "probability": .7, "shock": {}, "source_ids": ["inputs"]},
            {"id": "loss_a", "label": "Loss A", "probability": .1,
             "shock": {"long_term_margin_delta": -.7}, "source_ids": ["inputs"]},
            {"id": "loss_b", "label": "Loss B", "probability": .2,
             "shock": {"long_term_margin_delta": -.7}, "source_ids": ["inputs"]},
        ]
        result = evaluate(packet)
        self.assertAlmostEqual(result["decision"]["downside_probability"], .3)
        self.assertEqual(result["decision"]["status"], "review_candidate")
        packet["policy"]["max_downside_probability"] = .299
        self.assertEqual(evaluate(packet)["decision"]["status"], "watch")

    def test_duplicate_or_double_counted_claim_rejected(self):
        packet = request_fixture()
        packet["assumptions"]["debt_like_claims"] = 20
        claim = {"id": "obligation", "amount": 20, "in_cash_flows": False,
                 "in_equity_bridge": True, "source_id": "inputs"}
        packet["claims"] = [claim]
        self.assertAlmostEqual(evaluate(packet)["baseline"]["value_per_unit"], 98)
        packet["claims"] = [claim, deepcopy(claim)]
        with self.assertRaisesRegex(ValueError, "twice"):
            evaluate(packet)
        packet["claims"] = [claim | {"in_cash_flows": True}]
        with self.assertRaisesRegex(ValueError, "exactly one"):
            evaluate(packet)
        packet["claims"] = [claim | {"amount": 30}]
        with self.assertRaisesRegex(ValueError, "exceed"):
            evaluate(packet)

    def test_digest_changes_for_value_evidence_and_policy(self):
        original = request_fixture()
        digest = evaluate(original)["packet_digest"]
        for mutate in (
            lambda p: p["assumptions"].update(revenue=110),
            lambda p: p["policy"].update(margin_of_safety=.2),
            lambda p: p["sources"][0].update(notes="Revised source"),
        ):
            changed = deepcopy(original)
            mutate(changed)
            self.assertNotEqual(evaluate(changed)["packet_digest"], digest)
        self.assertEqual(evaluate(original)["packet_digest"], digest)

    def test_unreconciled_bridge_balances_remain_on_hold(self):
        packet = request_fixture()
        packet["assumptions"]["debt_like_claims"] = 20
        result = evaluate(packet)
        self.assertEqual(result["decision"]["status"], "hold")
        self.assertEqual(result["obligations"]["unreconciled_bridge_total"], 20)
        packet["claims"] = [{"id": "lease", "amount": 20, "in_cash_flows": False,
                             "in_equity_bridge": True, "source_id": "inputs"}]
        result = evaluate(packet)
        self.assertEqual(result["obligations"]["status"], "reconciled")
        self.assertEqual(result["obligations"]["unreconciled_bridge_total"], 0)

    def test_claim_reconciliation_preserves_small_balances_and_rejects_scaled_overclaims(self):
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            with self.subTest(scale=scale):
                packet = request_fixture()
                packet["assumptions"]["revenue"] *= scale
                packet["market"]["price"] = 40 * scale
                packet["assumptions"]["debt_like_claims"] = 20 * scale
                missing = evaluate(packet)
                self.assertEqual(missing["obligations"]["status"], "review_required")
                self.assertEqual(missing["decision"]["status"], "hold")
                claim = {"id": "lease", "amount": 20 * scale, "in_cash_flows": False,
                         "in_equity_bridge": True, "source_id": "inputs"}
                packet["claims"] = [claim]
                self.assertEqual(evaluate(packet)["obligations"]["status"], "reconciled")
                claim["amount"] = 20.2 * scale
                with self.assertRaisesRegex(ValueError, "exceed"):
                    evaluate(packet)
                packet["assumptions"]["debt_like_claims"] = 0
                claim["amount"] = 20 * scale
                with self.assertRaisesRegex(ValueError, "exceed"):
                    evaluate(packet)

    def test_absent_price_produces_no_implied_growth_or_allocation(self):
        packet = request_fixture()
        packet["market"]["price"] = None
        report = evaluate(packet)
        self.assertEqual(report["reverse_dcf"]["status"], "missing_price")
        self.assertIsNone(report["decision"]["upside"])
        self.assertEqual(report["decision"]["status"], "hold")

    def test_capital_limit_respects_reserves_concentration_and_holds(self):
        packet = request_fixture()
        packet["capital"] = {"available_cash": 1000, "reserve_floor": 400,
                             "portfolio_value": 10000, "max_position_fraction": .05,
                             "existing_asset_exposure": 100, "max_loss_budget": 100,
                             "transaction_cost_rate": 0, "quantity_step": 1}
        result = evaluate(packet)
        self.assertEqual(result["capital"]["proposed_units"], 5)
        self.assertEqual(result["capital"]["cash_committed"], 0)
        packet["illustrative"] = True
        self.assertEqual(evaluate(packet)["capital"]["proposed_units"], 0)

    def test_unknown_fields_and_opening_balance_override_are_rejected(self):
        packet = request_fixture()
        packet["scenarios"][0]["assumptions_override"] = {"units": 2}
        with self.assertRaises(ValueError):
            evaluate(packet)
        packet = request_fixture() | {"auto_trade": True}
        with self.assertRaises(ValueError):
            evaluate(packet)

    def test_whole_asset_capital_limit_cannot_buy_multiple_or_fractional_properties(self):
        packet = request_fixture()
        packet["model_type"] = "property_dcf"
        packet["assumptions"] = {"noi": 100, "growth_rate": 0, "discount_rate": .1,
                                 "terminal_cap_rate": .1, "annual_capex": 0,
                                 "selling_cost_rate": 0, "years": 5,
                                 "debt": 0, "cash": 0, "units": 1}
        packet["capital"] = {"available_cash": 10000, "reserve_floor": 0,
                             "portfolio_value": 100000, "max_position_fraction": .5,
                             "max_loss_budget": 10000, "quantity_step": 1}
        self.assertEqual(evaluate(packet)["capital"]["proposed_units"], 1)
        packet["capital"]["quantity_step"] = .25
        with self.assertRaisesRegex(ValueError, "quantity_step=1"):
            evaluate(packet)

    def test_market_price_bound_matches_inverse_solver_bound(self):
        packet = request_fixture()
        packet["market"]["price"] = 1e15
        self.assertEqual(evaluate(packet)["reverse_dcf"]["status"], "out_of_range")
        packet["market"]["price"] = 1e15 + 1
        with self.assertRaisesRegex(ValueError, "market.price"):
            evaluate(packet)


if __name__ == "__main__":
    unittest.main()
