"""Linked annual corporate statements in absolute USD, without a balancing plug.

This is a bounded research model, not a GAAP reporting or tax-compliance engine.
The explicit conventions are returned with every report and documented in
``docs/guides/corporate_model.md``. No AI, network, database or execution is used.
"""

from calendar import monthrange
from datetime import date
import math
import re


MODEL_VERSION = "br-statements-1"
_MAX_INPUT = 1e15
_MAX_OUTPUT = 1e100
_RELATIVE_TOLERANCE = 1e-12
_DAY_BASIS = 365.0

OPENING_FIELDS = frozenset({
    "period_end", "revenue", "cash", "accounts_receivable", "inventory",
    "operating_other_current_assets", "other_current_assets", "net_ppe",
    "net_intangibles", "other_noncurrent_assets", "accounts_payable",
    "operating_accruals", "other_current_liabilities", "debt",
    "other_noncurrent_liabilities", "equity", "retained_earnings", "shares",
    "tax_loss_carryforward",
})
DRIVER_FIELDS = frozenset({
    "period_end", "revenue_growth", "gross_margin", "ebitda_margin",
    "depreciation_rate", "amortization", "capex_pct_revenue", "intangible_capex",
    "receivable_days", "inventory_days", "payable_days",
    "operating_other_current_assets_pct_revenue", "operating_accruals_pct_revenue",
    "tax_rate", "nol_utilization_limit", "interest_rate", "debt_issued",
    "debt_repaid", "dividend_payout", "stock_compensation_pct_revenue",
    "stock_compensation_share_price", "equity_issued", "issuance_share_price",
    "shares_repurchased", "repurchase_share_price", "minimum_cash",
})
_ASSETS = (
    "cash", "accounts_receivable", "inventory", "operating_other_current_assets",
    "other_current_assets", "net_ppe", "net_intangibles", "other_noncurrent_assets",
)
_LIABILITIES = (
    "accounts_payable", "operating_accruals", "other_current_liabilities", "debt",
    "other_noncurrent_liabilities",
)
_FROZEN_BALANCES = (
    "other_current_assets", "other_noncurrent_assets", "other_current_liabilities",
    "other_noncurrent_liabilities",
)


def _object(name, value, fields):
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    missing, extra = fields - value.keys(), value.keys() - fields
    if missing:
        raise ValueError(f"{name} is missing: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{name} has unknown keys: {', '.join(sorted(extra))}")


def _number(name, value, low=0.0, high=_MAX_INPUT, *, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not a boolean or string")
    try:
        number = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number) or not low <= number <= high or (positive and number <= low):
        raise ValueError(f"{name} is outside its permitted finite numeric range")
    return number


def _date(name, value):
    if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{name} must be an ISO date YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid calendar date") from exc


def _anniversary(opening_date, year):
    target_year = opening_date.year + year
    if target_year > 9999:
        raise ValueError("Forecast dates exceed the supported calendar")
    day = min(opening_date.day, monthrange(target_year, opening_date.month)[1])
    return date(target_year, opening_date.month, day)


def _check(*parts):
    # No fixed currency floor. The tolerance represents numerical computation,
    # not a financial-statement rounding or materiality policy.
    residual = math.fsum(parts)
    tolerance = max((abs(value) for value in parts), default=0.0) * _RELATIVE_TOLERANCE
    return {"residual": residual, "tolerance": tolerance, "passed": abs(residual) <= tolerance}


def _opening(raw):
    _object("opening", raw, OPENING_FIELDS)
    opening_date = _date("opening.period_end", raw["period_end"])
    result = {"period_end": opening_date.isoformat()}
    for key in sorted(OPENING_FIELDS - {"period_end"}):
        result[key] = _number("opening." + key, raw[key],
                              -_MAX_INPUT if key in ("equity", "retained_earnings") else 0,
                              positive=key in ("revenue", "shares"))
    balance = _check(*(result[key] for key in _ASSETS),
                     *(-result[key] for key in _LIABILITIES), -result["equity"])
    if not balance["passed"]:
        raise ValueError("Opening balance sheet does not balance within numerical tolerance")
    return result, opening_date, balance


