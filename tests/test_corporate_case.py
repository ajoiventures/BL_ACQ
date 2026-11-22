"""Financial benchmarks and integration boundaries for the sourced corporate case.

Expected values in the small fixtures are solved independently of the adapter.
Source anchors test transcription/control stability, not the issuer's economics.
"""

from copy import deepcopy
import math
import unittest

from pilot.corporate_case import (
    compare_companies,
    evaluate_case,
    historical_checks,
    load_case,
    normalize_wdfc,
    value_forecast,
)


def valuation_assumptions(**changes):
    return {
        "risk_free_rate": .04, "equity_beta": 1.0, "equity_risk_premium": .06,
        "pretax_cost_of_debt": .05, "target_debt_weight": 0.0,
        "tax_rate": .25, "terminal_growth": 0.0, "terminal_roic": .20,
        "other_claims": 0.0,
    } | changes


def valuation_opening(**changes):
    return {"period_end": "2025-10-31", "cash": 20.0, "debt": 120.0,
            "shares": 10.0} | changes


def constant_cashflows(years=5, **changes):
    # EBIT 133 1/3 taxed at 25% leaves $100. No other reinvestment is needed
    # at zero growth. The infinite stream is worth 100/.10 = $1,000.
    return [{"year": year, "period_end": f"{2025 + year}-10-31",
             "ebit": 100 / .75, "tax_rate": .25, "depreciation": 0.0,
             "amortization": 0.0, "capex": 0.0, "delta_nwc": 0.0} | changes
            for year in range(1, years + 1)]


def peer_fixture():
    # All monetary statement/bridge figures are USD thousands; prices and
    # share counts are actual USD/share and actual shares. Values below are
    # deliberately synthetic and do not claim to be observed issuer data.
    def peer(ticker, price, debt, cash, nci, preferred, claims, assets):
        return {
            "entity": {"ticker": ticker},
            "quote": {"close": price, "date": "2025-10-31"},
            "shares": {"value": 100, "as_of": "2025-10-01"},
            "fiscal_period_end": "2025-08-31",
            "financials_published_on": "2025-10-20",
            "constructed_operating_ebit": {"value": .1},
            "suggested_enterprise_value_bridge": {
                "debt_including_finance_leases": debt,
                "cash_to_deduct": cash, "noncontrolling_interests": nci,
                "preferred_stock": preferred, "other_claims": claims,
                "nonoperating_assets_to_deduct": assets,
            },
        }
    return {
        "periods": {"2025": {"income_statement": {"operating_income": .1}}},
        "comparables": [
            peer("FIXTURE_A", 10, .300, .100, .020, .010, .030, .010),
            peer("FIXTURE_B", 20, .200, .050, 0, 0, .050, 0),
        ],
    }


