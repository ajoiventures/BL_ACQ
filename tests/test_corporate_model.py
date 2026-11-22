"""Independent arithmetic, accounting, timing and boundary cases for linked statements."""

from copy import deepcopy
import unittest

from pilot.corporate_model import project_statements


def opening(**changes):
    # Assets 600 = liabilities 250 + equity 350. Amounts are deliberately small
    # dollars so every expected result below can be checked by hand.
    return {
        "period_end": "2025-08-31", "revenue": 1000.0, "cash": 100.0,
        "accounts_receivable": 100.0, "inventory": 80.0,
        "operating_other_current_assets": 20.0, "other_current_assets": 10.0,
        "net_ppe": 200.0, "net_intangibles": 50.0, "other_noncurrent_assets": 40.0,
        "accounts_payable": 50.0, "operating_accruals": 30.0,
        "other_current_liabilities": 20.0, "debt": 100.0,
        "other_noncurrent_liabilities": 50.0, "equity": 350.0,
        "retained_earnings": 200.0, "shares": 100.0, "tax_loss_carryforward": 0.0,
    } | changes


def driver(**changes):
    return {
        "period_end": "2026-08-31", "revenue_growth": .10, "gross_margin": .50,
        "ebitda_margin": .20, "depreciation_rate": .10, "amortization": 5.0,
        "capex_pct_revenue": .05, "intangible_capex": 3.0, "receivable_days": 36.5,
        "inventory_days": 73.0, "payable_days": 36.5,
        "operating_other_current_assets_pct_revenue": .02,
        "operating_accruals_pct_revenue": .03, "tax_rate": .25,
        "nol_utilization_limit": .80, "interest_rate": .05, "debt_issued": 20.0,
        "debt_repaid": 30.0, "dividend_payout": .40,
        "stock_compensation_pct_revenue": .01, "stock_compensation_share_price": 11.0,
        "equity_issued": 10.0, "issuance_share_price": 5.0, "shares_repurchased": 2.0,
        "repurchase_share_price": 4.0, "minimum_cash": 0.0,
    } | changes


def simple_opening(**changes):
    record = {key: 0.0 for key in opening() if key != "period_end"}
    record.update(period_end="2025-08-31", revenue=1000.0, cash=100.0, equity=100.0,
                  shares=10.0)
    return record | changes


def simple_driver(**changes):
    record = {key: 0.0 for key in driver() if key != "period_end"}
    record.update(period_end="2026-08-31", gross_margin=1.0, ebitda_margin=.20,
                  tax_rate=.25, nol_utilization_limit=.80,
                  stock_compensation_share_price=1.0, issuance_share_price=1.0,
                  repurchase_share_price=1.0)
    return record | changes


