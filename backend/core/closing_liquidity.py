"""Evidence-gated closing liquidity calculations in integer cents."""

COMMON = ("purchase_price", "closing_costs", "immediate_repairs", "initial_reserves",
          "buyer_cash_available", "buyer_liquidity_floor")
EXTRA = {
    "CASH": (),
    "SELLER_NOTE": ("seller_note_proceeds", "annual_debt_service", "balloon_due",
                    "funds_available_at_balloon", "annual_cash_before_debt"),
    "JOINT_VENTURE": ("committed_partner_cash", "buyer_capital_call_reserve"),
}


def compare_closing_liquidity(structure, inputs):
    if structure not in EXTRA:
        raise ValueError("Unknown closing structure")
    required = COMMON + EXTRA[structure]
    if set(inputs) - set(required):
        raise ValueError("Unexpected closing input")
    for name, value in inputs.items():
        if value is not None and (type(value) is not int or (value < 0 and name != "annual_cash_before_debt")):
            raise ValueError("Closing inputs must be integer cents within the permitted range or null")
    missing = [name for name in required if inputs.get(name) is None]
    result = dict(structure=structure, missing_inputs=missing, closing_outlay_cents=None,
                  buyer_cash_needed_cents=None, closing_headroom_cents=None,
                  annual_debt_headroom_cents=None, balloon_headroom_cents=None,
                  status="HOLD_MISSING_INPUTS")
    if missing:
        return result
    outlay = sum(inputs[k] for k in COMMON[:4])
    note = inputs.get("seller_note_proceeds", 0)
    partner = inputs.get("committed_partner_cash", 0)
    if note > inputs["purchase_price"] or partner > outlay:
        raise ValueError("Financing proceeds exceed the applicable use")
    buyer_cash = outlay - note - partner
    headroom = (inputs["buyer_cash_available"] - buyer_cash - inputs["buyer_liquidity_floor"]
                - inputs.get("buyer_capital_call_reserve", 0))
    annual = balloon = None
    if structure == "SELLER_NOTE":
        annual = inputs["annual_cash_before_debt"] - inputs["annual_debt_service"]
        balloon = inputs["funds_available_at_balloon"] - inputs["balloon_due"]
    return {**result, "closing_outlay_cents":outlay, "buyer_cash_needed_cents":buyer_cash,
            "closing_headroom_cents":headroom, "annual_debt_headroom_cents":annual,
            "balloon_headroom_cents":balloon,
            "status":"REVIEW_CASH_DEFICIT" if any(x is not None and x < 0 for x in (headroom, annual, balloon))
            else "REVIEW_LIQUIDITY_MODEL"}
