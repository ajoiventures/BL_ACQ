"""Evidence, event scenarios and review policy around the valuation engine.

Amounts are in the stated currency's base unit and rates are decimal fractions.
This module computes research packets. It cannot approve, place or settle a trade.
"""

from copy import deepcopy
from datetime import date
import hashlib
import json
import math
import re
from urllib.parse import urlsplit

from .valuation import reverse_growth, sensitivity_grid, value_model


VERSION = "1.0"
MODEL_VERSION = "br-valuation-2"
PRICE_RELATIVE_TOLERANCE = 1e-12
CLAIM_RELATIVE_TOLERANCE = 1e-12
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}")
TOP_KEYS = {
    "schema_version", "deal_id", "asset_id", "as_of", "model_type", "currency",
    "assumptions", "market", "policy", "sources", "input_source_ids", "scenarios",
    "qualification", "qualification_source_ids", "claims", "notes", "illustrative",
    "reference_values", "capital",
}
POLICY_DEFAULTS = {
    "margin_of_safety": 0.30, "max_downside_probability": 0.35,
    "max_source_age_days": 365, "max_quote_age_days": 7,
}


def _object(value, name, allowed=None):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    if allowed is not None and set(value) - set(allowed):
        raise ValueError(f"Unknown {name} fields: {', '.join(sorted(set(value) - set(allowed)))}")
    return value


def _number(value, name, low=0, high=1e18):
    if type(value) not in (float, int) or not low <= value <= high or not math.isfinite(value):
        raise ValueError(f"{name} must be finite and between {low} and {high}")
    return float(value)


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def _price_exceeds(value, reference):
    """Compare finite model prices without an absolute currency tolerance.

    Relative tolerance absorbs DCF roundoff at an equality boundary while
    preserving the decision when economically equivalent amounts are rescaled.
    A fixed dollar tolerance would overwhelm valid small per-unit values.
    """
    return value > reference and not math.isclose(
        value, reference, rel_tol=PRICE_RELATIVE_TOLERANCE, abs_tol=0.0,
    )


def _text(value, name, limit=3000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be nonempty text of at most {limit} characters")
    return value


def _id(value, name):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _date(value, name, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name} must be YYYY-MM-DD") from None
    if parsed.isoformat() != value:
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return parsed


def _references(value, name, known):
    if not isinstance(value, list) or len(value) > 30:
        raise ValueError(f"{name} must be an array of at most 30 source IDs")
    if any(not isinstance(x, str) or x not in known for x in value):
        raise ValueError(f"{name} references an unknown source")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} contains duplicate sources")
    return value


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("NaN and infinity are not valid packet values")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Object keys must be text")
            _finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            _finite_tree(item)


def _sources(packet, as_of, policy):
    records = packet.get("sources", [])
    if not isinstance(records, list) or len(records) > 30:
        raise ValueError("sources must be an array of at most 30 records")
    indexed, ready, issues = {}, set(), []
    for source in records:
        _object(source, "source", {"id", "title", "url", "observed_on", "verified", "kind", "notes", "issues"})
        sid = _id(source.get("id"), "source ID")
        if sid in indexed:
            raise ValueError("Duplicate source ID")
        indexed[sid] = source
        _text(source.get("title"), "source title", 500)
        url = _text(source.get("url"), "source URL", 2048)
        parsed = urlsplit(url)
        if parsed.scheme not in ("https", "http") or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Source URLs must be credential-free HTTP(S) references")
        if source.get("kind") not in ("financials", "quote", "event", "assumptions", "qualification"):
            raise ValueError("Unknown source kind")
        if type(source.get("verified")) is not bool:
            raise ValueError("source.verified must be a boolean")
        if not isinstance(source.get("notes", ""), str) or len(source.get("notes", "")) > 5000:
            raise ValueError("Source notes must be text of at most 5000 characters")
        source_issues = source.get("issues", [])
        if not isinstance(source_issues, list) or len(source_issues) > 20:
            raise ValueError("Source issues must be an array of at most 20 descriptions")
        for item in source_issues:
            _text(item, "source issue", 2000)
        observed = _date(source.get("observed_on"), "source.observed_on", optional=True)
        problems = []
        if source["verified"] is not True:
            problems.append("inputs have not been independently verified")
        if observed is None:
            problems.append("observation date is missing")
        elif observed > as_of:
            problems.append("source postdates the analysis date")
        elif (as_of - observed).days > policy["max_source_age_days"]:
            problems.append("source is older than the permitted age")
        problems.extend(source_issues)
        if problems:
            issues.extend(f"{sid}: {item}" for item in problems)
        else:
            ready.add(sid)
    return indexed, ready, issues


