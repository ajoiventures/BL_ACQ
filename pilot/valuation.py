"""Deterministic, unlevered USD valuation; this module never approves a transaction.

Rates are decimal fractions and amounts are absolute dollars, not millions. See
``docs/guides/valuation.md`` for timing, terminal assumptions and numeric limits.
"""

import math


_CORPORATE = {
    "revenue", "operating_margin", "growth_rate", "target_margin", "tax_rate",
    "wacc", "terminal_growth", "sales_to_capital", "terminal_roic", "years",
    "cash", "non_operating_assets", "debt", "debt_like_claims", "units",
}
_PROPERTY = {
    "noi", "growth_rate", "discount_rate", "terminal_cap_rate", "annual_capex",
    "selling_cost_rate", "years", "debt", "cash", "units",
}
_PATHS = {"growth_path", "margin_path", "tax_path", "discount_path"}
_SHOCK_DEFAULTS = {
    "near_term_growth_delta": 0.0, "near_term_margin_delta": 0.0,
    "long_term_growth_delta": 0.0, "long_term_margin_delta": 0.0,
    "discount_rate_delta": 0.0, "reinvestment_multiplier": 1.0,
    "one_time_cost": 0.0, "duration_years": 1,
}
_MAX_AMOUNT = 1e15
_MAX_OUTPUT = 1e100
_SAMPLES = 129


def _number(name, value, low, high, *, open_low=False):
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number, not a boolean or string")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or result > high or result < low or (open_low and result == low):
        bound = "greater than" if open_low else "at least"
        raise ValueError(f"{name} must be {bound} {low} and at most {high}")
    return result


def _integer(name, value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}")
    return value


def _dictionary(name, value, allowed, required=()):
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise ValueError(f"{name} must be a dictionary with string keys")
    missing, extra = set(required) - value.keys(), value.keys() - allowed
    if missing:
        raise ValueError(f"{name} is missing: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{name} has unknown keys: {', '.join(sorted(extra))}")


def _inputs(model_type, assumptions, shock):
    if model_type not in ("corporate_dcf", "property_dcf"):
        raise ValueError("model_type must be corporate_dcf or property_dcf")
    corporate = model_type == "corporate_dcf"
    required = _CORPORATE if corporate else _PROPERTY
    optional = _PATHS | {"reinvestment_timing"} if corporate else set()
    _dictionary("assumptions", assumptions, required | optional, required)
    a = dict(assumptions)
    a["years"] = _integer("years", a["years"], 1, 30)
    amounts = {"cash", "debt", "revenue", "non_operating_assets", "debt_like_claims"} if corporate else {
        "cash", "debt", "noi", "annual_capex"}
    for key in amounts:
        a[key] = _number(key, a[key], 0, _MAX_AMOUNT, open_low=key in ("revenue", "noi"))
    a["units"] = _number("units", a["units"], 0, _MAX_AMOUNT, open_low=True)
    a["growth_rate"] = _number("growth_rate", a["growth_rate"], -1, 3, open_low=True)
    if corporate:
        for key in ("operating_margin", "target_margin"):
            a[key] = _number(key, a[key], -1, 1)
        for key in ("tax_rate", "wacc"):
            a[key] = _number(key, a[key], 0, 1)
        a["terminal_growth"] = _number("terminal_growth", a["terminal_growth"], 0, 0.20)
        a["terminal_roic"] = _number("terminal_roic", a["terminal_roic"], 0, 1, open_low=True)
        a["sales_to_capital"] = _number("sales_to_capital", a["sales_to_capital"], 0.01, 100)
        a["reinvestment_timing"] = a.get("reinvestment_timing", "same_year")
        if a["reinvestment_timing"] not in ("same_year", "next_year"):
            raise ValueError("reinvestment_timing must be same_year or next_year")
        limits = {"growth_path": (-1, 3, True), "margin_path": (-1, 1, False),
                  "tax_path": (0, 1, False), "discount_path": (0, 1, False)}
        for key in _PATHS & a.keys():
            if type(a[key]) is not list or len(a[key]) != a["years"]:
                raise ValueError(f"{key} must be a list with exactly years entries")
            low, high, open_low = limits[key]
            a[key] = [_number(f"{key}[{i}]", value, low, high, open_low=open_low)
                      for i, value in enumerate(a[key])]
    else:
        a["discount_rate"] = _number("discount_rate", a["discount_rate"], 0, 1)
        a["terminal_cap_rate"] = _number("terminal_cap_rate", a["terminal_cap_rate"], 0, 1, open_low=True)
        a["selling_cost_rate"] = _number("selling_cost_rate", a["selling_cost_rate"], 0, 1)
        if a["units"] != 1:
            raise ValueError("property_dcf units must be 1 for the whole property")
    if shock is None:
        shock = {}
    _dictionary("shock", shock, set(_SHOCK_DEFAULTS))
    s = _SHOCK_DEFAULTS | shock
    s["duration_years"] = _integer("duration_years", s["duration_years"], 0, 30)
    for key in s.keys() - {"duration_years", "one_time_cost", "reinvestment_multiplier"}:
        s[key] = _number(key, s[key], -1, 1)
    s["one_time_cost"] = _number("one_time_cost", s["one_time_cost"], 0, _MAX_AMOUNT)
    s["reinvestment_multiplier"] = _number("reinvestment_multiplier", s["reinvestment_multiplier"], 0, 10)
    if not s["duration_years"] and (s["near_term_growth_delta"] or s["near_term_margin_delta"]):
        raise ValueError("nonzero near-term shocks require duration_years greater than zero")
    if not corporate and (s["near_term_margin_delta"] or s["long_term_margin_delta"]):
        raise ValueError("property_dcf does not accept nonzero margin deltas; change NOI or growth")
    return a, s


