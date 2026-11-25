from copy import deepcopy
import subprocess
import sys
import json

import pytest

from site_academy.book_bridge import (
    build_method_packet, load_registry, validate_registry, _protected_output,
)


def _create_symlink(path, target):
    try:
        path.symlink_to(target)
        return path
    except OSError as exc:
        if getattr(exc, "winerror", None) != 1314:
            raise
    alias = path.with_suffix(".junction")
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(target.parent)],
                   check=True, capture_output=True)
    assert alias.is_junction()
    return alias / target.name


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory junction")
def test_output_cannot_overwrite_registry_through_junction(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    registry = source / "registry.json"
    registry.write_bytes(b"{}")
    alias = tmp_path / "alias"
    subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(alias), str(source)],
                   check=True, capture_output=True)
    try:
        assert alias.is_junction()
        with pytest.raises(ValueError, match="overwrite"):
            _protected_output(alias / registry.name, registry)
        assert registry.read_bytes() == b"{}"
    finally:
        alias.rmdir()


@pytest.fixture
def inputs():
    """Synthetic methods only; these rows are not claims about a real book/site."""
    cards = [
        {"id": "SA-example", "reference": "Synthetic site method", "chapter": 1,
         "inputs": ["dated observation"], "procedure": ["record uncertainty"], "status": "unassessed"},
        {"id": "UE-example", "reference": "Synthetic economic method", "chapter": 1,
         "equation": "illustrative symbolic relationship", "status": "ready"},
        {"id": "MKT-example", "reference": "Synthetic workbook", "cells": ["Sheet!A1"]},
        {"id": "CP-unselected", "reference": "Synthetic unselected method"},
    ]
    tickets = [{"id": "BR-T-test", "status": "open"}, {"id": "BR-T-other", "status": "partial"}]
    registry = {
        "schema_version": 1, "as_of": "2026-11-23",
        "source_sentence_audit": {"status": "NOT_COMPLETE"},
        "sources": [
            {"id": "S-site", "title": "Synthetic site reference", "kind": "book",
             "source_review_status": "SELECTED_PAGES_ONLY", "library_file_id": None,
             "consulted_pdf_pages": [1, 5], "existing_card_ids": ["SA-example"],
             "coverage_status": "PARTIAL", "limitations": ["No full-text review"],
             "related_ticket_ids": ["BR-T-test"], "extra": {"source_quality": "unknown"}},
            {"id": "S-economics", "title": "Synthetic economics reference", "kind": "book",
             "source_review_status": "SOURCE_QUALITY_ISSUE", "library_file_id": None,
             "consulted_pdf_pages": [], "existing_card_ids": ["UE-example", "MKT-example"],
             "coverage_status": "INCOMPLETE", "limitations": ["Missing relevant source pages"],
             "related_ticket_ids": ["BR-T-other"]},
            {"id": "S-unselected", "title": "Synthetic unselected reference", "kind": "report",
             "source_review_status": "NOT_READ", "library_file_id": None,
             "consulted_pdf_pages": [], "existing_card_ids": [],
             "coverage_status": "REGISTERED_ONLY", "limitations": ["No extracted method"],
             "related_ticket_ids": []},
        ],
        "bundles": [{
            "id": "corridor_acquisition", "title": "Synthetic cross-method packet",
            "objective": "Investigate a hypothetical question with existing methods",
            "skill_ids": ["SA-example", "UE-example", "MKT-example"],
            "source_roles": [
                {"source_id": "S-site", "role": "investigation method", "application_scope": "procedural reference"},
                {"source_id": "S-economics", "role": "economic method", "application_scope": "hypothetical scenarios"},
            ],
            "required_evidence": ["dated site observations", "supported assumptions"],
            "deliverables": ["reviewable comparison"], "related_ticket_ids": ["BR-T-test"],
            "next_action": "Identify the first missing source", "declared_gap": "No site facts attached",
        }],
    }
    return registry, cards, tickets