class HistoricalControlsTests(unittest.TestCase):
    def setUp(self):
        self.case, self.facts = load_case()

    def test_reported_controls_reconcile_including_fx_and_equity_movements(self):
        result = historical_checks(self.facts)
        self.assertTrue(result["all_reconciled"])
        self.assertEqual({item["period"] for item in result["items"]},
                         {"2023", "2024", "2025"})
        self.assertTrue(all(item["difference"] == 0 for item in result["items"]))
        latest = self.facts["periods"]["2025"]
        # F-3, F-4, F-6, F-7 of the October27,2025 filing. These are source
        # controls, not outputs copied from the forecast's own checks.
        self.assertEqual(latest["balance_sheet"]["total_assets"], 475809)
        self.assertEqual(latest["balance_sheet"]["total_liabilities"], 207657)
        self.assertEqual(latest["balance_sheet"]["total_equity"], 268152)
        self.assertEqual(latest["income_statement"]["net_income"], 90994)
        cf = latest["cash_flow"]
        self.assertEqual((cf["operating_cash_flow"], cf["investing_cash_flow"],
                          cf["financing_cash_flow"], cf["fx_cash_effect"]),
                         (87925, -2388, -74116, 10))
        self.assertEqual(46699 + 87925 - 2388 - 74116 + 10, 58130)
        eq = latest["equity_rollforward"]
        self.assertEqual(eq["ending_equity"],
                         230526 + 90994 - 50260 + 7306 - 2883 - 12314 + 4783)
        prior = self.facts["periods"]["2024"]
        self.assertEqual(prior["equity_rollforward"]["treasury_stock_purchases"], -8129)
        self.assertEqual(prior["cash_flow"]["treasury_stock_purchases"], -8094)

    def test_tampered_reported_totals_cannot_be_bypassed_by_recomputing_components(self):
        fields = {
            "income_statement": ("gross_profit", "total_operating_expenses", "net_income"),
            "balance_sheet": ("current_assets", "current_liabilities", "total_assets",
                              "total_liabilities", "total_equity", "total_liabilities_equity"),
            "cash_flow": ("operating_cash_flow", "investing_cash_flow",
                          "financing_cash_flow", "ending_cash"),
            "equity_rollforward": ("ending_equity",),
        }
        for statement, names in fields.items():
            for field in names:
                bad = deepcopy(self.facts)
                bad["periods"]["2025"][statement][field] += 1
                with self.subTest(statement=statement, field=field):
                    self.assertFalse(historical_checks(bad)["all_reconciled"])
                    with self.assertRaises(ValueError):
                        evaluate_case(self.case, bad)

    def test_historical_numeric_corruption_is_rejected(self):
        for bad_value in (True, "619985", None, float("nan"), float("inf")):
            bad = deepcopy(self.facts)
            bad["periods"]["2025"]["income_statement"]["revenue"] = bad_value
            with self.subTest(value=bad_value), self.assertRaises(ValueError):
                historical_checks(bad)

    def test_normalization_preserves_raw_facts_and_lease_classification(self):
        preserved = deepcopy(self.facts)
        opening = normalize_wdfc(self.facts, "2025-10-31")
        self.assertEqual(self.facts, preserved)
        self.assertEqual(opening["period_end"], "2025-10-31")
        self.assertEqual(self.facts["periods"]["2025"]["period_end"], "2025-08-31")
        expected = {"cash": 58130000, "debt": 86995000, "equity": 268152000,
                    "retained_earnings": 540665000, "shares": 13527614,
                    "other_current_assets": 26366000,
                    "operating_other_current_assets": 0,
                    "operating_accruals": 60363000,
                    "other_current_liabilities": 3139000,
                    "other_noncurrent_assets": 128043000,
                    "other_noncurrent_liabilities": 19205000}
        for field, value in expected.items():
            with self.subTest(field=field):
                self.assertEqual(opening[field], value)
        # 2,282 current operating lease liability is reclassified once;
        # held-for-sale assets and tax receivable are not operating prepaids.
        self.assertEqual(opening["operating_accruals"] + opening["other_current_liabilities"],
                         (34230 + 28415 + 857) * 1000)

    def test_issuer_specific_normalization_rejects_wrong_issuer_and_early_date(self):
        wrong = deepcopy(self.facts)
        wrong["entity"]["ticker"] = "OTHER"
        with self.assertRaises(ValueError):
            normalize_wdfc(wrong, "2025-10-31")
        with self.assertRaises(ValueError):
            normalize_wdfc(self.facts, "2025-08-30")


