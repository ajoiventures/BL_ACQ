"""A sourced historical corporate case, linked forecasts, DCF and acquisition finance.

The reusable statement and financing engines are separate. This adapter's
normalization is explicitly specific to WD-40 FY2025; it is not a filing parser.
Nothing in this module authorizes a transaction or asserts independent review.
"""

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

from .corporate_model import project_statements
from .acquisition_finance import evaluate_acquisition


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "data/corporate/wdfc_2025_case.json"
FACTS_PATH = ROOT / "data/corporate/wdfc_source_facts.json"
MODEL_VERSION = "br-corporate-case-1"
IMPLEMENTATION = {
    "python_version": sys.version.split()[0],
    "modules_sha256": {
        name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
        for name in ("corporate_case.py", "corporate_model.py", "acquisition_finance.py")
    },
}


def _number(value, name, low=-1e15, high=1e15):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number between {low} and {high}")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(result) or not low <= result <= high:
        raise ValueError(f"{name} must be a finite number between {low} and {high}")
    return result


def _date(value, name):
    if type(value) is not str:
        raise ValueError(f"{name} must be YYYY-MM-DD")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return result


def historical_checks(facts):
    """Reconcile independently reported source controls, preserving FX and other items."""
    results = []
    for year, period in sorted(facts["periods"].items()):
        inc, bs, cf, eq = (period[key] for key in
                           ("income_statement", "balance_sheet", "cash_flow", "equity_rollforward"))
        for statement in (inc, bs, cf, eq):
            for key, value in statement.items():
                _number(value, f"{year}.{key}")
        checks = {
            "gross_profit": inc["revenue"] - inc["cost_of_products_sold"] - inc["gross_profit"],
            "operating_expenses": sum(inc[k] for k in ("selling_general_administrative", "advertising_sales_promotion", "intangible_amortization")) - inc["total_operating_expenses"],
            "operating_income": inc["gross_profit"] - inc["total_operating_expenses"] - inc["operating_income"],
            "pretax_income": inc["operating_income"] + inc["interest_income"] - inc["interest_expense"] + inc["other_income_expense_net"] - inc["pretax_income"],
            "net_income": inc["pretax_income"] - inc["income_tax_expense"] - inc["net_income"],
            "current_assets": sum(bs[k] for k in ("cash", "accounts_receivable_net", "inventory", "other_current_assets")) - bs["current_assets"],
            "current_liabilities": sum(bs[k] for k in ("accounts_payable", "accrued_liabilities", "accrued_payroll", "short_term_borrowings", "income_taxes_payable")) - bs["current_liabilities"],
            "assets": sum(bs[k] for k in ("cash", "accounts_receivable_net", "inventory", "other_current_assets", "ppe_net", "goodwill", "intangibles_net", "right_of_use_assets", "deferred_tax_assets_net", "other_noncurrent_assets")) - bs["total_assets"],
            "liabilities": sum(bs[k] for k in ("accounts_payable", "accrued_liabilities", "accrued_payroll", "short_term_borrowings", "income_taxes_payable", "long_term_borrowings", "deferred_tax_liabilities_net", "long_term_operating_lease_liabilities", "other_long_term_liabilities")) - bs["total_liabilities"],
            "equity_components": sum(bs[k] for k in ("common_stock", "additional_paid_in_capital", "retained_earnings", "accumulated_other_comprehensive_income", "treasury_stock_cost")) - bs["total_equity"],
            "balance_sheet": bs["total_assets"] - bs["total_liabilities"] - bs["total_equity"],
            "reported_liabilities_equity": bs["total_liabilities"] + bs["total_equity"] - bs["total_liabilities_equity"],
            "cash_flow_net_income": cf["net_income"] - inc["net_income"],
            "equity_net_income": eq["net_income"] - inc["net_income"],
            "cfo": sum(cf[k] for k in ("net_income", "depreciation_amortization", "cloud_implementation_amortization", "deferred_income_taxes", "uncertain_tax_position_release", "stock_based_compensation", "unrealized_fx_losses_gains", "credit_loss_provision", "inventory_writeoffs", "other_noncash", "change_receivables", "change_inventory", "change_other_assets", "change_operating_leases_net", "change_accounts_payable_accrued", "change_payroll", "change_other_long_term_liabilities_taxes")) - cf["operating_cash_flow"],
            "cfi": sum(cf[k] for k in ("ppe_purchases", "ppe_sale_proceeds", "business_sale_proceeds", "business_acquisition_net_cash")) - cf["investing_cash_flow"],
            "cff": sum(cf[k] for k in ("treasury_stock_purchases", "dividends_paid", "senior_note_repayments", "net_revolver_repayments", "award_tax_withholding")) - cf["financing_cash_flow"],
            "cash_change": sum(cf[k] for k in ("operating_cash_flow", "investing_cash_flow", "financing_cash_flow", "fx_cash_effect")) - cf["net_cash_change"],
            "cash_rollforward": cf["beginning_cash"] + cf["net_cash_change"] - cf["ending_cash"],
            "cash_to_balance_sheet": cf["ending_cash"] - bs["cash"],
            "equity_rollforward": sum(eq[k] for k in ("beginning_equity", "net_income", "dividends", "stock_based_compensation", "award_tax_withholding", "treasury_stock_purchases", "other_comprehensive_income")) - eq["ending_equity"],
            "equity_to_balance_sheet": eq["ending_equity"] - bs["total_equity"],
            "shares": bs["shares_issued"] - bs["treasury_shares"] - bs["shares_outstanding"],
        }
        for name, difference in checks.items():
            results.append({"period": year, "check": name, "difference": difference,
                            "unit": "shares" if name == "shares" else "USD thousands",
                            "passed": difference == 0})
    return {"all_reconciled": all(x["passed"] for x in results), "items": results}


