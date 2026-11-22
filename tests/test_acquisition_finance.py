"""Independent cash/debt benchmarks and boundary cases for acquisition finance."""

from copy import deepcopy
import math
import unittest

from pilot.acquisition_finance import annual_irr, evaluate_acquisition


def opening(**changes):
    return {"period_end": "2025-08-31", "cash": 20.0, "debt": 10.0,
            "tax_loss_carryforward": 0.0} | changes


def terms(**changes):
    return {
        "entry_enterprise_value": 100.0, "transaction_fee_rate": .02,
        "financing_fee_rate": .01, "initial_term_debt": 60.0,
        "term_interest_rate": .10, "term_amortization_rate": .10,
        "term_maturity_year": 5, "revolver_limit": 20.0,
        "revolver_interest_rate": .12, "minimum_cash": 5.0,
        "cash_sweep_rate": 1.0, "exit_ebitda_multiple": 6.0,
        "exit_fee_rate": .01, "nol_utilization_limit": .80,
    } | changes


def forecast(years=2, **changes):
    return [{"year": year, "period_end": f"{2025 + year}-08-31", "revenue": 100.0,
             "cogs": 50.0, "ebitda": 30.0, "ebit": 25.0, "depreciation": 5.0,
             "amortization": 0.0, "stock_compensation": 3.0, "capex": 5.0,
             "delta_nwc": 2.0, "tax_rate": .25} | changes
            for year in range(1, years + 1)]


class SourcesAndUsesTests(unittest.TestCase):
    def test_cash_and_debt_are_included_once_at_entry(self):
        report = evaluate_acquisition(opening(), forecast(), terms())
        bridge = report["sources_uses"]
        # Seller receives 100 operating EV + 20 cash - 10 existing debt.
        self.assertEqual(bridge["seller_equity_purchase"], 110)
        self.assertEqual(bridge["existing_debt_payoff"], 10)
        self.assertEqual(bridge["acquired_cash_used"], 15)
        self.assertEqual(bridge["acquired_cash_retained"], 5)
        self.assertAlmostEqual(bridge["total_uses"], 122.6)
        self.assertAlmostEqual(bridge["sponsor_equity"], 47.6)
        self.assertAlmostEqual(bridge["total_sources"], 122.6)
        self.assertAlmostEqual(bridge["sources_less_uses"], 0)

    def test_less_acquired_cash_requires_explicit_top_up_not_more_equity(self):
        report = evaluate_acquisition(opening(cash=2), forecast(), terms())
        bridge = report["sources_uses"]
        self.assertEqual(bridge["seller_equity_purchase"], 92)
        self.assertEqual(bridge["cash_top_up"], 3)
        self.assertEqual(bridge["acquired_cash_used"], 0)
        self.assertEqual(bridge["acquired_cash_retained"], 5)
        # Lower cash reduces seller consideration and adds a top-up; required
        # sponsor funding remains EV + minimum cash + fees - term financing.
        self.assertAlmostEqual(bridge["sponsor_equity"], 47.6)

    def test_extra_original_debt_changes_seller_proceeds_not_sponsor_funding(self):
        report = evaluate_acquisition(opening(debt=90), forecast(), terms())
        self.assertEqual(report["sources_uses"]["seller_equity_purchase"], 30)
        self.assertAlmostEqual(report["sources_uses"]["sponsor_equity"], 47.6)

    def test_other_claims_reduce_seller_equity_and_are_settled_once(self):
        report = evaluate_acquisition(opening(other_claims=7.25), forecast(), terms())
        bridge = report["sources_uses"]
        self.assertEqual(report["opening"]["other_claims"], 7.25)
        self.assertEqual(bridge["seller_equity_purchase"], 102.75)
        self.assertEqual(bridge["existing_debt_payoff"], 10)
        self.assertEqual(bridge["existing_other_claims_payoff"], 7.25)
        self.assertAlmostEqual(bridge["total_uses"], 122.6)
        self.assertAlmostEqual(bridge["sponsor_equity"], 47.6)
        self.assertAlmostEqual(bridge["sources_less_uses"], 0)
        with self.assertRaisesRegex(ValueError, "restructuring"):
            evaluate_acquisition(opening(other_claims=111), forecast(), terms())

    def test_absent_other_claims_is_backward_compatible_with_explicit_zero(self):
        omitted = evaluate_acquisition(opening(), forecast(), terms())
        explicit = evaluate_acquisition(opening(other_claims=0), forecast(), terms())
        self.assertEqual(omitted, explicit)
        self.assertEqual(omitted["sources_uses"]["existing_other_claims_payoff"], 0)
        for invalid in (True, -1, float("nan"), "1"):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                evaluate_acquisition(opening(other_claims=invalid), forecast(), terms())

    def test_negative_seller_equity_and_nonpositive_sponsor_equity_are_unsupported(self):
        with self.assertRaisesRegex(ValueError, "restructuring"):
            evaluate_acquisition(opening(debt=121), forecast(), terms())
        with self.assertRaisesRegex(ValueError, "positive sponsor"):
            evaluate_acquisition(opening(), forecast(), terms(initial_term_debt=200))


