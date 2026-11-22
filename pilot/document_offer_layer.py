"""Apply reviewed document inputs to the deterministic offer engine.

This application layer joins two engines. It has no AI inference, network,
agent scheduler, offer submission, signature, or payment capability. It returns
an inspectable research packet; it never authorizes a real acquisition.
"""

from copy import deepcopy
import csv
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .offer_probability import MAX_MONEY_CENTS, evaluate_packet, validate_packet


LAYER_VERSION = "br-document-offer-layer/1"
BINDING_KEYS = {"field", "group", "record_id", "key", "offset_cents"}
MONEY_TARGETS = {
    "global": {"buyer_closing_cents", "spent_additional_allowance_cents"},
    "scenario": {"resale_cents", "renovation_cents", "carry_cents"},
    "offer": {"price_cents", "incremental_timing_cents"},
}


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _bindings(packet, bindings):
    if type(bindings) is not list or not 1 <= len(bindings) <= 256:
        raise ValueError("bindings must contain 1 to 256 explicit input bindings")
    targets = set()
    for binding in bindings:
        if type(binding) is not dict or set(binding) != BINDING_KEYS:
            raise ValueError("Each binding must specify field, group, record_id, key and offset_cents")
        if not isinstance(binding["field"], str) or not binding["field"].strip() or len(binding["field"]) > 100:
            raise ValueError("Invalid evidence field")
        group, key, identity = binding["group"], binding["key"], binding["record_id"]
        if (not isinstance(group, str) or group not in MONEY_TARGETS
                or not isinstance(key, str) or key not in MONEY_TARGETS[group]):
            raise ValueError("Only whitelisted economic money fields may be bound; probability and policy fields cannot")
        if group == "global":
            if identity is not None:
                raise ValueError("Global bindings require record_id=null")
        elif not isinstance(identity, str) or identity not in {x["id"] for x in packet[group+"s"]}:
            raise ValueError("Binding references an unknown scenario or offer")
        offset = binding["offset_cents"]
        if type(offset) is not int or not 0 <= offset <= MAX_MONEY_CENTS:
            raise ValueError("offset_cents must be a bounded nonnegative integer")
        if group != "scenario" and offset != 0:
            raise ValueError("Only scenario bindings may apply an explicit analyst cost offset")
        target = (group, identity, key)
        if target in targets:
            raise ValueError("A target input cannot have duplicate bindings")
        targets.add(target)


def _target(packet, binding):
    if binding["group"] == "global":
        return packet
    return next(x for x in packet[binding["group"]+"s"] if x["id"] == binding["record_id"])


def evaluate_with_evidence(store, packet, bindings, *, backend="cpu"):
    """Evaluate baseline and reviewed changes, preserving all source inputs.

    An unresolved projection returns the original assumptions for inspection,
    but withholds the document-adjusted result. A document cannot change the
    policy or probabilities. Scenario offsets are analyst assumptions, never
    claims extracted from the source. Changed offer terms invalidate the
    existing probability context and are held for revalidation. Economic
    changes also hold externally estimated probabilities until a new packet
    binds those estimates to the changed inputs.
    """
    validate_packet(packet)
    _bindings(packet, bindings)
    baseline = evaluate_packet(packet, backend=backend)
    fields = sorted({b["field"] for b in bindings})
    projection = store.project_inputs(packet["deal_id"], packet["as_of"], required_fields=fields)
    report = {
        "schema_version": LAYER_VERSION, "deal_id": packet["deal_id"],
        "as_of": packet["as_of"], "timezone": packet["timezone"], "currency": packet["currency"],
        "status": "evidence_review_required", "execution_allowed": False,
        "ai_enabled": False, "runtime_agents_enabled": False,
        "illustrative": packet["illustrative"] or projection.get("illustrative", False),
        "input_packet": deepcopy(packet), "bindings": deepcopy(bindings),
        "evidence": deepcopy(projection), "baseline": baseline, "after_evidence": None,
        "changes": [], "application_blockers": [],
        "interpretation": "Research calculation only. Scenario offsets and outcome probabilities remain explicit analyst inputs.",
    }
    if projection["state"] != "ready":
        report["report_sha256"] = _digest(report)
        return report
    adjusted = deepcopy(packet)
    adjusted["illustrative"] = report["illustrative"]
    changes = []
    for binding in bindings:
        field, key = binding["field"], binding["key"]
        fact = projection["facts"].get(field)
        if (not isinstance(fact, dict) or fact.get("value_type") != "money_cents"
                or fact.get("unit") != "cents" or fact.get("currency") != packet["currency"]
                or type(fact.get("value")) is not int or not 0 <= fact["value"] <= MAX_MONEY_CENTS):
            raise ValueError(f"{field}: expected reviewed integer cents in the packet currency")
        if not isinstance(fact.get("provenance"), list) or not fact["provenance"]:
            raise ValueError(f"{field}: source provenance is required")
        original, target = _target(packet, binding), _target(adjusted, binding)
        value = fact["value"] + binding["offset_cents"]
        if value > MAX_MONEY_CENTS or (key == "price_cents" and value <= 0):
            raise ValueError("Bound input exceeds the financial engine range")
        if binding["group"] == "offer" and value != original[key]:
            live_counter = original["kind"] == "accept_live_counter"
            report["application_blockers"].append({
                "code": "live_counter_terms_changed" if live_counter else "offer_probability_context_changed",
                "offer_id": original["id"], "field": key,
                "reason": "Revalidate the exact offer terms and their agreement/closing probability context in a new packet before applying changed terms.",
            })
            continue
        if value != original[key] and packet["probability_basis"] == "external_estimate":
            report["application_blockers"].append({
                "code": "external_probability_context_changed", "field": key,
                "reason": "Revalidate externally estimated outcome probabilities against the changed economics in a new packet.",
            })
            continue
        target[key] = value
        changes.append({"field": field, "group": binding["group"], "record_id": binding["record_id"],
                        "key": key, "before_cents": original[key], "document_value_cents": fact["value"],
                        "analyst_offset_cents": binding["offset_cents"], "after_cents": value,
                        "delta_cents": value-original[key], "provenance": deepcopy(fact["provenance"])})
    if report["application_blockers"]:
        report["report_sha256"] = _digest(report)
        return report
    # Changes are atomic at the application boundary: a partial binding set is
    # never exposed as the new model if an evidence or probability-context hold remains.
    report["after_evidence"] = evaluate_packet(adjusted, backend=backend)
    report["changes"] = changes
    report["status"] = "research_requires_review"
    report["report_sha256"] = _digest(report)
    return report


