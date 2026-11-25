import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tools.reconcile_idea_coverage import audit, build


@pytest.fixture
def inputs(tmp_path):
    tickets = [{"id": f"T-{number}", "status": status, "dependencies": []}
               for number, status in enumerate(("open", "delivered_local", "review_required", "closed", "blocked", "partial", "in_progress"))]
    tickets[1]["dependencies"] = ["T-0"]
    tickets[2]["dependencies"] = ["T-1"]
    index = {
        "schema_version": 1,
        "as_of": "2026-11-23",
        "sources": [{"id": "S-1", "locator": "synthetic://one"}, {"id": "S-2"}, {"id": "S-unused"}],
        "ideas": [
            {"id": "I-mixed", "title": "Mixed state coverage", "source_ids": ["S-1"],
             "ticket_ids": [row["id"] for row in tickets], "personal_skills": ["domain-skill", "builder-skill"],
             "activation": "ACTIVE", "note": "Actual capital remains unknown.\nPreserve this note."},
            {"id": "I-claimed", "title": "Closed in register", "source_ids": ["S-2"],
             "ticket_ids": ["T-3"], "personal_skills": ["builder-skill"],
             "activation": "LATER", "note": "A manifest closed state is not independent acceptance."},
            {"id": "I-open", "title": "Open work", "source_ids": ["S-1"],
             "ticket_ids": ["T-0"], "personal_skills": ["domain-skill"],
             "activation": "NEXT", "note": ""},
        ],
        "limitation": "Only supplied sources were decomposed; older unindexed conversations are unknown.",
        "retained_unknowns": ["Source contents have not been independently verified."],
    }
    registry = {"personal_skills": ["domain-skill"], "existing_builder_skills": ["builder-skill"]}
    payloads = {"index_path": index, "tickets_path": tickets, "skills_path": registry}
    paths = {key: tmp_path / f"{key}.json" for key in payloads}
    for key, path in paths.items():
        path.write_text(json.dumps(payloads[key]), encoding="utf-8")
    return paths, payloads


def write_payload(paths, payloads, key):
    paths[key].write_text(json.dumps(payloads[key]), encoding="utf-8")


def test_traceability_and_delivery_claims_are_separate_and_unknowns_retained(inputs):
    paths, payloads = inputs
    report = audit(**paths)
    assert report["mode"] == "OFFLINE_IDEA_COVERAGE_AUDIT"
    assert report["all_covered"] and report["covered_idea_count"] == len(payloads["index_path"]["ideas"])
    assert report["uncovered_idea_count"] == 0
    assert report["active_idea_ids"] == ["I-mixed"]
    assert report["activation_queues"]["LATER"] == ["I-claimed"]
    assert report["sources_without_indexed_ideas"] == ["S-unused"]
    assert report["sources"] == payloads["index_path"]["sources"]
    assert report["linked_ticket_count"] == len(payloads["tickets_path"])
    assert report["canonical_ticket_status_counts"] == report["linked_ticket_status_counts"]
    mixed, claimed, open_idea = report["ideas"]
    assert mixed["coverage_complete"]
    assert mixed["ticket_status_subsets"]["open"] == ["T-0"]
    assert mixed["ticket_status_subsets"]["partial"] == ["T-5"]
    assert mixed["ticket_status_subsets"]["blocked"] == ["T-4"]
    assert mixed["ticket_status_subsets"]["in_progress"] == ["T-6"]
    assert mixed["delivery_claim"]["claimed_delivery_ticket_ids"] == ["T-1", "T-2", "T-3"]
    assert mixed["delivery_claim"]["not_claimed_delivery_ticket_ids"] == ["T-0", "T-4", "T-5", "T-6"]
    assert not mixed["delivery_claim"]["all_linked_tickets_claim_delivery"]
    assert claimed["delivery_claim"]["all_linked_tickets_claim_delivery"]
    assert claimed["delivery_claim"]["manifest_closed_ticket_ids"] == ["T-3"]
    assert not open_idea["delivery_claim"]["claimed_delivery_ticket_ids"]
    assert report["ideas_with_all_tickets_claiming_delivery"] == 1
    assert report["ideas_with_mixed_delivery_claims"] == 1
    assert report["ideas_without_ticket_delivery_claims"] == 1
    for idea in report["ideas"]:
        assert idea["delivery_claim"]["evidence_class"] == "MANIFEST_DELIVERY_CLAIM"
        assert not idea["delivery_claim"]["independent_acceptance_verified"]
    unknowns = report["retained_unknowns"]
    assert unknowns["limitation"] == payloads["index_path"]["limitation"]
    assert unknowns["declared"] == payloads["index_path"]["retained_unknowns"]
    assert unknowns["idea_notes"][0]["note"] == payloads["index_path"]["ideas"][0]["note"]
    assert report["known_skill_count"] == report["linked_skill_count"] == 2
    assert report["dag_valid"]


