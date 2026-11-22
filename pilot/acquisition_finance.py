"""Deterministic annual acquisition financing, with no transaction authority.

Amounts are absolute USD. The model uses annual cash flows, beginning-of-year
debt interest and end-of-year debt movements. Stock compensation in the incoming
operating forecast is replaced with an equal cash expense for the hypothetical
acquisition; it is not added back to sponsor cash flow. See the file guide for
the cash-free/debt-free bridge, tax assumptions and supported-use boundary.
"""

from datetime import date
import math


MODEL_VERSION = "br-acquisition-finance-1"
_MAX_AMOUNT = 1e15
_REQUIRED_OPENING = {"period_end", "cash", "debt", "tax_loss_carryforward"}
_OPENING = _REQUIRED_OPENING | {"other_claims"}
_TERM_KEYS = {
    "entry_enterprise_value", "transaction_fee_rate", "financing_fee_rate",
    "initial_term_debt", "term_interest_rate", "term_amortization_rate",
    "term_maturity_year", "revolver_limit", "revolver_interest_rate",
    "minimum_cash", "cash_sweep_rate", "exit_ebitda_multiple", "exit_fee_rate",
    "nol_utilization_limit", "max_net_leverage", "min_interest_coverage",
}
_OPTIONAL_TERMS = {"max_net_leverage", "min_interest_coverage"}
_FORECAST_NUMBERS = {
    "revenue", "cogs", "ebitda", "ebit", "depreciation", "amortization",
    "stock_compensation", "capex", "delta_nwc", "tax_rate",
}


def _number(name, value, low=0.0, high=_MAX_AMOUNT, *, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not a boolean or string")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if (not math.isfinite(value) or value < low or value > high
            or (positive and value == 0)):
        raise ValueError(f"{name} is outside the supported numeric range")
    return value


def _object(name, value, allowed, required):
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError(f"{name} must be an object with string keys")
    if missing := required - value.keys():
        raise ValueError(f"{name} is missing: {', '.join(sorted(missing))}")
    if extra := value.keys() - allowed:
        raise ValueError(f"{name} has unknown keys: {', '.join(sorted(extra))}")


def _date(name, value):
    if type(value) is not str:
        raise ValueError(f"{name} must be an ISO calendar date")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO calendar date") from exc
    if result.isoformat() != value:
        raise ValueError(f"{name} must use YYYY-MM-DD")
    return result


def _anniversary(start, years):
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        if start.month == 2 and start.day == 29:
            return date(start.year + years, 2, 28)
        raise ValueError("Forecast dates exceed the supported calendar range")


def _tolerance(*values):
    """Arithmetic resolution at the local scale, with no fixed USD floor."""
    return 32 * max(math.ulp(value) for value in values)


def _finite(value, name):
    if not math.isfinite(value) or abs(value) > 1e100:
        raise ValueError(f"{name} exceeds the supported output range")
    return value


def _exceeds(value, reference):
    return value > reference and not math.isclose(value, reference, rel_tol=1e-12, abs_tol=0.0)


def annual_irr(cash_flows):
    """Solve a unique conventional annual IRR, without guessing across roots.

    A strictly negative initial contribution and nonnegative subsequent receipts
    establish a single root when at least one receipt is positive. Multiple sign
    patterns return an explicit unsupported result. A complete loss is reported
    as a -100% annualized boundary convention, not as a finite NPV root.
    """
    if type(cash_flows) is not list or not 2 <= len(cash_flows) <= 31:
        raise ValueError("cash_flows must contain two to 31 annual values")
    flows = [_number(f"cash_flows[{i}]", item, -1e100, 1e100)
             for i, item in enumerate(cash_flows)]
    result = {"rate": None, "iterations": 0, "relative_npv_residual": None}
    if flows[0] >= 0 or any(item < 0 for item in flows[1:]):
        return result | {"status": "unsupported_cash_flow_pattern",
                         "reason": "Requires one initial contribution followed only by nonnegative receipts."}
    if not any(flows[1:]):
        return result | {"status": "total_loss", "rate": -1.0,
                         "reason": "No receipts; -100% is the annualized total-loss boundary convention."}

    # Evaluate discounted positive receipts in log space. Scaling every flow
    # cannot change the root and tiny contributions do not cause division overflow.
    initial_log = math.log(-flows[0])
    receipts = [(i, math.log(amount) - initial_log)
                for i, amount in enumerate(flows[1:], 1) if amount > 0]

    def log_value(log_gross_return):
        parts = [amount_log - period * log_gross_return for period, amount_log in receipts]
        largest = max(parts)
        return largest + math.log(math.fsum(math.exp(part - largest) for part in parts))

    left, right = -745.0, 709.0
    if log_value(left) < 0 or log_value(right) > 0:
        return result | {"status": "numerical_limit",
                         "reason": "The unique conventional root is outside finite rate resolution."}
    for iteration in range(1, 161):
        midpoint = (left + right) / 2
        residual = log_value(midpoint)
        if abs(residual) <= 1e-12 or midpoint in (left, right):
            rate = math.expm1(midpoint)
            if not math.isfinite(rate) or rate <= -1:
                return result | {"status": "numerical_limit", "iterations": iteration,
                                 "reason": "The root cannot be represented as a finite rate above -100%."}
            return result | {"status": "solved", "rate": rate, "iterations": iteration,
                             "relative_npv_residual": math.expm1(residual),
                             "reason": "Unique conventional annual root."}
        if residual > 0:
            left = midpoint
        else:
            right = midpoint
    return result | {"status": "numerical_limit", "iterations": 160,
                     "reason": "Annual IRR did not converge within the numerical tolerance."}