def _claims(packet, assumptions, sources):
    claims = packet.get("claims", [])
    if not isinstance(claims, list) or len(claims) > 50:
        raise ValueError("claims must be an array of at most 50 obligations")
    identities, bridge_amounts = set(), []
    for claim in claims:
        _object(claim, "claim", {"id", "amount", "in_cash_flows", "in_equity_bridge", "source_id"})
        identity = _id(claim.get("id"), "claim ID")
        if identity in identities:
            raise ValueError("An obligation cannot appear twice")
        identities.add(identity)
        amount = _number(claim.get("amount"), "claim.amount")
        cash_flow, bridge = claim.get("in_cash_flows"), claim.get("in_equity_bridge")
        if type(cash_flow) is not bool or type(bridge) is not bool or cash_flow == bridge:
            raise ValueError("Each obligation must have exactly one cash-flow or equity-bridge treatment")
        if not isinstance(claim.get("source_id"), str) or claim["source_id"] not in sources:
            raise ValueError("Claim references an unknown source")
        if bridge:
            bridge_amounts.append(amount)
    # These are reconciliation records, never a second automatic deduction.
    bridge_total = math.fsum(bridge_amounts)
    available = math.fsum((_number(assumptions.get("debt", 0), "debt"),
                           _number(assumptions.get("debt_like_claims", 0), "debt_like_claims")))
    # Numerical reconciliation has no fixed dollar floor: no positive claim
    # can match zero debt, and small balances cannot disappear as immaterial.
    # This tolerance addresses computation; it is not an accounting materiality rule.
    reconciled = math.isclose(bridge_total, available, rel_tol=CLAIM_RELATIVE_TOLERANCE, abs_tol=0.0)
    if bridge_total > available and not reconciled:
        raise ValueError("Bridge obligations exceed the model's declared debt and debt-like claims")
    return {"status": "reconciled" if reconciled else "review_required",
            "declared_bridge_total": available, "reconciled_bridge_total": bridge_total,
            "unreconciled_bridge_total": max(0, available - bridge_total)}


def _capital_limit(capital, decision, scenario_values, model_type, assumptions):
    if capital is None:
        return None
    _object(capital, "capital", {"available_cash", "reserve_floor", "portfolio_value", "max_position_fraction",
                                  "existing_asset_exposure", "max_loss_budget", "transaction_cost_rate", "quantity_step"})
    cash = _number(capital.get("available_cash"), "available_cash")
    reserve = _number(capital.get("reserve_floor"), "reserve_floor")
    portfolio = _number(capital.get("portfolio_value"), "portfolio_value")
    fraction = _number(capital.get("max_position_fraction"), "max_position_fraction", 0, 1)
    exposure = _number(capital.get("existing_asset_exposure", 0), "existing_asset_exposure")
    loss_budget = _number(capital.get("max_loss_budget"), "max_loss_budget")
    cost_rate = _number(capital.get("transaction_cost_rate", 0), "transaction_cost_rate", 0, 0.25)
    step = _number(capital.get("quantity_step", 1), "quantity_step", 1e-8, 1e12)
    whole_asset = model_type == "property_dcf" or assumptions["units"] == 1
    if whole_asset and step != 1:
        raise ValueError("A whole property or single-unit business requires quantity_step=1")
    price = decision["market_price"]
    if price is None:
        return {"status": "hold", "proposed_units": 0, "cash_committed": 0, "reason": "A price is required"}
    unit_cost = price * (1 + cost_rate)
    capacity = max(0, min(cash - reserve, portfolio * fraction - exposure))
    worst_value = min(scenario_values)
    unit_loss = max(0, unit_cost - worst_value)
    risk_units = loss_budget / unit_loss if unit_loss else capacity / unit_cost
    theoretical = math.floor(min(capacity / unit_cost, risk_units, assumptions["units"]) / step) * step
    proposed = theoretical if decision["status"] == "review_candidate" else 0
    return {"status": "review_only", "theoretical_unit_limit": theoretical, "proposed_units": proposed,
            "proposed_cost": proposed * unit_cost, "capacity_after_reserves": capacity,
            "modeled_loss_per_unit": unit_loss, "worst_modeled_value": worst_value,
            "quantity_step": step, "available_asset_units": assumptions["units"],
            "cash_committed": 0, "limitation": "Scenario losses are not a maximum loss guarantee; approval is separate."}