def normalize_wdfc(facts, model_date):
    if (facts.get("schema_version") != "1.0" or facts["entity"].get("currency") != "USD"
            or facts.get("units") != "USD thousands unless a field-specific unit says otherwise"):
        raise ValueError("Source schema, currency or monetary units do not match the USD-thousands adapter")
    if facts["entity"]["ticker"] != "WDFC":
        raise ValueError("The WD-40 normalization adapter cannot normalize another issuer")
    p = facts["periods"]["2025"]
    if _date(model_date, "model_date") < _date(p["period_end"], "source period"):
        raise ValueError("Model date cannot precede the source balance sheet")
    b = p["balance_sheet"]
    supplementary = {x["key"]: x for x in facts["supplemental_facts"]}
    current_lease = supplementary["current_operating_lease_liabilities"]["values"]["2025"]
    opening = {
        "period_end": model_date, "revenue": p["income_statement"]["revenue"],
        "cash": b["cash"], "accounts_receivable": b["accounts_receivable_net"],
        "inventory": b["inventory"], "operating_other_current_assets": 0,
        "other_current_assets": b["other_current_assets"], "net_ppe": b["ppe_net"],
        "net_intangibles": b["intangibles_net"],
        "other_noncurrent_assets": sum(b[k] for k in ("goodwill", "right_of_use_assets", "deferred_tax_assets_net", "other_noncurrent_assets")),
        "accounts_payable": b["accounts_payable"],
        "operating_accruals": b["accrued_liabilities"] + b["accrued_payroll"] - current_lease,
        "other_current_liabilities": b["income_taxes_payable"] + current_lease,
        "debt": b["short_term_borrowings"] + b["long_term_borrowings"],
        "other_noncurrent_liabilities": sum(b[k] for k in ("deferred_tax_liabilities_net", "long_term_operating_lease_liabilities", "other_long_term_liabilities")),
        "equity": b["total_equity"], "retained_earnings": b["retained_earnings"],
        "shares": b["shares_outstanding"], "tax_loss_carryforward": 0,
    }
    return {k: v if k in ("period_end", "shares") else v * 1000 for k, v in opening.items()}


