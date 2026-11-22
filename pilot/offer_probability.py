"""Deterministic offer probability engine. No AI, network, or transaction actions.

Money inputs are integer USD cents and probability inputs are integer basis
points. The CPU reference enumerates conditional outcomes with exact fractions.
CUDA accelerates optional expected-value batches; policy decisions retain the
exact reference. Every result is a research calculation, never an authorization.
"""

from datetime import date
from fractions import Fraction
from functools import lru_cache
import hashlib
import json
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .cuda_screen import cuda_runtime


SCHEMA_VERSION = "br-offer-probability/1"
ENGINE_VERSION = "br-offer-probability-engine/1"
BPS = 10_000
MAX_MONEY_CENTS = 10**12
MAX_PAYOFF_CENTS = 8 * MAX_MONEY_CENTS
MAX_BATCH_ROWS = 2_000_000
CUDA_TOLERANCE_CENTS = 0.01  # One hundredth of one cent; never used in policy comparisons.
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}")
TOP_KEYS = {
    "schema_version", "model_id", "deal_id", "as_of", "timezone", "currency",
    "probability_basis", "probability_reference", "illustrative", "provenance",
    "event_horizon_note", "cost_note", "selling_cost_bp", "buyer_closing_cents",
    "spent_additional_allowance_cents", "required_profit_cents",
    "no_agreement_total_loss_cents", "agreement_no_close_total_loss_cents",
    "closing_given_agreement_bp", "policy", "scenarios", "offers",
}
SCENARIO_KEYS = {"id", "weight_bp", "resale_cents", "renovation_cents", "carry_cents"}
OFFER_KEYS = {
    "id", "kind", "price_cents", "closing_days", "incremental_timing_cents",
    "agreement_bp", "closing_given_agreement_bp", "counter_premise",
}


def _object(value, name, allowed, required=None):
    if type(value) is not dict:
        raise ValueError(f"{name} must be an object")
    if any(type(key) is not str for key in value):
        raise ValueError(f"{name} keys must be strings")
    if set(value) - allowed:
        raise ValueError(f"Unknown {name} fields: {', '.join(sorted(set(value)-allowed))}")
    if required is not None and set(required) - set(value):
        raise ValueError(f"Missing {name} fields: {', '.join(sorted(set(required)-set(value)))}")
    return value


