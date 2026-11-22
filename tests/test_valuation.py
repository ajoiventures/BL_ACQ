"""Cash-flow, terminal, claims, shock and inverse-model regression cases."""

from copy import deepcopy
import json
import unittest

from pilot.valuation import reverse_growth, sensitivity_grid, value_model


def corporate(**changes):
    return {"revenue": 100.0, "operating_margin": 0.20, "growth_rate": 0.0,
            "target_margin": 0.20, "tax_rate": 0.25, "wacc": 0.10,
            "terminal_growth": 0.0, "sales_to_capital": 2.0, "terminal_roic": 0.12,
            "years": 5, "cash": 10.0, "non_operating_assets": 3.0, "debt": 20.0,
            "debt_like_claims": 5.0, "units": 2.0} | changes


def property_case(**changes):
    return {"noi": 100.0, "growth_rate": 0.10, "discount_rate": 0.10,
            "terminal_cap_rate": 0.10, "annual_capex": 10.0,
            "selling_cost_rate": 0.10, "years": 2, "debt": 200.0,
            "cash": 20.0, "units": 1} | changes


class CashFlowTests(unittest.TestCase):
    def test_level_corporate_perpetuity_and_equity_bridge(self):
        # $100 sales * 20% margin * (1 - 25% tax) / 10% WACC = $150 EV.
        for horizon in (1, 2, 5, 30):
            with self.subTest(horizon=horizon):
                result = value_model("corporate_dcf", corporate(years=horizon))
                self.assertAlmostEqual(result["enterprise_value"], 150.0)
                self.assertAlmostEqual(result["net_claims"], 12.0)
                self.assertAlmostEqual(result["equity_value"], 138.0)
                self.assertAlmostEqual(result["value_per_unit"], 69.0)
                self.assertAlmostEqual(result["terminal_value"], 150.0)
                self.assertAlmostEqual(result["pv_terminal"], 150 / 1.1 ** horizon)

    def test_growth_and_margin_fade_and_required_reinvestment(self):
        a = corporate(growth_rate=.20, terminal_growth=.02, target_margin=.35, years=3)
        result = value_model("corporate_dcf", a)
        for row, growth, revenue, margin in zip(result["forecast"], [.20, .11, .02],
                                               [120, 133.2, 135.864], [.25, .30, .35]):
            self.assertAlmostEqual(row["growth_rate"], growth)
            self.assertAlmostEqual(row["revenue"], revenue)
            self.assertAlmostEqual(row["operating_margin"], margin)
        self.assertAlmostEqual(result["forecast"][0]["fcf"], 12.5)
        terminal_nopat = 135.864 * 1.02 * .35 * .75
        self.assertAlmostEqual(result["terminal_cash_flow"], terminal_nopat * (1 - .02 / .12))
        self.assertAlmostEqual(result["terminal_value"], terminal_nopat * (1 - .02 / .12) / .08)

    def test_one_year_growth_is_initial_growth(self):
        result = value_model("corporate_dcf", corporate(years=1, growth_rate=.2, terminal_growth=.02))
        self.assertAlmostEqual(result["forecast"][0]["revenue"], 120)
        self.assertAlmostEqual(result["effective_terminal_growth"], .02)

    def test_losses_receive_no_tax_credit_or_automatic_asset_release(self):
        result = value_model("corporate_dcf", corporate(operating_margin=-.8, years=2, growth_rate=-.2))
        first, second = result["forecast"]
        self.assertLess(first["operating_profit"], 0)
        self.assertEqual(first["tax"], 0)
        self.assertEqual(first["nopat"], first["operating_profit"])
        self.assertEqual(first["reinvestment"], 0)
        self.assertAlmostEqual(second["tax"], second["operating_profit"] * .25)

    def test_negative_fcf_and_equity_are_retained(self):
        a = corporate(operating_margin=.05, target_margin=.05, tax_rate=0,
                      growth_rate=.5, years=2, sales_to_capital=.1)
        result = value_model("corporate_dcf", a)
        self.assertAlmostEqual(result["forecast"][0]["fcf"], -492.5)
        self.assertLess(result["enterprise_value"], 0)
        self.assertLess(result["equity_value"], 0)
        self.assertIsNone(result["terminal_share"])
        self.assertTrue(any("negative" in item.lower() for item in result["warnings"]))

    def test_property_exit_uses_next_year_noi_and_end_year_discount(self):
        result = value_model("property_dcf", property_case())
        terminal = 133.1 / .1 * .9
        enterprise = 100 / 1.1 + 111 / 1.1 ** 2 + terminal / 1.1 ** 2
        self.assertAlmostEqual(result["terminal_noi"], 133.1)
        self.assertAlmostEqual(result["terminal_value"], terminal)
        self.assertAlmostEqual(result["enterprise_value"], enterprise)
        self.assertAlmostEqual(result["equity_value"], enterprise - 180)
        self.assertAlmostEqual(result["value_per_unit"], result["equity_value"])
        self.assertEqual(result["forecast"][0]["tax"], 0)

    def test_cumulative_discount_paths_and_lead_reinvestment(self):
        a = corporate(years=2, growth_path=[.2, .1], margin_path=[.2, .3],
                      tax_path=[0, .25], discount_path=[.1, .2], terminal_growth=.02,
                      reinvestment_timing="next_year")
        result = value_model("corporate_dcf", a)
        first, second = result["forecast"]
        self.assertAlmostEqual(first["reinvestment"], (132 - 120) / 2)
        self.assertAlmostEqual(second["reinvestment"], (132 * 1.02 - 132) / 2)
        self.assertAlmostEqual(second["discount_factor"], 1 / (1.1 * 1.2))
        self.assertAlmostEqual(result["effective_discount_rate"], .2)
        self.assertAlmostEqual(result["terminal_nopat"], 132 * 1.02 * .2 * .75)

    def test_published_workbook_numeric_reproduction_is_not_a_quote(self):
        # Numerical audit of the supplied historical workbook; its evidence status
        # and treatment of commitments remain the caller's responsibility.
        a = corporate(
            revenue=302970e6, operating_margin=.65, growth_rate=.45, target_margin=.5,
            tax_rate=.25, wacc=.0979423938135254, terminal_growth=.0495,
            sales_to_capital=1.206668138058751, terminal_roic=.12, years=10,
            cash=56586e6, non_operating_assets=51157e6, debt=38351e6,
            debt_like_claims=448070655203.99054, units=24315e6,
            growth_path=[.45, .2, .2, .2, .2, .1699, .1398, .1097, .0796, .0495],
            margin_path=[.65, .59, .56, .53, .5, .5, .5, .5, .5, .5],
            tax_path=[.175] * 5 + [.19, .205, .22, .235, .25],
            discount_path=[.0979423938135254] * 5 + [.09635391505082032,
                .09476543628811523, .09317695752541015, .09158847876270507, .09],
            reinvestment_timing="next_year")
        result = value_model("corporate_dcf", a)
        self.assertAlmostEqual(result["enterprise_value"], 5229292259308.031, delta=.02)
        self.assertAlmostEqual(result["equity_value"], 4850613604104.04, delta=.02)
        self.assertAlmostEqual(result["value_per_unit"], 199.49058622677524, places=10)