def value_forecast(opening, forecast, assumptions):
    if type(opening) is not dict or not {"cash", "debt", "shares"} <= opening.keys():
        raise ValueError("DCF opening needs cash, debt and shares")
    for key in ("cash", "debt", "shares"):
        _number(opening[key], f"opening.{key}", 0)
    if opening["shares"] == 0:
        raise ValueError("DCF shares must be positive")
    if type(forecast) is not list or not 1 <= len(forecast) <= 30:
        raise ValueError("DCF forecast must contain one to thirty annual rows")
    for i, row in enumerate(forecast, 1):
        fields = {"year", "period_end", "ebit", "depreciation", "amortization", "capex", "delta_nwc", "tax_rate"}
        if type(row) is not dict or not fields <= row.keys():
            raise ValueError("DCF forecast row is missing required cash-flow fields")
        if type(row["year"]) is not int or row["year"] != i:
            raise ValueError("DCF forecast years must be consecutive integers starting at one")
        _date(row["period_end"], "DCF period end")
        for key in fields - {"year", "period_end"}:
            _number(row[key], key, -1e100 if key in ("ebit", "delta_nwc") else 0, 1 if key == "tax_rate" else 1e100)
    required = {"risk_free_rate", "equity_beta", "equity_risk_premium", "pretax_cost_of_debt",
                "target_debt_weight", "tax_rate", "terminal_growth", "terminal_roic", "other_claims"}
    if type(assumptions) is not dict or set(assumptions) != required:
        raise ValueError("Valuation assumptions must contain exactly the documented fields")
    a = {k: _number(v, k, 0, 1e15 if k == "other_claims" else (5 if k == "equity_beta" else 1))
         for k, v in assumptions.items()}
    cost_of_equity = a["risk_free_rate"] + a["equity_beta"] * a["equity_risk_premium"]
    wacc = cost_of_equity * (1 - a["target_debt_weight"]) + a["pretax_cost_of_debt"] * (1 - a["tax_rate"]) * a["target_debt_weight"]
    if not 0 <= a["terminal_growth"] < wacc <= 1 or not a["terminal_growth"] <= a["terminal_roic"] <= 1 or a["terminal_roic"] == 0:
        raise ValueError("Require WACC above nonnegative terminal growth and positive terminal ROIC at least equal to growth")
    rows = []
    for row in forecast:
        nopat = row["ebit"] * (1 - row["tax_rate"]) if row["ebit"] > 0 else row["ebit"]
        fcf = math.fsum((nopat, row["depreciation"], row["amortization"], -row["capex"], -row["delta_nwc"]))
        factor = (1 + wacc) ** -row["year"]
        rows.append({"year": row["year"], "period_end": row["period_end"], "nopat": nopat,
                     "fcff": fcf, "discount_factor": factor, "present_value": fcf * factor})
    terminal_nopat = forecast[-1]["ebit"] * (1 + a["terminal_growth"]) * (1 - a["tax_rate"])
    if terminal_nopat <= 0:
        raise ValueError("A nonpositive terminal NOPAT needs a separate terminal or restructuring method")
    terminal_reinvestment = terminal_nopat * a["terminal_growth"] / a["terminal_roic"]
    terminal_fcf = terminal_nopat - terminal_reinvestment
    terminal_value = terminal_fcf / (wacc - a["terminal_growth"])
    pv_terminal = terminal_value * rows[-1]["discount_factor"]
    operating_value = math.fsum([x["present_value"] for x in rows] + [pv_terminal])
    equity = math.fsum((operating_value, opening["cash"], -opening["debt"], -a["other_claims"]))
    result = {"cost_of_equity": cost_of_equity, "wacc": wacc, "forecast": rows,
            "terminal_nopat": terminal_nopat, "terminal_reinvestment": terminal_reinvestment,
            "terminal_fcff": terminal_fcf, "terminal_value": terminal_value, "pv_terminal": pv_terminal,
            "enterprise_value": operating_value, "equity_value": equity,
            "cash": opening["cash"], "debt": opening["debt"], "other_claims": a["other_claims"],
            "shares": opening["shares"], "value_per_share": equity / opening["shares"],
            "terminal_share_of_enterprise_value": pv_terminal / operating_value if operating_value > 0 else None,
            "convention": "Annual end-year FCFF. Recurring SBC stays an economic expense. Full reported cash bridge and current common shares; no option valuation."}
    for item in [result] + rows:
        if any(type(v) is float and not math.isfinite(v) for v in item.values()):
            raise ValueError("DCF output exceeds finite numerical resolution")
    return result


