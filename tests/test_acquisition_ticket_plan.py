import copy
import csv
import hashlib
import json
from pathlib import Path
import pytest
from tools.build_acquisition_ticket_plan import build, validate_graph, validate_integration_plan


ROOT = Path(__file__).resolve().parents[1]


def test_dependency_validation_rejects_unknown_duplicate_and_cyclic_graphs():
    rows = [{"id": "A", "status": "open", "dependencies": []},
            {"id": "B", "status": "open", "dependencies": ["A"]}]
    assert validate_graph(rows) == ["A", "B"]
    with pytest.raises(ValueError):
        validate_graph(rows + [rows[0]])
    wrong = copy.deepcopy(rows)
    wrong[1]["dependencies"] = ["UNKNOWN"]
    with pytest.raises(ValueError):
        validate_graph(wrong)
    wrong = copy.deepcopy(rows)
    wrong[0]["dependencies"] = ["B"]
    with pytest.raises(ValueError):
        validate_graph(wrong)


def test_projection_preserves_status_and_does_not_close_or_dispatch(tmp_path):
    canonical = ROOT / "docs/session-tickets.json"
    before = canonical.read_bytes()
    rows = json.loads(before)
    report = build(tmp_path)
    assert canonical.read_bytes() == before
    assert [(r["id"], r["status"]) for r in report["records"]] == [(r["id"], r["status"]) for r in rows]
    assert report["ticket_count"] == len(rows) and report["curriculum_units"] == 95
    assert report["new_ticket_range"] == f"BR-T046–{rows[-1]['id'].removeprefix('BR-')}"
    assert report["dag_valid"]
    assert report["current_action"]["ticket_id"] == "BR-T076"
    assert report["capacity"]["continuously_running_workers"] == 0
    assert report["tickets_closed_by_this_application"] == 0
    assert report["external_actions_performed"] == 0
    assert all(not r["external_authority"] and not r["financial_authority"] for r in report["records"])
    old = next(r for r in report["records"] if r["id"] == "BR-T044")
    assert old["evidence_class"] == "HISTORICAL_MANIFEST_CLAIM"


def test_economic_development_reuses_existing_ticket_without_expansion_gate():
    rows = json.loads((ROOT / "docs/session-tickets.json").read_text(encoding="utf-8"))
    by_id = {r["id"]: r for r in rows}
    assert len(rows) == len(by_id)
    assert {f"BR-T{n:03d}" for n in range(96, 109)} <= by_id.keys()
    validate_graph(rows)
    dc = by_id["BR-T096"]
    assert dc["status"] == "partial" and dc["stage"] == "PARALLEL"
    assert not {"BR-T090", "BR-T070"}.intersection(dc["dependencies"])
    assert "br-select-data-center-sites" in dc["personal_skills"]
    # The development pilot is gated by actual specialist work, while screening
    # does not wait for all 288 recovered projects or entity formation.
    assert {"BR-T103", "BR-T104", "BR-T105", "BR-T101", "BR-T102"} <= set(by_id["BR-T106"]["dependencies"])
    # The buy-box work remains active; bounded preparation can move it to in_progress.
    assert by_id["BR-T076"]["status"] in {"open", "in_progress"}
    assert by_id["BR-T076"]["priority"] == "P0"
    for ticket in (by_id[f"BR-T{n:03d}"] for n in range(96, 109)):
        if ticket["status"] == "closed":
            assert ticket["evidence"].strip()
            assert all(by_id[dep]["status"] == "closed" for dep in ticket["dependencies"])


def test_economic_suite_retains_rex_proposal_and_eight_module_coverage():
    index = json.loads((ROOT / "docs/acquisition/idea-system-index.json").read_text(encoding="utf-8"))
    suite_ideas = [r for r in index["ideas"] if r.get("suite_module_id")]
    assert {r["suite_module_id"] for r in suite_ideas} == {f"ED-{n:02d}" for n in range(1, 9)}
    source_ids = {s["id"] for s in index["sources"]}
    assert {"SRC-CURRENT-ECON", "SRC-REX-DOCUMENT", "SRC-CURRENT-IVES"} <= source_ids
    rex = json.loads((ROOT / "docs/acquisition/rex-project-crosswalk.json").read_text(encoding="utf-8"))
    domain = next(d for d in rex["domains"] if d["id"] == "REX-31")
    assert domain["activation"] == "ACTIVE"
    assert len(domain["projects"]) == 6
    assert all(p["status"] == "SPECIFIED" and not p["active_academy_unit_created"]
               and not p["independent_evidence_accepted"] for p in domain["projects"])
    assert rex["project_count"] == 288 and rex["claimed_project_completions"] == 0
    assert rex["active_acquisition_curriculum_units"] == 95


