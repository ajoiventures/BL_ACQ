from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from backend.core.economic_development import data_center

brief = Path("docs/economic-development/data-center-demand-brief.md")
fixture = Path("docs/economic-development/fixtures/data-center-hypothetical.json")
seed = json.loads(fixture.read_bytes())
phases = [("initial", "5", "8", "2029-01-01"), ("expansion", "10", "15", "2030-01-01")]
scenarios = [
    ("missing_site_evidence", {}, ("UNKNOWN","UNKNOWN","UNKNOWN")),
    ("preliminary_estimate", {"deliverable_mw":"18","energization_date":"2028-12-01","evidence_stage":"PRELIMINARY_ASSESSMENT"}, ("MEETS_SUPPLIED_CONSTRAINT","MEETS_SUPPLIED_CONSTRAINT","UNKNOWN")),
    ("hypothetical_phased_service", {"deliverable_mw":"10","energization_date":"2029-06-01","evidence_stage":"SERVICE_AGREEMENT"}, None),
]
receipt = {
    "ticket": "BR-T104",
    "scope": "Hypothetical comparison and missing-evidence replay; no selected site or utility approval.",
    "source_hashes": {p.as_posix(): sha256(p.read_bytes()).hexdigest() for p in (brief, fixture)},
    "utility_evidence_requested": {
        "capacity_and_date": "Executed service agreement and utility-issued load and facilities study showing firm MW by phase, energization dependencies and any conditional windows.",
        "upgrades_and_equipment": "Utility schedule showing supply upgrades, procurement milestones, commissioning, ownership and cost allocation.",
        "price_and_commitments": "Tariff effective for the site and service date, approved rate schedule and riders, deposits, demand charges and minimum financial or usage commitments.",
        "curtailment_and_reliability": "Executed firm/interruptible terms, curtailment rights and triggers, reserved headroom and written reliability conditions.",
        "revision_control": "Utility issuer, service address, revision, issue and effective dates, signed status, and superseding versions. Retain proposed filings separately.",
    },
    "cases": [],
}
for phase, it, peak, date in phases:
    for name, values, expected in scenarios:
        packet = deepcopy(seed)
        packet["review_id"] = f"{phase}-{name}"
        packet["gates"] = {}
        packet["context"] = {}
        for key, value in (("it_load_mw", it), ("requested_peak_facility_mw", peak), ("required_operation_date", date)):
            packet["program"][key]["value"] = value
            packet["program"][key]["source_ref"] = brief.as_posix() + "#data-center-workload-and-delivery-brief"
        packet["utility"] = {key: {**seed["utility"][key], "value": value,
                                  "source_ref": "urn:black-river:br-t104-hypothetical-utility-replay"}
                             for key, value in values.items()}
        result = data_center(packet)
        gates = {key: result["gate_results"][key] for key in ("utility_capacity","utility_delivery","utility_commitment_stage")}
        if expected is None:
            expected = ("MEETS_SUPPLIED_CONSTRAINT","FAIL","MEETS_SUPPLIED_CONSTRAINT") if phase == "initial" else ("FAIL","MEETS_SUPPLIED_CONSTRAINT","MEETS_SUPPLIED_CONSTRAINT")
        assert tuple(gate["status"] for gate in gates.values()) == expected
        assert not result["utility_capacity_promised"] and result["acquisition_readiness"] == "NOT_DETERMINED"
        receipt["cases"].append(dict(phase=phase, scenario=name, input_sha256=result["input_sha256"],
                                     requested_peak_mw=peak, needed_by=date, supplied_terms=values, gates=gates))
out = Path("docs/economic-development/data-center-utility-replay.json")
out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(len(receipt["cases"]), "phase/utility cases")