def compare_companies(facts, opening, cutoff, other_claims=0):
    other_claims = _number(other_claims, "target other claims", 0)
    for key in ("cash", "debt", "shares"):
        _number(opening[key], f"target {key}", 0)
    if not opening["shares"]:
        raise ValueError("Target shares must be positive")
    comparisons, tickers = [], set()
    cutoff_date = _date(cutoff, "analysis_cutoff")
    for peer in facts["comparables"]:
        ticker = peer["entity"]["ticker"]
        if type(ticker) is not str or not ticker or ticker in tickers:
            raise ValueError("Peer tickers must be nonempty and unique")
        tickers.add(ticker)
        price = _number(peer["quote"]["close"], "peer price", 0)
        if price == 0:
            raise ValueError("Peer price must be positive")
        quote_date = _date(peer["quote"]["date"], "peer quote date")
        if quote_date != cutoff_date:
            raise ValueError("Peer quote date must equal the common analysis cutoff")
        publication = _date(peer["financials_published_on"], "financial publication")
        if publication > cutoff_date:
            raise ValueError("Peer financials were not public at the analysis cutoff")
        if (_date(peer["shares"]["as_of"], "peer share-count date") > cutoff_date
                or _date(peer["fiscal_period_end"], "peer fiscal period") > publication):
            raise ValueError("Peer share count or financial period postdates the analysis cutoff")
        bridge = peer["suggested_enterprise_value_bridge"]
        for key in ("debt_including_finance_leases", "cash_to_deduct", "noncontrolling_interests", "preferred_stock", "other_claims", "nonoperating_assets_to_deduct"):
            _number(bridge[key], f"peer bridge.{key}", 0)
        shares = _number(peer["shares"]["value"], "peer shares", 0)
        ebit = _number(peer["constructed_operating_ebit"]["value"], "peer operating EBIT", 0) * 1000
        if "income_statement" in peer and ticker in ("RPM", "CLX"):
            inc = peer["income_statement"]
            expenses = (("cost_of_sales", "selling_general_administrative", "restructuring_expense", "goodwill_impairment")
                        if ticker == "RPM" else ("cost_of_products_sold", "selling_administrative", "advertising", "research_development", "loss_on_divestiture"))
            derived = _number(inc["revenue"], "peer reported revenue", 0) - math.fsum(
                _number(inc[k], f"peer expense.{k}", 0) for k in expenses)
            if ticker == "CLX":
                derived -= _number(inc["other_income_expense_components"]["intangible_amortization_expense"], "reclassified intangible amortization", 0)
            if not math.isclose(derived * 1000, ebit, rel_tol=1e-12, abs_tol=0):
                raise ValueError("Constructed peer EBIT does not reconcile to reported source lines")
        if not shares or not ebit:
            raise ValueError("Peer shares and EBIT must be positive")
        market_cap = price * shares
        ev = market_cap + 1000 * math.fsum((bridge["debt_including_finance_leases"], bridge["noncontrolling_interests"], bridge["preferred_stock"], bridge["other_claims"], -bridge["cash_to_deduct"], -bridge["nonoperating_assets_to_deduct"]))
        comparisons.append({"ticker": peer["entity"]["ticker"], "price": price, "price_date": quote_date.isoformat(),
                            "shares": shares, "market_cap": market_cap, "enterprise_value": ev,
                            "operating_ebit": ebit, "ev_ebit": ev / ebit,
                            "financial_period_end": peer["fiscal_period_end"], "share_count_date": peer["shares"]["as_of"]})
    if len(comparisons) < 2:
        raise ValueError("The case requires at least two documented comparison companies")
    multiples = [p["ev_ebit"] for p in comparisons]
    target_ebit = facts["periods"]["2025"]["income_statement"]["operating_income"] * 1000
    values = {}
    for label, multiple in (("low", min(multiples)), ("median", statistics.median(multiples)), ("high", max(multiples))):
        ev = multiple * target_ebit
        values[label] = {"multiple": multiple, "enterprise_value": ev,
                         "value_per_share": (ev + opening["cash"] - opening["debt"] - other_claims) / opening["shares"]}
    return {"peers": comparisons, "implied_values": values,
            "basis": "Selected FY2025 operating EBIT, common-date reference closes, disclosed financing/other claims. Two imperfect peers, not a full sector universe or latest-LTM dataset."}


def load_case():
    return json.loads(CASE_PATH.read_text()), json.loads(FACTS_PATH.read_text())


