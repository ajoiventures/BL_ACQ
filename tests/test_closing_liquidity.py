from backend.core.closing_liquidity import compare_closing_liquidity


def test_unknown_liquidity_cannot_be_treated_as_zero():
    result = compare_closing_liquidity("CASH", {"purchase_price": 100, "closing_costs": 0})
    assert result["closing_outlay_cents"] is None
    assert "closing_costs" not in result["missing_inputs"]
    assert result["status"] == "HOLD_MISSING_INPUTS"


def test_seller_note_cash_deficit_at_maturity_even_if_closing_has_headroom():
    result = compare_closing_liquidity("SELLER_NOTE", {
        "purchase_price":100, "closing_costs":5, "immediate_repairs":5, "initial_reserves":10,
        "buyer_cash_available":50, "buyer_liquidity_floor":10, "seller_note_proceeds":90,
        "annual_debt_service":7, "annual_cash_before_debt":10,
        "balloon_due":50, "funds_available_at_balloon":49,
    })
    assert result["closing_headroom_cents"] == 10
    assert result["annual_debt_headroom_cents"] == 3
    assert result["balloon_headroom_cents"] == -1
    assert result["status"] == "REVIEW_CASH_DEFICIT"