class ShockTests(unittest.TestCase):
    def test_zero_shock_exactly_recovers_base_and_never_mutates_input(self):
        for model, a in (("corporate_dcf", corporate()), ("property_dcf", property_case())):
            original = deepcopy(a)
            zero = {"near_term_growth_delta": 0, "near_term_margin_delta": 0,
                    "long_term_growth_delta": 0, "long_term_margin_delta": 0,
                    "discount_rate_delta": 0, "reinvestment_multiplier": 1,
                    "one_time_cost": 0, "duration_years": 2}
            self.assertEqual(value_model(model, a), value_model(model, a, {}))
            self.assertEqual(value_model(model, a), value_model(model, a, zero))
            self.assertEqual(a, original)
            json.dumps(value_model(model, a), allow_nan=False)

    def test_temporary_margin_recovers_and_one_time_cost_is_once(self):
        a = corporate()
        base = value_model("corporate_dcf", a)
        shocked = value_model("corporate_dcf", a, {
            "near_term_margin_delta": -.05, "duration_years": 2, "one_time_cost": 11})
        expected_drop = 100 * .05 * .75 / 1.1 + 100 * .05 * .75 / 1.1 ** 2 + 11 / 1.1
        self.assertAlmostEqual(base["enterprise_value"] - shocked["enterprise_value"], expected_drop)
        self.assertEqual(base["forecast"][2:], shocked["forecast"][2:])
        self.assertEqual(base["terminal_value"], shocked["terminal_value"])

    def test_temporary_growth_rate_recovers_but_level_does_not(self):
        a = corporate(growth_rate=.10, terminal_growth=.02, years=4)
        base = value_model("corporate_dcf", a)
        shocked = value_model("corporate_dcf", a, {"near_term_growth_delta": -.05, "duration_years": 1})
        self.assertEqual(base["forecast"][1]["growth_rate"], shocked["forecast"][1]["growth_rate"])
        self.assertLess(shocked["forecast"][-1]["revenue"], base["forecast"][-1]["revenue"])
        self.assertEqual(shocked["effective_terminal_growth"], .02)

    def test_permanent_margin_terminal_reinvestment_and_discount_shocks(self):
        a = corporate(growth_rate=.1, terminal_growth=.02)
        result = value_model("corporate_dcf", a, {"long_term_growth_delta": .01,
            "long_term_margin_delta": -.02, "discount_rate_delta": .01,
            "reinvestment_multiplier": 2})
        self.assertAlmostEqual(result["forecast"][-1]["growth_rate"], .03)
        self.assertAlmostEqual(result["effective_terminal_growth"], .02)
        self.assertAlmostEqual(result["effective_terminal_margin"], .18)
        self.assertAlmostEqual(result["effective_discount_rate"], .11)
        self.assertAlmostEqual(result["effective_terminal_roic"], .06)
        self.assertAlmostEqual(result["terminal_reinvestment"], result["terminal_nopat"] * .02 / .06)

    def test_shocks_apply_to_explicit_paths(self):
        a = corporate(years=2, growth_path=[.1, .03], margin_path=[.2, .3],
                      tax_path=[.1, .2], discount_path=[.1, .12])
        result = value_model("corporate_dcf", a, {"near_term_growth_delta": -.02,
            "near_term_margin_delta": -.01, "long_term_growth_delta": .01,
            "long_term_margin_delta": .02, "discount_rate_delta": .01, "duration_years": 1})
        self.assertAlmostEqual(result["forecast"][0]["growth_rate"], .09)
        self.assertAlmostEqual(result["forecast"][1]["growth_rate"], .04)
        self.assertAlmostEqual(result["forecast"][0]["operating_margin"], .21)
        self.assertAlmostEqual(result["forecast"][1]["operating_margin"], .32)
        self.assertAlmostEqual(result["forecast"][1]["discount_factor"], 1 / (1.11 * 1.13))

    def test_property_shocks_have_separate_capex_and_noi_timing(self):
        result = value_model("property_dcf", property_case(), {
            "near_term_growth_delta": -.05, "long_term_growth_delta": .02,
            "reinvestment_multiplier": 2, "one_time_cost": 7, "duration_years": 1})
        first, second = result["forecast"]
        self.assertAlmostEqual(first["noi"], 107)
        self.assertAlmostEqual(first["fcf"], 80)
        self.assertAlmostEqual(second["noi"], 119.84)
        self.assertAlmostEqual(second["fcf"], 99.84)
        self.assertAlmostEqual(result["terminal_noi"], 119.84 * 1.12)


