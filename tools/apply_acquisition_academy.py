"""Apply the Acquisition Academy to saved data and explicit synthetic cases.

Run from the workspace root: python -m tools.apply_acquisition_academy
This is an offline CPU application, not a live agent/dispatch/GPU service.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from backend.core.acquisition_patterns import DecisionReceipts, digest, screen_rule, validate_rule
from site_academy import catalog
from site_academy.runner import load_skills

ROOT = Path(__file__).resolve().parents[1]


def table_audit(path: Path, key: str, namespace: str) -> dict:
    raw = path.read_bytes()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    counts = Counter((row.get(key) or "").strip() for row in rows)
    nonempty = {k: v for k, v in counts.items() if k}
    return {"file": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(raw).hexdigest(),
            "raw_rows": len(rows), "unique_nonempty_parcel_ids": len(nonempty),
            "duplicate_rows_by_parcel_key": sum(v - 1 for v in nonempty.values()),
            "missing_parcel_ids": counts.get("", 0), "jurisdiction_namespace": namespace,
            "declared_review_status_counts": dict(Counter(row.get("validation_status", "NOT_SUPPLIED") for row in rows)),
            "current_district_completeness_verified": False,
            "title_verified": False, "source_effective_date": None,
            "interpretation": "Saved source observations; counts do not establish current coverage, title, occupancy or acquisition readiness."}


def fixture_fact(value, unit, *, status="ACCEPTED"):
    return {"value": value, "unit": unit, "review_status": status,
            "evidence_id": "synthetic://academy/fixture-only", "valid_from": "2026-11-23",
            "valid_to": None, "simulation": True}


def apply(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    units = load_skills("acquisition")
    identifiers = [row["id"] for row in catalog()]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Catalog ID collision")
    seeds = json.loads((ROOT / "site_academy/acquisition-pattern-seeds.json").read_text())
    for rule in seeds:
        validate_rule(rule)
        if rule["lifecycle"] != "DRAFT":
            raise ValueError("This application only accepts draft curriculum seeds")
    cases = [
        {"case_id": "SYNTHETIC-MS-01", "track": "MS", "jurisdiction": "US-FL",
         "facts": {"lot_coverage_ratio": fixture_fact("0.20", "ratio"),
                   "entity_status": fixture_fact("INACTIVE", "category"),
                   "owner_name_match_count": fixture_fact(2, "count"),
                   "zoning_use_confirmed": fixture_fact(None, "boolean")}},
        {"case_id": "SYNTHETIC-BIO500-01", "track": "BIO500", "jurisdiction": "US-FL",
         "facts": {"contiguous_upland_acres": fixture_fact("34", "m2"),
                   "wetlands_overlay_present": fixture_fact(True, "boolean"),
                   "annual_cash_after_reserves_usd": fixture_fact("-123504.27", "USD")}},
        {"case_id": "SYNTHETIC-OTHER-JURISDICTION", "track": "MS", "jurisdiction": "US-GA",
         "facts": {"lot_coverage_ratio": fixture_fact("0.20", "ratio")}},
    ]
    store = DecisionReceipts(str(output / "pattern-receipts.sqlite3"))
    evaluations = []
    try:
        for rule in seeds:
            store.register_version(rule)
        for case in cases:
            for rule in seeds:
                result = screen_rule(rule, case["facts"], jurisdiction=case["jurisdiction"],
                                     track=case["track"], as_of="2026-11-23", similarity=0.97)
                payload = {"simulation": True, "case_id": case["case_id"], "result": result}
                operation_id = "academy-v1:" + digest({"case_id": case["case_id"], "result": result})
                receipt = store.append(operation_id, payload)
                replay = store.append(operation_id, payload)
                if receipt["sequence"] != replay["sequence"]:
                    raise AssertionError("Duplicate replay created a new receipt")
                evaluations.append({"case_id": case["case_id"], "pattern_id": rule["pattern_id"],
                                    "status": result["status"], "reasons": result["reasons"],
                                    "receipt_hash": receipt["receipt_hash"]})
        integrity = store.verify()
        stored_receipts = store.db.execute("SELECT COUNT(*) FROM acquisition_pattern_receipts").fetchone()[0]
    finally:
        store.close()
    report = {
        "application_version": 1, "as_of": "2026-11-23", "mode": "OFFLINE_CPU_REVIEW_APPLICATION",
        "curriculum_units": len(units), "personal_skill_names": sorted({u["personal_skill"] for u in units}),
        "catalog_total_units": len(identifiers), "existing_ticket_authority_preserved": True,
        "curriculum_maturity": "SPECIFIED; installed skills do not establish practitioner mastery",
        "dataset_audits": [table_audit(ROOT / "docs/orange-parcels.csv", "PARCEL", "US-FL-12095"),
                           table_audit(ROOT / "docs/acquisition/college-park-parcel-spine.csv", "parcel_id", "US-FL-12095")],
        "draft_pattern_count": len(seeds), "activated_rules": 0,
        "synthetic_case_count": len(cases), "evaluations": len(evaluations),
        "status_counts": dict(Counter(e["status"] for e in evaluations)),
        "stored_receipts": stored_receipts, "receipt_chain_verified": integrity,
        "immediate_replay_deduplicated": True,
        "executed_backends": ["CPU_REFERENCE", "SQLite"],
        "unexecuted_backends": ["CUDA/cuDF/cuGraph", "cuOpt", "LangGraph", "PostgreSQL/pgvector", "Lob"],
        "external_messages_sent": 0, "offers_executed": 0, "title_determinations": 0,
        "independent_review": "See separate review artifact; no production SW-13 closure claimed",
        "case_results": evaluations,
        "next_evidence": ["Current official College Park district/corridor boundary",
                          "Parcel-to-business join reconciliation and dated source refresh",
                          "Applicable title, zoning, infrastructure and demand evidence",
                          "Measured GPU parity and end-to-end benefit on actual hardware"],
    }
    (output / "application-report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/acquisition/run")
    args = parser.parse_args()
    report = apply(args.output)
    print(json.dumps({k: report[k] for k in ("mode", "curriculum_units", "draft_pattern_count", "evaluations", "status_counts", "stored_receipts", "receipt_chain_verified", "external_messages_sent")}, indent=2))


if __name__ == "__main__":
    main()