def _finite(value, name):
    if not math.isfinite(value) or abs(value) > _MAX_OUTPUT:
        raise ValueError(f"{name} exceeds the finite model numeric envelope")
    return value


def _corporate(a, s):
    years, revenue = a["years"], a["revenue"]
    terminal_growth = a["terminal_growth"]
    terminal_margin = _number("effective terminal margin", a["target_margin"] + s["long_term_margin_delta"], -1, 1)
    discount = a.get("discount_path", [a["wacc"]] * years)
    terminal_rate = _number("effective terminal discount rate", discount[-1] + s["discount_rate_delta"], 0, 1)
    if terminal_rate <= terminal_growth:
        raise ValueError("terminal discount rate must exceed terminal_growth")
    if a["terminal_roic"] < terminal_growth:
        raise ValueError("terminal_roic must be at least terminal_growth")
    reinvestment_rate = terminal_growth / a["terminal_roic"] * s["reinvestment_multiplier"]
    if reinvestment_rate > 1:
        raise ValueError("effective terminal reinvestment exceeds NOPAT; terminal growth is not sustainable")
    rows, discount_factor = [], 1.0
    for year in range(1, years + 1):
        fraction = (year - 1) / (years - 1) if years > 1 else 0
        growth = a.get("growth_path", [])[year - 1] if "growth_path" in a else (
            a["growth_rate"] + (terminal_growth - a["growth_rate"]) * fraction)
        growth += s["long_term_growth_delta"]
        if year <= s["duration_years"]:
            growth += s["near_term_growth_delta"]
        growth = _number(f"effective growth in year {year}", growth, -1, 5, open_low=True)
        margin = a["margin_path"][year - 1] if "margin_path" in a else (
            a["operating_margin"] + (a["target_margin"] - a["operating_margin"]) * year / years)
        margin += s["long_term_margin_delta"]
        if year <= s["duration_years"]:
            margin += s["near_term_margin_delta"]
        margin = _number(f"effective margin in year {year}", margin, -1, 1)
        tax_rate = a["tax_path"][year - 1] if "tax_path" in a else a["tax_rate"]
        rate = _number(f"effective discount rate in year {year}", discount[year - 1] + s["discount_rate_delta"], 0, 1)
        previous_revenue, revenue = revenue, _finite(revenue * (1 + growth), "forecast revenue")
        operating_profit = revenue * margin
        tax = max(operating_profit, 0.0) * tax_rate
        discount_factor /= 1 + rate
        rows.append({"year": year, "revenue": revenue, "noi": None, "growth_rate": growth,
                     "operating_margin": margin, "operating_profit": operating_profit,
                     "tax_rate": tax_rate, "tax": tax, "nopat": operating_profit - tax,
                     "reinvestment": max(revenue - previous_revenue, 0.0) / a["sales_to_capital"],
                     "discount_rate": rate, "discount_factor": discount_factor})
    terminal_revenue = revenue * (1 + terminal_growth)
    terminal_nopat = terminal_revenue * terminal_margin * (1 - a["tax_rate"])
    if terminal_nopat <= 0:
        raise ValueError("corporate_dcf requires positive sustainable terminal NOPAT")
    terminal_cash_flow = terminal_nopat * (1 - reinvestment_rate)
    terminal_value = _finite(terminal_cash_flow / (terminal_rate - terminal_growth), "terminal value")
    for i, row in enumerate(rows):
        if a["reinvestment_timing"] == "next_year":
            next_revenue = rows[i + 1]["revenue"] if i + 1 < years else terminal_revenue
            row["reinvestment"] = max(next_revenue - row["revenue"], 0.0) / a["sales_to_capital"]
        row["reinvestment"] *= s["reinvestment_multiplier"]
        row["one_time_cost"] = s["one_time_cost"] if i == 0 else 0.0
        row["fcf"] = row["nopat"] - row["reinvestment"] - row["one_time_cost"]
        row["pv"] = row["fcf"] * row["discount_factor"]
    details = {"terminal_cash_flow": terminal_cash_flow, "terminal_nopat": terminal_nopat,
               "terminal_reinvestment": terminal_nopat * reinvestment_rate,
               "effective_discount_rate": terminal_rate, "effective_terminal_growth": terminal_growth,
               "effective_terminal_margin": terminal_margin,
               "effective_terminal_roic": (_finite(a["terminal_roic"] / s["reinvestment_multiplier"],
                                                    "effective terminal ROIC")
                                           if s["reinvestment_multiplier"] else None)}
    claims = a["debt"] + a["debt_like_claims"] - a["cash"] - a["non_operating_assets"]
    return rows, terminal_value, claims, details


