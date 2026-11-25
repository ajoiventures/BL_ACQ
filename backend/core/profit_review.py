"""Bounded deterministic USD cash reviewer; supplied facts are never authenticated.

This CPU reference complements the Academy's research models. It is not an
accounting, tax, valuation, loan approval, or enterprise financial engine.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import re
from typing import Any

from .ontology import DOMAINS

VERSION = "br-profit-review/1"
# Keep every money result exact in JSON consumers as well as Python.
MAX_CENTS = 9_007_199_254_740_991
OPERATING_FIELDS = (
    "revenue_cents", "operating_cost_cents", "debt_service_cents",
    "reserve_contribution_cents", "cash_capex_cents",
)
CAPITAL_FIELDS = ("opening_unrestricted_cash_cents", "opening_unspent_reserves_cents")
SALE_CASH_FIELDS = (
    "gross_price_cents", "selling_costs_cents", "debt_payoff_cents",
    "tax_reserve_cents", "other_cash_costs_cents", "redeployment_commitment_cents",
)
SALE_CONTEXT_FIELDS = ("purchase_cost_cents", "tax_basis_cents")
EVIDENCE_STATES = ("HYPOTHETICAL", "SUPPLIED_UNVERIFIED", "UNKNOWN")


class ProfitReviewError(ValueError):
    """A malformed or out-of-scope review packet."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _object(value: Any, allowed: set[str], path: str) -> dict:
    if type(value) is not dict or any(type(k) is not str for k in value):
        raise ProfitReviewError(f"{path} must be an object")
    extra = set(value) - allowed
    if extra:
        raise ProfitReviewError(f"{path} has unsupported keys: {', '.join(sorted(extra))}")
    return value


def _text(value: Any, path: str, maximum: int = 2000) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise ProfitReviewError(f"{path} requires nonempty text of at most {maximum} characters")
    return value