@pytest.mark.parametrize("field", ["source_ids", "ticket_ids", "personal_skills"])
@pytest.mark.parametrize("value", [[], "not-a-list", [None], [""], ["UNKNOWN"], ["UNKNOWN", "UNKNOWN"]])
def test_missing_malformed_or_unknown_idea_links_fail_without_output(inputs, tmp_path, field, value):
    paths, payloads = inputs
    payloads["index_path"]["ideas"][0][field] = value
    write_payload(paths, payloads, "index_path")
    output = tmp_path / "must-not-be-written"
    with pytest.raises(ValueError):
        build(output, **paths)
    assert not output.exists()


@pytest.mark.parametrize("field", ["source_ids", "ticket_ids", "personal_skills"])
def test_duplicate_known_links_are_rejected(inputs, field):
    paths, payloads = inputs
    links = payloads["index_path"]["ideas"][0][field]
    links.append(links[0])
    write_payload(paths, payloads, "index_path")
    with pytest.raises(ValueError, match="unique"):
        audit(**paths)


@pytest.mark.parametrize("key,collection", [("index_path", "sources"), ("index_path", "ideas"), ("tickets_path", None)])
def test_duplicate_ids_cannot_replace_records(inputs, key, collection):
    paths, payloads = inputs
    rows = payloads[key][collection] if collection else payloads[key]
    rows.append(copy.deepcopy(rows[0]))
    write_payload(paths, payloads, key)
    with pytest.raises(ValueError, match="Duplicate"):
        audit(**paths)


@pytest.mark.parametrize("field,value", [("schema_version", True), ("schema_version", 2), ("as_of", ""),
                                        ("sources", []), ("ideas", []), ("limitation", " "),
                                        ("retained_unknowns", "not-a-list")])
def test_malformed_index_contract_fails(inputs, field, value):
    paths, payloads = inputs
    payloads["index_path"][field] = value
    write_payload(paths, payloads, "index_path")
    with pytest.raises(ValueError):
        audit(**paths)


@pytest.mark.parametrize("field,value", [("id", ""), ("title", " "), ("activation", "NOW"), ("note", 2)])
def test_malformed_idea_contract_fails(inputs, field, value):
    paths, payloads = inputs
    payloads["index_path"]["ideas"][0][field] = value
    write_payload(paths, payloads, "index_path")
    with pytest.raises(ValueError):
        audit(**paths)


@pytest.mark.parametrize("patch", [{"status": "accepted"}, {"status": None}, {"id": None},
                                   {"dependencies": None}, {"dependencies": ["UNKNOWN"]},
                                   {"dependencies": ["T-0", "T-0"]}, {"dependencies": [None]}])
def test_malformed_canonical_ticket_graph_fails(inputs, patch):
    paths, payloads = inputs
    payloads["tickets_path"][1].update(patch)
    write_payload(paths, payloads, "tickets_path")
    with pytest.raises(ValueError):
        audit(**paths)


def test_canonical_cycle_is_rejected_even_outside_linked_tickets(inputs):
    paths, payloads = inputs
    payloads["tickets_path"].extend([
        {"id": "UNLINKED-A", "status": "open", "dependencies": ["UNLINKED-B"]},
        {"id": "UNLINKED-B", "status": "open", "dependencies": ["UNLINKED-A"]},
    ])
    write_payload(paths, payloads, "tickets_path")
    with pytest.raises(ValueError, match="cycle"):
        audit(**paths)


@pytest.mark.parametrize("value", [None, "skill", [""], ["domain-skill", "domain-skill"]])
def test_malformed_skill_registry_fails(inputs, value):
    paths, payloads = inputs
    payloads["skills_path"]["personal_skills"] = value
    write_payload(paths, payloads, "skills_path")
    with pytest.raises(ValueError):
        audit(**paths)