def _property(a, s):
    rate = _number("effective discount_rate", a["discount_rate"] + s["discount_rate_delta"], 0, 1)
    long_growth = _number("effective long-term NOI growth", a["growth_rate"] + s["long_term_growth_delta"], -1, 5, open_low=True)
    noi, rows, discount_factor = a["noi"], [], 1.0
    for year in range(1, a["years"] + 1):
        growth = long_growth + (s["near_term_growth_delta"] if year <= s["duration_years"] else 0)
        growth = _number(f"effective NOI growth in year {year}", growth, -1, 5, open_low=True)
        noi = _finite(noi * (1 + growth), "forecast NOI")
        capex = a["annual_capex"] * s["reinvestment_multiplier"]
        cost = s["one_time_cost"] if year == 1 else 0.0
        fcf = noi - capex - cost
        discount_factor /= 1 + rate
        rows.append({"year": year, "revenue": None, "noi": noi, "growth_rate": growth,
                     "operating_margin": None, "operating_profit": noi, "tax_rate": None,
                     "tax": 0.0, "nopat": noi, "reinvestment": capex, "one_time_cost": cost,
                     "fcf": fcf, "discount_rate": rate, "discount_factor": discount_factor,
                     "pv": fcf * discount_factor})
    terminal_noi = noi * (1 + long_growth)
    terminal_value = _finite(terminal_noi / a["terminal_cap_rate"] * (1 - a["selling_cost_rate"]), "terminal value")
    return rows, terminal_value, a["debt"] - a["cash"], {
        "terminal_cash_flow": terminal_noi, "terminal_noi": terminal_noi,
        "effective_discount_rate": rate, "effective_terminal_cap_rate": a["terminal_cap_rate"],
    }