class IndependentValuationBenchmarks(unittest.TestCase):
    def test_constant_perpetuity_is_independent_of_explicit_forecast_horizon(self):
        for horizon in (1, 5, 30):
            with self.subTest(horizon=horizon):
                report = value_forecast(valuation_opening(), constant_cashflows(horizon),
                                        valuation_assumptions())
                self.assertAlmostEqual(report["wacc"], .10, places=12)
                self.assertAlmostEqual(report["enterprise_value"], 1000, places=9)
                self.assertAlmostEqual(report["equity_value"], 900, places=9)
                self.assertAlmostEqual(report["value_per_share"], 90, places=10)
                self.assertAlmostEqual(report["terminal_reinvestment"], 0)
                self.assertTrue(all(math.isclose(row["fcff"], 100, abs_tol=1e-10)
                                    for row in report["forecast"]))

    def test_capm_and_after_tax_debt_build_to_nine_percent_wacc(self):
        # Cost of equity .04 +1.2*.05 =.10. 75% equity contributes.075;
        # 25% debt at.08 after25%tax contributes.015. WACC is.09.
        report = value_forecast(valuation_opening(), constant_cashflows(),
                                valuation_assumptions(equity_beta=1.2,
                                    equity_risk_premium=.05, target_debt_weight=.25,
                                    pretax_cost_of_debt=.08))
        self.assertAlmostEqual(report["cost_of_equity"], .10, places=12)
        self.assertAlmostEqual(report["wacc"], .09, places=12)
        self.assertAlmostEqual(report["enterprise_value"], 100 / .09, places=9)

    def test_fcff_and_terminal_growth_pay_for_reinvestment(self):
        # Year1: NOPAT100 +D&A20 -capex35 -WC5 =80.
        # Terminal: NOPAT102, reinvestment10.2 at20%ROIC, FCFF91.8;
        # terminal value91.8/(.10-.02)=1147.5 at year1.
        report = value_forecast(valuation_opening(), constant_cashflows(
            1, depreciation=15, amortization=5, capex=35, delta_nwc=5),
            valuation_assumptions(terminal_growth=.02))
        self.assertAlmostEqual(report["forecast"][0]["fcff"], 80)
        self.assertAlmostEqual(report["terminal_nopat"], 102)
        self.assertAlmostEqual(report["terminal_reinvestment"], 10.2)
        self.assertAlmostEqual(report["terminal_fcff"], 91.8)
        self.assertAlmostEqual(report["terminal_value"], 1147.5)
        self.assertAlmostEqual(report["enterprise_value"], 1227.5 / 1.1)

    def test_claims_and_financing_bridge_affect_equity_once_without_changing_fcff(self):
        baseline = value_forecast(valuation_opening(), constant_cashflows(),
                                  valuation_assumptions())
        claims = value_forecast(valuation_opening(), constant_cashflows(),
                                valuation_assumptions(other_claims=30))
        debt = value_forecast(valuation_opening(debt=150), constant_cashflows(),
                              valuation_assumptions())
        cash = value_forecast(valuation_opening(cash=50), constant_cashflows(),
                              valuation_assumptions())
        for result in (claims, debt, cash):
            self.assertAlmostEqual(result["enterprise_value"], 1000)
            self.assertEqual(result["forecast"], baseline["forecast"])
        self.assertAlmostEqual(claims["value_per_share"], 87)
        self.assertAlmostEqual(debt["value_per_share"], 87)
        self.assertAlmostEqual(cash["value_per_share"], 93)

    def test_input_objects_are_preserved_and_report_is_repeatable(self):
        opening, forecast, assumptions = (valuation_opening(audit_label="fixture"),
                                          constant_cashflows(), valuation_assumptions())
        saved = deepcopy((opening, forecast, assumptions))
        first = value_forecast(opening, forecast, assumptions)
        self.assertEqual((opening, forecast, assumptions), saved)
        self.assertEqual(first, value_forecast(opening, forecast, assumptions))