class StatementArithmeticTests(unittest.TestCase):
    def test_hand_calculated_full_statement_case(self):
        report = project_statements(opening(), [driver()])
        row = report["forecast"][0]
        expected = {
            "revenue": 1100, "cogs": 550, "gross_profit": 550, "ebitda": 220,
            "operating_expenses_before_da": 330, "cash_operating_expenses_before_da": 319,
            "depreciation": 20, "amortization": 5, "ebit": 195,
            "interest_expense": 5, "pretax_income": 190, "tax_expense": 47.5,
            "net_income": 142.5, "accounts_receivable": 110, "inventory": 110,
            "operating_other_current_assets": 22, "accounts_payable": 55,
            "operating_accruals": 33, "opening_nwc": 120, "nwc": 154, "delta_nwc": 34,
            "ppe_capex": 55, "intangible_capex": 3, "capex": 58, "net_ppe": 235,
            "net_intangibles": 48, "stock_compensation": 11, "dividends": 57,
            "cash_from_operations": 144.5, "cash_from_investing": -58,
            "cash_from_financing": -65, "change_in_cash": 21.5, "cash": 121.5,
            "debt": 90, "retained_earnings": 285.5, "other_equity": 163,
            "equity": 448.5, "total_assets": 696.5, "total_liabilities": 248,
            "total_liabilities_and_equity": 696.5, "shares": 101,
            "weighted_average_shares": 100, "eps": 1.425,
            "fcff": 79.25, "fcfe_before_cash_equity_transactions": 76.5,
        }
        for key, expected_value in expected.items():
            with self.subTest(key=key):
                self.assertAlmostEqual(row[key], expected_value, places=10)
        self.assertEqual(report["status"], "calculated")
        self.assertTrue(report["checks"]["all_reconciled"])

    def test_multi_period_statements_and_independent_rollforwards(self):
        assumptions = [driver(period_end=f"{2026 + year}-08-31", debt_repaid=10)
                       for year in range(5)]
        report = project_statements(opening(), assumptions)
        previous = opening()
        for row in report["forecast"]:
            assets = sum(row[key] for key in ("cash", "accounts_receivable", "inventory",
                         "operating_other_current_assets", "other_current_assets", "net_ppe",
                         "net_intangibles", "other_noncurrent_assets"))
            liabilities = sum(row[key] for key in ("accounts_payable", "operating_accruals",
                              "other_current_liabilities", "debt", "other_noncurrent_liabilities"))
            self.assertAlmostEqual(assets, liabilities + row["equity"], places=9)
            self.assertAlmostEqual(row["cash"] - previous["cash"],
                                   row["cash_from_operations"] + row["cash_from_investing"]
                                   + row["cash_from_financing"], places=9)
            self.assertAlmostEqual(row["retained_earnings"] - previous["retained_earnings"],
                                   row["net_income"] - row["dividends"], places=9)
            for key in ("other_current_assets", "other_noncurrent_assets",
                        "other_current_liabilities", "other_noncurrent_liabilities"):
                self.assertEqual(row[key], previous[key])
            previous = row
        self.assertTrue(report["checks"]["all_reconciled"])

    def test_sbc_is_expensed_added_back_and_diluted_but_not_added_to_fcff(self):
        with_sbc = project_statements(simple_opening(), [simple_driver(
            stock_compensation_pct_revenue=.02, stock_compensation_share_price=10)])["forecast"][0]
        without_sbc = project_statements(simple_opening(), [simple_driver()])["forecast"][0]
        # EBITDA margin is held constant: its total expense already includes SBC.
        self.assertEqual(with_sbc["ebitda"], without_sbc["ebitda"])
        self.assertEqual(with_sbc["fcff"], without_sbc["fcff"])
        self.assertEqual(with_sbc["cash_from_operations"] - without_sbc["cash_from_operations"], 20)
        self.assertEqual(with_sbc["equity"] - without_sbc["equity"], 20)
        self.assertEqual(with_sbc["shares"] - without_sbc["shares"], 2)
        self.assertEqual(with_sbc["weighted_average_shares"], 10)

    def test_losses_generate_nol_and_limited_use_does_not_create_a_tax_credit(self):
        report = project_statements(simple_opening(), [
            simple_driver(ebitda_margin=-.10),
            simple_driver(period_end="2027-08-31", ebitda_margin=.10),
            simple_driver(period_end="2028-08-31", ebitda_margin=.10),
        ])
        first, second, third = report["forecast"]
        self.assertEqual((first["net_income"], first["cash_taxes"], first["tax_loss_carryforward"]), (-100, 0, 100))
        self.assertEqual((second["nol_used"], second["cash_taxes"], second["net_income"],
                          second["tax_loss_carryforward"]), (80, 5, 95, 20))
        self.assertEqual((third["nol_used"], third["cash_taxes"], third["net_income"],
                          third["tax_loss_carryforward"]), (20, 20, 80, 0))
        self.assertEqual((first["fcff"], second["fcff"], third["fcff"]), (-100, 75, 75))
        self.assertTrue(report["checks"]["all_reconciled"])

    def test_interest_uses_opening_debt_and_share_events_use_year_end_timing(self):
        report = project_statements(simple_opening(debt=100, equity=0), [
            simple_driver(interest_rate=.10, debt_issued=50, debt_repaid=100,
                          equity_issued=10, issuance_share_price=2),
            simple_driver(period_end="2027-08-31", interest_rate=.10),
        ])
        first, second = report["forecast"]
        self.assertEqual((first["interest_expense"], first["debt"]), (10, 50))
        self.assertEqual((second["interest_expense"], second["debt"]), (5, 50))
        self.assertEqual((first["weighted_average_shares"], first["shares"], second["weighted_average_shares"]), (10, 15, 15))

    def test_minimum_cash_and_negative_cash_remain_unfunded_without_a_plug(self):
        minimum = project_statements(opening(), [driver(minimum_cash=150)])
        row = minimum["forecast"][0]
        self.assertEqual(minimum["status"], "funding_shortfall")
        self.assertAlmostEqual(row["funding_shortfall"], 28.5)
        self.assertEqual(row["debt"], 90)
        negative = project_statements(opening(), [driver(capex_pct_revenue=1)])
        row = negative["forecast"][0]
        self.assertAlmostEqual(row["cash"], -923.5)
        self.assertEqual(row["debt"], 90)
        self.assertEqual(negative["checks"]["negative_cash_years"], [1])
        self.assertTrue(negative["checks"]["all_reconciled"])
        self.assertTrue(any("unfunded gap" in warning for warning in negative["warnings"]))

    def test_scale_equivalent_models_keep_decisions_and_share_counts(self):
        baseline = project_statements(opening(), [driver()])["forecast"][0]
        money_driver_fields = ("amortization", "intangible_capex", "debt_issued", "debt_repaid",
                               "stock_compensation_share_price", "equity_issued", "issuance_share_price",
                               "repurchase_share_price", "minimum_cash")
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            with self.subTest(scale=scale):
                start, assumption = opening(), driver()
                for key in start.keys() - {"period_end", "shares"}:
                    start[key] *= scale
                for key in money_driver_fields:
                    assumption[key] *= scale
                report = project_statements(start, [assumption])
                row = report["forecast"][0]
                for key in ("revenue", "net_income", "cash", "equity", "fcff", "capex", "delta_nwc"):
                    self.assertAlmostEqual(row[key] / scale, baseline[key], places=9)
                self.assertAlmostEqual(row["shares"], 101, places=10)
                self.assertEqual(report["status"], "calculated")
                self.assertTrue(report["checks"]["all_reconciled"])
                start["equity"] += scale
                with self.assertRaisesRegex(ValueError, "does not balance"):
                    project_statements(start, [assumption])

    def test_zero_cash_boundary_preserves_scale_but_real_small_gaps_remain_visible(self):
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            with self.subTest(scale=scale):
                start = simple_opening(revenue=1000 * scale, cash=100 * scale, equity=100 * scale)
                assumption = simple_driver(ebitda_margin=-.1)
                report = project_statements(start, [assumption])
                row = report["forecast"][0]
                self.assertEqual(report["status"], "calculated")
                self.assertEqual(row["funding_shortfall"], 0)
                self.assertLessEqual(abs(row["cash"]), row["cash_roundoff_tolerance"])
                self.assertEqual(report["checks"]["negative_cash_years"], [])
                assumption["ebitda_margin"] = -.10001
                short = project_statements(start, [assumption])
                self.assertEqual(short["status"], "funding_shortfall")
                self.assertAlmostEqual(short["forecast"][0]["funding_shortfall"] / scale, .01, places=10)