def value_model(model_type: str, assumptions: dict, shock: dict | None = None) -> dict:
    """Return an unrounded operating-asset/equity DCF, or raise ValueError.

    Taxes never credit operating losses. Financing cash flows must be excluded
    from operating inputs, and claims already captured in FCF must not be deducted
    again. Property cash flows are before investor income tax and debt service.
    """
    a, s = _inputs(model_type, assumptions, shock)
    rows, terminal, claims, details = (_corporate(a, s) if model_type == "corporate_dcf" else _property(a, s))
    pv_terminal = _finite(terminal * rows[-1]["discount_factor"], "present terminal value")
    enterprise = _finite(math.fsum(row["pv"] for row in rows) + pv_terminal, "enterprise value")
    equity = _finite(enterprise - claims, "equity value")
    price = _finite(equity / a["units"], "value per unit")
    terminal_share = _finite(pv_terminal / enterprise, "terminal share") if enterprise > 0 else None
    warnings = ["Model estimate only; evidence quality and transaction approval are separate.",
                "Exclude financing cash flows and do not deduct claims already included in FCF."]
    if terminal_share is not None and terminal_share > 0.75:
        warnings.append("More than 75% of operating-asset value comes from the terminal assumption.")
    if any(row["fcf"] < 0 for row in rows):
        warnings.append("Negative forecast cash flow requires financing or available liquidity not modeled here.")
    if equity < 0:
        warnings.append("Equity value is negative; it is not floored at zero or an option valuation.")
    if enterprise <= 0:
        warnings.append("Terminal share is undefined because operating-asset value is nonpositive.")
    if s["near_term_growth_delta"]:
        warnings.append("Temporary growth rates recover, but the lost or gained revenue/NOI level persists.")
    if (s["near_term_growth_delta"] or s["near_term_margin_delta"]) and s["duration_years"] >= a["years"]:
        warnings.append("The temporary shock spans the explicit forecast; recovery is assumed at the terminal transition.")
    if s["reinvestment_multiplier"] == 0:
        warnings.append("Zero reinvestment is an optimistic assumption; the model does not establish its feasibility.")
    if model_type == "property_dcf":
        warnings.append("Property value is before investor income tax and debt service; NOI must exclude modeled capex.")
    return {"model_type": model_type, "value_per_unit": price, "equity_value": equity,
            "enterprise_value": enterprise, "net_claims": claims, "terminal_value": terminal,
            "pv_terminal": pv_terminal, "terminal_share": terminal_share, "forecast": rows,
            "warnings": warnings, **details}