class ValuationInputBoundaries(unittest.TestCase):
    def test_terminal_rate_boundaries_reject_undefined_or_unsupported_valuations(self):
        invalid = (
            {"risk_free_rate": 0, "equity_risk_premium": 0},
            {"terminal_growth": .10}, {"terminal_growth": .11},
            {"terminal_growth": .02, "terminal_roic": .01},
            {"terminal_roic": 0}, {"target_debt_weight": 1.01},
            {"other_claims": -1},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), constant_cashflows(),
                               valuation_assumptions(**changes))

    def test_nonpositive_terminal_operating_profit_requires_another_method(self):
        for ebit in (0, -10):
            with self.subTest(ebit=ebit), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), constant_cashflows(ebit=ebit),
                               valuation_assumptions())

    def test_empty_malformed_and_nonannual_index_forecasts_raise_value_errors(self):
        bad_forecasts = (None, {}, [], constant_cashflows(31),
                         [None], [constant_cashflows(1)[0] | {"year": 0}],
                         [constant_cashflows(1)[0] | {"year": True}],
                         constant_cashflows(2, year=1),
                         constant_cashflows(1, period_end="2026-02-30"))
        for forecast in bad_forecasts:
            with self.subTest(forecast=forecast), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), forecast, valuation_assumptions())
        missing = constant_cashflows(1)
        del missing[0]["ebit"]
        with self.assertRaises(ValueError):
            value_forecast(valuation_opening(), missing, valuation_assumptions())

    def test_nonfinite_nonnumeric_and_impossible_core_inputs_are_rejected(self):
        for value in (True, "100", None, float("nan"), float("inf"), float("-inf")):
            with self.subTest(kind="forecast", value=value), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), constant_cashflows(ebit=value),
                               valuation_assumptions())
            with self.subTest(kind="opening", value=value), self.assertRaises(ValueError):
                value_forecast(valuation_opening(shares=value), constant_cashflows(),
                               valuation_assumptions())
            with self.subTest(kind="assumption", value=value), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), constant_cashflows(),
                               valuation_assumptions(risk_free_rate=value))
        for changes in ({"shares": 0}, {"shares": -1}, {"debt": -1}, {"cash": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                value_forecast(valuation_opening(**changes), constant_cashflows(),
                               valuation_assumptions())
        for changes in ({"tax_rate": 1.01}, {"capex": -1}, {"depreciation": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), constant_cashflows(**changes),
                               valuation_assumptions())

    def test_assumption_schema_and_finite_derived_value_are_enforced(self):
        missing = valuation_assumptions()
        del missing["terminal_roic"]
        for assumptions in (None, [], missing, valuation_assumptions(unrecognized_spread=.01)):
            with self.subTest(assumptions=assumptions), self.assertRaises(ValueError):
                value_forecast(valuation_opening(), constant_cashflows(), assumptions)
        # All inputs are finite. A subnormal discount rate nevertheless makes
        # the perpetuity overflow; the public result must not contain infinity.
        with self.assertRaises(ValueError):
            value_forecast(valuation_opening(), constant_cashflows(1),
                           valuation_assumptions(risk_free_rate=5e-324,
                                                 equity_risk_premium=0))


class ComparisonBenchmarks(unittest.TestCase):
    def test_enterprise_bridge_includes_nci_preferred_claims_and_excess_assets_once(self):
        facts = peer_fixture()
        preserved = deepcopy(facts)
        report = compare_companies(facts, valuation_opening(), "2025-10-31")
        self.assertEqual(facts, preserved)
        a, b = report["peers"]
        # A:1,000+300+20+10+30-100-10=1,250. B:2,000+200+50-50=2,200.
        self.assertAlmostEqual(a["market_cap"], 1000)
        self.assertAlmostEqual(a["enterprise_value"], 1250)
        self.assertAlmostEqual(a["operating_ebit"], 100)
        self.assertAlmostEqual(a["ev_ebit"], 12.5)
        self.assertAlmostEqual(b["enterprise_value"], 2200)
        self.assertAlmostEqual(b["ev_ebit"], 22)
        middle = report["implied_values"]["median"]
        self.assertAlmostEqual(middle["multiple"], 17.25)
        self.assertAlmostEqual(middle["enterprise_value"], 1725)
        self.assertAlmostEqual(middle["value_per_share"], 162.5)

    def test_only_same_date_quotes_support_the_common_date_comparison(self):
        for day in ("2025-10-30", "2025-09-01", "2025-11-01"):
            facts = peer_fixture()
            facts["comparables"][0]["quote"]["date"] = day
            with self.subTest(day=day), self.assertRaises(ValueError):
                compare_companies(facts, valuation_opening(), "2025-10-31")

    def test_financial_and_share_dates_cannot_look_forward(self):
        for field in ("financials_published_on", "fiscal_period_end", "share_date"):
            facts = peer_fixture()
            peer = facts["comparables"][0]
            if field == "share_date":
                peer["shares"]["as_of"] = "2025-11-01"
            else:
                peer[field] = "2025-11-01"
            with self.subTest(field=field), self.assertRaises(ValueError):
                compare_companies(facts, valuation_opening(), "2025-10-31")

    def test_invalid_prices_denominators_and_bridge_amounts_are_rejected(self):
        for section, key in (("quote", "close"), ("shares", "value"),
                             ("constructed_operating_ebit", "value")):
            for value in (0, -1, True, float("nan")):
                facts = peer_fixture()
                facts["comparables"][0][section][key] = value
                with self.subTest(section=section, value=value), self.assertRaises(ValueError):
                    compare_companies(facts, valuation_opening(), "2025-10-31")
        for field in ("debt_including_finance_leases", "cash_to_deduct",
                      "noncontrolling_interests", "preferred_stock", "other_claims",
                      "nonoperating_assets_to_deduct"):
            for value in (-1, True, float("nan")):
                facts = peer_fixture()
                facts["comparables"][0]["suggested_enterprise_value_bridge"][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    compare_companies(facts, valuation_opening(), "2025-10-31")


class SourceCutoffAndCaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.case, self.facts = load_case()

    def test_retrospective_quote_evidence_is_accepted_without_invented_publication_dates(self):
        quote_sources = [source for source in self.facts["sources"]
                         if source["source_type"] == "public_market_data_publisher"]
        self.assertTrue(quote_sources)
        for source in quote_sources:
            self.assertIsNone(source["published_on"])
            self.assertEqual(source["market_event_date"], "2025-10-31")
            self.assertGreater(source["retrieved_on"], source["market_event_date"])
        report = evaluate_case(self.case, self.facts)
        self.assertEqual(report["market_quote"]["close"], 194.28)
        self.assertEqual({row["ticker"]: row["price"] for row in report["comparables"]["peers"]},
                         {"RPM": 109.28, "CLX": 112.46})
        self.assertFalse(report["execution_allowed"])
        self.assertEqual(report["source_balance_date"], "2025-08-31")
        self.assertEqual(report["model_start_date"], "2025-10-31")

    def test_null_or_missing_publication_date_is_not_a_general_source_bypass(self):
        for mode in ("null_issuer", "missing_issuer", "quote_disguised_as_issuer",
                     "quote_missing_event_date", "quote_future_event",
                     "quote_missing_retrieval_date", "quote_retrieved_before_event"):
            facts = deepcopy(self.facts)
            if mode in ("null_issuer", "missing_issuer"):
                if mode == "null_issuer":
                    facts["sources"][0]["published_on"] = None
                else:
                    del facts["sources"][0]["published_on"]
            else:
                source = next(x for x in facts["sources"]
                              if x["source_type"] == "public_market_data_publisher")
                if mode == "quote_disguised_as_issuer":
                    source["source_type"] = "issuer_sec_filing"
                elif mode == "quote_missing_event_date":
                    del source["market_event_date"]
                elif mode == "quote_missing_retrieval_date":
                    del source["retrieved_on"]
                elif mode == "quote_retrieved_before_event":
                    source["retrieved_on"] = "2025-10-30"
                else:
                    source["market_event_date"] = "2025-11-01"
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                evaluate_case(self.case, facts)

    def test_future_filing_and_bad_target_quotes_are_rejected(self):
        facts = deepcopy(self.facts)
        facts["sources"][0]["published_on"] = "2025-11-01"
        with self.assertRaises(ValueError):
            evaluate_case(self.case, facts)
        for field, value in (("date", "2025-10-30"), ("date", "2025-11-01"),
                             ("close", -1), ("close", 0), ("close", True),
                             ("close", "194.28")):
            facts = deepcopy(self.facts)
            facts["market_quote"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evaluate_case(self.case, facts)

    def test_scenarios_change_business_outcomes_without_changing_reported_facts(self):
        source_copy = deepcopy(self.facts)
        reports = {}
        for scenario in ("Base", "Downside", "Upside"):
            case = deepcopy(self.case)
            case["selected_case"] = scenario
            case_copy = deepcopy(case)
            result = evaluate_case(case, self.facts)
            self.assertEqual(case, case_copy)
            self.assertEqual(self.facts, source_copy)
            self.assertEqual(result["selected_case"], scenario)
            self.assertFalse(result["execution_allowed"])
            self.assertTrue(result["historical_checks"]["all_reconciled"])
            self.assertTrue(result["projection"]["checks"]["all_reconciled"])
            self.assertEqual([row["period_end"] for row in result["projection"]["forecast"]],
                             [f"{year}-10-31" for year in range(2026, 2031)])
            self.assertEqual(result["opening"]["cash"], 58130000)
            reports[scenario] = result
        for output in (lambda r: r["projection"]["forecast"][-1]["revenue"],
                       lambda r: r["valuation"]["enterprise_value"]):
            self.assertLess(output(reports["Downside"]), output(reports["Base"]))
            self.assertLess(output(reports["Base"]), output(reports["Upside"]))
        self.assertEqual(len({r["input_digest"] for r in reports.values()}), 3)
        self.assertEqual(reports["Base"], evaluate_case(self.case, self.facts))

    def test_constructed_peer_ebit_must_reconcile_to_its_documented_income_lines(self):
        for peer_index in range(len(self.facts["comparables"])):
            facts = deepcopy(self.facts)
            peer = facts["comparables"][peer_index]
            peer["constructed_operating_ebit"]["value"] += 1000
            with self.subTest(ticker=peer["entity"]["ticker"]), self.assertRaises(ValueError):
                evaluate_case(self.case, facts)

    def test_target_claims_flow_consistently_to_dcf_comparables_and_entry_settlement(self):
        baseline = evaluate_case(self.case, self.facts)
        changed_case = deepcopy(self.case)
        changed_case["valuation"]["other_claims"] += 1000000
        changed = evaluate_case(changed_case, self.facts)
        shares = baseline["opening"]["shares"]
        self.assertEqual(baseline["valuation"]["other_claims"], 1100000)
        self.assertEqual(changed["valuation"]["enterprise_value"],
                         baseline["valuation"]["enterprise_value"])
        self.assertAlmostEqual(baseline["valuation"]["equity_value"] -
                               changed["valuation"]["equity_value"], 1000000)
        for label in ("low", "median", "high"):
            first = baseline["comparables"]["implied_values"][label]
            second = changed["comparables"]["implied_values"][label]
            self.assertEqual(first["enterprise_value"], second["enterprise_value"])
            self.assertAlmostEqual(first["value_per_share"] - second["value_per_share"],
                                   1000000 / shares, places=10)
        original_uses = baseline["acquisition"]["sources_uses"]
        changed_uses = changed["acquisition"]["sources_uses"]
        self.assertAlmostEqual(original_uses["seller_equity_purchase"] -
                               changed_uses["seller_equity_purchase"], 1000000)
        # The extra claim is settled at closing: seller consideration falls
        # while settlement rises, preserving total uses and sponsor funding.
        self.assertAlmostEqual(original_uses["total_uses"], changed_uses["total_uses"])
        self.assertAlmostEqual(original_uses["sponsor_equity"], changed_uses["sponsor_equity"])

    def test_malformed_case_and_driver_inputs_fail_as_contract_errors(self):
        for invalid in (None, [], self.case | {"unexpected": True},
                        self.case | {"selected_case": "Missing"},
                        self.case | {"cases": None}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                evaluate_case(invalid, self.facts)
        for changes in ({"revenue_growth": float("nan")}, {"tax_rate": True},
                        {"period_end": "2026-08-31"}):
            case = deepcopy(self.case)
            case["cases"]["Base"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                evaluate_case(case, self.facts)
        case = deepcopy(self.case)
        del case["cases"]["Base"][0]["capex_pct_revenue"]
        with self.assertRaises(ValueError):
            evaluate_case(case, self.facts)


if __name__ == "__main__":
    unittest.main()