@pytest.fixture
def integration_plan():
    def item(ticket, queue, dependencies):
        return {
            "id": ticket + ":S1", "ticket_id": ticket, "milestone_id": "M1",
            "title": "Prepare a bounded contract", "queue": queue,
            "depends_on": dependencies, "deliverable": "A versioned context contract",
            "acceptance": ["Unknown evidence remains unknown", "Input revisions are preserved"],
            "preparation_gate": "Inspect the existing adapter",
            "activation_gate": "Review the required evidence before integration",
            "write_scopes": ["backend/core", "tests"],
            "skills": ["br-build-evidence-engine"], "estimate_hours": None,
            "estimate_basis": "Size after contract review"
        }

    return {
        "schema_version": 1, "as_of": "2026-11-23", "mode": "ADVISORY_PLAN_ONLY",
        "source_path": "README.md",
        "source_sha256": hashlib.sha256((ROOT / "README.md").read_bytes()).hexdigest(),
        "current_instruction": "Optimize existing work without changing status",
        "optimization_rationale": ["Reuse the shared evidence authority"],
        "business_focus": ["BR-T076", "BR-T061", "BR-T063"],
        "technical_focus": ["BR-T056", "BR-T057", "BR-T011"],
        "capacity": {"workers": 3, "integrator": 1, "dispatch_performed": False},
        "milestones": [{"id": "M1", "title": "Shared context", "sequence": 1,
                        "ticket_ids": ["BR-T056", "BR-T057", "BR-T011", "BR-T109", "BR-T019"],
                        "exit_criteria": ["Two engines reference the same input versions"]}],
        "slices": [item("BR-T056", "NEXT", []),
                   item("BR-T057", "AFTER_INPUTS", ["BR-T056:S1"]),
                   item("BR-T011", "PARALLEL", []),
                   item("BR-T109", "NEXT", [])],
        "review_ticket_ids": ["BR-T109"],
        "deferred": [{"ticket_ids": ["BR-T060", "BR-T014"], "capability": "GPU execution and storage migration",
                      "activation_gate": "Verified hardware and measured workload"}],
        "runtime_sync": {"status": "NOT_PERFORMED", "note": "Existing runtime states are preserved."},
        "operating_next_action": {"ticket_id": "BR-T076", "owner": "SW-02", "minutes": 35,
                                  "action": "Complete the buy box with explicit unknowns"}
    }


def test_integration_projection_preserves_current_statuses_and_excludes_review_from_build(
    integration_plan, tmp_path, monkeypatch
):
    rows = json.loads((ROOT / "docs/session-tickets.json").read_bytes())
    fixture_statuses = {
        "BR-T056": "open",
        "BR-T057": "open",
        "BR-T011": "open",
        "BR-T109": "review_required",
    }
    for row in rows:
        if row["id"] in fixture_statuses:
            row["status"] = fixture_statuses[row["id"]]
    source = tmp_path / "session-tickets.json"
    source.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr("tools.build_acquisition_ticket_plan.MANIFEST", source)
    before = source.read_bytes()
    plan_path = tmp_path / "integration.json"
    plan_path.write_text(json.dumps(integration_plan))
    plan_before = plan_path.read_bytes()
    out = tmp_path / "projection"
    report = build(out, integration_path=plan_path)
    rows = json.loads(before)
    assert len(rows) == report["ticket_count"]
    assert [(r["id"], r["status"]) for r in report["records"]] == [(r["id"], r["status"]) for r in rows]
    assert source.read_bytes() == before and plan_path.read_bytes() == plan_before
    derived = report["frontier_integration"]
    assert derived["advisory_build_ticket_ids"] == ["BR-T056", "BR-T057", "BR-T011"]
    assert derived["review_queue_ticket_ids"] == ["BR-T109"]
    assert derived["preparation_candidate_slice_ids"] == ["BR-T056:S1", "BR-T011:S1"]
    assert "BR-T057:S1" in derived["waiting_slice_ids"]
    assert not derived["worker_process_running"] and not derived["closure_authority"]
    assert report["current_focus"] == ["BR-T076", "BR-T061", "BR-T063"]
    assert report["current_action"]["ticket_id"] == "BR-T076"
    assert report["tickets_added_by_this_revision"] == 0
    assert report["statuses_changed_by_this_projection"] == 0
    assert report["role_queues_interpretation"].startswith("Full owner register of nonclosed tickets;")
    text = (out / "ticket-plan.md").read_text(encoding="utf-8")
    assert "Optimized AI data architecture integration" in text
    assert "### BR-T011" in text
    assert "### BR-T019" in text  # Milestone-only early reference.
    assert "### BR-T014" in text  # Deferred-only early reference.
    assert "**Proposed write scopes:**" in text
    assert "BR-T056:S1" in text
    with (out / "ticket-plan.csv").open() as stream:
        csv_rows = {r["id"]: r for r in csv.DictReader(stream)}
    assert csv_rows["BR-T056"]["planning_slice_ids"] == "BR-T056:S1"
    assert csv_rows["BR-T109"]["planning_queue"] == "REVIEW"
    assert csv_rows["BR-T056"]["evidence_class"] == "RETAINED_REGISTER_EVIDENCE"
    assert csv_rows["BR-T010"]["evidence_class"] == "HISTORICAL_MANIFEST_CLAIM"