def reverse_growth(model_type, assumptions, shock, target_price, low=-0.20, high=0.80) -> dict:
    """Solve scalar initial growth, after a deterministic monotonicity screen.

    Bounds are observed model bounds, not a statement of economically possible
    growth. A reported solution is verified by revaluing at the implied rate.
    """
    a, s = _inputs(model_type, assumptions, shock)
    target = _number("target_price", target_price, -_MAX_AMOUNT, _MAX_AMOUNT)
    low = _number("low", low, -1, 3, open_low=True)
    high = _number("high", high, -1, 3, open_low=True)
    if low >= high:
        raise ValueError("low must be less than high")
    value_model(model_type, a, s)
    result = {"target_price": target, "growth_bounds": {"low": low, "high": high},
              "implied_growth_rate": None, "implied_rate": None, "achieved_price": None,
              "iterations": 0, "attainable_bounds": None, "sample_count": 0}
    if "growth_path" in a:
        return result | {"status": "unsupported_explicit_path",
                         "reason": "An explicit growth_path overrides scalar growth_rate; no inverse is defined."}

    def price_at(growth):
        return value_model(model_type, a | {"growth_rate": growth}, s)["value_per_unit"]

    samples = [(low + (high - low) * i / (_SAMPLES - 1), None) for i in range(_SAMPLES)]
    samples = [(growth, price_at(growth)) for growth, _ in samples]
    prices = [price for _, price in samples]
    tolerance = max(1e-8, abs(target) * 1e-10)
    monotonic_tolerance = max(1e-10, max(abs(price) for price in prices) * 1e-12)
    rising = any(b - a > monotonic_tolerance for a, b in zip(prices, prices[1:]))
    falling = any(a - b > monotonic_tolerance for a, b in zip(prices, prices[1:]))
    result |= {"attainable_bounds": {"minimum": min(prices), "maximum": max(prices),
                                     "price_at_low": prices[0], "price_at_high": prices[-1],
                                     "basis": "129 sampled growth rates"}, "sample_count": _SAMPLES}
    if rising == falling:
        return result | {"status": "non_monotonic", "reason": (
            "The sampled growth/value curve changes direction; a unique inverse is not established."
            if rising else "The sampled growth/value curve is flat; a unique inverse is not established.")}
    if target < min(prices) - tolerance or target > max(prices) + tolerance:
        return result | {"status": "out_of_range", "reason": "Target is outside the observed value range for the selected growth bounds."}
    for growth, price in (samples[0], samples[-1]):
        if abs(price - target) <= tolerance:
            return result | {"status": "solved", "implied_growth_rate": growth, "implied_rate": growth,
                             "achieved_price": price, "reason": "Target verified at a growth bound."}
    left, right = low, high
    for iteration in range(1, 101):
        midpoint = (left + right) / 2
        price = price_at(midpoint)
        if abs(price - target) <= tolerance:
            return result | {"status": "solved", "implied_growth_rate": midpoint,
                             "implied_rate": midpoint, "achieved_price": price, "iterations": iteration,
                             "reason": "Bisection solution independently revalued within price tolerance."}
        if (price < target) == rising:
            left = midpoint
        else:
            right = midpoint
    return result | {"status": "out_of_range", "iterations": 100,
                     "reason": "No verified solution within tolerance; numerical precision limit reached."}


def sensitivity_grid(model_type, assumptions, shock) -> dict:
    """Return a 5x5 per-unit grid. Invalid cells contain null and a reason."""
    a, s = _inputs(model_type, assumptions, shock)
    baseline = value_model(model_type, a, s)
    corporate = model_type == "corporate_dcf"
    rate_key = "wacc" if corporate else "discount_rate"
    column_key = "terminal_growth" if corporate else "terminal_cap_rate"
    offsets = (-0.02, -0.01, 0.0, 0.01, 0.02)
    row_values = [baseline["effective_discount_rate"] + offset for offset in offsets]
    column_values = [a[column_key] + offset for offset in (-0.01, -0.005, 0.0, 0.005, 0.01)]
    cells = []
    for offset in offsets:
        row = []
        for column in column_values:
            scenario = a | {rate_key: a[rate_key] + offset, column_key: column}
            if corporate and "discount_path" in a:
                scenario["discount_path"] = [rate + offset for rate in a["discount_path"]]
            try:
                value = value_model(model_type, scenario, s)["value_per_unit"]
                row.append({"value_per_unit": value, "reason": None})
            except ValueError as exc:
                row.append({"value_per_unit": None, "reason": str(exc)})
        cells.append(row)
    return {"model_type": model_type, "row_parameter": rate_key, "row_values": row_values,
            "column_parameter": column_key, "column_values": column_values, "cells": cells,
            "row_definition": "Effective terminal discount rate; parallel shift if discount_path is supplied.",
            "units": "USD per unit"}