def _drivers(raw, opening_date):
    if type(raw) is not list or not 1 <= len(raw) <= 10:
        raise ValueError("drivers must be a list of one to ten annual driver objects")
    percentages = {
        "gross_margin", "depreciation_rate", "capex_pct_revenue",
        "operating_other_current_assets_pct_revenue", "operating_accruals_pct_revenue",
        "tax_rate", "nol_utilization_limit", "interest_rate", "dividend_payout",
        "stock_compensation_pct_revenue",
    }
    days = {"receivable_days", "inventory_days", "payable_days"}
    prices = {"stock_compensation_share_price", "issuance_share_price", "repurchase_share_price"}
    normalized = []
    for index, record in enumerate(raw, 1):
        name = f"drivers[{index - 1}]"
        _object(name, record, DRIVER_FIELDS)
        period = _date(name + ".period_end", record["period_end"])
        if period != _anniversary(opening_date, index):
            raise ValueError(f"{name}.period_end must be annual anniversary {_anniversary(opening_date, index)}")
        item = {"period_end": period.isoformat()}
        for key in sorted(DRIVER_FIELDS - {"period_end"}):
            low, high = (0, 1) if key in percentages else (0, 3650) if key in days else (0, _MAX_INPUT)
            if key == "revenue_growth":
                low, high = -1, 3
            elif key == "ebitda_margin":
                low, high = -1, 1
            item[key] = _number(name + "." + key, record[key], low, high,
                                positive=key == "revenue_growth" or key in prices)
        if item["ebitda_margin"] > item["gross_margin"]:
            raise ValueError(f"{name}.ebitda_margin cannot exceed the pre-D&A gross margin")
        operating_expense_ratio = item["gross_margin"] - item["ebitda_margin"]
        if (item["stock_compensation_pct_revenue"] > operating_expense_ratio
                and not math.isclose(item["stock_compensation_pct_revenue"], operating_expense_ratio,
                                     rel_tol=_RELATIVE_TOLERANCE, abs_tol=0)):
            raise ValueError(f"{name}.stock_compensation_pct_revenue exceeds pre-D&A operating expense")
        normalized.append(item)
    return normalized


def _nwc(record):
    return math.fsum((record["accounts_receivable"], record["inventory"],
                      record["operating_other_current_assets"], -record["accounts_payable"],
                      -record["operating_accruals"]))


def _verify_finite(record):
    for key, value in record.items():
        if type(value) in (int, float) and (not math.isfinite(value) or abs(value) > _MAX_OUTPUT):
            raise ValueError(f"Forecast {key} exceeds the finite output envelope")