@pytest.mark.parametrize("raw", ["{", '{"schema_version": 1, "schema_version": 1}', '{"value": NaN}', "[]"])
def test_invalid_json_and_top_level_contracts_fail_as_value_error(inputs, raw):
    paths, _ = inputs
    paths["index_path"].write_text(raw, encoding="utf-8")
    with pytest.raises(ValueError):
        audit(**paths)


def test_missing_file_fails_as_value_error(inputs):
    paths, _ = inputs
    paths["skills_path"].unlink()
    with pytest.raises(ValueError, match="Cannot read valid JSON"):
        audit(**paths)


def test_deterministic_reports_hash_inputs_and_never_mutate_them(inputs, tmp_path):
    paths, _ = inputs
    before = {key: path.read_bytes() for key, path in paths.items()}
    output = tmp_path / "derived"
    report = build(output, **paths)
    assert report == audit(**paths)
    first_outputs = {path.name: path.read_bytes() for path in output.iterdir()}
    assert set(first_outputs) == {"idea-coverage-report.json", "idea-coverage.md"}
    assert build(output, **paths) == report
    assert first_outputs == {path.name: path.read_bytes() for path in output.iterdir()}
    assert before == {key: path.read_bytes() for key, path in paths.items()}
    for field, key in (("idea_index", "index_path"), ("canonical_tickets", "tickets_path"), ("skill_registry", "skills_path")):
        assert report["input_hashes"][field] == hashlib.sha256(before[key]).hexdigest()
    for field in ("external_authority", "financial_authority", "closure_authority", "independent_acceptance_verified", "worker_process_running"):
        assert report[field] is False
    for field in ("tickets_created", "tickets_closed_by_this_application", "external_actions_performed"):
        assert report[field] == 0
    markdown = (output / "idea-coverage.md").read_text()
    assert "MANIFEST_DELIVERY_CLAIM" in markdown
    assert "unindexed ideas cannot be discovered" in markdown
    assert "open: T-0" in markdown and "closed: T-3" in markdown
    assert "Actual capital remains unknown.\nPreserve this note." in markdown


@pytest.mark.parametrize("alias", ["same-path", "symlink", "hardlink"])
def test_output_cannot_overwrite_inputs(inputs, tmp_path, alias):
    paths, _ = inputs
    output_dir = tmp_path
    destination = output_dir / "idea-coverage-report.json"
    if alias == "same-path":
        paths["tickets_path"].rename(destination)
        paths["tickets_path"] = destination
    elif alias == "symlink":
        try:
            destination.symlink_to(paths["tickets_path"])
        except OSError as exc:
            if getattr(exc, "winerror", None) != 1314:
                raise
            target_dir = tmp_path / "junction-target"
            target_dir.mkdir()
            target = target_dir / destination.name
            paths["tickets_path"].rename(target)
            paths["tickets_path"] = target
            output_dir = tmp_path / "junction-output"
            subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(output_dir), str(target_dir)],
                check=True, capture_output=True,
            )
            assert output_dir.is_junction()
    else:
        destination.hardlink_to(paths["tickets_path"])
    before = {key: path.read_bytes() for key, path in paths.items()}
    with pytest.raises(ValueError, match="overwrite"):
        build(output_dir, **paths)
    assert before == {key: path.read_bytes() for key, path in paths.items()}
    assert not (output_dir / "idea-coverage.md").exists()


def test_module_cli_uses_explicit_fixture_paths(inputs, tmp_path):
    paths, _ = inputs
    output = tmp_path / "cli"
    result = subprocess.run(
        [sys.executable, "-m", "tools.reconcile_idea_coverage", "--index", str(paths["index_path"]),
         "--tickets", str(paths["tickets_path"]), "--skills", str(paths["skills_path"]), "--output", str(output)],
        cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=True,
    )
    summary = json.loads(result.stdout)
    saved = json.loads((output / "idea-coverage-report.json").read_text())
    assert summary["mode"] == "OFFLINE_IDEA_COVERAGE_AUDIT"
    assert summary["idea_count"] == saved["idea_count"]
    assert saved == audit(**paths)
