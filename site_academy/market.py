"""Research-only workbook calculations. Rates are fractions, amounts are US dollars."""
import json
from math import isfinite


def number(value, name, *, positive=False, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError(f"{name} requires a finite number")
    if value < 0 or (positive and value == 0) or (maximum is not None and value > maximum):
        raise ValueError(f"{name} outside permitted range")
    return value


def cap_scenario(monthly_rent, expense_fraction, cap_rate):
    rent = number(monthly_rent, "monthly_rent")
    expenses = number(expense_fraction, "expense_fraction", maximum=1)
    rate = number(cap_rate, "cap_rate", positive=True, maximum=1)
    annual_income = rent * 12 * (1 - expenses)
    return {"annual_income_proxy": annual_income, "indicated_value": annual_income / rate}


def price_band(area_sqft, low_per_sqft, high_per_sqft):
    area = number(area_sqft, "area_sqft", positive=True)
    low = number(low_per_sqft, "low_per_sqft")
    high = number(high_per_sqft, "high_per_sqft", positive=True)
    if low > high:
        raise ValueError("lower price exceeds upper price")
    return [area * (low + quartile * (high - low) / 4) for quartile in range(5)]


def overlap(band_a, band_b):
    for bounds in [band_a, band_b]:
        if len(bounds) != 2 or number(bounds[0], "low") > number(bounds[1], "high"):
            raise ValueError("expected ascending price pair")
    low, high = max(band_a[0], band_b[0]), min(band_a[1], band_b[1])
    return [low, high] if low <= high else None


def arv_screen(arv, renovation, transaction_fraction, other, assignment, purchase):
    for key, value in locals().copy().items():
        number(value, key, maximum=1 if key == "transaction_fraction" else None)
    transaction = arv * transaction_fraction
    residual = arv - renovation - transaction - other - assignment
    return {"transaction": transaction, "residual": residual, "spread": residual - purchase}


def exit_bridge(entry, markup, fee_revenue, renovation, days, cost_per_day, transaction_rate, commission_rate):
    for key, value in locals().copy().items():
        number(value, key, maximum=1 if key in ("transaction_rate", "commission_rate") else None)
    if int(days) != days:
        raise ValueError("days requires a whole number")
    resale = entry * (1 + markup)
    holding = days * cost_per_day
    margin = resale + fee_revenue - entry - renovation - holding - entry * (transaction_rate + commission_rate)
    return {"resale_assumption": resale, "holding": holding, "estimated_margin": margin}


if __name__ == "__main__":
    print(json.dumps({
        "status": "workbook simulation",
        "three_percent": cap_scenario(3000, .25, .03),
        "five_percent": cap_scenario(3000, .25, .05),
        "price_levels": price_band(3300, 186, 196),
        "arv_left": arv_screen(550000, 10000, .09, 0, 15000, 425000),
        "arv_right": arv_screen(155000, 5000, .09, 0, 15000, 115000),
    }, indent=2))