def _inputs(opening, operating_forecast, terms):
    _object("opening", opening, _OPENING, _REQUIRED_OPENING)
    start = _date("opening.period_end", opening["period_end"])
    initial = {key: _number(f"opening.{key}", opening.get(key, 0.0)) for key in _OPENING - {"period_end"}}
    initial["period_end"] = start.isoformat()
    _object("terms", terms, _TERM_KEYS, _TERM_KEYS - _OPTIONAL_TERMS)
    t = {}
    for key in _TERM_KEYS - {"term_maturity_year"} - _OPTIONAL_TERMS:
        upper = 1 if key.endswith("_rate") or key == "nol_utilization_limit" else _MAX_AMOUNT
        if key == "exit_ebitda_multiple":
            upper = 100
        t[key] = _number(f"terms.{key}", terms[key], high=upper,
                         positive=key in {"entry_enterprise_value", "exit_ebitda_multiple"})
    maturity = terms["term_maturity_year"]
    if type(maturity) is not int or not 1 <= maturity <= 30:
        raise ValueError("term_maturity_year must be an integer from one to 30")
    t["term_maturity_year"] = maturity
    for key in _OPTIONAL_TERMS:
        t[key] = None if terms.get(key) is None else _number(f"terms.{key}", terms[key], high=100, positive=True)

    if type(operating_forecast) is not list or not 1 <= len(operating_forecast) <= 10:
        raise ValueError("operating_forecast must contain one to ten annual rows")
    rows = []
    for i, source in enumerate(operating_forecast, 1):
        # Full linked-statement rows carry additional schedules. Required finance
        # fields are validated here; other reported fields are intentionally unused.
        if type(source) is not dict or (_FORECAST_NUMBERS | {"year", "period_end"}) - source.keys():
            raise ValueError(f"operating_forecast[{i - 1}] is missing required finance fields")
        if type(source["year"]) is not int or source["year"] != i:
            raise ValueError("Forecast years must be consecutive integers starting at one")
        end = _date(f"forecast[{i - 1}].period_end", source["period_end"])
        if end != _anniversary(start, i):
            raise ValueError("Forecast periods must be exact annual anniversaries of opening.period_end")
        row = {"year": i, "period_end": end.isoformat()}
        for key in _FORECAST_NUMBERS:
            low = -_MAX_AMOUNT if key in {"ebitda", "ebit", "delta_nwc"} else 0
            row[key] = _number(f"forecast[{i - 1}].{key}", source[key], low,
                               1 if key == "tax_rate" else _MAX_AMOUNT,
                               positive=key == "revenue")
        computed_ebitda = math.fsum((row["ebit"], row["depreciation"], row["amortization"]))
        if abs(computed_ebitda - row["ebitda"]) > _tolerance(computed_ebitda, row["ebitda"]):
            raise ValueError("Forecast EBITDA must equal EBIT plus depreciation and amortization")
        rows.append(row)
    return initial, rows, t