def project_statements(opening, drivers):
    """Project linked annual statements and expose reconciliation/liquidity issues.

    Every schema field is required, including explicit zero values. Inputs are
    copied and never mutated. See OPENING_FIELDS, DRIVER_FIELDS and the guide for
    definitions. A ``calculated`` status is arithmetic completion, not approval.
    """
    first, opening_date, opening_check = _opening(opening)
    assumptions = _drivers(drivers, opening_date)
    previous = dict(first)
    previous["other_equity"] = first["equity"] - first["retained_earnings"]
    forecast = []
    for year, driver in enumerate(assumptions, 1):
        revenue = previous["revenue"] * (1 + driver["revenue_growth"])
        cogs = revenue * (1 - driver["gross_margin"])
        gross_profit = revenue - cogs
        ebitda = revenue * driver["ebitda_margin"]
        operating_expenses = gross_profit - ebitda
        depreciation = previous["net_ppe"] * driver["depreciation_rate"]
        amortization = driver["amortization"]
        if amortization > previous["net_intangibles"]:
            raise ValueError(f"Year {year}: amortization exceeds opening finite-lived intangible assets")
        ebit = math.fsum((ebitda, -depreciation, -amortization))
        stock_compensation = revenue * driver["stock_compensation_pct_revenue"]
        interest = previous["debt"] * driver["interest_rate"]
        pretax_income = ebit - interest
        opening_nol = previous["tax_loss_carryforward"]
        positive_taxable_income = max(pretax_income, 0.0)
        nol_generated = max(-pretax_income, 0.0)
        nol_used = min(opening_nol, positive_taxable_income * driver["nol_utilization_limit"])
        taxable_income = positive_taxable_income - nol_used
        taxes = taxable_income * driver["tax_rate"]
        net_income = pretax_income - taxes
        ppe_capex = revenue * driver["capex_pct_revenue"]
        intangible_capex = driver["intangible_capex"]
        capex = ppe_capex + intangible_capex
        debt_issued, debt_repaid = driver["debt_issued"], driver["debt_repaid"]
        if debt_repaid > previous["debt"] + debt_issued:
            raise ValueError(f"Year {year}: debt repayment exceeds available debt principal")
        dividends = max(net_income, 0.0) * driver["dividend_payout"]
        equity_issued = driver["equity_issued"]
        cash_issue_shares = equity_issued / driver["issuance_share_price"]
        stock_compensation_shares = stock_compensation / driver["stock_compensation_share_price"]
        shares_repur = driver["shares_repurchased"]
        repurchases = shares_repur * driver["repurchase_share_price"]
        closing_shares = math.fsum((previous["shares"], cash_issue_shares, stock_compensation_shares, -shares_repur))
        if closing_shares <= 0:
            raise ValueError(f"Year {year}: share repurchase leaves no positive outstanding shares")

        row = {
            "year": year, "period_end": driver["period_end"],
            "opening_revenue": previous["revenue"], "revenue": revenue,
            "revenue_growth": driver["revenue_growth"], "gross_margin": driver["gross_margin"],
            "cogs": cogs, "cogs_before_da": cogs, "gross_profit": gross_profit,
            "gross_profit_before_da": gross_profit,
            "operating_expenses_before_da": operating_expenses,
            "cash_operating_expenses_before_da": operating_expenses - stock_compensation,
            "ebitda": ebitda, "ebitda_margin": driver["ebitda_margin"],
            "depreciation": depreciation, "amortization": amortization, "ebit": ebit,
            "stock_compensation": stock_compensation, "interest_expense": interest,
            "pretax_income": pretax_income, "tax_rate": driver["tax_rate"],
            "nol_utilization_limit": driver["nol_utilization_limit"], "opening_nol": opening_nol,
            "nol_generated": nol_generated, "nol_used": nol_used,
            "taxable_income_before_nol": positive_taxable_income, "taxable_income": taxable_income,
            "tax_expense": taxes, "cash_taxes": taxes, "net_income": net_income,
            "opening_ppe": previous["net_ppe"], "ppe_capex": ppe_capex,
            "net_ppe": math.fsum((previous["net_ppe"], ppe_capex, -depreciation)),
            "opening_intangibles": previous["net_intangibles"], "intangible_capex": intangible_capex,
            "net_intangibles": math.fsum((previous["net_intangibles"], intangible_capex, -amortization)),
            "capex": capex,
            "accounts_receivable": revenue * driver["receivable_days"] / _DAY_BASIS,
            "inventory": cogs * driver["inventory_days"] / _DAY_BASIS,
            "operating_other_current_assets": revenue * driver["operating_other_current_assets_pct_revenue"],
            "accounts_payable": cogs * driver["payable_days"] / _DAY_BASIS,
            "operating_accruals": revenue * driver["operating_accruals_pct_revenue"],
            "opening_debt": previous["debt"], "debt_issued": debt_issued, "debt_repaid": debt_repaid,
            "debt": math.fsum((previous["debt"], debt_issued, -debt_repaid)),
            "tax_loss_carryforward": math.fsum((opening_nol, nol_generated, -nol_used)),
            "dividends": dividends, "equity_issued": equity_issued,
            "cash_issue_shares": cash_issue_shares, "stock_compensation_shares": stock_compensation_shares,
            "shares_repurchased": shares_repur, "repurchases": repurchases,
            "opening_shares": previous["shares"], "shares": closing_shares,
            "weighted_average_shares": previous["shares"],
            "eps": net_income / previous["shares"],
            "opening_retained_earnings": previous["retained_earnings"],
            "retained_earnings": math.fsum((previous["retained_earnings"], net_income, -dividends)),
            "opening_other_equity": previous["other_equity"],
            "other_equity": math.fsum((previous["other_equity"], stock_compensation, equity_issued, -repurchases)),
            "opening_equity": previous["equity"], "opening_cash": previous["cash"],
            "minimum_cash": driver["minimum_cash"],
        }
        row.update({key: previous[key] for key in _FROZEN_BALANCES})
        row["equity"] = row["retained_earnings"] + row["other_equity"]
        row["opening_nwc"] = _nwc(previous)
        row["nwc"] = _nwc(row)
        row["delta_nwc"] = row["nwc"] - row["opening_nwc"]
        row["cash_from_operations"] = math.fsum((net_income, depreciation, amortization,
                                                stock_compensation, -row["delta_nwc"]))
        row["cash_from_investing"] = -capex
        row["cash_from_financing"] = math.fsum((debt_issued, -debt_repaid, -dividends, equity_issued, -repurchases))
        row["change_in_cash"] = math.fsum((row["cash_from_operations"], row["cash_from_investing"],
                                          row["cash_from_financing"]))
        row["cash"] = math.fsum((previous["cash"], row["cash_from_operations"],
                                  row["cash_from_investing"], row["cash_from_financing"]))
        # A zero-cash boundary can subtract larger flows. Use local floating-
        # point resolution to avoid a spurious gap when equivalent inputs are
        # rescaled. The reported allowance has no fixed currency floor.
        row["cash_roundoff_tolerance"] = 8 * max(math.ulp(value) for value in (
            previous["cash"], row["cash_from_operations"], row["cash_from_investing"],
            row["cash_from_financing"], driver["minimum_cash"], row["cash"],
        ))
        cash_gap = max(driver["minimum_cash"] - row["cash"], 0.0)
        row["funding_shortfall"] = cash_gap if cash_gap > row["cash_roundoff_tolerance"] else 0.0
        row["total_assets"] = math.fsum(row[key] for key in _ASSETS)
        row["total_liabilities"] = math.fsum(row[key] for key in _LIABILITIES)
        row["total_liabilities_and_equity"] = row["total_liabilities"] + row["equity"]
        # Economic FCFF retains recurring SBC as compensation expense. This is
        # deliberately different from the statement CFO's equity-award addback.
        # No levered NOL tax benefit is mixed into this unlevered metric.
        row["unlevered_cash_tax_before_nol"] = max(ebit, 0.0) * driver["tax_rate"]
        row["fcff"] = math.fsum((ebit, -row["unlevered_cash_tax_before_nol"], depreciation,
                                 amortization, -capex, -row["delta_nwc"]))
        row["fcfe_before_cash_equity_transactions"] = math.fsum((row["cash_from_operations"], -capex,
                                                                 debt_issued, -debt_repaid))
        _verify_finite(row)
        row["checks"] = {
            "income_statement": _check(revenue, -cogs, -operating_expenses, -depreciation,
                                        -amortization, -interest, -taxes, -net_income),
            "balance_sheet": _check(*(row[key] for key in _ASSETS),
                                     *(-row[key] for key in _LIABILITIES), -row["equity"]),
            "cash_rollforward": _check(row["cash"], -previous["cash"], -row["cash_from_operations"],
                                        -row["cash_from_investing"], -row["cash_from_financing"]),
            "operating_cash_flow": _check(row["cash_from_operations"], -ebitda, -stock_compensation,
                                           interest, taxes, row["delta_nwc"]),
            "ppe_rollforward": _check(row["net_ppe"], -previous["net_ppe"], -ppe_capex, depreciation),
            "intangibles_rollforward": _check(row["net_intangibles"], -previous["net_intangibles"],
                                               -intangible_capex, amortization),
            "debt_rollforward": _check(row["debt"], -previous["debt"], -debt_issued, debt_repaid),
            "equity_rollforward": _check(row["equity"], -previous["equity"], -net_income, dividends,
                                          -stock_compensation, -equity_issued, repurchases),
            "retained_earnings_rollforward": _check(row["retained_earnings"], -previous["retained_earnings"],
                                                     -net_income, dividends),
            "shares_rollforward": _check(closing_shares, -previous["shares"], -cash_issue_shares,
                                          -stock_compensation_shares, shares_repur),
            "nol_rollforward": _check(row["tax_loss_carryforward"], -opening_nol, -nol_generated, nol_used),
        }
        forecast.append(row)
        previous = row

    shortfalls = [row["year"] for row in forecast if row["funding_shortfall"] > 0]
    negative_cash = [row["year"] for row in forecast if row["cash"] < -row["cash_roundoff_tolerance"]]
    negative_equity = [row["year"] for row in forecast if row["equity"] < 0]
    reconciled = opening_check["passed"] and all(check["passed"] for row in forecast for check in row["checks"].values())
    warnings = [
        "Normalized annual research statements; no GAAP, tax, or institutional-use approval is implied.",
        "Forecast COGS and gross margin exclude D&A; all modeled D&A is deducted below EBITDA.",
        "Other current/noncurrent assets and liabilities are frozen, with no FX, OCI, acquisitions or impairment forecast.",
        "Aggregate debt has no current/noncurrent maturity classification; borrowing and repayment are explicit year-end inputs.",
        "SBC is expensed in EBITDA, added back to statement CFO, credited to equity, and settled in new shares at the assumed price.",
        "FCFF retains recurring SBC as an economic expense and excludes levered NOL benefits.",
        "Tax assumes book pretax income equals taxable income except for the specified NOL schedule; jurisdictional limitations are not modeled.",
    ]
    if shortfalls:
        warnings.append("Minimum cash is unmet in forecast years " + ", ".join(map(str, shortfalls)) + "; no automatic funding is inserted.")
    if negative_cash:
        warnings.append("Negative projected cash is an unfunded gap, not an executable cash balance; later periods remain mechanical projections.")
    if negative_equity:
        warnings.append("Negative book equity occurs in forecast years " + ", ".join(map(str, negative_equity)) + ".")
    return {
        "model_version": MODEL_VERSION, "currency": "USD", "amount_scale": 1,
        "opening": first, "forecast": forecast,
        "checks": {"opening_balance_sheet": opening_check, "all_reconciled": reconciled,
                   "all_minimum_cash_requirements_met": not shortfalls,
                   "funding_shortfall_years": shortfalls, "negative_cash_years": negative_cash,
                   "negative_equity_years": negative_equity},
        "status": "reconciliation_error" if not reconciled else "funding_shortfall" if shortfalls else "calculated",
        "warnings": warnings,
        "conventions": {
            "periods": "Annual anniversaries; February 29 rolls to February 28 only in nonleap years; no stub periods.",
            "working_capital_day_basis": _DAY_BASIS,
            "income_statement": "COGS and gross margin before D&A; all SBC in operating expense before D&A; all D&A below EBITDA.",
            "capex": "PPE and intangible additions occur at year end; depreciation uses opening net PPE; amortization cannot exceed opening intangibles.",
            "interest": "Simple annual rate times opening debt; no interest income, intra-year draws, fees, capitalized interest or interest limits.",
            "tax": "Losses create nominal NOLs without a tax credit; use is capped by the specified fraction of positive pretax income; no expiry or DTA recognition.",
            "equity": "All share movements occur at year end. SBC immediately issues common shares at the specified price; no vesting, options or net settlement.",
            "eps": "Net income divided by opening shares because all forecast share changes occur at year end.",
            "cash": "Cash is calculated from the three cash-flow sections; no balancing plug or automatic financing. Funding comparisons expose an eight-ULP local roundoff allowance.",
            "fcff": "EBIT less tax on positive EBIT, plus D&A, less total capex and change in operating NWC; no SBC addback or NOL benefit.",
            "numerical_relative_tolerance": _RELATIVE_TOLERANCE,
        },
    }