def evaluate(packet):
    """Validate inputs, rerun each scenario, and return a digest-bound research packet."""
    _object(packet, "packet", TOP_KEYS)
    _finite_tree(packet)
    packet = deepcopy(packet)
    if packet.get("schema_version") != VERSION:
        raise ValueError("Unsupported schema_version")
    deal_id = _id(packet.get("deal_id"), "deal_id")
    asset_id = _id(packet.get("asset_id"), "asset_id")
    as_of = _date(packet.get("as_of"), "as_of")
    currency = packet.get("currency", "USD")
    if currency != "USD":
        raise ValueError("This version requires USD amounts; convert and document currency inputs first")
    model_type = packet.get("model_type")
    assumptions = _object(packet.get("assumptions"), "assumptions")
    if type(packet.get("illustrative", False)) is not bool:
        raise ValueError("illustrative must be a boolean")
    if not isinstance(packet.get("notes", ""), str) or len(packet.get("notes", "")) > 10000:
        raise ValueError("notes must be text of at most 10000 characters")
    policy = POLICY_DEFAULTS | _object(packet.get("policy", {}), "policy", POLICY_DEFAULTS)
    _number(policy["margin_of_safety"], "margin_of_safety", 0, 0.95)
    _number(policy["max_downside_probability"], "max_downside_probability", 0, 1)
    _integer(policy["max_source_age_days"], "max_source_age_days", 1, 3650)
    _integer(policy["max_quote_age_days"], "max_quote_age_days", 0, 365)
    sources, ready_sources, issues = _sources(packet, as_of, policy)
    input_refs = _references(packet.get("input_source_ids", []), "input_source_ids", sources)
    if not input_refs:
        issues.append("No financial-input provenance has been supplied")
    if not input_refs or not set(input_refs) <= ready_sources:
        issues.append("Financial inputs require source review")
    if packet.get("illustrative"):
        issues.append("Illustrative inputs cannot qualify as an investment decision")
    obligations = _claims(packet, assumptions, sources)
    if obligations["status"] != "reconciled":
        issues.append("Debt and debt-like bridge balances are not fully reconciled to obligation records")
    market = _object(packet.get("market", {}), "market", {"price", "as_of", "source_id"})
    price = market.get("price")
    if price is not None:
        price = _number(price, "market.price", 1e-12, 1e15)
    else:
        issues.append("No observed market or proposed transaction price")
    price_date = _date(market.get("as_of"), "market.as_of", optional=True)
    if price_date is None:
        issues.append("Price observation date is missing; this is not a live quote")
    elif price_date > as_of:
        issues.append("Price observation postdates the analysis date")
    elif (as_of - price_date).days > policy["max_quote_age_days"]:
        issues.append("Price is stale under the selected policy")
    quote_source = market.get("source_id")
    if not isinstance(quote_source, str) or quote_source not in sources:
        issues.append("Price source is missing")
    elif quote_source not in ready_sources:
        issues.append("Price source requires review")
    if isinstance(quote_source, str) and quote_source in sources:
        record = sources[quote_source]
        observed = _date(record.get("observed_on"), "price source.observed_on", optional=True)
        if record["kind"] != "quote":
            issues.append("Price must reference a source identified as a quote or transaction price")
        if observed is not None:
            if (as_of - observed).days > policy["max_quote_age_days"]:
                issues.append("Price source is stale under the quote-age policy")
            if price_date is not None and price_date > observed:
                issues.append("Price date is later than its supporting source observation")

    baseline = value_model(model_type, assumptions)
    scenarios = packet.get("scenarios")
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 12:
        raise ValueError("Supply between one and twelve mutually exclusive scenarios")
    scenario_ids, evaluated, probabilities = set(), [], []
    for scenario in scenarios:
        _object(scenario, "scenario", {"id", "label", "probability", "shock", "source_ids", "assumptions_override"})
        sid = _id(scenario.get("id"), "scenario ID")
        if sid in scenario_ids:
            raise ValueError("Duplicate scenario ID")
        scenario_ids.add(sid)
        label = _text(scenario.get("label"), "scenario label", 200)
        probability = _number(scenario.get("probability"), "scenario probability", 0, 1)
        probabilities.append(probability)
        refs = _references(scenario.get("source_ids", []), "scenario.source_ids", sources)
        if probability > 0 and (not refs or not set(refs) <= ready_sources):
            issues.append(f"{label}: scenario assumptions or probabilities require evidence review")
        shock = _object(scenario.get("shock", {}), "shock")
        overrides = _object(scenario.get("assumptions_override", {}), "assumptions_override")
        # Identity, units and the opening equity bridge cannot be silently changed by an event.
        forbidden = {"units", "years", "revenue", "noi", "cash", "debt", "debt_like_claims", "non_operating_assets"}
        if set(overrides) & forbidden:
            raise ValueError("Scenario overrides cannot change opening balances, units or horizon")
        valuation = value_model(model_type, assumptions | overrides, shock)
        evaluated.append({"id": sid, "label": label, "probability": probability,
                          "shock": shock, "assumptions_override": overrides,
                          "source_ids": refs, "valuation": valuation,
                          "change_from_baseline": (valuation["value_per_unit"] / baseline["value_per_unit"] - 1)
                          if baseline["value_per_unit"] > 0 else None})
    if not math.isclose(math.fsum(probabilities), 1.0, abs_tol=1e-9, rel_tol=0):
        raise ValueError("Scenario probabilities must sum to one; they are never normalized silently")
    adjusted = math.fsum(x["probability"] * x["valuation"]["value_per_unit"] for x in evaluated)
    ceiling = adjusted * (1 - policy["margin_of_safety"])
    loss_probability = (math.fsum(x["probability"] for x in evaluated
                                 if _price_exceeds(price, x["valuation"]["value_per_unit"]))
                        if price is not None else None)
    qualification = _object(packet.get("qualification", {}), "qualification", {"buyable", "fundable", "sellable"})
    qrefs = _object(packet.get("qualification_source_ids", {}), "qualification_source_ids", {"buyable", "fundable", "sellable"})
    gates = {}
    for gate in ("buyable", "fundable", "sellable"):
        declared = qualification.get(gate, "unknown")
        if declared not in ("unknown", "confirmed", "failed"):
            raise ValueError(f"Invalid {gate} qualification")
        refs = _references(qrefs.get(gate, []), f"{gate} sources", sources)
        supported = bool(refs) and set(refs) <= ready_sources
        status = declared if declared != "confirmed" or supported else "unknown"
        gates[gate] = {"status": status, "declared_status": declared, "source_ids": refs,
                       "reason": "Source-supported declaration; independent approval remains separate" if status == "confirmed"
                       else ("Criterion failed" if status == "failed" else "Criterion lacks reviewed evidence")}
        if status != "confirmed":
            issues.append(f"{gate.capitalize()} qualification is {status}")
    issues = list(dict.fromkeys(issues))
    reasons = list(issues)
    if price is not None and _price_exceeds(price, ceiling):
        reasons.append("Price exceeds the event-adjusted margin-of-safety entry ceiling")
    if (loss_probability is not None and loss_probability > policy["max_downside_probability"]
            and not math.isclose(loss_probability, policy["max_downside_probability"],
                                 rel_tol=0, abs_tol=1e-12)):
        reasons.append("Assumed scenario weight below price exceeds the selected policy limit")
    if adjusted <= 0:
        reasons.append("No positive modeled equity value")
    status = "hold" if issues or adjusted <= 0 else ("watch" if reasons else "review_candidate")
    warnings = list(dict.fromkeys(
        list(baseline.get("warnings", [])) + [w for x in evaluated for w in x["valuation"].get("warnings", [])]
    ))
    warnings.append("Scenario weights are user assumptions. Weight below price compares current modeled "
                    "intrinsic value with the reference price; it does not estimate the probability of "
                    "a realized loss over a holding period.")
    decision = {"adjusted_value": adjusted, "entry_ceiling": ceiling, "market_price": price,
                "price_as_of": market.get("as_of"), "upside": adjusted / price - 1 if price else None,
                "discount_to_value": 1 - price / adjusted if adjusted > 0 and price is not None else None,
                "downside_probability": loss_probability, "margin_of_safety": policy["margin_of_safety"],
                "status": status, "reasons": reasons, "qualification": gates,
                "baseline_entry_reference": baseline["value_per_unit"] * (1 - policy["margin_of_safety"]),
                "approval_required": True, "execution_allowed": False}
    digest = hashlib.sha256(json.dumps({"model_version": MODEL_VERSION, "request": packet},
                                      sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    reverse = (reverse_growth(model_type, assumptions, {}, price) if price is not None
               else {"status": "missing_price", "implied_growth_rate": None})
    return {"schema_version": VERSION, "model_version": MODEL_VERSION,
            "deal_id": deal_id, "asset_id": asset_id, "as_of": as_of.isoformat(), "currency": currency,
            "model_type": model_type, "baseline": baseline, "scenarios": evaluated, "decision": decision,
            "sensitivity": sensitivity_grid(model_type, assumptions, {}), "reverse_dcf": reverse,
            "evidence": {"status": "review_required" if issues else "verified", "issues": issues,
                         "sources": list(sources.values()), "warnings": warnings,
                         "verification_scope": "User-supplied source assertions; no live data verification is performed."},
            "obligations": obligations,
            "capital": _capital_limit(packet.get("capital"), decision,
                                      [x["valuation"]["value_per_unit"] for x in evaluated if x["probability"] > 0],
                                      model_type, assumptions),
            "packet_digest": digest, "request": packet,
            "reference_values": packet.get("reference_values", {}),
            "explanation": "Event assumptions change cash flows first. Margin of safety is then applied once to scenario-weighted equity value."}