def evaluate_case(case, facts):
    required = {"schema_version", "case_id", "model_start_date", "analysis_cutoff", "selected_case", "cases", "valuation", "acquisition", "assumption_notes"}
    if type(case) is not dict or set(case) != required or case["schema_version"] != "1.0":
        raise ValueError("Case fields do not match schema 1.0")
    if (type(case["cases"]) is not dict or type(case["selected_case"]) is not str
            or case["selected_case"] not in case["cases"] or not 1 <= len(case["cases"]) <= 5):
        raise ValueError("Select an existing case from a set of one to five")
    if type(case["case_id"]) is not str or not 1 <= len(case["case_id"]) <= 100:
        raise ValueError("case_id must be nonempty text of at most 100 characters")
    if (type(case["assumption_notes"]) is not list or len(case["assumption_notes"]) > 100
            or any(type(n) is not str or len(n) > 4000 for n in case["assumption_notes"])):
        raise ValueError("assumption_notes must be at most 100 text notes")
    cutoff = _date(case["analysis_cutoff"], "analysis cutoff")
    if _date(case["model_start_date"], "model start") != cutoff:
        raise ValueError("The first case uses its analysis cutoff as its hypothetical model opening")
    for source in facts["sources"]:
        if source.get("published_on") is None and source.get("source_type") != "public_market_data_publisher":
            raise ValueError("A filing source needs a known publication date")
        if source.get("source_type") == "public_market_data_publisher":
            market_event = _date(source.get("market_event_date"), "market source event date")
            if market_event > cutoff:
                raise ValueError("Market source event postdates the analysis cutoff")
            if _date(source.get("retrieved_on"), "market source retrieval date") < market_event:
                raise ValueError("Market source retrieval cannot precede its event")
        if source.get("published_on") is not None and _date(source["published_on"], "source publication") > cutoff:
            raise ValueError("Source published after the analysis cutoff")
    known_sources = {source["id"] for source in facts["sources"]}
    if len(known_sources) != len(facts["sources"]):
        raise ValueError("Source IDs must be unique")

    def check_references(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "source_id" and value not in known_sources:
                    raise ValueError("Fact references an unknown source ID")
                if key == "source_ids" and (type(value) is not list or any(x not in known_sources for x in value)):
                    raise ValueError("Fact references unknown source IDs")
                check_references(value)
        elif isinstance(node, list):
            for value in node:
                check_references(value)

    check_references(facts)
    checks = historical_checks(facts)
    if not checks["all_reconciled"]:
        raise ValueError("Reported historical financial statements do not reconcile")
    quote = facts["market_quote"]
    if _number(quote["close"], "target reference price", 0) == 0:
        raise ValueError("Target reference price must be positive")
    if _date(quote["date"], "reference quote") != cutoff:
        raise ValueError("Target reference quote must match the case cutoff")
    opening = normalize_wdfc(facts, case["model_start_date"])
    drivers = deepcopy(case["cases"][case["selected_case"]])
    projection = project_statements(opening, drivers)
    valuation = value_forecast(opening, projection["forecast"], case["valuation"])
    comparison = compare_companies(facts, opening, case["analysis_cutoff"], case["valuation"]["other_claims"])
    financing_opening = {k: opening[k] for k in ("period_end", "cash", "debt", "tax_loss_carryforward")}
    financing_opening["other_claims"] = case["valuation"]["other_claims"]
    acquisition = evaluate_acquisition(financing_opening, projection["forecast"], case["acquisition"])
    digest = hashlib.sha256(json.dumps({"case": case, "facts": facts, "model_version": MODEL_VERSION}, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"model_version": MODEL_VERSION, "case_id": case["case_id"], "selected_case": case["selected_case"],
            "entity": facts["entity"], "analysis_cutoff": case["analysis_cutoff"], "model_start_date": case["model_start_date"],
            "source_balance_date": facts["periods"]["2025"]["period_end"], "currency": "USD", "input_digest": digest,
            "implementation": IMPLEMENTATION,
            "historical_checks": checks, "opening": opening, "projection": projection,
            "valuation": valuation, "comparables": comparison, "acquisition": acquisition,
            "market_quote": quote, "sources": facts["sources"], "assumption_notes": case["assumption_notes"],
            "status": "research_requires_review", "execution_allowed": False,
            "review_items": [
                "Reported August balances are carried unchanged into the hypothetical October opening. Verify interim operations, dividends, disposals and closing balances before real use.",
                "Forecast columns are model years ending October31, not the issuer's August fiscal-year forecasts.",
                "Market-price history was retrieved later; an archived point-in-time vendor vintage was not obtained.",
                "WACC, operating drivers, acquisition terms and terminal assumptions are editable analyst assumptions, not lender commitments or company guidance.",
                "Deferred taxes, leases, foreign exchange and other frozen balances have no detailed forecast schedules; current statutory tax and purchase accounting are outside this case.",
                "Reported cash availability, existing award dilution and debt-like claim completeness require review.",
                "Independent qualified human validation and employer acceptance remain outstanding.",
            ]}
