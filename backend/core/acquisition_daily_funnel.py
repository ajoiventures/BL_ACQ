"""Persist a dated funnel derived from a completed acquisition run."""

import json

from . import unit_evidence
from .acquisition_runs import encode, get, sha, snapshot_available


def initialize(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS acquisition_daily_funnel (
            day TEXT PRIMARY KEY,
            run_id TEXT NOT NULL REFERENCES acq_runs(id),
            report TEXT NOT NULL
        )
    """)
    for operation in ("UPDATE", "DELETE"):
        db.execute(f"""CREATE TRIGGER IF NOT EXISTS acquisition_daily_funnel_no_{operation.lower()}
            BEFORE {operation} ON acquisition_daily_funnel BEGIN
            SELECT RAISE(ABORT, 'Immutable daily funnel'); END""")


def verified_report(row, day):
    report = json.loads(row[0])
    if not isinstance(report, dict):
        raise ValueError("Daily funnel receipt must be an object")
    body = {key: value for key, value in report.items() if key != "report_sha256"}
    if report.get("day") != day or report.get("run_id") != row[1] or report.get("report_sha256") != sha(body):
        raise ValueError("Daily funnel receipt integrity check failed")
    return report


def read(db, day):
    row = db.execute("SELECT report,run_id FROM acquisition_daily_funnel WHERE day=?", (day,)).fetchone()
    if row is None:
        return None
    report = verified_report(row, day)
    snapshot_available(db, report["snapshot_id"])
    if report["prior_day"] is not None:
        prior = db.execute(
            "SELECT report,run_id FROM acquisition_daily_funnel WHERE day=?",
            (report["prior_day"],),
        ).fetchone()
        if prior is None:
            raise LookupError("Prior funnel snapshot is unavailable")
        snapshot_available(db, verified_report(prior, report["prior_day"])["snapshot_id"])
    return report


def later_stages(reported, lawful_counts, underwritten_cash, decision, selected_parcel=None):
    """Rank already-verified inputs. The caller supplies evidence decisions, never raw claims."""
    lawful = [key for key in reported if lawful_counts.get(key) in (2, 3, 4)][:10]
    underwritten = sorted(
        (key for key in lawful if type(underwritten_cash.get(key)) is int and underwritten_cash[key] > 0),
        key=lambda key: (-underwritten_cash[key], key),
    )[:3]
    if decision == "SELECT":
        if selected_parcel not in underwritten:
            raise ValueError("Select a candidate that cleared both verification and underwriting")
    elif decision not in {"DEFER", "NO_SELECTION"} or selected_parcel is not None:
        raise ValueError("A selection is only permitted with a SELECT decision")

    return {
        "lawful_units_10": lawful,
        "underwritten_3": underwritten,
        "founder_selection_1": [selected_parcel] if selected_parcel is not None else [],
    }


def publish(db, day, run_id, decision):
    existing = read(db, day)
    if existing:
        if existing["run_id"] != run_id or existing["founder_decision"] != decision:
            raise ValueError("A different funnel is already recorded for this day")
        return existing

    run = get(db, run_id)
    if run["state"] != "COMPLETED":
        raise ValueError("A completed acquisition run is required")
    if db.execute("SELECT 1 FROM acquisition_daily_funnel WHERE day > ? LIMIT 1", (day,)).fetchone():
        raise ValueError("Daily funnels must be recorded in chronological order")
    previous = db.execute(
        "SELECT report,run_id,day FROM acquisition_daily_funnel WHERE day < ? ORDER BY day DESC LIMIT 1", (day,)
    ).fetchone()
    prior = verified_report(previous, previous[2]) if previous else None
    if prior is not None:
        snapshot_available(db, prior["snapshot_id"])
    rows = db.execute(
        "SELECT result FROM acq_results WHERE run_id=? ORDER BY parcel_key LIMIT 100", (run_id,)
    )

    candidates = []
    reported = []
    reviewed_research = []
    for row in rows:
        result = json.loads(row[0])
        numeric = result.get("numeric_screen", {})
        count_in_scope = any(numeric.get(f"reported_{unit}") for unit in (2, 3, 4))
        if count_in_scope and len(reported) < 25:
            reported.append(result["parcel_key"])
            reason = "No accepted lawful unit count or underwriting in the research run"
            if day <= unit_evidence.today():
                evidence = unit_evidence.state(db, run["snapshot_id"], result["parcel_key"], as_of=day)
                status = evidence["status"]
                if status == "CONFLICT":
                    reason = "Conflicting unit evidence requires resolution"
                elif status == "REVIEWED_RESEARCH_COUNT":
                    reviewed_research.append({
                        "parcel_key": result["parcel_key"],
                        "reviewed_units": evidence["reviewed_units"],
                        "evidence_sha256": evidence["evidence_sha256"],
                        "review_ids": evidence["active_review_ids"],
                    })
                    reason = "Reviewed research count; lawful verification still required"
        elif count_in_scope:
            reason = "Reported-unit review capacity reached"
        else:
            reason = "No in-scope reported unit count"
        candidates.append({"parcel_key": result["parcel_key"], "reason": reason})

    prior_rows = {row["parcel_key"]: row["reason"] for row in prior["candidates"]} if prior else {}
    current_rows = {row["parcel_key"]: row["reason"] for row in candidates}
    report = {
        "day": day,
        "run_id": run_id,
        "snapshot_id": run["snapshot_id"],
        "run_total": run["total"],
        "candidates": candidates,
        "reviewed_unit_research": reviewed_research,
        "stages": {"intake_100": list(current_rows), "reported_units_25": reported,
                   **later_stages(reported, {}, {}, decision)},
        "stage_reasons": {
            "lawful_units_10": "Only research results are available; no accepted lawful units",
            "underwritten_3": "No candidate cleared lawful-unit verification",
            "founder_selection_1": "No candidate cleared both verification and underwriting",
        },
        "founder_decision": decision,
        "selected_parcel": None,
        "prior_day": prior["day"] if prior else None,
        "changes": {
            "added": sorted(current_rows.keys() - prior_rows.keys()),
            "removed": sorted(prior_rows.keys() - current_rows.keys()),
            "reason_changed": sorted(key for key in current_rows.keys() & prior_rows.keys()
                                     if current_rows[key] != prior_rows[key]),
        },
    }
    report["report_sha256"] = sha(report)
    db.execute("INSERT INTO acquisition_daily_funnel VALUES(?,?,?)", (day, run_id, encode(report)))
    return report