def _date(value: Any, path: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    try:
        if type(value) is not str or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError as exc:
        raise ProfitReviewError(f"{path} requires an ISO YYYY-MM-DD date") from exc
    return value


def _money(value: Any, path: str) -> int | None:
    if value is not None and (type(value) is not int or not 0 <= value <= MAX_CENTS):
        raise ProfitReviewError(f"{path} requires null or a nonnegative integer number of USD cents <= {MAX_CENTS}")
    return value


def _result_money(value: int | None) -> int | None:
    if value is not None and not -MAX_CENTS <= value <= MAX_CENTS:
        raise ProfitReviewError("Computed money exceeds the exact JSON integer range")
    return value


def _sum(*values: int | None) -> int | None:
    return None if any(v is None for v in values) else _result_money(sum(values))


def _subtract(start: int | None, *costs: int | None) -> int | None:
    return None if start is None or any(v is None for v in costs) else _result_money(start - sum(costs))


def _observation(value: Any, path: str, *, money: bool = True) -> dict:
    key = "value_cents" if money else "value"
    if value is None:
        value = {key: None, "evidence_status": "UNKNOWN"}
    row = _object(value, {key, "evidence_status", "source_ref", "source_date", "note"}, path)
    if key not in row or "evidence_status" not in row:
        raise ProfitReviewError(f"{path} requires {key} and evidence_status")
    raw = _money(row[key], path + "." + key) if money else row[key]
    if not money and raw is not None:
        raw = _text(raw, path + ".value", 300)
    status = row["evidence_status"]
    if type(status) is not str or status not in EVIDENCE_STATES:
        raise ProfitReviewError(f"{path}.evidence_status must be HYPOTHETICAL, SUPPLIED_UNVERIFIED, or UNKNOWN; this reviewer cannot accept facts")
    if (raw is None) != (status == "UNKNOWN"):
        raise ProfitReviewError(f"{path}: null requires UNKNOWN; a supplied value requires an unverified or hypothetical marker")
    source = row.get("source_ref")
    if source is not None:
        source = _text(source, path + ".source_ref")
    note = row.get("note")
    if note is not None:
        note = _text(note, path + ".note", 1000)
    return {key: raw, "evidence_status": status, "source_ref": source,
            "source_date": _date(row.get("source_date"), path + ".source_date", nullable=True), "note": note}


def _amount_group(value: Any, fields: tuple[str, ...], path: str) -> dict:
    row = _object({} if value is None else value, set(fields), path)
    return {key: _observation(row.get(key), path + "." + key) for key in fields}


def validate(packet: Any) -> dict:
    """Return a detached, normalized snapshot; never coerce numbers or fill zeroes."""
    row = _object(packet, {"schema_version", "review_id", "domain", "currency", "period",
                          "mode", "as_of", "source", "subject", "operations", "capital", "sale", "scenarios"}, "packet")
    for field, expected in (("schema_version", VERSION), ("currency", "USD"),
                            ("period", "ANNUAL"), ("mode", "ANALYST_REVIEW")):
        if row.get(field) != expected:
            raise ProfitReviewError(f"{field} must be {expected}")
    review_id = _text(row.get("review_id"), "review_id", 128)
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", review_id):
        raise ProfitReviewError("review_id contains unsupported characters")
    domain = row.get("domain")
    if type(domain) is not str or domain not in DOMAINS:
        raise ProfitReviewError("Unknown domain")
    source = _object(row.get("source"), {"reference", "source_date"}, "source")
    subject = _object(row.get("subject"), {"label", "owner"}, "subject")
    snapshot = {
        "schema_version": VERSION, "review_id": review_id, "domain": domain,
        "currency": "USD", "period": "ANNUAL", "mode": "ANALYST_REVIEW",
        "as_of": _date(row.get("as_of"), "as_of"),
        "source": {"reference": _text(source.get("reference"), "source.reference"),
                   "source_date": _date(source.get("source_date"), "source.source_date", nullable=True)},
        "subject": {"label": _text(subject.get("label"), "subject.label", 300),
                    "owner": _observation(subject.get("owner"), "subject.owner", money=False)},
        "operations": None, "capital": None, "sale": None, "scenarios": [],
    }
    if row.get("operations") is not None:
        snapshot["operations"] = _amount_group(row["operations"], OPERATING_FIELDS, "operations")
        snapshot["capital"] = _amount_group(row.get("capital"), CAPITAL_FIELDS, "capital")
    elif row.get("capital") is not None:
        raise ProfitReviewError("capital requires an operations model")
    if row.get("sale") is not None:
        snapshot["sale"] = _amount_group(row["sale"], SALE_CASH_FIELDS + SALE_CONTEXT_FIELDS, "sale")
    if snapshot["operations"] is None and snapshot["sale"] is None:
        raise ProfitReviewError("Supply an operations or sale object; empty objects preserve unknown inputs")
    scenarios = row.get("scenarios", [])
    if type(scenarios) is not list or len(scenarios) > 8:
        raise ProfitReviewError("scenarios must be a list of at most eight explicit scenarios")
    ids = {"BASE"}
    for i, scenario in enumerate(scenarios):
        path = f"scenarios[{i}]"
        item = _object(scenario, {"id", "label", "operations"}, path)
        sid = _text(item.get("id"), path + ".id", 80)
        if sid in ids or not re.fullmatch(r"[A-Za-z0-9_.:-]+", sid):
            raise ProfitReviewError("Scenario IDs must be distinct, non-BASE identifiers")
        ids.add(sid)
        if snapshot["operations"] is None:
            raise ProfitReviewError("Operating scenarios require an operations model")
        changes = _object(item.get("operations"), set(OPERATING_FIELDS), path + ".operations")
        if not changes:
            raise ProfitReviewError("A scenario requires at least one explicit amount override")
        snapshot["scenarios"].append({
            "id": sid, "label": _text(item.get("label"), path + ".label", 300),
            "operations": {key: _observation(value, path + ".operations." + key) for key, value in changes.items()},
        })
    return snapshot


def _values(group: dict) -> dict[str, int | None]:
    return {key: row["value_cents"] for key, row in group.items()}


def _availability(group: dict) -> dict[str, str]:
    return {key: "UNKNOWN" if row["value_cents"] is None else "KNOWN_AS_SUPPLIED" for key, row in group.items()}


def _cash_result(value: int | None) -> str:
    return "UNKNOWN" if value is None else "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "ZERO"


def _partial_cash_upper_bound(start: int | None, *deductions: int | None) -> int | None:
    """A bound under nonnegative missing deductions, never an exact missing total."""
    if start is None or all(value is not None for value in deductions):
        return None
    return _subtract(start, *(value for value in deductions if value is not None))


def _operations(group: dict, capital: dict) -> dict:
    v, c = _values(group), _values(capital)
    noi = _subtract(v["revenue_cents"], v["operating_cost_cents"])
    after_debt = _subtract(noi, v["debt_service_cents"])
    after_reserve = _subtract(after_debt, v["reserve_contribution_cents"])
    cash = _subtract(after_reserve, v["cash_capex_cents"])
    partial_bound = _partial_cash_upper_bound(v["revenue_cents"], v["operating_cost_cents"],
                                             v["debt_service_cents"], v["reserve_contribution_cents"], v["cash_capex_cents"])
    unrestricted = _sum(c["opening_unrestricted_cash_cents"], cash)
    reserves = _sum(c["opening_unspent_reserves_cents"], v["reserve_contribution_cents"])
    debt = v["debt_service_cents"]
    dscr = None
    if debt is not None and debt > 0 and noi is not None:
        with localcontext() as ctx:
            ctx.prec = 48
            display = (Decimal(noi) / Decimal(debt)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)
        dscr = {"numerator_cents": noi, "denominator_cents": debt, "display_ratio": str(display),
                "display_rounding": "6 decimal places, ROUND_HALF_EVEN"}
    missing = ["operations." + k for k, value in v.items() if value is None]
    capital_missing = ["capital." + k for k, value in c.items() if value is None]
    return {
        "currency": "USD", "period": "ANNUAL", "calculation_status": "NEEDS_EVIDENCE" if missing else "SCENARIO_CALCULATED",
        "input_availability": _availability(group), "capital_availability": _availability(capital),
        "missing_operating_inputs": missing, "missing_capital_inputs": capital_missing,
        "noi_cents": noi, "cash_after_debt_service_cents": after_debt,
        "cash_after_reserve_contribution_cents": after_reserve,
        "distributable_cash_cents": cash, "scenario_cash_result": _cash_result(cash),
        "cash_after_known_deductions_upper_bound_cents": partial_bound,
        "break_even_revenue_cents": _sum(v["operating_cost_cents"], debt, v["reserve_contribution_cents"], v["cash_capex_cents"]),
        "dscr": dscr, "dscr_reason": "DEBT_FREE" if debt == 0 else "CALCULATED" if dscr else "NEEDS_EVIDENCE",
        "lender_dscr_threshold": None, "lender_compliance": "NOT_EVALUATED",
        "ending_unrestricted_cash_before_distributions_cents": unrestricted,
        "annual_cash_gap_cents": None if unrestricted is None else max(0, -unrestricted),
        "ending_unspent_reserves_cents": reserves,
        "ending_total_cash_including_earmarked_reserves_cents": _sum(unrestricted, reserves),
        "within_year_cash_survival": "NOT_EVALUATED",
        "accounting_profit_cents": None,
        "cash_convention": "Reserve contributions remain earmarked cash, not operating expense. Cash capex is paid from unrestricted cash; reserve draws and owner distributions are not modeled.",
    }


def _sale(group: dict) -> dict:
    v = _values(group)
    after_selling = _subtract(v["gross_price_cents"], v["selling_costs_cents"])
    before_reserve = _subtract(after_selling, v["debt_payoff_cents"])
    after_tax_reserve = _subtract(before_reserve, v["tax_reserve_cents"])
    net = _subtract(after_tax_reserve, v["other_cash_costs_cents"])
    remaining = _subtract(net, v["redeployment_commitment_cents"])
    partial_bound = _partial_cash_upper_bound(v["gross_price_cents"], *(v[key] for key in SALE_CASH_FIELDS[1:]))
    missing = ["sale." + k for k in SALE_CASH_FIELDS if v[k] is None]
    return {
        "currency": "USD", "period": "ONE_TIME", "calculation_status": "NEEDS_EVIDENCE" if missing else "SCENARIO_CALCULATED",
        "input_availability": _availability(group), "missing_cash_inputs": missing,
        "cash_after_selling_costs_cents": after_selling,
        "cash_before_tax_reserve_and_other_costs_cents": before_reserve,
        "cash_after_tax_reserve_cents": after_tax_reserve,
        "net_cash_available_before_redeployment_cents": net,
        "cash_after_redeployment_cents": remaining, "scenario_cash_result": _cash_result(remaining),
        "cash_after_known_deductions_upper_bound_cents": partial_bound,
        "cash_reserved_for_tax_cents": v["tax_reserve_cents"],
        "historical_context_only": {k: v[k] for k in SALE_CONTEXT_FIELDS},
        "tax_liability_cents": None, "accounting_gain_cents": None, "section_1031_eligibility": "NOT_EVALUATED",
        "cash_convention": "Purchase cost and tax basis are historical context, not spendable cash or additional sale deductions. The supplied tax reserve is earmarked cash, not a calculated liability or paid tax.",
    }


def review(packet: Any) -> dict:
    """Calculate scenario arithmetic and bounded evidence priorities, with zero authority."""
    snapshot = validate(packet)
    base = _operations(snapshot["operations"], snapshot["capital"]) if snapshot["operations"] is not None else None
    sale = _sale(snapshot["sale"]) if snapshot["sale"] is not None else None
    scenarios = []
    for item in snapshot["scenarios"]:
        effective = {**snapshot["operations"], **item["operations"]}
        scenarios.append({"id": item["id"], "label": item["label"],
                          "effective_operations": deepcopy(effective),
                          "result": _operations(effective, snapshot["capital"])})
    missing, unverified, incomplete_provenance = [], [], []

    def track(path, observation, value_key):
        (missing if observation[value_key] is None else unverified).append(path)
        if observation['evidence_status'] == 'SUPPLIED_UNVERIFIED' and (
            not observation['source_ref'] or not observation['source_date']
        ):
            incomplete_provenance.append(path)

    for name in ("operations", "capital", "sale"):
        for key, item in (snapshot[name] or {}).items():
            track(name + "." + key, item, "value_cents")
    track("subject.owner", snapshot["subject"]["owner"], "value")
    for i, item in enumerate(snapshot["scenarios"]):
        for key, observation in item["operations"].items():
            track(f"scenarios[{i}].operations.{key}", observation, "value_cents")
    cash_cases = [("BASE", base)] if base is not None else []
    cash_cases += [(item["id"], item["result"]) for item in scenarios]
    operating_steps = ("noi_cents", "cash_after_debt_service_cents", "cash_after_reserve_contribution_cents",
                       "distributable_cash_cents", "cash_after_known_deductions_upper_bound_cents")
    sale_steps = ("cash_after_selling_costs_cents", "cash_before_tax_reserve_and_other_costs_cents",
                  "cash_after_tax_reserve_cents", "net_cash_available_before_redeployment_cents",
                  "cash_after_redeployment_cents", "cash_after_known_deductions_upper_bound_cents")
    assessed_cases = [(sid, case, operating_steps) for sid, case in cash_cases]
    if sale is not None:
        assessed_cases.append(("SALE", sale, sale_steps))
    shortfalls = [{"case_id": sid, "field": field, "amount_cents": case[field], "period": case["period"],
                   "amount_kind": "UPPER_BOUND" if field.endswith("upper_bound_cents") else "KNOWN_INTERMEDIATE_OR_FINAL"}
                  for sid, case, fields in assessed_cases for field in fields
                  if case[field] is not None and case[field] < 0]
    negative = list(dict.fromkeys(item["case_id"] for item in shortfalls))
    priorities = []
    if negative:
        priorities.append({"code": "REVIEW_CASH_SHORTFALL", "owner": "L3 / SW-10", "cases": negative,
                           "action": "Reconcile the negative cash cases against a dated debt schedule, operating records, capex plan, reserve policy, and unrestricted cash balance before any commitment."})
    if missing:
        priorities.append({"code": "SUPPLY_MISSING_EVIDENCE", "owner": "L3 with L4", "fields": sorted(missing),
                           "action": "Obtain dated source records for the unknown inputs and establish the subject's owner and authority. Preserve nulls until supplied."})
    if unverified:
        priorities.append({"code": "VERIFY_SUPPLIED_ASSUMPTIONS", "owner": "SW-13", "fields": sorted(unverified),
                           "incomplete_provenance_fields": sorted(incomplete_provenance),
                           "action": "Attach missing source references and dates, then review the supplied assumptions against the source documents."})
    findings = []
    if base is not None:
        findings.append({"code": "OPERATING_CASH_BRIDGE", "noi_cents": base["noi_cents"],
                         "cash_after_debt_service_cents": base["cash_after_debt_service_cents"],
                         "distributable_cash_cents": base["distributable_cash_cents"],
                         "meaning": "Annual scenario cash after supplied operating costs, debt service, reserve contributions, and cash capex; not accounting profit."})
    if negative:
        findings.append({"code": "NEGATIVE_SCENARIO_CASH", "cases": negative, "known_shortfalls": shortfalls,
                         "meaning": "A known cash bridge step or an upper bound after known nonnegative deductions is negative. Unknown final totals stay null; no likelihood, cash survival, or investment rejection is inferred."})
    if sale is not None:
        findings.append({"code": "SALE_CASH_BRIDGE", "net_cash_available_before_redeployment_cents": sale["net_cash_available_before_redeployment_cents"],
                         "meaning": "Cash remaining after the specified selling costs, payoff, tax reserve, and other cash costs. Historical purchase cost and basis are excluded from this cash bridge."})
    findings.append({"code": "EVIDENCE_REVIEW_REQUIRED", "meaning": "All supplied values remain hypothetical or unverified. Missing values remain unknown; ownership, profit, available capital, and bank compliance are not authenticated."})
    report = {
        "engine_version": VERSION, "backend": "CPU_REFERENCE", "mode": "ANALYST_REVIEW",
        "review_id": snapshot["review_id"], "domain": snapshot["domain"], "as_of": snapshot["as_of"],
        "currency": "USD", "period": "ANNUAL", "sale_period": "ONE_TIME",
        "status": "NEEDS_EVIDENCE", "supported_profit_claim": False,
        "financial_authority_cents": 0, "contractual_authority": 0, "external_authority": 0,
        "input_snapshot": snapshot, "input_sha256": digest(snapshot),
        "operating_review": base, "sale_review": sale, "scenarios": scenarios,
        "known_cash_shortfalls": shortfalls,
        "missing_inputs": sorted(missing), "unverified_inputs": sorted(unverified),
        "supplied_inputs_with_incomplete_provenance": sorted(incomplete_provenance),
        "findings": findings, "priorities": priorities[:3],
        "limitations": ["Annual totals cannot establish within-year liquidity or cash survival.",
                        "No evidence authentication, lender policy determination, tax liability, 1031 eligibility, valuation, or accounting profit calculation.",
                        "No probabilities, outreach, transfer of funds, offer approval, or automatic deal rejection.",
                        "Independent evidence review and an authenticated application connection are separate from this local calculation."],
    }
    report["report_sha256"] = digest(report)
    return report


COACH_VERSION = "br-acquisition-coach/1"
STAGE_REQUIREMENTS = {
    "buy_box": ("objective", "buy_box"),
    "capital": ("available_cash", "financing_terms", "reserve_policy", "investment_limits"),
    "corridor_sourcing": ("corridor_boundary", "parcel_sources", "corridor_thesis"),
    "shortlist": ("candidate_comparison", "source_reconciliation"),
    "underwriting": ("operating_inputs", "debt_schedule", "capex_reserve_plan", "downside_review"),
    "title_use": ("ownership_authority", "title_review", "permitted_use", "access_utilities"),
    "outreach_prep": ("owner_contact_basis", "owner_packet", "outreach_scope"),
    "offer_review": ("financial_policy_review", "offer_terms", "offer_scope"),
    "due_diligence": ("inspection", "leases_income", "lender_conditions", "title_conditions"),
    "closing": ("final_cash_uses", "final_title", "closing_scope"),
    "operations": ("operating_budget", "reserve_funding", "reporting_calendar"),
}
STAGE_ACTIONS = {
    "buy_box": ("L4 / SW-02", 30, "Draft a one-page 2–4-unit buy box and connect its location criteria to the whole Main Street corridor; the founder supplies the decision-critical choices.",
                "Versioned buy box with corridor criteria, operating objective, and explicitly unknown budget and financing where applicable."),
    "capital": ("L3 / SW-10", 45, "Build a capital evidence worksheet from accessible cash records, obligations, reserve needs, and any supplied lender terms.",
                "Dated capital worksheet with source references and unresolved balances or financing terms left unknown."),
    "corridor_sourcing": ("L4 / SW-02", 45, "Map one candidate Main Street corridor and record the sources needed to identify 2–4-unit parcels within its context.",
                         "Corridor map or boundary reference, parcel-source register, and acquisition thesis."),
    "shortlist": ("L4 / SW-05", 30, "Compare the candidates already identified and select the next property fact to verify; no minimum candidate count is required.",
                  "Source-linked candidate comparison with unknowns and one next verification item."),
    "underwriting": ("L3 / SW-05", 45, "Populate the operating cash bridge and an explicit downside case for the candidate under review.",
                     "Integer-cent review packet with revenue, costs, debt, reserves, capex, cash balances, and dated source references."),
    "title_use": ("L4 / SW-07", 45, "Assemble the parcel's ownership, title, permitted-use, access, and utility evidence questions for review.",
                  "Property-rights and use review packet with document references and unresolved questions."),
    "outreach_prep": ("L4 / SW-05", 30, "Prepare one unsent owner outreach packet with a documented contact basis and proposed scope.",
                      "Unsent packet linked to the candidate, contact-source evidence, and the scope awaiting founder review."),
    "offer_review": ("L4 with L3", 45, "Assemble an unsigned offer review packet linked to the supplied financial limits, financing terms, reserves, and evidence.",
                     "Unsigned terms and cash bridge with unresolved conditions and the exact scope awaiting review."),
    "due_diligence": ("L4 / SW-07", 45, "Consolidate inspection, lease, financing, and title findings into one dated open-items list.",
                      "Evidence-linked diligence list with accountable owners and unresolved conditions."),
    "closing": ("L3 with L4", 45, "Reconcile the draft closing cash bridge against payoff, title, financing, and authorized scope documents.",
                "Draft sources-and-uses reconciliation with unknowns preserved and no funds movement."),
    "operations": ("L4 with L3", 30, "Draft the first-year operating and reserve reporting schedule from the current referenced assumptions.",
                   "Operating budget and reserve reporting schedule linked to the acquired-property evidence, if supplied."),
}


def _references(value: Any, path: str) -> list[str]:
    if type(value) is not list or len(value) > 12:
        raise ProfitReviewError(f"{path} requires at most twelve source references")
    return [_text(item, path, 2000) for item in value]


def coach_acquisition(context: Any) -> dict:
    """Guide one reviewable preparation action; never complete or advance a stage."""
    row = _object(context, {"schema_version", "plan_id", "ticket_id", "revision", "domain", "as_of", "stage",
                            "target", "evidence", "policy", "financial_review", "blockers"}, "coach")
    if row.get("schema_version") != COACH_VERSION:
        raise ProfitReviewError(f"schema_version must be {COACH_VERSION}")
    revision, stage, domain = row.get("revision"), row.get("stage"), row.get("domain")
    if type(revision) is not int or not 1 <= revision <= 1_000_000:
        raise ProfitReviewError("revision requires an integer from 1 to 1000000")
    if type(stage) is not str or stage not in STAGE_REQUIREMENTS:
        raise ProfitReviewError("Unknown acquisition stage")
    if type(domain) is not str or domain not in DOMAINS:
        raise ProfitReviewError("Unknown domain")
    target = _object(row.get("target"), {"minimum_units", "maximum_units", "corridor_context"}, "target")
    if (type(target.get("minimum_units")) is not int or target["minimum_units"] != 2
            or type(target.get("maximum_units")) is not int or target["maximum_units"] != 4
            or target.get("corridor_context") != "WHOLE_MAIN_STREET"):
        raise ProfitReviewError("This coach requires an explicit 2–4-unit target connected to the whole Main Street corridor")
    evidence = row.get("evidence", [])
    if type(evidence) is not list or len(evidence) > 64:
        raise ProfitReviewError("evidence requires a list of at most 64 records")
    known_keys = {key for keys in STAGE_REQUIREMENTS.values() for key in keys}
    records = {}
    for i, item in enumerate(evidence):
        path = f"evidence[{i}]"
        item = _object(item, {"key", "status", "source_refs", "source_date", "note"}, path)
        key, status = item.get("key"), item.get("status")
        if type(key) is not str or key not in known_keys or key in records:
            raise ProfitReviewError("Evidence keys must be supported and unique")
        if type(status) is not str or status not in ("UNKNOWN", "SUPPLIED_UNVERIFIED", "REVIEW_REFERENCED", "OBJECTIVE_CONFIRMED"):
            raise ProfitReviewError("Unsupported coach evidence status; accepted facts cannot be declared here")
        refs = _references(item.get("source_refs", []), path + ".source_refs")
        if status != "UNKNOWN" and not refs:
            raise ProfitReviewError("A supplied completion or objective marker requires source references")
        if status == "OBJECTIVE_CONFIRMED" and key != "objective":
            raise ProfitReviewError("OBJECTIVE_CONFIRMED applies only to the stated objective")
        note = item.get("note")
        records[key] = {"key": key, "status": status, "source_refs": refs,
                        "source_date": _date(item.get("source_date"), path + ".source_date", nullable=True),
                        "note": None if note is None else _text(note, path + ".note", 1000)}
    policy = row.get("policy")
    if policy is not None:
        policy = _object(policy, {"outcome", "source_refs", "note"}, "policy")
        if type(policy.get("outcome")) is not str or policy["outcome"] not in ("UNKNOWN", "REQUIRES_REVIEW", "WITHIN_SUPPLIED_LIMITS", "OUTSIDE_SUPPLIED_LIMITS"):
            raise ProfitReviewError("Unsupported supplied policy outcome")
        refs = _references(policy.get("source_refs", []), "policy.source_refs")
        if policy["outcome"] != "UNKNOWN" and not refs:
            raise ProfitReviewError("A supplied policy outcome requires source references")
        policy = {"outcome": policy["outcome"], "source_refs": refs,
                  "note": None if policy.get("note") is None else _text(policy["note"], "policy.note", 1000)}
    financial = row.get("financial_review")
    if financial is not None:
        if type(financial) is not dict or type(financial.get("input_snapshot")) is not dict:
            raise ProfitReviewError("financial_review requires a complete deterministic profit review report")
        expected = review(financial["input_snapshot"])
        try:
            matches = canonical(financial) == canonical(expected)
        except (TypeError, ValueError) as exc:
            raise ProfitReviewError("Invalid financial report") from exc
        if not matches or expected["domain"] != domain:
            raise ProfitReviewError("Financial review must match its recomputed snapshot and coach domain")
        financial = expected
    blockers = row.get("blockers", [])
    if type(blockers) is not list or len(blockers) > 10:
        raise ProfitReviewError("blockers requires a list of at most ten records")
    normalized_blockers = []
    for i, blocker in enumerate(blockers):
        path = f"blockers[{i}]"
        item = _object(blocker, {"code", "detail", "source_ref"}, path)
        normalized_blockers.append({"code": _text(item.get("code"), path + ".code", 80),
                                    "detail": _text(item.get("detail"), path + ".detail", 1000),
                                    "source_ref": None if item.get("source_ref") is None else _text(item["source_ref"], path + ".source_ref")})
    snapshot = {"schema_version": COACH_VERSION, "plan_id": _text(row.get("plan_id"), "plan_id", 128),
                "ticket_id": _text(row.get("ticket_id"), "ticket_id", 128), "revision": revision,
                "domain": domain, "as_of": _date(row.get("as_of"), "as_of"), "stage": stage,
                "target": deepcopy(target), "evidence": [records[key] for key in sorted(records)],
                "policy": policy, "financial_review": financial, "blockers": normalized_blockers}
    stages = list(STAGE_REQUIREMENTS)
    gates = []
    for name in stages[:stages.index(stage) + 1]:
        missing = [key for key in STAGE_REQUIREMENTS[name]
                   if key not in records or records[key]["status"] == "UNKNOWN"]
        gates.append({"stage": name, "missing_evidence": missing,
                      "status": "NEEDS_EVIDENCE" if missing else "REFERENCES_PRESENT_REVIEW_REQUIRED",
                      "completed": False})
    gate = next((item for item in gates if item["missing_evidence"]), gates[-1])
    action_owner, minutes, action, deliverable = STAGE_ACTIONS[gate["stage"]]
    negative_cash = bool(financial and any(item["code"] == "NEGATIVE_SCENARIO_CASH" for item in financial["findings"]))
    outside_policy = bool(policy and policy["outcome"] == "OUTSIDE_SUPPLIED_LIMITS")
    if negative_cash or outside_policy:
        action_owner, minutes = "L3 / SW-10", 45
        action = "Reconcile the reported financial shortfall or supplied policy breach and document the evidence or plan revision needed before any acquisition commitment."
        deliverable = "Revised cash assumptions or a documented unresolved policy exception for human review; no approval or rejection."
    elif normalized_blockers:
        action = "Document the evidence and responsible owner needed to resolve the first recorded blocker: " + normalized_blockers[0]["code"] + "."
        deliverable = "A source-linked resolution note for the recorded blocker, retaining any unresolved dependency."
    elif not gate["missing_evidence"]:
        action = f"Prepare the referenced {gate['stage']} evidence packet for independent review without marking the stage complete."
        deliverable = "Review packet with source references, current revision, unresolved questions, and a recorded reviewer decision when available."
    next_handoff = {
        "recipient": "SW-13 with " + action_owner,
        "output": deliverable,
        "condition": "After the deliverable is saved with its revision and source references; unresolved inputs remain explicit.",
        "dispatch_status": "NOT_SENT", "stage_transition_authorized": False,
    }
    if negative_cash or outside_policy:
        next_handoff.update(recipient="L3 / SW-10 and SW-05",
                            output="Reconciled cash bridge and unresolved financial limits for review before any acquisition commitment.")
    elif gate["stage"] == "buy_box" and gate["missing_evidence"] and not normalized_blockers:
        next_handoff.update(
            recipient="L4 / SW-01 and SW-02",
            output="Dated buy box with founder choices and unresolved capital evidence for one source-backed whole-corridor screen.",
            condition="After the founder supplies decision-critical choices and a referenced buy-box revision is saved; this handoff does not pass the capital gate.",
            later_underwriting="SW-05 receives a selected candidate when price, rent, operating costs, debt, reserve, and capex evidence is available.",
        )
        if "available_cash" in records:
            next_handoff.update(
                recipient="L3 / SW-10 and SW-07",
                output="Source-linked capital-source worksheet separating planning intent from owner/taxpayer, payoff, available cash, intended treatment, and timing evidence.",
                condition="After the founder's choices and capital-source context are recorded in the referenced buy box; the planned source does not establish spendable or unrestricted cash.",
                corridor_sourcing="SW-01/SW-02 prepare one source-backed whole-corridor screen with capital constraints still explicit.",
            )
    priorities = [
        {"code": "CURRENT_GATE_EVIDENCE", "stage": gate["stage"], "missing_evidence": gate["missing_evidence"]},
        {"code": "FINANCIAL_DISCIPLINE", "financial_review_supplied": financial is not None,
         "negative_scenario_cash": negative_cash, "supplied_policy_outcome": policy["outcome"] if policy else "UNKNOWN",
         "action": "Keep budget, financing, and limits unknown until evidenced; resolve supplied constraints before commitment."},
        {"code": "WHOLE_CORRIDOR_CONTEXT", "action": "Keep the 2–4-unit acquisition linked to the full Main Street corridor thesis and source map."},
    ]
    result = {"engine_version": COACH_VERSION, "backend": "CPU_REFERENCE", "mode": "ANALYST_REVIEW",
              "plan_id": snapshot["plan_id"], "ticket_id": snapshot["ticket_id"], "revision": revision,
              "domain": domain, "as_of": snapshot["as_of"], "target": deepcopy(target),
              "capital_context": {"available_cash_evidence": deepcopy(records.get("available_cash")),
                                  "actual_available_cash_cents": None, "evidence_acceptance": "NOT_PERFORMED"},
              "stage": stage, "stage_status": gate["status"], "stage_advanced": False,
              "current_gate": gate, "preceding_and_current_gates": gates,
              "next_action": {"action": action, "owner": action_owner, "estimated_timebox_minutes": minutes,
                              "timebox_basis": "PLANNING_ESTIMATE_NOT_MEASURED_DURATION", "deliverable": deliverable,
                              "completion_evidence": ["Saved deliverable reference and revision", "Dated source references for supplied claims",
                                                      "Documented unresolved inputs and reviewer decision when applicable"]},
              "next_handoff": next_handoff,
              "priorities": priorities, "evidence_acceptance": "NOT_PERFORMED",
              "financial_authority_cents": 0, "contractual_authority": 0, "external_authority": 0,
              "notifications_scheduled": 0, "input_snapshot": snapshot, "input_sha256": digest(snapshot),
              "limits": "Preparation guidance only. Referenced evidence is caller-supplied and is not authenticated or accepted. No stage advancement, sends, financing choice, funds movement, or automatic rejection."}
    result["report_sha256"] = digest(result)
    return result
