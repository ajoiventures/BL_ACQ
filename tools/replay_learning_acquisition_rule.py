"""Replay a proposed access-and-utility predicate on frozen training cases."""
import json

from backend.core import acquisition_patterns as engine


def fact(value, evidence_id, *, available_from="2026-03-01"):
    return {
        "value": value, "unit": "boolean", "review_status": "ACCEPTED",
        "evidence_id": evidence_id, "valid_from": "2026-03-01",
        "available_from": available_from,
    }


def compare():
    access = {"field": "legal_access_confirmed", "op": "eq", "value": True, "unit": "boolean"}
    utility = {"field": "utility_capacity_confirmed", "op": "eq", "value": True, "unit": "boolean"}
    candidate = {"all": [access, utility]}
    cases = {
        "documented_both": {
            "legal_access_confirmed": fact(True, "training:both-access"),
            "utility_capacity_confirmed": fact(True, "training:both-utility"),
        },
        "later_utility": {
            "legal_access_confirmed": fact(True, "training:later-access"),
            "utility_capacity_confirmed": fact(True, "training:later-utility", available_from="2026-04-01"),
        },
        "confirmed_no_access": {
            "legal_access_confirmed": fact(False, "training:no-access"),
        },
        "utility_denied": {
            "legal_access_confirmed": fact(True, "training:denied-access"),
            "utility_capacity_confirmed": fact(False, "training:denied-utility"),
        },
    }
    cutoffs = ("2026-03-15", "2026-04-15")
    expected = {
        "documented_both": [(True, True), (True, True)],
        "later_utility": [(True, None), (True, True)],
        "confirmed_no_access": [(False, False), (False, False)],
        "utility_denied": [(True, False), (True, False)],
    }
    outcomes = []
    for name, facts in cases.items():
        for cutoff, answers in zip(cutoffs, expected[name], strict=True):
            before = engine.evaluate_predicate(access, facts, cutoff)
            after = engine.evaluate_predicate(candidate, facts, cutoff)
            if (before.value, after.value) != answers:
                raise ValueError(f"Unexpected rule result for {name} at {cutoff}")
            outcomes.append({
                "case": name, "knowledge_cutoff": cutoff, "input_sha256": engine.digest(facts),
                "baseline": before.value, "candidate": after.value,
                "candidate_reasons": list(after.reasons),
            })
    return {
        "ticket": "BR-T071", "component_id": "acquisition:access-and-utility-screen",
        "engine_version": engine.VERSION, "scope": "SYNTHETIC_RESEARCH_REPLAY",
        "baseline": {"predicate": access, "sha256": engine.digest(access)},
        "candidate": {"predicate": candidate, "sha256": engine.digest(candidate)},
        "case_count": len(cases), "cutoff_count": len(cutoffs), "outcomes": outcomes,
        "expected_outcome": "Require evidence of capacity alongside access and preserve missingness.",
        "rollback": "Retain the baseline predicate until review is recorded.",
        "promotion_authorized": False,
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