class StatementContractTests(unittest.TestCase):
    def test_inputs_are_not_mutated(self):
        start, assumptions = opening(), [driver()]
        preserved = deepcopy((start, assumptions))
        project_statements(start, assumptions)
        self.assertEqual((start, assumptions), preserved)

    def test_missing_unknown_bool_string_and_nonfinite_values_are_rejected(self):
        for bad in (True, "100", float("nan"), float("inf"), float("-inf"), None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                project_statements(opening(cash=bad), [driver()])
            with self.subTest(driver_value=bad), self.assertRaises(ValueError):
                project_statements(opening(), [driver(tax_rate=bad)])
        for key in ("cash", "retained_earnings", "tax_loss_carryforward"):
            start = opening()
            del start[key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "missing"):
                project_statements(start, [driver()])
        with self.assertRaisesRegex(ValueError, "unknown keys"):
            project_statements(opening(cash_plug=0), [driver()])
        with self.assertRaisesRegex(ValueError, "unknown keys"):
            project_statements(opening(), [driver(revolver_plug=True)])
        for bad in (None, {}, (), [], [driver()] * 11):
            with self.subTest(drivers=type(bad)), self.assertRaises(ValueError):
                project_statements(opening(), bad)

    def test_annual_dates_and_leap_anniversaries(self):
        for bad in ("20250831", "2025-02-31", "2025-8-31", True):
            with self.subTest(opening_date=bad), self.assertRaises(ValueError):
                project_statements(opening(period_end=bad), [driver()])
        for bad in ("2026-09-01", "2025-08-31", "2026-02-30"):
            with self.subTest(period_end=bad), self.assertRaises(ValueError):
                project_statements(opening(), [driver(period_end=bad)])
        with self.assertRaisesRegex(ValueError, "annual anniversary"):
            project_statements(opening(), [driver(), driver()])
        dates = ("2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29")
        report = project_statements(simple_opening(period_end="2024-02-29"),
                                    [simple_driver(period_end=day) for day in dates])
        self.assertEqual([row["period_end"] for row in report["forecast"]], list(dates))

    def test_impossible_debt_asset_share_and_cost_schedules_are_rejected(self):
        cases = (
            driver(debt_repaid=121), driver(amortization=51),
            driver(shares_repurchased=104), driver(ebitda_margin=.6),
            driver(stock_compensation_pct_revenue=.4), driver(depreciation_rate=1.01),
            driver(revenue_growth=-1), driver(issuance_share_price=0),
        )
        for assumption in cases:
            with self.subTest(assumption=assumption), self.assertRaises(ValueError):
                project_statements(opening(), [assumption])
        with self.assertRaisesRegex(ValueError, "opening finite-lived"):
            project_statements(opening(), [driver(), driver(period_end="2027-08-31", amortization=49)])

    def test_nonfinite_derived_share_count_is_not_serialized(self):
        with self.assertRaisesRegex(ValueError, "finite output envelope"):
            project_statements(opening(), [driver(issuance_share_price=1e-310)])


if __name__ == "__main__":
    unittest.main()