def evaluate_acquisition(opening, operating_forecast, terms):
    """Build the financing and investor-return schedule for a hypothetical buyout."""
    initial, operations, t = _inputs(opening, operating_forecast, terms)
    seller_equity = math.fsum((t["entry_enterprise_value"], initial["cash"], -initial["debt"], -initial["other_claims"]))
    if seller_equity < 0:
        raise ValueError("Negative seller equity requires a separate restructuring model")
    acquired_cash_used = max(0.0, initial["cash"] - t["minimum_cash"])
    cash_top_up = max(0.0, t["minimum_cash"] - initial["cash"])
    transaction_fees = t["entry_enterprise_value"] * t["transaction_fee_rate"]
    financing_fees = t["initial_term_debt"] * t["financing_fee_rate"]
    uses = math.fsum((seller_equity, initial["debt"], initial["other_claims"], transaction_fees,
                      financing_fees, cash_top_up))
    sponsor_equity = math.fsum((uses, -acquired_cash_used, -t["initial_term_debt"]))
    if sponsor_equity <= _tolerance(uses, acquired_cash_used, t["initial_term_debt"]):
        raise ValueError("The supported transaction must require a positive sponsor equity contribution")
    sources = math.fsum((sponsor_equity, t["initial_term_debt"], acquired_cash_used))
    initial_cash = math.fsum((initial["cash"], -acquired_cash_used, cash_top_up))
    sources_uses = {
        "entry_enterprise_value": t["entry_enterprise_value"], "seller_equity_purchase": seller_equity,
        "existing_debt_payoff": initial["debt"], "existing_other_claims_payoff": initial["other_claims"],
        "transaction_fees": transaction_fees,
        "financing_fees": financing_fees, "cash_top_up": cash_top_up, "total_uses": uses,
        "new_term_debt": t["initial_term_debt"], "acquired_cash_used": acquired_cash_used,
        "sponsor_equity": sponsor_equity, "total_sources": sources,
        "sources_less_uses": sources - uses, "acquired_cash_retained": initial_cash,
    }
    cash, term, revolver = initial_cash, t["initial_term_debt"], 0.0
    nol = initial["tax_loss_carryforward"]
    schedule, issues = [], []
    for op in operations:
        year = op["year"]
        opening_cash, opening_term, opening_revolver, opening_nol = cash, term, revolver, nol
        term_interest = opening_term * t["term_interest_rate"]
        revolver_interest = opening_revolver * t["revolver_interest_rate"]
        interest = term_interest + revolver_interest
        pretax_income = op["ebit"] - interest
        nol_generated = max(0.0, -pretax_income)
        nol_used = min(opening_nol, max(pretax_income, 0.0) * t["nol_utilization_limit"])
        taxable_income = max(pretax_income, 0.0) - nol_used
        cash_taxes = taxable_income * op["tax_rate"]
        nol = math.fsum((opening_nol, nol_generated, -nol_used))
        net_income = pretax_income - cash_taxes
        # Recurring SBC remains an expense. A cash replacement prevents an
        # unsupported increase in sponsor cash flow through an ignored dilution.
        cash_flow_available_for_debt_service = math.fsum((
            op["ebitda"], -cash_taxes, -op["capex"], -op["delta_nwc"],
        ))
        cash_flow_after_interest = cash_flow_available_for_debt_service - interest
        cash_before_debt = math.fsum((opening_cash, cash_flow_after_interest))
        scheduled_due = min(opening_term, t["initial_term_debt"] * t["term_amortization_rate"])
        maturity_at_exit = year == len(operations) == t["term_maturity_year"]
        # A balloon due on the modeled sale date is settled by that same exit
        # transaction. Requiring a pre-sale draw would manufacture a refinancing
        # need. Earlier maturities remain payable in the operating waterfall.
        maturity_due_before_exit = (max(0.0, opening_term - scheduled_due)
                                    if year >= t["term_maturity_year"] and not maturity_at_exit else 0.0)
        mandatory_due = scheduled_due + maturity_due_before_exit
        revolver_capacity = max(0.0, t["revolver_limit"] - opening_revolver)
        requested_draw = max(0.0, t["minimum_cash"] + mandatory_due - cash_before_debt)
        revolver_draw = min(revolver_capacity, requested_draw)
        cash_with_draw = math.fsum((cash_before_debt, revolver_draw))
        mandatory_paid = min(mandatory_due, max(0.0, cash_with_draw - t["minimum_cash"]))
        mandatory_shortfall = max(0.0, mandatory_due - mandatory_paid)
        cash_after_mandatory = cash_with_draw - mandatory_paid
        revolver_before_paydown = opening_revolver + revolver_draw
        revolver_repayment = min(revolver_before_paydown,
                                 max(0.0, cash_after_mandatory - t["minimum_cash"]))
        cash_after_revolver = cash_after_mandatory - revolver_repayment
        term_after_mandatory = max(0.0, opening_term - mandatory_paid)
        term_sweep = min(term_after_mandatory,
                         max(0.0, cash_after_revolver - t["minimum_cash"]) * t["cash_sweep_rate"])
        term = max(0.0, term_after_mandatory - term_sweep)
        revolver = max(0.0, revolver_before_paydown - revolver_repayment)
        cash = cash_after_revolver - term_sweep
        liquidity_shortfall = max(0.0, t["minimum_cash"] - cash)
        cash_tolerance = _tolerance(opening_cash, cash_flow_after_interest, mandatory_due,
                                    revolver_draw, cash, t["minimum_cash"])
        year_issues = []
        if liquidity_shortfall > cash_tolerance:
            year_issues.append({"year": year, "kind": "liquidity_shortfall", "amount": liquidity_shortfall})
        if mandatory_shortfall > cash_tolerance:
            year_issues.append({"year": year, "kind": "unpaid_mandatory_principal", "amount": mandatory_shortfall})

        net_debt = math.fsum((term, revolver, -cash))
        net_leverage = net_debt / op["ebitda"] if op["ebitda"] > 0 else None
        interest_coverage = op["ebitda"] / interest if interest > 0 else None
        contractual_debt_service = interest + mandatory_due
        debt_service_coverage = (cash_flow_available_for_debt_service / contractual_debt_service
                                 if contractual_debt_service > 0 else None)
        if t["max_net_leverage"] is not None and (
            net_leverage is None or _exceeds(net_leverage, t["max_net_leverage"])
        ):
            year_issues.append({"year": year, "kind": "net_leverage_covenant",
                                "observed": net_leverage, "limit": t["max_net_leverage"]})
        if (t["min_interest_coverage"] is not None and interest > 0
                and _exceeds(t["min_interest_coverage"], interest_coverage)):
            year_issues.append({"year": year, "kind": "interest_coverage_covenant",
                                "observed": interest_coverage, "limit": t["min_interest_coverage"]})
        issues.extend(year_issues)
        row = op | {
            "opening_cash": opening_cash, "opening_term_debt": opening_term,
            "opening_revolver": opening_revolver, "term_interest": term_interest,
            "revolver_interest": revolver_interest, "interest": interest,
            "pretax_income": pretax_income, "opening_nol": opening_nol,
            "nol_generated": nol_generated, "nol_used": nol_used, "closing_nol": nol,
            "taxable_income": taxable_income, "cash_taxes": cash_taxes, "net_income": net_income,
            "cash_flow_available_for_debt_service": cash_flow_available_for_debt_service,
            "cash_flow_after_interest": cash_flow_after_interest, "cash_before_debt": cash_before_debt,
            "scheduled_principal_due": scheduled_due,
            "maturity_principal_due_before_exit": maturity_due_before_exit,
            "maturity_balloon_due_at_exit": term if maturity_at_exit else 0.0,
            "mandatory_principal_due": mandatory_due, "mandatory_principal_paid": mandatory_paid,
            "mandatory_principal_shortfall": mandatory_shortfall, "revolver_draw": revolver_draw,
            "revolver_repayment": revolver_repayment, "term_cash_sweep": term_sweep,
            "closing_term_debt": term, "closing_revolver": revolver, "closing_cash": cash,
            "liquidity_shortfall": liquidity_shortfall, "net_debt": net_debt,
            "net_leverage": net_leverage, "interest_coverage": interest_coverage,
            "contractual_debt_service": contractual_debt_service,
            "debt_service_coverage": debt_service_coverage,
            "cash_rollforward_difference": cash - math.fsum((opening_cash, cash_flow_after_interest,
                revolver_draw, -mandatory_paid, -revolver_repayment, -term_sweep)),
            "term_rollforward_difference": term - math.fsum((opening_term, -mandatory_paid, -term_sweep)),
            "revolver_rollforward_difference": revolver - math.fsum((opening_revolver, revolver_draw,
                                                                     -revolver_repayment)),
            "issues": year_issues,
        }
        for key, value in row.items():
            if type(value) is float:
                _finite(value, key)
        schedule.append(row)

    final = schedule[-1]
    if final["ebitda"] <= 0:
        issues.append({"year": final["year"], "kind": "unsupported_nonpositive_exit_ebitda"})
        exit_ev = None
    else:
        exit_ev = final["ebitda"] * t["exit_ebitda_multiple"]
    exit_fees = exit_ev * t["exit_fee_rate"] if exit_ev is not None else None
    exit_before_floor = math.fsum((exit_ev, -exit_fees, cash, -term, -revolver)) if exit_ev is not None else None
    equity_proceeds = max(0.0, exit_before_floor) if exit_before_floor is not None else None
    exit_debt_shortfall = max(0.0, -exit_before_floor) if exit_before_floor is not None else None
    if (exit_debt_shortfall is not None
            and exit_debt_shortfall > _tolerance(exit_ev, exit_fees, cash, term, revolver)):
        issues.append({"year": final["year"], "kind": "exit_debt_repayment_shortfall", "amount": exit_debt_shortfall})
    feasible = not issues
    exit_report = {
        "period_end": final["period_end"], "ebitda": final["ebitda"],
        "enterprise_value": exit_ev, "exit_fees": exit_fees, "cash": cash,
        "term_debt_payoff": term, "revolver_payoff": revolver,
        "term_maturity_settlement": term if t["term_maturity_year"] == len(schedule) else 0.0,
        "maturity_coincides_with_exit": t["term_maturity_year"] == len(schedule),
        "equity_before_limited_liability_floor": exit_before_floor,
        "debt_repayment_shortfall": exit_debt_shortfall,
        "sponsor_equity_proceeds": equity_proceeds, "indicative_only": not feasible,
    }
    if feasible:
        flows = [-sponsor_equity] + [0.0] * (len(schedule) - 1) + [equity_proceeds]
        irr = annual_irr(flows)
        moic = _finite(equity_proceeds / sponsor_equity, "moic")
        returns = {"status": irr["status"], "sponsor_cash_flows": flows,
                   "cash_flow_dates": [initial["period_end"]] + [row["period_end"] for row in schedule],
                   "invested_equity": sponsor_equity, "proceeds": equity_proceeds,
                   "moic": moic, "annual_irr": irr["rate"], "irr_detail": irr,
                   "timing": "Equal annual periods; end-of-year exit, with no interim distributions."}
    else:
        returns = {"status": "unavailable_financing_or_exit_failure", "sponsor_cash_flows": None,
                   "cash_flow_dates": None, "invested_equity": sponsor_equity, "proceeds": None,
                   "moic": None, "annual_irr": None, "irr_detail": None,
                   "timing": "Returns withheld because the modeled financing or exit conditions fail."}
    return {
        "model_version": MODEL_VERSION, "currency": "USD", "opening": initial, "terms": t,
        "sources_uses": sources_uses, "schedule": schedule, "exit": exit_report, "returns": returns,
        "feasibility": {"status": "modeled_feasible" if feasible else "not_feasible",
                        "issues": issues, "execution_allowed": False},
        "conventions": [
            "Entry enterprise value excludes all cash and interest-bearing debt; required operating cash is funded separately.",
            "Existing debt is repaid at close; only acquired cash above minimum cash is a funding source.",
            "Other declared debt-like claims reduce seller equity and are separately settled at face amount at close; this is an explicit assumption, not a tax-settlement prediction.",
            "Interest uses beginning-of-year balances; draws, repayments and sweeps occur at year end.",
            "Revolver is assumed available through exit; annual balances do not model seasonal liquidity or lender commitments.",
            "Mandatory term principal, then revolver repayment, then the selected term cash sweep use cash above the reserve.",
            "A term maturity before exit must be funded in the annual waterfall. If maturity coincides with exit, scheduled amortization remains a period obligation and the residual balloon is settled once from exit proceeds.",
            "Debt-service coverage uses cash interest plus required principal before the exit transaction; a coincident sale-settled balloon is shown separately and tested in the exit repayment bridge.",
            "Recurring stock compensation is replaced by equal cash compensation; no SBC addback or sponsor dilution is assumed.",
            "Cash taxes use a simple NOL allowance and fully deductible interest; transaction/change-of-control tax rules are outside scope.",
            "Fees are paid at close or exit without tax deductions, financing-fee amortization or purchase accounting.",
            "No interim sponsor distributions; all residual cash and debt are included once in the exit equity bridge.",
            "Negative exit equity is floored at zero for limited liability; this does not model debt recovery or lender losses.",
        ],
    }