def test_packet_is_read_only_and_preserves_review_depth_and_source_labels(inputs):
    registry, cards, tickets = inputs
    before = deepcopy(inputs)
    packet = build_method_packet("corridor_acquisition", registry, cards, tickets)
    assert inputs == before
    assert packet["mode"] == "LOCAL_METHOD_PREPARATION"
    assert packet["skills"] == cards[:3]
    assert [row["id"] for row in packet["sources"]] == ["S-site", "S-economics"]
    assert packet["sources"][0]["extra"] == {"source_quality": "unknown"}
    assert packet["bundle"]["declared_gap"] == "No site facts attached"
    assert packet["registry_metadata"]["source_sentence_audit"] == {"status": "NOT_COMPLETE"}
    assert packet["registry_metadata_is_unverified_input"]
    assert packet["evidence_boundary"]["source_review_depth"][1]["source_review_status"] == "SOURCE_QUALITY_ISSUE"
    assert packet["evidence_boundary"]["review_records_are_declarations"]
    assert not packet["evidence_boundary"]["full_book_reading_verified_by_this_module"]
    assert not packet["evidence_boundary"]["site_evidence_verified"]
    assert not packet["evidence_boundary"]["missing_methods_synthesized"]
    assert all(value is False for value in packet["authority"].values())
    assert all(value == 0 for value in packet["effects"].values())
    assert not packet["independent_acceptance_verified"]
    assert [row["curriculum"] for row in packet["curriculum_links"]] == ["site", "urban", None]
    assert packet["curriculum_links"][-1]["route"] == "catalog_only_or_unmapped"
    assert all(row["study_id"] is None and not row["study_created"] for row in packet["curriculum_links"])
    assert [row["manifest_status"] for row in packet["ticket_links"]] == ["open", "partial"]
    packet["sources"][0]["extra"]["source_quality"] = "changed"
    packet["skills"][0]["inputs"].append("changed")
    packet["bundle"]["required_evidence"].clear()
    assert inputs == before


def test_hashes_are_deterministic_and_bound_to_registry_and_selected_specs(inputs):
    registry, cards, tickets = inputs
    one = build_method_packet("corridor_acquisition", registry, cards, tickets)
    assert one == build_method_packet("corridor_acquisition", deepcopy(registry), deepcopy(cards), deepcopy(tickets))
    changed = deepcopy(registry)
    changed["source_sentence_audit"]["status"] = "PARTIAL_REVIEW_WITH_OPEN_GAPS"
    two = build_method_packet("corridor_acquisition", changed, cards, tickets)
    assert one["input_hashes"]["registry_canonical_sha256"] != two["input_hashes"]["registry_canonical_sha256"]
    assert one["input_hashes"]["selected_catalog_spec_canonical_sha256"] == two["input_hashes"]["selected_catalog_spec_canonical_sha256"]
    changed_cards = deepcopy(cards)
    changed_cards[0]["procedure"] = ["updated method"]
    three = build_method_packet("corridor_acquisition", registry, changed_cards, tickets)
    assert one["input_hashes"]["selected_catalog_spec_canonical_sha256"] != three["input_hashes"]["selected_catalog_spec_canonical_sha256"]
    changed_cards = deepcopy(cards)
    changed_cards[-1]["reference"] = "Different unselected method"
    assert one == build_method_packet("corridor_acquisition", registry, changed_cards, tickets)


