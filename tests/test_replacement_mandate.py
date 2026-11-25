from backend.core.replacement_mandate import prepare


def test_debt_free_mandate_has_no_dscr_or_assumed_capital():
    report = prepare("2026-11-24", {"financing_mode": "DEBT_FREE", "investment_intent": "HOLD_FOR_RENT"})
    assert report["status"] == "HOLD_MISSING_OWNER_INPUTS"
    assert report["dscr_status"] == "NOT_APPLICABLE"
    assert "available_capital_cents" in report["missing_inputs"]
    assert report["authorized_spendable_cash_cents"] is None
    assert report["exchange_eligibility"] is None