class InverseAndSensitivityTests(unittest.TestCase):
    def test_growth_inverse_recovers_known_rate_and_bounds(self):
        for model, a in (("corporate_dcf", corporate(growth_rate=.17)),
                         ("property_dcf", property_case(growth_rate=.17))):
            target = value_model(model, a)["value_per_unit"]
            result = reverse_growth(model, a, None, target)
            self.assertEqual(result["status"], "solved")
            self.assertAlmostEqual(result["implied_growth_rate"], .17, places=7)
            self.assertAlmostEqual(result["achieved_price"], target, places=6)
            endpoint = value_model(model, a | {"growth_rate": -.2})["value_per_unit"]
            self.assertEqual(reverse_growth(model, a, None, endpoint)["implied_growth_rate"], -.2)

    def test_out_of_range_returns_no_invented_rate(self):
        a = corporate()
        result = reverse_growth("corporate_dcf", a, None, 1e9)
        self.assertEqual(result["status"], "out_of_range")
        self.assertIsNone(result["implied_growth_rate"])
        self.assertIsNone(result["achieved_price"])
        self.assertLess(result["attainable_bounds"]["maximum"], 1e9)

    def test_known_inverse_root_preserves_accuracy_across_monetary_scales(self):
        known_growth = .123456
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            with self.subTest(scale=scale):
                a = corporate(growth_rate=.1, terminal_growth=.02, sales_to_capital=10)
                for key in ("revenue", "cash", "non_operating_assets", "debt", "debt_like_claims"):
                    a[key] *= scale
                target = value_model("corporate_dcf", a | {"growth_rate": known_growth})["value_per_unit"]
                result = reverse_growth("corporate_dcf", a, None, target)
                self.assertEqual(result["status"], "solved")
                self.assertAlmostEqual(result["implied_growth_rate"], known_growth, places=8)
                self.assertLessEqual(abs(result["achieved_price"] - target), result["price_tolerance"])
                self.assertLessEqual(abs(result["achieved_price"] / target - 1), 1e-10)

    def test_out_of_range_classification_preserves_monetary_scale(self):
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            with self.subTest(scale=scale):
                a = corporate(growth_rate=.1, terminal_growth=.02, sales_to_capital=10)
                for key in ("revenue", "cash", "non_operating_assets", "debt", "debt_like_claims"):
                    a[key] *= scale
                result = reverse_growth("corporate_dcf", a, None, 1000 * scale)
                self.assertEqual(result["status"], "out_of_range")
                self.assertIsNone(result["implied_growth_rate"])

    def test_zero_target_tolerance_uses_local_bridge_scale_not_distant_samples(self):
        known_growth = .123456
        a = corporate(years=30, growth_rate=.1, terminal_growth=.02, sales_to_capital=100,
                      cash=0, non_operating_assets=0, debt_like_claims=0)
        a["debt"] = value_model("corporate_dcf", a | {"growth_rate": known_growth, "debt": 0})["enterprise_value"]
        result = reverse_growth("corporate_dcf", a, None, 0, high=3)
        self.assertGreater(result["attainable_bounds"]["maximum"], 1e11)
        self.assertEqual(result["status"], "solved")
        self.assertAlmostEqual(result["implied_growth_rate"], known_growth, places=12)
        self.assertGreater(result["price_tolerance"], 0)
        self.assertLess(result["price_tolerance"], 1e-10)
        self.assertLessEqual(abs(result["achieved_price"]), result["price_tolerance"])

    def test_flat_curve_has_no_unique_inverse(self):
        # Positive-growth reinvestment exactly offsets growth's cash-flow value.
        a = corporate(years=1, tax_rate=0, sales_to_capital=1 / 2.2, growth_rate=.3)
        result = reverse_growth("corporate_dcf", a, None, 94, low=.01, high=.8)
        self.assertEqual(result["status"], "non_monotonic")
        self.assertIn("flat", result["reason"])
        self.assertIsNone(result["implied_growth_rate"])

    def test_value_destroying_growth_can_be_non_monotonic(self):
        # Below zero growth there is no disinvestment; above zero, poor capital
        # efficiency destroys value. The peak at zero makes a single inverse unsafe.
        a = corporate(years=2, tax_rate=0, sales_to_capital=.1)
        result = reverse_growth("corporate_dcf", a, None, 50)
        self.assertEqual(result["status"], "non_monotonic")
        self.assertIsNone(result["implied_growth_rate"])

    def test_decreasing_monotonic_curve_can_be_solved(self):
        a = corporate(years=2, tax_rate=0, sales_to_capital=.1, growth_rate=.3)
        target = value_model("corporate_dcf", a)["value_per_unit"]
        result = reverse_growth("corporate_dcf", a, None, target, low=.01, high=.8)
        self.assertEqual(result["status"], "solved")
        self.assertAlmostEqual(result["implied_growth_rate"], .3, places=7)

    def test_explicit_growth_path_has_no_scalar_inverse(self):
        a = corporate(growth_path=[0] * 5)
        result = reverse_growth("corporate_dcf", a, None, 69)
        self.assertEqual(result["status"], "unsupported_explicit_path")
        self.assertIsNone(result["implied_growth_rate"])

    def test_grid_center_matches_base_and_invalid_cells_are_explicit(self):
        a = corporate(wacc=.02, terminal_growth=.01)
        grid = sensitivity_grid("corporate_dcf", a, None)
        self.assertEqual((len(grid["cells"]), len(grid["cells"][0])), (5, 5))
        self.assertEqual(grid["cells"][2][2]["value_per_unit"], value_model("corporate_dcf", a)["value_per_unit"])
        self.assertIsNone(grid["cells"][0][0]["value_per_unit"])
        self.assertIn("exceed", grid["cells"][0][0]["reason"])
        p = sensitivity_grid("property_dcf", property_case(terminal_cap_rate=.005), None)
        self.assertIsNone(p["cells"][2][0]["value_per_unit"])
        self.assertTrue(p["cells"][2][0]["reason"])
        json.dumps(grid, allow_nan=False)

    def test_grid_parallel_shifts_explicit_discount_path(self):
        a = corporate(years=2, discount_path=[.12, .1])
        grid = sensitivity_grid("corporate_dcf", a, {"discount_rate_delta": .01})
        self.assertAlmostEqual(grid["row_values"][2], .11)
        expected = value_model("corporate_dcf", a | {"wacc": .11,
            "discount_path": [.13, .11]}, {"discount_rate_delta": .01})
        self.assertAlmostEqual(grid["cells"][3][2]["value_per_unit"], expected["value_per_unit"])