def _integer(value, name, low=0, high=MAX_MONEY_CENTS):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _text(value, name, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonempty text of at most {maximum} characters")
    return value


def _id(value, name):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _probability(value, name="probability"):
    return Fraction(_integer(value, name, 0, BPS), BPS)


def _fraction_record(value):
    fraction = Fraction(value)
    # JSON numbers cannot preserve arbitrary rational integers in JavaScript/R.
    return {"numerator": str(fraction.numerator), "denominator": str(fraction.denominator)}


def _numeric(value):
    fraction = Fraction(value)
    return fraction.numerator if fraction.denominator == 1 else float(fraction)


def _metric(target, name, value):
    """Write a convenient numeric value and its authoritative exact representation."""
    target[name] = _numeric(value)
    target[name + "_exact"] = _fraction_record(value)


def validate_packet(packet):
    """Validate the versioned packet without modifying it or reading external state."""
    required = TOP_KEYS - {"probability_reference"}
    p = _object(packet, "packet", TOP_KEYS, required)
    if p["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("model_id", "deal_id"):
        _id(p[key], key)
    if p["currency"] != "USD":
        raise ValueError("Version 1 supports USD integer cents only")
    try:
        if type(p["as_of"]) is not str or date.fromisoformat(p["as_of"]).isoformat() != p["as_of"]:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("as_of must be a canonical YYYY-MM-DD date") from None
    try:
        ZoneInfo(_text(p["timezone"], "timezone", 100))
    except ZoneInfoNotFoundError:
        raise ValueError("timezone must identify an installed IANA time zone") from None
    if p["probability_basis"] not in ("assumed", "external_estimate"):
        raise ValueError("probability_basis must be assumed or external_estimate")
    if p["probability_basis"] == "external_estimate":
        _text(p.get("probability_reference"), "probability_reference")
    elif "probability_reference" in p:
        _text(p["probability_reference"], "probability_reference")
    if type(p["illustrative"]) is not bool:
        raise ValueError("illustrative must be a Boolean")
    for key in ("provenance", "event_horizon_note", "cost_note"):
        _text(p[key], key)
    _probability(p["selling_cost_bp"], "selling_cost_bp")
    if p["closing_given_agreement_bp"] is not None:
        _probability(p["closing_given_agreement_bp"], "closing_given_agreement_bp")
    for key in ("buyer_closing_cents", "spent_additional_allowance_cents", "required_profit_cents",
                "no_agreement_total_loss_cents", "agreement_no_close_total_loss_cents"):
        _integer(p[key], key)
    policy_keys = {"mode", "required_floor_probability_bp", "required_closing_days"}
    policy = _object(p["policy"], "policy", policy_keys, policy_keys)
    if policy["mode"] not in ("baseline", "expected_conditional", "chance_conditional"):
        raise ValueError("Unknown policy mode")
    _integer(policy["required_floor_probability_bp"], "required_floor_probability_bp", 1, BPS)
    if policy["required_closing_days"] is not None:
        _integer(policy["required_closing_days"], "required_closing_days", 1, 3650)
    for key in ("scenarios", "offers"):
        if type(p[key]) is not list or not 1 <= len(p[key]) <= 1000:
            raise ValueError(f"{key} must contain between 1 and 1000 records")
    if len(p["scenarios"]) * len(p["offers"]) > 100_000:
        raise ValueError("A packet is limited to 100000 offer/scenario cells; split larger work")
    scenario_ids = set()
    weight_total = 0
    for scenario in p["scenarios"]:
        _object(scenario, "scenario", SCENARIO_KEYS, SCENARIO_KEYS)
        sid = _id(scenario["id"], "scenario id")
        if sid in scenario_ids:
            raise ValueError("Duplicate scenario id")
        scenario_ids.add(sid)
        weight_total += _integer(scenario["weight_bp"], "scenario weight", 0, BPS)
        for key in ("resale_cents", "renovation_cents", "carry_cents"):
            _integer(scenario[key], key)
    if weight_total != BPS or "baseline" not in scenario_ids:
        raise ValueError("Scenario weights must sum to 10000 and include a baseline scenario")
    offer_ids = set()
    for offer in p["offers"]:
        required_offer = OFFER_KEYS - {"counter_premise", "closing_given_agreement_bp"}
        _object(offer, "offer", OFFER_KEYS, required_offer)
        oid = _id(offer["id"], "offer id")
        if oid in offer_ids:
            raise ValueError("Duplicate offer id")
        offer_ids.add(oid)
        if offer["kind"] not in ("new_offer", "new_counter", "accept_live_counter"):
            raise ValueError("Unknown offer kind")
        _integer(offer["price_cents"], "price_cents", 1)
        _integer(offer["incremental_timing_cents"], "incremental_timing_cents")
        _integer(offer["closing_days"], "closing_days", 1, 3650)
        for key in ("agreement_bp", "closing_given_agreement_bp"):
            if offer.get(key) is not None:
                _probability(offer[key], key)
        if offer["kind"] == "accept_live_counter":
            premise_keys = {"exact_terms", "authorized", "still_open", "effectively_accepted", "reference"}
            premise = _object(offer.get("counter_premise"), "counter_premise", premise_keys, premise_keys)
            if offer["agreement_bp"] != BPS or any(premise[key] is not True for key in premise_keys-{"reference"}):
                raise ValueError("A live-counter calculation requires 10000 agreement basis points and every conditioning premise")
            _text(premise["reference"], "counter_premise.reference")
        elif "counter_premise" in offer:
            raise ValueError("counter_premise applies only to accept_live_counter")


def _available(packet, scenario):
    # Match pilot.underwriting: floor net resale proceeds at the selling-fee step.
    net = scenario["resale_cents"] * (BPS-packet["selling_cost_bp"]) // BPS
    return net - scenario["renovation_cents"] - scenario["carry_cents"] - packet["buyer_closing_cents"] - packet["spent_additional_allowance_cents"]


def _event_value(agreement, closing, mean_cents, rejection_loss, failure_loss):
    return -(1-agreement)*rejection_loss - agreement*(1-closing)*failure_loss + agreement*closing*mean_cents


def _evaluate_offer(packet, offer):
    weights = [_probability(s["weight_bp"]) for s in packet["scenarios"]]
    profits = [_available(packet, s)-offer["price_cents"]-offer["incremental_timing_cents"] for s in packet["scenarios"]]
    mean = sum((w*p for w, p in zip(weights, profits)), Fraction())
    floor = packet["required_profit_cents"]
    floor_probability = sum((w for w, p in zip(weights, profits) if p >= floor), Fraction())
    loss_probability = sum((w for w, p in zip(weights, profits) if p < 0), Fraction())
    baseline = profits[next(i for i, s in enumerate(packet["scenarios"]) if s["id"] == "baseline")]
    chance = _probability(packet["policy"]["required_floor_probability_bp"])
    policy_results = {"baseline": baseline >= floor, "expected_conditional": mean >= floor,
                      "chance_conditional": floor_probability >= chance}
    required_days = packet["policy"]["required_closing_days"]
    timing = required_days is None or offer["closing_days"] == required_days
    result = {"id": offer["id"], "kind": offer["kind"], "price_cents": offer["price_cents"],
              "closing_days": offer["closing_days"], "baseline_profit_cents": baseline,
              "worst_modeled_profit_cents": min(profits), "policy_checks": policy_results,
              "financial_policy_passed": policy_results[packet["policy"]["mode"]], "timing_feasible": timing,
              "policy_passed": timing and policy_results[packet["policy"]["mode"]],
              "profits_given_close_cents": dict(zip([s["id"] for s in packet["scenarios"]], profits)),
              "event_tree": None, "decision_scope": "research_only"}
    _metric(result, "expected_profit_given_close_cents", mean)
    _metric(result, "probability_floor_given_close", floor_probability)
    _metric(result, "probability_loss_given_close", loss_probability)
    q_bp = offer.get("closing_given_agreement_bp", packet["closing_given_agreement_bp"])
    unknown = offer["agreement_bp"] is None or q_bp is None
    result["decision_state"] = ("policy_rejected" if not result["policy_passed"] else
                                "probability_unknown" if unknown else "research_candidate")
    if unknown:
        result["probability_issue"] = "Agreement or conditional closing probability is unknown; expected pursuit value is not computed"
        return result, None
    a, q = _probability(offer["agreement_bp"]), _probability(q_bp)
    k, failure = packet["no_agreement_total_loss_cents"], packet["agreement_no_close_total_loss_cents"]
    branches = [("no_agreement", 1-a, -k), ("agreement_no_close", a*(1-q), -failure)]
    branches += [("closed_"+s["id"], a*q*w, profit) for s, w, profit in zip(packet["scenarios"], weights, profits)]
    mass = sum((p for _, p, _ in branches), Fraction())
    ev = sum((p*cash for _, p, cash in branches), Fraction())
    if mass != 1 or ev != _event_value(a, q, mean, k, failure):
        raise ArithmeticError("Internal event-tree reconciliation failed")
    tree = {"agreement_bp": offer["agreement_bp"], "closing_given_agreement_bp": q_bp,
            "agreement_interpretation": ("conditioning_on_effective_acceptance" if offer["kind"] == "accept_live_counter"
                                         else "supplied_response_probability"), "branches": []}
    for state, probability, cash in branches:
        branch = {"state": state, "total_net_cash_cents": cash}
        _metric(branch, "probability", probability)
        tree["branches"].append(branch)
    _metric(tree, "probability_acquisition", a*q)
    _metric(tree, "probability_acquire_and_meet_floor", a*q*floor_probability)
    _metric(tree, "probability_any_negative_attempt_cash", sum((p for _, p, cash in branches if cash < 0), Fraction()))
    _metric(tree, "expected_net_cents_per_attempt", ev)
    _metric(tree, "terminal_probability_sum", mass)
    if offer["kind"] == "accept_live_counter":
        tree["counter_premise"] = dict(offer["counter_premise"])
        tree["premise_status"] = "supplied_conditioning_assumption_not_verified_by_engine"
    result["event_tree"] = tree
    return result, ev


def _price_ceilings(packet):
    entries = [(_available(packet, s), _probability(s["weight_bp"])) for s in packet["scenarios"]]
    baseline = _available(packet, next(s for s in packet["scenarios"] if s["id"] == "baseline"))
    mean = sum((value*weight for value, weight in entries), Fraction())
    floor = packet["required_profit_cents"]
    chance = _probability(packet["policy"]["required_floor_probability_bp"])
    packages = sorted({(o["closing_days"], o["incremental_timing_cents"]) for o in packet["offers"]})
    ceilings = []
    for days, timing in packages:
        candidates = [value-timing-floor for value, weight in entries if weight > 0]
        chance_ceiling = max(price for price in candidates
                             if sum(weight for value, weight in entries if value-timing-price >= floor) >= chance)
        row = {"closing_days": days, "incremental_timing_cents": timing,
               "baseline_floor_price_cents": baseline-timing-floor,
               "chance_floor_price_cents": chance_ceiling,
               "required_floor_probability_bp": packet["policy"]["required_floor_probability_bp"],
               "all_modeled_scenarios_floor_price_cents": min(value for value, _ in entries)-timing-floor,
               "nonnegative_baseline_price_feasible": baseline-timing-floor >= 0,
               "scope": "Conditional on closing; common scenario and fixed cost structure; not acceptance or financing approval"}
        expected = mean-timing-floor
        # Purchase prices must be whole cents, so floor the exact expected ceiling.
        row["expected_conditional_floor_price_cents"] = expected.numerator // expected.denominator
        row["expected_conditional_unrounded_price_cents_exact"] = _fraction_record(expected)
        _metric(row, "probability_floor_at_chance_ceiling", sum(weight for value, weight in entries if value-timing-chance_ceiling >= floor))
        ceilings.append(row)
    return ceilings


@lru_cache(maxsize=1)
def _cuda_backend():
    with cuda_runtime():
        try:
            import cupy as cp
        except ImportError as exc:
            raise RuntimeError("CUDA requested but CuPy is unavailable; no CPU fallback") from exc
        try:
            if cp.cuda.runtime.getDeviceCount() < 1:
                raise RuntimeError("No CUDA device")
        except Exception as exc:
            raise RuntimeError("CUDA requested but no usable CUDA device is available; no CPU fallback") from exc

    @cp.fuse()
    def fused(a, q, mean, k, failure):
        return -(1-a)*k-a*(1-q)*failure+a*q*mean
    return cp, fused


def batch_expected_values(agreement_bps, closing_bps, mean_profit_cents,
                         no_agreement_total_loss_cents, agreement_no_close_total_loss_cents,
                         *, backend="cpu"):
    """Return float64 expected cents for 1..2M independent rows in input order.

    Probability arrays must have integer dtype; mean profits may be fractional
    cents. NumPy is needed for this optional batch API. No transfers occur per
    row. Inputs are host arrays; long-lived device storage is a future adapter.
    Exact policy decisions belong to evaluate_packet, not this floating batch.
    """
    if backend not in ("cpu", "cuda"):
        raise ValueError("backend must be cpu or cuda")
    import numpy as np
    a, q = np.asarray(agreement_bps), np.asarray(closing_bps)
    mu = np.asarray(mean_profit_cents)
    if any(x.ndim != 1 for x in (a, q, mu)) or not (a.shape == q.shape == mu.shape):
        raise ValueError("Batch arrays must be one-dimensional and have equal lengths")
    if not 1 <= a.size <= MAX_BATCH_ROWS:
        raise ValueError(f"Batch rows must be between 1 and {MAX_BATCH_ROWS}")
    if a.dtype.kind not in "iu" or q.dtype.kind not in "iu" or mu.dtype.kind not in "iuf":
        raise ValueError("Probabilities require integer basis points and means require real numbers")
    if np.any(a < 0) or np.any(a > BPS) or np.any(q < 0) or np.any(q > BPS):
        raise ValueError("Probabilities must be between 0 and 10000 basis points")
    if not np.all(np.isfinite(mu)) or np.any(np.abs(mu.astype(np.float64)) > MAX_PAYOFF_CENTS):
        raise ValueError("Mean payoff is nonfinite or exceeds the supported cents range")
    k = _integer(no_agreement_total_loss_cents, "no_agreement_total_loss_cents")
    failure = _integer(agreement_no_close_total_loss_cents, "agreement_no_close_total_loss_cents")
    a = a.astype(np.float64)/BPS
    q = q.astype(np.float64)/BPS
    mu = mu.astype(np.float64)
    if backend == "cpu":
        return -(1-a)*k-a*(1-q)*failure+a*q*mu
    with cuda_runtime():
        cp, fused = _cuda_backend()
        result = fused(cp.asarray(a), cp.asarray(q), cp.asarray(mu), np.float64(k), np.float64(failure))
        # This return includes synchronization and the device-to-host transfer.
        return cp.asnumpy(result)


def evaluate_packet(packet: dict, *, backend="cpu") -> dict:
    """Evaluate the exact research packet; optionally check CUDA event-value batches.

    Explicit CUDA never silently falls back. Even with CUDA, financial traces
    and policy comparisons use the exact CPU reference. No predictive model is
    fitted and no claim of calibrated probabilities is made.
    """
    validate_packet(packet)
    if backend not in ("cpu", "cuda"):
        raise ValueError("backend must be cpu or cuda")
    if backend == "cuda":
        _cuda_backend()  # Honor an explicit request even if all probabilities are unknown.
    rows_and_values = [_evaluate_offer(packet, offer) for offer in packet["offers"]]
    rows = [row for row, _ in rows_and_values]
    eligible = [(row["id"], ev) for row, ev in rows_and_values if row["policy_passed"] and ev is not None]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    execution = {"financial_reference": "cpu_exact_integer_cents_and_fractions",
                 "requested_backend": backend, "event_value_backend": "cpu_exact",
                 "cuda_executed": False, "accelerated_rows": 0, "ai_runtime_used": False,
                 "policy_comparisons": "exact", "max_parity_difference_cents": 0}
    if backend == "cuda":
        known = [row for row in rows if row["event_tree"] is not None]
        if known:
            values = batch_expected_values(
                [r["event_tree"]["agreement_bp"] for r in known],
                [r["event_tree"]["closing_given_agreement_bp"] for r in known],
                [r["expected_profit_given_close_cents"] for r in known],
                packet["no_agreement_total_loss_cents"], packet["agreement_no_close_total_loss_cents"], backend="cuda")
            difference = max(abs(float(value)-float(row["event_tree"]["expected_net_cents_per_attempt"])) for value, row in zip(values, known))
            if not math.isfinite(difference) or difference > CUDA_TOLERANCE_CENTS:
                raise ArithmeticError("CUDA result exceeds the 0.01-cent exact-reference tolerance")
            execution.update(event_value_backend="cuda_float64", cuda_executed=True,
                             accelerated_rows=len(known), max_parity_difference_cents=difference,
                             parity_tolerance_cents=CUDA_TOLERANCE_CENTS)
            cp, _ = _cuda_backend()
            device = cp.cuda.runtime.getDeviceProperties(cp.cuda.runtime.getDevice())
            name = device.get("name", "unknown")
            execution["cuda_device"] = name.decode() if isinstance(name, bytes) else str(name)
    digest = hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"schema_version": SCHEMA_VERSION, "engine_version": ENGINE_VERSION,
            "model_id": packet["model_id"], "deal_id": packet["deal_id"], "as_of": packet["as_of"],
            "timezone": packet["timezone"], "currency": "USD", "input_sha256": digest,
            "exact_integer_encoding": "base10_strings",
            "illustrative": packet["illustrative"], "probability_basis": packet["probability_basis"],
            "probability_reference": packet.get("probability_reference"),
            "probabilities_validated_by_engine": False, "provenance": packet["provenance"],
            "event_horizon_note": packet["event_horizon_note"], "cost_note": packet["cost_note"],
            "decision_scope": "research_only", "runtime_agents_enabled": False,
            "selling_rounding": "floor_net_resale_proceeds_to_cents",
            "policy": dict(packet["policy"]), "required_profit_cents": packet["required_profit_cents"],
            "offers": rows, "price_ceilings": _price_ceilings(packet),
            "ranked_research_candidates": [oid for oid, _ in eligible],
            "ranking_note": "Conditional on supplied probabilities and retained policy. Includes negative EV candidates; compare with the zero-value pass alternative. No offer is approved or submitted.",
            "execution": execution}
