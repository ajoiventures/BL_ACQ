"""Prepare a replacement mandate from explicitly supplied owner evidence."""
from datetime import date

REQUIRED = ("taxpayer_id", "available_capital_cents", "minimum_reserves_cents",
            "financing_mode", "minimum_annual_cash_cents", "geography_revision",
            "target_date", "management_capacity_units", "investment_intent")


def prepare(as_of, inputs):
    date.fromisoformat(as_of)
    unknown = set(inputs) - set(REQUIRED)
    if unknown:
        raise ValueError("Unknown mandate inputs")
    fields = {key: inputs.get(key) for key in REQUIRED}
    for key in ("available_capital_cents", "minimum_reserves_cents", "management_capacity_units"):
        value = fields[key]
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"Invalid {key}")
    target = fields["target_date"]
    if target is not None:
        date.fromisoformat(target)
    mode = fields["financing_mode"]
    if mode not in (None, "DEBT_FREE", "DEBT_FINANCED"):
        raise ValueError("Unknown financing mode")
    missing = [key for key, value in fields.items() if value is None or value == ""]
    return dict(as_of=as_of, inputs=fields, missing_inputs=missing,
                status="HOLD_MISSING_OWNER_INPUTS" if missing else "REVIEW_REQUIRED",
                dscr_status="NOT_APPLICABLE" if mode=="DEBT_FREE" else "NOT_EVALUATED",
                exchange_eligibility=None, authorized_spendable_cash_cents=None)