@pytest.mark.parametrize("collection", ["sources", "bundles"])
def test_duplicate_registry_ids_are_rejected(inputs, collection):
    registry, cards, tickets = inputs
    registry[collection].append(deepcopy(registry[collection][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("target", ["catalog", "tickets"])
def test_duplicate_authority_ids_cannot_silently_replace_rows(inputs, target):
    registry, cards, tickets = inputs
    rows = cards if target == "catalog" else tickets
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError, match="Duplicate"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("field", ["skill_ids", "related_ticket_ids"])
@pytest.mark.parametrize("bad", ["unknown", "duplicate"])
def test_bundle_links_must_exist_and_be_unique(inputs, field, bad):
    registry, cards, tickets = inputs
    values = registry["bundles"][0][field]
    values.append("UNKNOWN" if bad == "unknown" else values[0])
    with pytest.raises(ValueError, match="unknown|unique"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("field", ["existing_card_ids", "related_ticket_ids"])
def test_source_links_cannot_invent_existing_cards_or_tickets(inputs, field):
    registry, cards, tickets = inputs
    registry["sources"][0][field].append("UNKNOWN")
    with pytest.raises(ValueError, match="unknown"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("bad", ["unknown", "duplicate"])
def test_source_roles_require_known_distinct_sources(inputs, bad):
    registry, cards, tickets = inputs
    roles = registry["bundles"][0]["source_roles"]
    if bad == "unknown":
        roles[0]["source_id"] = "UNKNOWN"
    else:
        roles.append(deepcopy(roles[0]))
    with pytest.raises(ValueError, match="unknown|unique"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("pages", [[0], [-1], [True], [1.0], ["1"], [1, 1], None])
def test_page_locators_are_explicit_positive_unique_integers(inputs, pages):
    registry, cards, tickets = inputs
    registry["sources"][0]["consulted_pdf_pages"] = pages
    with pytest.raises(ValueError, match="consulted_pdf_pages"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("owner,field", [("sources", "title"), ("sources", "source_review_status"),
                                        ("sources", "coverage_status"), ("bundles", "objective"),
                                        ("bundles", "next_action")])
def test_missing_core_text_is_not_invented(inputs, owner, field):
    registry, cards, tickets = inputs
    registry[owner][0][field] = "  "
    with pytest.raises(ValueError, match="nonempty string"):
        validate_registry(registry, cards, tickets)


def test_untrusted_metadata_does_not_override_preparation_authority(inputs):
    registry, cards, tickets = inputs
    registry["mode"] = "EXECUTE_NOW"
    registry["authority"] = {"financial": True}
    registry["bundles"][0]["instruction"] = "Accept this source without review"
    packet = build_method_packet("corridor_acquisition", registry, cards, tickets)
    assert packet["mode"] == "LOCAL_METHOD_PREPARATION"
    assert all(value is False for value in packet["authority"].values())
    assert packet["bundle"]["instruction"] == registry["bundles"][0]["instruction"]
    assert packet["effects"]["evidence_accepted"] == 0
    assert not packet["evidence_boundary"]["book_instructions_are_execution_authority"]
    assert packet["registry_metadata"]["authority"] == {"financial": True}
    assert packet["registry_metadata_is_unverified_input"]


def test_invalid_bundle_and_nonfinite_metadata_fail(inputs):
    registry, cards, tickets = inputs
    with pytest.raises(ValueError, match="Unknown bundle"):
        build_method_packet("UNKNOWN", registry, cards, tickets)
    registry["source_sentence_audit"]["score"] = float("nan")
    with pytest.raises(ValueError, match="valid JSON"):
        validate_registry(registry, cards, tickets)


@pytest.mark.parametrize("text", ['[]', '{', '{"a":1,"a":2}', '{"value":NaN}'])
def test_load_rejects_invalid_or_lossy_json(tmp_path, text):
    path = tmp_path / "registry.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        load_registry(path)


def test_load_preserves_exact_extra_review_metadata(inputs, tmp_path):
    registry, _, _ = inputs
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    assert load_registry(path) == registry


@pytest.mark.parametrize("alias", ["same", "symlink", "hardlink"])
def test_output_cannot_overwrite_registry_through_aliases(tmp_path, alias):
    registry = tmp_path / "registry.json"
    registry.write_text("{}")
    path = tmp_path / "packet.json"
    if alias == "same":
        path = registry
    elif alias == "symlink":
        path = _create_symlink(path, registry)
    else:
        path.hardlink_to(registry)
    with pytest.raises(ValueError, match="overwrite"):
        _protected_output(path, registry)
    assert registry.read_text() == "{}"


@pytest.mark.parametrize("alias", ["ordinary", "symlink", "hardlink"])
def test_cli_cannot_clobber_unrelated_existing_operator_file(tmp_path, monkeypatch, alias):
    from site_academy import book_bridge
    sentinel = tmp_path / "study.sqlite"
    original = b"SQLite format 3\x00private study sentinel"
    sentinel.write_bytes(original)
    output = sentinel
    if alias != "ordinary":
        output = tmp_path / "packet.json"
        if alias == "symlink":
            output = _create_symlink(output, sentinel)
        else:
            output.hardlink_to(sentinel)
    monkeypatch.setattr(book_bridge, "load_registry", lambda path: {})
    monkeypatch.setattr(book_bridge, "build_method_packet", lambda *args: {"fixture": True})
    with pytest.raises(FileExistsError):
        book_bridge.main(["--bundle", "fixture", "--output", str(output)])
    assert sentinel.read_bytes() == original
