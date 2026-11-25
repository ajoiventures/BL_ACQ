"""Run and verify the REX-02.03 hypothetical multifamily underwriting exercise."""
from decimal import Decimal, ROUND_HALF_EVEN
import json

from backend.core.profit_review import review
from tools.apply_profit_review import hypothetical, packet


def run():
    inputs = packet("REX-02.03", "Hypothetical duplex training case")
    annual = {
        "revenue_cents": 3_648_000, "operating_cost_cents": 1_120_000,
        "debt_service_cents": 1_800_000, "reserve_contribution_cents": 240_000,
        "cash_capex_cents": 120_000,
    }
    capital = {"opening_unrestricted_cash_cents": 750_000, "opening_unspent_reserves_cents": 100_000}
    sale = {
        "gross_price_cents": 34_000_000, "selling_costs_cents": 2_040_000,
        "debt_payoff_cents": 22_000_000, "tax_reserve_cents": 900_000,
        "other_cash_costs_cents": 180_000, "redeployment_commitment_cents": 6_000_000,
    }
    for key, values in (("operations", annual), ("capital", capital), ("sale", sale)):
        inputs[key] = {k: hypothetical(v, "urn:black-river:rex-02.03") for k, v in values.items()}
    inputs["scenarios"] = [{"id": "VACANCY", "label": "20% vacancy on scheduled rent",
                            "operations": {"revenue_cents": hypothetical(3_072_000, "urn:black-river:rex-02.03")}}]
    return review(inputs)


def hold_analysis(report):
    """Discount the explicit year-end equity cash flows of the training case."""
    rate = Decimal("0.08")
    equity = 8_000_000
    base = report["operating_review"]["distributable_cash_cents"]
    stress = report["scenarios"][0]["result"]["distributable_cash_cents"]
    sale = report["sale_review"]["net_cash_available_before_redeployment_cents"]
    if any(value is None for value in (base, stress, sale)):
        return {"status": "NEEDS_EVIDENCE", "npv_cents": None}
    scenarios = {}
    for name, year_two in (("base", base), ("vacancy_in_year_two", stress)):
        cash = [-equity, base, year_two, base + sale]
        npv = sum(Decimal(value) / (1 + rate) ** year for year, value in enumerate(cash))
        scenarios[name] = {
            "equity_cash_flows_cents": cash,
            "npv_cents": int(npv.quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)),
        }
    return {"status": "HYPOTHETICAL", "discount_rate": str(rate), "scenarios": scenarios,
            "exit_year": 3, "exit_proceeds_cents": sale}


if __name__ == "__main__":
    operating_report = run()
    print(json.dumps({"annual_and_sale": operating_report,
                      "three_year_hold": hold_analysis(operating_report)}, indent=2))
