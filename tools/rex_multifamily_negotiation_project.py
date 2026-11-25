"""Compare hypothetical purchase terms for the REX-02.05 training case."""
from decimal import Decimal, ROUND_FLOOR
import json

from tools.rex_multifamily_underwriting_project import hold_analysis, run


def compare(hold, debt_cents, cash_cost_cents, proposed_prices, *, rights_verified):
    if hold["status"] != "HYPOTHETICAL":
        return {"decision": "HOLD", "price_ceiling_cents": None, "options": []}

    rate = Decimal(hold["discount_rate"])
    ceilings = {}
    for name, scenario in hold["scenarios"].items():
        future_cash = scenario["equity_cash_flows_cents"][1:]
        present_value = sum(
            Decimal(cash) / (1 + rate) ** year
            for year, cash in enumerate(future_cash, start=1)
        )
        ceiling = present_value + debt_cents - cash_cost_cents
        ceilings[name] = int(ceiling.to_integral_value(rounding=ROUND_FLOOR))

    binding_ceiling = min(ceilings.values())
    options = []
    for label, price in proposed_prices.items():
        cash_required = price + cash_cost_cents - debt_cents
        within_ceiling = 0 <= cash_required and price <= binding_ceiling
        options.append({
            "label": label,
            "price_cents": price,
            "initial_equity_cents": cash_required,
            "within_ceiling": within_ceiling,
            "decision": "ELIGIBLE_FOR_TRAINING_REVIEW" if rights_verified and within_ceiling else "HOLD",
        })
    return {
        "decision": "HYPOTHETICAL_COMPARISON" if rights_verified else "HOLD",
        "rights_verified": rights_verified,
        "fixed_debt_cents": debt_cents,
        "acquisition_cost_cents": cash_cost_cents,
        "scenario_ceilings_cents": ceilings,
        "price_ceiling_cents": binding_ceiling,
        "options": options,
    }


if __name__ == "__main__":
    print(json.dumps(compare(
        hold_analysis(run()), 22_000_000, 500_000,
        {"ask": 29_500_000, "lower_price": 28_800_000},
        rights_verified=False,
    ), indent=2))