class ValidationTests(unittest.TestCase):
    def test_invalid_numbers_and_schema_are_rejected(self):
        cases = [{"revenue": True}, {"revenue": "100"}, {"revenue": float("nan")},
                 {"cash": float("inf")}, {"cash": 10 ** 500}, {"cash": 1e16},
                 {"years": True}, {"years": 1.5}, {"years": 0}, {"years": 31},
                 {"units": 0}, {"growth_rate": -1}, {"sales_to_capital": 0},
                 {"terminal_growth": -.01}, {"wacc": 0}, {"tax_rate": 1},
                 {"target_margin": 0}, {"terminal_growth": .15}, {"unknown": 1},
                 {"growth_path": [0]}, {"growth_path": [0, 0, 0, 0, True]},
                 {"discount_path": [-.1] * 5}, {"reinvestment_timing": "sometime"}]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ValueError):
                value_model("corporate_dcf", corporate(**change))
        with self.assertRaises(ValueError):
            value_model("unknown", corporate())
        with self.assertRaises(ValueError):
            value_model("corporate_dcf", {})
        with self.assertRaises(ValueError):
            value_model("corporate_dcf", None)

    def test_shocks_and_property_domains_are_validated(self):
        for shock in ({"unknown": 0}, {"duration_years": True}, {"one_time_cost": -1},
                      {"discount_rate_delta": float("inf")}, {"reinvestment_multiplier": -1},
                      {"near_term_growth_delta": -.9, "duration_years": 0},
                      {"long_term_margin_delta": -1}):
            with self.subTest(shock=shock), self.assertRaises(ValueError):
                value_model("corporate_dcf", corporate(), shock)
        with self.assertRaises(ValueError):
            value_model("corporate_dcf", corporate(terminal_growth=.08), {"reinvestment_multiplier": 2})
        with self.assertRaises(ValueError):
            value_model("corporate_dcf", corporate(), {"reinvestment_multiplier": 1e-320})
        for change in ({"terminal_cap_rate": 0}, {"units": 2}, {"annual_capex": -1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                value_model("property_dcf", property_case(**change))
        with self.assertRaises(ValueError):
            value_model("property_dcf", property_case(), {"near_term_margin_delta": -.01})
        for kwargs in ({"target_price": True}, {"target_price": 5, "low": .5, "high": .1}):
            with self.assertRaises(ValueError):
                reverse_growth("corporate_dcf", corporate(), None, **kwargs)


if __name__ == "__main__":
    unittest.main()
