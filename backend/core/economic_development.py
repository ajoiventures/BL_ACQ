"""Deterministic analyst screening; supplied data never becomes accepted evidence.

This bounded CPU reference calculates corridor survey coverage and preliminary
data-center constraints. It neither certifies a site nor models investment returns.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
import hashlib
import json
import re
from typing import Any

VERSION = "br-economic-development/1"
DOMAINS = ("COMMERCIAL", "MAIN_STREET_INSTITUTIONAL")
EVIDENCE_STATES = ("HYPOTHETICAL", "SUPPLIED_UNVERIFIED", "UNKNOWN")
UTILITY_STAGES = ("PROXIMITY", "PRELIMINARY_ASSESSMENT", "ENGINEERING_STUDY", "SERVICE_AGREEMENT", "ENERGIZED")
IT_LOAD_BASES = ("ANNUAL_AVERAGE", "NAMEPLATE", "PEAK")
MAX_COUNT = 9_007_199_254_740_991
GATES = {
    "demand_profile": "Load ramp, peak and seasonal operating profile are specified for utility review.",
    "reserve_redundancy_headroom": "Separate reserve, redundancy and headroom requirements are addressed.",
    "utility_service_terms_reliability": "Utility service terms, tariff and reliability requirements are addressed.",
    "utility_study_service_costs": "Utility study scope, service construction costs and cost allocation are addressed.",
    "fiber_route_diversity": "Required physically diverse fiber routes and service terms are addressed.",
    "land_control_title": "Site control, title, access and easement requirements are addressed.",
    "land_use_permit_path": "Permitted use, approvals and development conditions have a documented path.",
    "cooling_water": "Cooling design, water supply, discharge and drought constraints are addressed.",
    "environmental_flood": "Environmental, flood, habitat and site constraints are addressed.",
    "noise_air_generator_community": "Noise, air, generator permits and community compatibility are addressed.",
    "customer_commercial_readiness": "Customer demand, offtake and commercial readiness are addressed.",
}


class EconomicDevelopmentError(ValueError):
    """A malformed or out-of-scope analyst packet."""


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _object(value: Any, allowed: set[str], path: str) -> dict:
    if type(value) is not dict or any(type(key) is not str for key in value):
        raise EconomicDevelopmentError(f"{path} must be an object")
    extra = set(value) - allowed
    if extra:
        raise EconomicDevelopmentError(f"{path} has unsupported keys: {', '.join(sorted(extra))}")
    return value


def _text(value: Any, path: str, maximum: int = 1000) -> str:
    if type(value) is not str or not value.strip() or len(value) > maximum:
        raise EconomicDevelopmentError(f"{path} requires nonempty text of at most {maximum} characters")
    return value


def _date(value: Any, path: str, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    try:
        if type(value) is not str or date.fromisoformat(value).isoformat() != value:
            raise ValueError()
    except ValueError as exc:
        raise EconomicDevelopmentError(f"{path} requires an ISO YYYY-MM-DD date") from exc
    return value


def _count(value: Any, path: str, nullable: bool = False) -> int | None:
    if value is None and nullable:
        return None
    if type(value) is not int or not 0 <= value <= MAX_COUNT:
        raise EconomicDevelopmentError(f"{path} requires a nonnegative integer <= {MAX_COUNT}")
    return value


def _decimal(value: Any, path: str, minimum: Decimal = Decimal(0)) -> str:
    # Decimal strings avoid binary-float coercion, bool-as-int and NaN/Infinity.
    if type(value) is not str or not re.fullmatch(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?", value):
        raise EconomicDevelopmentError(f"{path} requires a nonnegative decimal string, up to 12 integer and 6 fractional digits")
    number = Decimal(value)
    if number < minimum:
        raise EconomicDevelopmentError(f"{path} must be >= {minimum}")
    return _decimal_text(number)


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _ratio(numerator: int, denominator: int) -> dict:
    with localcontext() as context:
        context.prec = 50
        value = None if denominator == 0 else _decimal_text((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001")))
    return {"numerator": numerator, "denominator": denominator, "value": value}


def _status(value: Any, path: str) -> str:
    if type(value) is not str or value not in EVIDENCE_STATES:
        raise EconomicDevelopmentError(f"{path} must be HYPOTHETICAL, SUPPLIED_UNVERIFIED, or UNKNOWN; accepted evidence cannot be supplied here")
    return value


def _source(value: Any, path: str, as_of: str) -> dict:
    row = _object(value, {"reference", "source_date", "evidence_status"}, path)
    source_date = _date(row.get("source_date"), path + ".source_date")
    if source_date > as_of:
        raise EconomicDevelopmentError(f"{path}.source_date cannot be later than as_of")
    return {"reference": _text(row.get("reference"), path + ".reference"), "source_date": source_date,
            "evidence_status": _status(row.get("evidence_status"), path + ".evidence_status")}


def _base(packet: Any, specific: set[str]) -> tuple[dict, dict]:
    row = _object(packet, {"schema_version", "review_id", "domain", "mode", "as_of", "geography", "source"} | specific, "packet")
    if row.get("schema_version") != VERSION or row.get("mode") != "ANALYST_SCREENING":
        raise EconomicDevelopmentError(f"schema_version must be {VERSION} and mode must be ANALYST_SCREENING")
    identifier = _text(row.get("review_id"), "review_id", 128)
    if not re.fullmatch(r"[A-Za-z0-9_.:-]+", identifier):
        raise EconomicDevelopmentError("review_id contains unsupported characters")
    if type(row.get("domain")) is not str or row["domain"] not in DOMAINS:
        raise EconomicDevelopmentError("Economic development requires COMMERCIAL or MAIN_STREET_INSTITUTIONAL domain")
    as_of = _date(row.get("as_of"), "as_of")
    geography = _object(row.get("geography"), {"id", "label", "boundary_ref"}, "geography")
    snapshot = {"schema_version": VERSION, "review_id": identifier, "domain": row["domain"],
                "mode": "ANALYST_SCREENING", "as_of": as_of,
                "geography": {key: _text(geography.get(key), "geography." + key) for key in ("id", "label", "boundary_ref")},
                "source": _source(row.get("source"), "source", as_of)}
    return row, snapshot


def _observation(value: Any, path: str, kind: str, as_of: str) -> dict:
    row = _object({"value": None, "evidence_status": "UNKNOWN"} if value is None else value,
                  {"value", "evidence_status", "source_ref", "source_date", "note"}, path)
    if "value" not in row:
        raise EconomicDevelopmentError(f"{path}.value is required")
    status = _status(row.get("evidence_status"), path + ".evidence_status")
    raw = row["value"]
    if (raw is None) != (status == "UNKNOWN"):
        raise EconomicDevelopmentError(f"{path}: null requires UNKNOWN; a value requires HYPOTHETICAL or SUPPLIED_UNVERIFIED")
    if raw is not None:
        if kind in ("decimal", "pue"):
            raw = _decimal(raw, path + ".value", Decimal(1) if kind == "pue" else Decimal(0))
        elif kind == "date":
            raw = _date(raw, path + ".value")
        elif kind == "stage" and (type(raw) is not str or raw not in UTILITY_STAGES):
            raise EconomicDevelopmentError(f"{path}.value requires a defined utility evidence stage")
        elif kind == "load_basis" and (type(raw) is not str or raw not in IT_LOAD_BASES):
            raise EconomicDevelopmentError(f"{path}.value requires ANNUAL_AVERAGE, NAMEPLATE, or PEAK")
        elif kind == "bool" and type(raw) is not bool:
            raise EconomicDevelopmentError(f"{path}.value requires true, false, or null")
    source = row.get("source_ref")
    if raw is not None or source is not None:
        source = _text(source, path + ".source_ref")
    source_date = _date(row.get("source_date"), path + ".source_date", nullable=raw is None)
    if source_date is not None and source_date > as_of:
        raise EconomicDevelopmentError(f"{path}.source_date cannot be later than as_of")
    note = row.get("note")
    if note is not None:
        note = _text(note, path + ".note")
    return {"value": raw, "evidence_status": status, "source_ref": source, "source_date": source_date, "note": note}


def _report(snapshot: dict, kind: str) -> dict:
    return {"schema_version": VERSION, "review_id": snapshot["review_id"], "domain": snapshot["domain"],
            "kind": kind, "mode": "ANALYST_SCREENING", "as_of": snapshot["as_of"],
            "accepted_evidence": False, "financial_authority_cents": 0, "external_authority": 0,
            "contractual_authority": 0, "ticket_closure_authority": 0, "stage_advanced": False,
            "input_snapshot": snapshot, "input_sha256": digest(snapshot),
            "ledger_boundaries": {"public_economic_outcomes": "SEPARATE_NOT_CAUSALLY_MODELED",
                                  "private_property_return": "SEPARATE_NOT_MODELED",
                                  "public_fiscal_net_benefit": "SEPARATE_NOT_MODELED"}}


def _finish(report: dict) -> dict:
    report["report_sha256"] = digest(report)
    return report


def _program_consistency(it: str | None, load_basis: str | None, pue: str | None,
                         peak: str | None, equivalent: Decimal | None) -> dict:
    """Check necessary bounds without sizing service or treating nameplate as demand."""
    missing = [key for key, value in (("program.it_load_mw", it), ("program.it_load_basis", load_basis),
                                     ("program.requested_peak_facility_mw", peak)) if value is None]
    if load_basis == "ANNUAL_AVERAGE" and pue is None:
        missing.append("program.pue")
    failures = []
    if load_basis in ("ANNUAL_AVERAGE", "PEAK") and it is not None and peak is not None:
        if Decimal(it) > Decimal(peak):
            failures.append("IT_DEMAND_EXCEEDS_FACILITY_PEAK")
        if load_basis == "ANNUAL_AVERAGE" and equivalent is not None and equivalent > Decimal(peak):
            failures.append("ANNUAL_AVERAGE_FACILITY_EXCEEDS_PEAK")
    unresolved = ["NAMEPLATE_IS_NOT_OPERATING_DEMAND"] if load_basis == "NAMEPLATE" else []
    return {
        "status": "FAIL" if failures else ("UNKNOWN" if missing or unresolved else "MEETS_SUPPLIED_CONSTRAINT"),
        "criterion": "Facility peak must be at least supplied peak IT demand or same-period annual-average facility demand; NAMEPLATE alone does not establish operating demand.",
        "missing_inputs": missing, "failure_reasons": failures, "unresolved_reasons": unresolved,
    }


def baseline(packet: Any) -> dict:
    """Calculate survey coverage, vacancy/ownership bounds and optional employment LQ."""
    row, snapshot = _base(packet, {"storefronts", "local_ownership", "employment"})
    if snapshot["source"]["evidence_status"] == "UNKNOWN":
        raise EconomicDevelopmentError("A baseline count sheet requires a HYPOTHETICAL or SUPPLIED_UNVERIFIED source; unknown storefronts belong in unknown_count")
    fields = ("eligible_count", "occupied_count", "vacant_count", "unknown_count")
    counts = _object(row.get("storefronts"), set(fields), "storefronts")
    counts = {key: _count(counts.get(key), "storefronts." + key) for key in fields}
    eligible, occupied, vacant, unknown = (counts[key] for key in fields)
    if occupied + vacant + unknown != eligible:
        raise EconomicDevelopmentError("Storefront occupied + vacant + unknown must equal eligible_count")
    snapshot["storefronts"] = counts
    snapshot["local_ownership"] = None
    snapshot["employment"] = None
    report = _report(snapshot, "ECONOMIC_BASELINE")
    report["status"] = "COMPUTED_FROM_SUPPLIED_COUNTS"
    report["storefront_metrics"] = {
        "known_count": occupied + vacant, "survey_coverage": _ratio(occupied + vacant, eligible),
        "known_vacancy_rate": _ratio(vacant, occupied + vacant),
        "vacancy_rate_lower_bound": _ratio(vacant, eligible),
        "vacancy_rate_upper_bound": _ratio(vacant + unknown, eligible),
    }
    report["local_ownership_metrics"] = None
    if row.get("local_ownership") is not None:
        fields = ("eligible_assets_count", "known_owner_count", "locally_owned_count")
        ownership = _object(row["local_ownership"], set(fields) | {"local_definition", "source"}, "local_ownership")
        normalized = {key: _count(ownership.get(key), "local_ownership." + key) for key in fields}
        total, known, local = (normalized[key] for key in fields)
        if not local <= known <= total:
            raise EconomicDevelopmentError("Local ownership requires locally_owned_count <= known_owner_count <= eligible_assets_count")
        normalized["local_definition"] = _text(ownership.get("local_definition"), "local_ownership.local_definition")
        normalized["source"] = _source(ownership.get("source"), "local_ownership.source", snapshot["as_of"])
        if normalized["source"]["evidence_status"] == "UNKNOWN":
            raise EconomicDevelopmentError("Supplied local-ownership counts require a hypothetical or unverified source")
        snapshot["local_ownership"] = normalized
        report["local_ownership_metrics"] = {
            "ownership_coverage": _ratio(known, total), "known_owner_local_share": _ratio(local, known),
            "local_share_lower_bound": _ratio(local, total), "local_share_upper_bound": _ratio(local + total - known, total),
        }
    report["employment_location_quotient"] = None
    if row.get("employment") is not None:
        employment = _object(row["employment"], {"local", "reference"}, "employment")
        fields = {"geography_id", "period", "industry_definition", "employment_basis", "industry_count", "total_count", "source"}
        normalized = {}
        for side in ("local", "reference"):
            path = "employment." + side
            data = _object(employment.get(side), fields, path)
            item = {key: _text(data.get(key), path + "." + key) for key in ("geography_id", "period", "industry_definition", "employment_basis")}
            item.update({key: _count(data.get(key), path + "." + key, nullable=True) for key in ("industry_count", "total_count")})
            if item["industry_count"] is not None and item["total_count"] is not None and item["industry_count"] > item["total_count"]:
                raise EconomicDevelopmentError(f"{path}.industry_count cannot exceed total_count")
            item["source"] = _source(data.get("source"), path + ".source", snapshot["as_of"])
            if item["source"]["evidence_status"] == "UNKNOWN" and (item["industry_count"] is not None or item["total_count"] is not None):
                raise EconomicDevelopmentError(f"{path} UNKNOWN source requires null employment counts")
            normalized[side] = item
        snapshot["employment"] = normalized
        left, right = normalized["local"], normalized["reference"]
        comparable = all(left[key] == right[key] for key in ("period", "industry_definition", "employment_basis"))
        comparable = comparable and left["geography_id"] == snapshot["geography"]["id"]
        result = {"status": "NOT_COMPARABLE" if not comparable else "UNKNOWN", "value": None,
                  "local_share": None, "reference_share": None, "definitions_match_as_supplied": comparable,
                  "compatibility_authenticated": False}
        if comparable and all(item[key] is not None for item in (left, right) for key in ("industry_count", "total_count")):
            result["local_share"] = _ratio(left["industry_count"], left["total_count"])
            result["reference_share"] = _ratio(right["industry_count"], right["total_count"])
            if left["total_count"] == 0 or right["total_count"] == 0 or right["industry_count"] == 0:
                result["status"] = "UNDEFINED_DENOMINATOR"
            else:
                quotient = _ratio(left["industry_count"] * right["total_count"], left["total_count"] * right["industry_count"])
                result.update(status="COMPUTED_FROM_SUPPLIED_COUNTS", value=quotient["value"], exact_ratio=quotient)
        report["employment_location_quotient"] = result
    report["warnings"] = ["Counts, geography boundaries, dates and source identities are supplied and have not been authenticated.",
                          "Unknown observations are retained; rates describe this eligible survey population only.",
                          "Employment compatibility is checked only against supplied labels; no causal jobs, footfall or property-profit effect is inferred."]
    # Optional blocks were normalized after base report construction.
    report["input_sha256"] = digest(snapshot)
    return _finish(report)


def data_center(packet: Any) -> dict:
    """Screen explicit assumptions; missing evidence cannot pass a critical gate."""
    row, snapshot = _base(packet, {"program", "utility", "context", "gates"})
    groups = {
        "program": {"it_load_mw": "decimal", "it_load_basis": "load_basis", "pue": "pue", "requested_peak_facility_mw": "decimal", "required_operation_date": "date"},
        "utility": {"deliverable_mw": "decimal", "energization_date": "date", "evidence_stage": "stage"},
        "context": {"land_acres": "decimal", "nearby_substation": "bool"},
        "gates": {key: "bool" for key in GATES},
    }
    for group, fields in groups.items():
        data = _object(row.get(group, {}), set(fields), group)
        snapshot[group] = {key: _observation(data.get(key), group + "." + key, kind, snapshot["as_of"]) for key, kind in fields.items()}
    it = snapshot["program"]["it_load_mw"]["value"]
    load_basis = snapshot["program"]["it_load_basis"]["value"]
    pue = snapshot["program"]["pue"]["value"]
    peak = snapshot["program"]["requested_peak_facility_mw"]["value"]
    capacity = snapshot["utility"]["deliverable_mw"]["value"]
    with localcontext() as context:
        context.prec = 64
        equivalent = None if it is None or pue is None or load_basis != "ANNUAL_AVERAGE" else Decimal(it) * Decimal(pue)
        margin = None if peak is None or capacity is None else Decimal(capacity) - Decimal(peak)
    required = snapshot["program"]["required_operation_date"]["value"]
    delivery = snapshot["utility"]["energization_date"]["value"]
    stage = snapshot["utility"]["evidence_stage"]["value"]
    capacity_status = "UNKNOWN" if peak is None or capacity is None else ("MEETS_SUPPLIED_CONSTRAINT" if Decimal(capacity) >= Decimal(peak) else "FAIL")
    date_status = "UNKNOWN" if required is None or delivery is None else ("MEETS_SUPPLIED_CONSTRAINT" if delivery <= required else "FAIL")
    gates = {
        "utility_capacity": {"status": capacity_status, "criterion": "Supplied deliverable MW is at least the separately supplied requested peak facility MW.",
                             "missing_inputs": [key for key, val in (("program.requested_peak_facility_mw", peak), ("utility.deliverable_mw", capacity)) if val is None]},
        "utility_delivery": {"status": date_status, "criterion": "Supplied energization date is on or before the required operation date.",
                             "missing_inputs": [key for key, val in (("program.required_operation_date", required), ("utility.energization_date", delivery)) if val is None]},
        "utility_commitment_stage": {"status": "MEETS_SUPPLIED_CONSTRAINT" if stage in ("SERVICE_AGREEMENT", "ENERGIZED") else "UNKNOWN",
                                     "criterion": "A service agreement or energized-service stage is supplied; proximity, preliminary assessment and engineering study alone are not commitments.",
                                     "missing_inputs": [] if stage in ("SERVICE_AGREEMENT", "ENERGIZED") else ["utility.service_agreement_or_energized_stage"],
                                     "supplied_stage": stage},
        "program_consistency": _program_consistency(it, load_basis, pue, peak, equivalent),
        "utility_stage_consistency": {
            "status": "UNKNOWN" if stage is None or delivery is None else
                      ("FAIL" if stage == "ENERGIZED" and delivery > snapshot["as_of"] else "MEETS_SUPPLIED_CONSTRAINT"),
            "criterion": "ENERGIZED asserts current service as of the packet date and requires energization on or before as_of; future dates remain planned service.",
            "missing_inputs": [key for key, value in (("utility.evidence_stage", stage), ("utility.energization_date", delivery)) if value is None],
            "failure_reasons": ["ENERGIZED_DATE_AFTER_AS_OF"] if stage == "ENERGIZED" and delivery is not None and delivery > snapshot["as_of"] else [],
        },
    }
    for key, criterion in GATES.items():
        value = snapshot["gates"][key]["value"]
        gates[key] = {"status": "UNKNOWN" if value is None else ("MEETS_SUPPLIED_CONSTRAINT" if value else "FAIL"),
                      "criterion": criterion, "missing_inputs": ["gates." + key] if value is None else []}
    failed = [key for key, result in gates.items() if result["status"] == "FAIL"]
    missing = [key for key, result in gates.items() if result["status"] == "UNKNOWN"]
    report = _report(snapshot, "DATA_CENTER_SCREENING")
    report.update({
        "status": "FAIL" if failed else ("UNKNOWN" if missing else "MEETS_SUPPLIED_CONSTRAINT"),
        "gate_results": gates, "failed_gates": failed, "unknown_gates": missing,
        "planning_load": {"it_load_mw": it, "it_load_basis": load_basis, "annual_pue_assumption": pue,
                          "approximate_energy_equivalent_facility_mw": None if equivalent is None else _decimal_text(equivalent),
                          "energy_equivalent_status": "COMPUTED_FROM_SUPPLIED_ANNUAL_AVERAGE" if equivalent is not None else "REQUIRES_ANNUAL_AVERAGE_IT_AND_PUE",
                          "requested_peak_facility_mw": peak,
                          "supplied_deliverable_mw": capacity,
                          "capacity_margin_mw": None if margin is None else _decimal_text(margin),
                          "energy_equivalent_formula": "Annual-average IT MW * assumed annual PUE over the same period; approximate energy-equivalent power only",
                          "capacity_gate_formula": "supplied deliverable MW >= separately supplied requested peak facility MW",
                          "service_sizing_complete": False},
        "acquisition_readiness": "NOT_DETERMINED", "utility_capacity_promised": False,
        "next_action": {"owner": "L4 / SW-01 with L3 / SW-05; independent review by SW-13",
                        "action": "Resolve supplied constraint failures and retain all missing-evidence items." if failed else
                                  ("Obtain dated supporting evidence for the unknown gates before a readiness decision." if missing else
                                   "Submit supporting source records for independent review; this result meets supplied assumptions only.")},
        "warnings": ["All gate values and source labels are supplied; even a complete hypothetical case establishes no accepted evidence or site readiness.",
                     "Nearby substations and acreage do not establish utility capacity, service terms, reliability or delivery timing.",
                     "PUE is an energy ratio. Only explicitly annual-average IT MW over the same period may be multiplied by annual PUE for approximate energy-equivalent power. Nameplate/peak IT MW is not an annual average; the capacity gate uses separate requested peak facility MW.",
                     "Separate program consistency checks reject average facility demand or peak IT demand above the supplied facility peak; they do not calculate the required peak or certify the demand model.",
                     "Reserve, redundancy, headroom, tariff, studies and reliability remain separate evidence requirements. A preliminary assessment is not a binding utility commitment.",
                     "Required operation and energization dates are supplied scenarios; source dates are distinct.",
                     "No jobs, tax receipts, property return or public fiscal benefit is inferred from IT load or a passing screen."],
    })
    return _finish(report)


def contract() -> dict:
    return {"schema_version": VERSION, "mode": "ANALYST_SCREENING", "allowed_domains": list(DOMAINS),
            "evidence_statuses": list(EVIDENCE_STATES), "gate_statuses": ["MEETS_SUPPLIED_CONSTRAINT", "FAIL", "UNKNOWN"],
            "required_data_center_gates": {"utility_capacity": "Derived numeric constraint", "utility_delivery": "Derived date constraint",
                                          "utility_commitment_stage": "Service agreement or energized stage supplied",
                                          "program_consistency": "Necessary operating-demand versus facility-peak bounds",
                                          "utility_stage_consistency": "ENERGIZED must be on or before as_of", **GATES},
            "utility_evidence_stages": list(UTILITY_STAGES),
            "it_load_bases": list(IT_LOAD_BASES),
            "decimal_format": "Nonnegative decimal string; 12 integer digits and up to 6 fractional digits; PUE >= 1",
            "accepted_evidence": False, "financial_authority_cents": 0, "external_authority": 0,
            "contractual_authority": 0, "ticket_closure_authority": 0}