class FinancingScheduleTests(unittest.TestCase):
    def test_hand_calculated_two_year_financing_and_exit(self):
        report = evaluate_acquisition(opening(), forecast(), terms())
        first, second = report["schedule"]
        # Year 1: EBITDA30 - interest6 - tax4.75 - capex5 - WC2 =12.25.
        self.assertEqual(first["interest"], 6)
        self.assertEqual(first["cash_taxes"], 4.75)
        self.assertEqual(first["cash_flow_after_interest"], 12.25)
        self.assertEqual(first["mandatory_principal_paid"], 6)
        self.assertEqual(first["term_cash_sweep"], 6.25)
        self.assertEqual(first["closing_term_debt"], 47.75)
        self.assertEqual(first["closing_cash"], 5)
        self.assertAlmostEqual(first["interest_coverage"], 5)
        self.assertAlmostEqual(first["net_leverage"], 1.425)
        self.assertAlmostEqual(first["debt_service_coverage"], 18.25 / 12)
        # Year 2 interest4.775; tax5.05625; total principal reduction13.16875.
        self.assertAlmostEqual(second["interest"], 4.775)
        self.assertAlmostEqual(second["cash_taxes"], 5.05625)
        self.assertAlmostEqual(second["closing_term_debt"], 34.58125)
        self.assertAlmostEqual(report["exit"]["sponsor_equity_proceeds"], 148.61875)
        self.assertAlmostEqual(report["returns"]["moic"], 148.61875 / 47.6)
        self.assertAlmostEqual(report["returns"]["annual_irr"], math.sqrt(148.61875 / 47.6) - 1)
        self.assertEqual(report["feasibility"]["status"], "modeled_feasible")
        for row in report["schedule"]:
            self.assertAlmostEqual(row["cash_rollforward_difference"], 0)
            self.assertAlmostEqual(row["term_rollforward_difference"], 0)
            self.assertAlmostEqual(row["revolver_rollforward_difference"], 0)

    def test_stock_compensation_is_cash_replaced_not_added_back(self):
        base = evaluate_acquisition(opening(), forecast(stock_compensation=0), terms())
        stock = evaluate_acquisition(opening(), forecast(stock_compensation=10), terms())
        self.assertEqual(base["schedule"][0]["cash_flow_after_interest"],
                         stock["schedule"][0]["cash_flow_after_interest"])
        self.assertEqual(base["returns"]["moic"], stock["returns"]["moic"])
        self.assertTrue(any("cash compensation" in item for item in stock["conventions"]))

    def test_revolver_funds_mandatory_principal_then_is_repaid_before_term_sweep(self):
        operations = forecast()
        operations[0].update(ebitda=8, ebit=8, depreciation=0, capex=0, delta_nwc=0)
        report = evaluate_acquisition(opening(), operations, terms())
        first, second = report["schedule"]
        self.assertEqual(first["cash_flow_after_interest"], 1.5)
        self.assertEqual(first["revolver_draw"], 4.5)
        self.assertEqual(first["closing_term_debt"], 54)
        self.assertEqual(first["closing_revolver"], 4.5)
        self.assertAlmostEqual(second["revolver_interest"], .54)
        self.assertAlmostEqual(second["revolver_repayment"], 4.5)
        self.assertAlmostEqual(second["term_cash_sweep"], 1.795)
        self.assertAlmostEqual(second["closing_term_debt"], 46.205)
        self.assertEqual(second["closing_revolver"], 0)

    def test_revolver_capacity_and_unpaid_principal_are_visible_and_returns_withheld(self):
        report = evaluate_acquisition(opening(), forecast(1, ebitda=-20, ebit=-25),
                                      terms(revolver_limit=10))
        row = report["schedule"][0]
        self.assertEqual(row["revolver_draw"], 10)
        self.assertEqual(row["closing_revolver"], 10)
        self.assertEqual(row["mandatory_principal_paid"], 0)
        self.assertEqual(row["mandatory_principal_shortfall"], 6)
        self.assertEqual(row["liquidity_shortfall"], 23)
        self.assertEqual(row["closing_term_debt"], 60)
        self.assertEqual(row["closing_cash"], -18)
        self.assertEqual(report["feasibility"]["status"], "not_feasible")
        self.assertIsNone(report["returns"]["annual_irr"])
        self.assertIsNone(report["returns"]["moic"])
        self.assertIsNone(report["returns"]["sponsor_cash_flows"])

    def test_maturity_requires_repayment_before_exit(self):
        report = evaluate_acquisition(opening(), forecast(),
                                      terms(term_maturity_year=1, revolver_limit=10))
        first = report["schedule"][0]
        self.assertEqual(first["mandatory_principal_due"], 60)
        self.assertEqual(first["scheduled_principal_due"], 6)
        self.assertEqual(first["maturity_principal_due_before_exit"], 54)
        self.assertEqual(first["maturity_balloon_due_at_exit"], 0)
        self.assertEqual(first["mandatory_principal_paid"], 22.25)
        self.assertEqual(first["mandatory_principal_shortfall"], 37.75)
        self.assertEqual(first["closing_term_debt"], 37.75)
        self.assertIsNone(report["returns"]["annual_irr"])

    def test_maturity_coincident_with_exit_settles_balloon_once_from_sale(self):
        ordinary_exit = evaluate_acquisition(opening(), forecast(), terms())
        coincident = evaluate_acquisition(opening(), forecast(), terms(term_maturity_year=2))
        final = coincident["schedule"][-1]
        self.assertEqual(coincident["feasibility"]["status"], "modeled_feasible")
        self.assertEqual(final["scheduled_principal_due"], 6)
        self.assertEqual(final["mandatory_principal_due"], 6)
        self.assertEqual(final["maturity_principal_due_before_exit"], 0)
        self.assertEqual(final["revolver_draw"], 0)
        self.assertAlmostEqual(final["maturity_balloon_due_at_exit"], 34.58125)
        self.assertAlmostEqual(coincident["exit"]["term_maturity_settlement"], 34.58125)
        self.assertAlmostEqual(coincident["exit"]["term_debt_payoff"], 34.58125)
        self.assertTrue(coincident["exit"]["maturity_coincides_with_exit"])
        self.assertAlmostEqual(coincident["exit"]["sponsor_equity_proceeds"], 148.61875)
        self.assertEqual(coincident["returns"], ordinary_exit["returns"])

    def test_coincident_maturity_still_fails_if_sale_cannot_repay_balloon(self):
        report = evaluate_acquisition(opening(), forecast(),
                                      terms(term_maturity_year=2, exit_ebitda_multiple=.1))
        final = report["schedule"][-1]
        self.assertEqual(final["mandatory_principal_shortfall"], 0)
        self.assertEqual(final["liquidity_shortfall"], 0)
        self.assertAlmostEqual(report["exit"]["term_maturity_settlement"], 34.58125)
        self.assertAlmostEqual(report["exit"]["debt_repayment_shortfall"], 26.61125)
        self.assertEqual(report["feasibility"]["status"], "not_feasible")
        self.assertIsNone(report["returns"]["annual_irr"])
        self.assertIsNone(report["returns"]["moic"])

    def test_no_excess_repayment_and_zero_interest_denominator(self):
        report = evaluate_acquisition(opening(), forecast(3),
                                      terms(initial_term_debt=10, term_interest_rate=0,
                                            term_amortization_rate=1, cash_sweep_rate=1))
        first, second, third = report["schedule"]
        self.assertEqual(first["mandatory_principal_paid"], 10)
        self.assertEqual(first["closing_term_debt"], 0)
        self.assertEqual(second["mandatory_principal_paid"], 0)
        self.assertEqual(second["term_cash_sweep"], 0)
        self.assertEqual(third["closing_term_debt"], 0)
        self.assertGreater(third["closing_cash"], second["closing_cash"])
        self.assertIsNone(first["interest_coverage"])
        self.assertIsNone(second["debt_service_coverage"])

    def test_nol_generation_and_limited_use_without_tax_refund(self):
        operations = forecast(2, depreciation=0, capex=0, delta_nwc=0)
        operations[0].update(ebitda=-40, ebit=-40)
        operations[1].update(ebitda=20, ebit=20)
        report = evaluate_acquisition(opening(), operations,
                                      terms(initial_term_debt=0, revolver_limit=100,
                                            revolver_interest_rate=0))
        first, second = report["schedule"]
        self.assertEqual(first["cash_taxes"], 0)
        self.assertEqual(first["nol_generated"], 40)
        self.assertEqual(second["opening_nol"], 40)
        self.assertEqual(second["nol_used"], 16)
        self.assertEqual(second["cash_taxes"], 1)
        self.assertEqual(second["closing_nol"], 24)

    def test_covenant_failure_withholds_returns_after_later_recovery(self):
        for covenant in ({"max_net_leverage": 1}, {"min_interest_coverage": 6}):
            with self.subTest(covenant=covenant):
                report = evaluate_acquisition(opening(), forecast(), terms(**covenant))
                self.assertEqual(report["feasibility"]["status"], "not_feasible")
                self.assertIsNone(report["returns"]["annual_irr"])
                self.assertTrue(report["exit"]["indicative_only"])

    def test_exit_debt_shortfall_does_not_claim_feasible_full_repayment(self):
        report = evaluate_acquisition(opening(), forecast(), terms(exit_ebitda_multiple=.1))
        self.assertAlmostEqual(report["exit"]["debt_repayment_shortfall"], 26.61125)
        self.assertEqual(report["exit"]["sponsor_equity_proceeds"], 0)
        self.assertIsNone(report["returns"]["annual_irr"])
        self.assertTrue(any(issue["kind"] == "exit_debt_repayment_shortfall"
                            for issue in report["feasibility"]["issues"]))

    def test_exact_covenant_boundaries_allow_numerical_roundoff(self):
        report = evaluate_acquisition(opening(), forecast(),
                                      terms(max_net_leverage=1.425, min_interest_coverage=5))
        self.assertEqual(report["feasibility"]["status"], "modeled_feasible")

    def test_equivalent_monetary_scales_preserve_financing_and_returns(self):
        expected = evaluate_acquisition(opening(), forecast(), terms())
        for scale in (1e-12, 1e-6, 1, 1e6, 1e12):
            with self.subTest(scale=scale):
                initial = opening()
                for key in ("cash", "debt", "tax_loss_carryforward"):
                    initial[key] *= scale
                operations = forecast()
                for row in operations:
                    for key in ("revenue", "cogs", "ebitda", "ebit", "depreciation", "amortization",
                                "stock_compensation", "capex", "delta_nwc"):
                        row[key] *= scale
                assumption = terms()
                for key in ("entry_enterprise_value", "initial_term_debt", "revolver_limit", "minimum_cash"):
                    assumption[key] *= scale
                report = evaluate_acquisition(initial, operations, assumption)
                self.assertEqual(report["feasibility"]["status"], "modeled_feasible")
                self.assertAlmostEqual(report["sources_uses"]["sponsor_equity"] / scale, 47.6)
                self.assertAlmostEqual(report["schedule"][-1]["closing_term_debt"] / scale, 34.58125)
                self.assertAlmostEqual(report["returns"]["moic"], expected["returns"]["moic"], places=10)
                self.assertAlmostEqual(report["returns"]["annual_irr"], expected["returns"]["annual_irr"], places=10)