def _fraction_from(metric, key):
    exact = metric[key+"_exact"]
    return Fraction(int(exact["numerator"]), int(exact["denominator"]))


def export_r_review(report, directory):
    """Write a versioned, read-only R review exchange; no R process is executed.

    Exact numerators/denominators are decimal integer strings. Consumers must
    preserve them as character or use arbitrary precision, never silently
    coerce an unbounded rational numerator to an R double. Money inputs are
    bounded integer cents. The directory must be new to prevent stale mixes.
    """
    if report.get("schema_version") != LAYER_VERSION or report.get("after_evidence") is None:
        raise ValueError("A reviewed document-adjusted report is required")
    payload = deepcopy(report)
    fingerprint = payload.pop("report_sha256", None)
    if fingerprint != _digest(payload):
        raise ValueError("Report digest does not match its contents")
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=False)
    header = ["schema_version", "report_sha256", "deal_id", "as_of", "currency", "case", "offer_id",
              "price_cents", "baseline_profit_cents", "mean_profit_cents_numerator",
              "mean_profit_cents_denominator", "ev_cents_numerator", "ev_cents_denominator",
              "policy_passed", "execution_allowed"]
    with (destination/"offer_review.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for case in ("baseline", "after_evidence"):
            for offer in report[case]["offers"]:
                mean = _fraction_from(offer, "expected_profit_given_close_cents")
                ev = None if offer["event_tree"] is None else _fraction_from(offer["event_tree"], "expected_net_cents_per_attempt")
                writer.writerow({
                    "schema_version": "br-r-offer-review/1", "report_sha256": fingerprint,
                    "deal_id": report["deal_id"], "as_of": report["as_of"], "currency": report["currency"],
                    "case": case, "offer_id": offer["id"], "price_cents": offer["price_cents"],
                    "baseline_profit_cents": offer["baseline_profit_cents"],
                    "mean_profit_cents_numerator": str(mean.numerator), "mean_profit_cents_denominator": str(mean.denominator),
                    "ev_cents_numerator": "" if ev is None else str(ev.numerator),
                    "ev_cents_denominator": "" if ev is None else str(ev.denominator),
                    "policy_passed": str(offer["policy_passed"]).lower(), "execution_allowed": "false",
                })
    manifest = {"schema_version": "br-r-offer-review/1", "report_sha256": fingerprint,
                "deal_id": report["deal_id"], "currency": report["currency"], "timezone": report["timezone"],
                "money_unit": "integer cents", "rational_columns": "base-10 integer strings; preserve as character or arbitrary precision",
                "unknown_ev": "both EV columns are empty; never treat as zero", "R_executed": False,
                "python_rules_canonical": True, "files": {}}
    for path in (destination/"offer_review.csv",):
        manifest["files"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (destination/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest
