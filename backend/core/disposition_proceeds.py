"""Compare explicit settlement allocations using integer-cent inputs."""
from .acquisition_runs import sha

ROUTES = ("CASH_SALE", "PARTIAL_EXCHANGE", "FULL_INTENDED_EXCHANGE")
SETTLEMENT = ("gross_price", "selling_costs", "payoff", "other_settlement_obligations")
ALLOCATION = ("intermediary_funds", "other_owner_allocation", "tax_provision", "owner_reserve")


def compare(settlement, scenarios):
    if set(settlement) != set(SETTLEMENT) or set(scenarios) != set(ROUTES):
        raise ValueError("Supply all settlement fields and all three scenario routes")
    if any(set(values) != set(ALLOCATION) for values in scenarios.values()):
        raise ValueError("Supply all allocation fields for each route")
    values = [*settlement.values(), *(value for route in scenarios.values() for value in route.values())]
    if any(value is not None and (type(value) is not int or value < 0) for value in values):
        raise ValueError("Amounts must be nonnegative integer cents or null")
    if scenarios["CASH_SALE"]["intermediary_funds"] not in (0, None):
        raise ValueError("Cash sale cannot allocate funds to an intermediary")
    rows = []
    for route in ROUTES:
        allocation = scenarios[route]
        missing = [field for field in SETTLEMENT if settlement[field] is None]
        missing += [field for field in ALLOCATION if allocation[field] is None]
        net = owner = headroom = None
        if not missing:
            net = settlement["gross_price"] - sum(settlement[key] for key in SETTLEMENT[1:])
            owner = net - allocation["intermediary_funds"] - allocation["other_owner_allocation"]
            headroom = owner - allocation["tax_provision"] - allocation["owner_reserve"]
        rows.append(dict(route=route, missing_inputs=missing, settlement_net_cents=net,
                         modeled_owner_distribution_cents=owner, modeled_headroom_cents=headroom,
                         authorized_spendable_cash_cents=None,
                         status="HOLD_MISSING_INPUTS" if missing else
                         "REVIEW_SHORTFALL" if headroom < 0 else "REVIEW_SCENARIO"))
    return dict(input_sha256=sha({"settlement":settlement,"scenarios":scenarios}),
                scenarios=rows, election=None, financial_authority_cents=0)