class ReturnAndValidationTests(unittest.TestCase):
    def test_known_annual_roots_and_interim_receipts(self):
        for flows, expected in (([-100, 0, 121], .10), ([-100, 20, 99], .10),
                                 ([-100, 0, 100], 0), ([-100, 0, 25], -.50)):
            with self.subTest(flows=flows):
                result = annual_irr(flows)
                self.assertEqual(result["status"], "solved")
                self.assertAlmostEqual(result["rate"], expected, places=10)
                residual = sum(amount / (1 + result["rate"]) ** i for i, amount in enumerate(flows))
                self.assertAlmostEqual(residual, 0, places=8)

    def test_total_loss_and_nonconventional_cashflows_are_explicit(self):
        total_loss = annual_irr([-100, 0, 0])
        self.assertEqual(total_loss["status"], "total_loss")
        self.assertEqual(total_loss["rate"], -1)
        self.assertIsNone(total_loss["relative_npv_residual"])
        for flows in ([0, 100], [100, 110], [-100, 230, -132]):
            result = annual_irr(flows)
            self.assertEqual(result["status"], "unsupported_cash_flow_pattern")
            self.assertIsNone(result["rate"])

    def test_exact_anniversaries_and_leap_year_convention(self):
        initial = opening(period_end="2024-02-29")
        operations = forecast(4)
        for row, period in zip(operations, ("2025-02-28", "2026-02-28", "2027-02-28", "2028-02-29")):
            row["period_end"] = period
        report = evaluate_acquisition(initial, operations, terms())
        self.assertEqual(report["returns"]["cash_flow_dates"][-1], "2028-02-29")
        operations[-1]["period_end"] = "2028-02-28"
        with self.assertRaisesRegex(ValueError, "anniversaries"):
            evaluate_acquisition(initial, operations, terms())

    def test_invalid_values_unknown_keys_and_inconsistent_ebitda_fail(self):
        for invalid in (True, float("nan"), float("inf"), "100"):
            with self.subTest(value=invalid):
                with self.assertRaises(ValueError):
                    evaluate_acquisition(opening(), forecast(), terms(entry_enterprise_value=invalid))
        for mutation in (lambda data: data.pop("minimum_cash"),
                         lambda data: data.update(ignored_fee=10),
                         lambda data: data.update(term_maturity_year=True),
                         lambda data: data.update(cash_sweep_rate=1.01)):
            t = terms()
            mutation(t)
            with self.assertRaises(ValueError):
                evaluate_acquisition(opening(), forecast(), t)
        with self.assertRaisesRegex(ValueError, "EBITDA"):
            evaluate_acquisition(opening(), forecast(ebitda=31), terms())
        for change in ({"period_end": "2026-09-01"}, {"year": True}, {"year": 3}):
            rows = deepcopy(forecast())
            rows[0].update(change)
            with self.assertRaises(ValueError):
                evaluate_acquisition(opening(), rows, terms())
        with self.assertRaisesRegex(ValueError, "required finance fields"):
            evaluate_acquisition(opening(), [{"year": 1}], terms())

    def test_inputs_are_not_mutated(self):
        initial, operations, t = opening(), forecast(), terms()
        before = deepcopy((initial, operations, t))
        evaluate_acquisition(initial, operations, t)
        self.assertEqual((initial, operations, t), before)


if __name__ == "__main__":
    unittest.main()