@pytest.mark.parametrize("case", ["ticket", "prefix", "dependency", "cycle", "milestone", "hash", "absolute_path",
                                  "traversal_path", "blank_deliverable", "dispatch", "closure", "duplicate_slice"])
def test_invalid_integration_fails_before_writing_outputs(integration_plan, tmp_path, case):
    plan = copy.deepcopy(integration_plan)
    first = plan["slices"][0]
    if case == "ticket":
        plan["technical_focus"] = ["BR-T999"]
    elif case == "prefix":
        first["id"] = "BR-T057:S2"
    elif case == "dependency":
        first["depends_on"] = ["BR-T999:S1"]
    elif case == "cycle":
        first["depends_on"] = ["BR-T057:S1"]
    elif case == "milestone":
        first["milestone_id"] = "UNKNOWN"
    elif case == "hash":
        plan["source_sha256"] = "0" * 64
    elif case == "absolute_path":
        first["write_scopes"] = ["/tmp/elsewhere"]
    elif case == "traversal_path":
        first["write_scopes"] = ["backend/../../elsewhere"]
    elif case == "blank_deliverable":
        first["deliverable"] = " "
    elif case == "dispatch":
        plan["capacity"]["dispatch_performed"] = True
    elif case == "closure":
        first["status"] = "closed"
    elif case == "duplicate_slice":
        plan["slices"].append(copy.deepcopy(first))
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(plan))
    out = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        build(out, integration_path=path)
    assert not out.exists()


def test_missing_optional_integration_keeps_legacy_build_and_authority(tmp_path):
    report = build(tmp_path / "legacy", integration_path=tmp_path / "absent.json")
    assert "frontier_integration" not in report
    assert report["dag_valid"] and report["current_action"]["ticket_id"] == "BR-T076"
    assert report["tickets_closed_by_this_application"] == 0
    assert report["external_actions_performed"] == 0


def test_integration_validation_is_non_mutating(integration_plan):
    rows = json.loads((ROOT / "docs/session-tickets.json").read_text(encoding="utf-8"))
    before = copy.deepcopy((integration_plan, rows))
    validate_integration_plan(integration_plan, rows)
    assert (integration_plan, rows) == before




def test_review_handoff_covers_current_register(tmp_path):
    result = build(tmp_path)
    records = {row["id"]: row for row in result["records"]}
    queue = result["manifest_review_handoff"]
    expected = [key for key in result["dependency_order"] if records[key]["status"] == "review_required"]
    expected.sort(key=lambda key: bool(records[key]["review_dependencies_unclosed"]))
    assert [row["ticket_id"] for row in queue] == expected
    assert result["review_ready_count"] + result["review_prerequisite_count"] == len(queue)
    by_ticket = {row["ticket_id"]: row for row in queue}
    for entry in queue:
        row = records[entry["ticket_id"]]
        assert entry["unclosed_prerequisites"] == [
            dep for dep in row["dependencies"] if records[dep]["status"] != "closed"
        ]
    assert all(row["evidence"] == records[row["ticket_id"]]["evidence"] for row in queue)
    markdown = (tmp_path / "ticket-plan.md").read_text(encoding="utf-8")
    assert all(f"| {entry['ticket_id']} | {entry['review_owner']} |" in markdown for entry in queue)
