from backend.core.disposition_proceeds import ALLOCATION, ROUTES, SETTLEMENT, compare


def test_settlement_bridge_keeps_intermediary_funds_and_tax_out_of_headroom():
    settlement = dict(gross_price=100, selling_costs=10, payoff=20, other_settlement_obligations=5)
    common = dict(other_owner_allocation=5,tax_provision=10,owner_reserve=10)
    scenarios = {route:dict(common,intermediary_funds=transfer)
                 for route,transfer in zip(ROUTES,(0,30,60))}
    rows = compare(settlement,scenarios)["scenarios"]
    assert [row["settlement_net_cents"] for row in rows] == [65]*3
    assert [row["modeled_headroom_cents"] for row in rows] == [40,10,-20]
    assert rows[-1]["status"] == "REVIEW_SHORTFALL"
    assert all(row["authorized_spendable_cash_cents"] is None for row in rows)


def test_unknown_inputs_stay_unknown():
    result = compare(dict.fromkeys(SETTLEMENT), {route:dict.fromkeys(ALLOCATION) for route in ROUTES})
    assert all(row["status"] == "HOLD_MISSING_INPUTS" and row["modeled_headroom_cents"] is None
               for row in result["scenarios"])
