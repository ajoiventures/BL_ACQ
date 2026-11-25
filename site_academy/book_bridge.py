"""Prepare source-linked, cross-book work packets without executing a study.

This standard-library module reads the existing Academy catalog and canonical
ticket register. It never starts a study, changes a status, runs a model,
dispatches an agent or accepts evidence. Source review depth is retained as a
declared record; validation checks structure and references, not book coverage.

Examples:
    python -m site_academy.book_bridge --validate
    python -m site_academy.book_bridge --bundle corridor_acquisition --output packet.json
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from . import catalog


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = Path(__file__).with_name("book-integration.json")
TICKETS = ROOT / "docs/session-tickets.json"
CATALOG_FILES = (
    "acquisition.json", "planning.json", "skills.json", "market-skills.json",
    "econ1.json", "econ2.json", "econ3.json",
)
CURRICULA = {
    "SA": "site", "UE": "urban", "CP": "planning", "AQ": "acquisition",
}


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _strings(value: Any, label: str, *, empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not empty):
        raise ValueError(f"{label} must be a {'possibly empty' if empty else 'nonempty'} list")
    for item in value:
        _text(item, label)
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must contain unique values")
    return value


def _records(value: Any, label: str) -> dict[str, dict]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty list")
    by_id = {}
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"{label} entries must be objects")
        key = _text(row.get("id"), f"{label} ID")
        if key in by_id:
            raise ValueError(f"Duplicate {label} ID: {key}")
        by_id[key] = row
    return by_id


def _assert_json(value: Any) -> None:
    """Reject lossy non-JSON inputs before calculating canonical input hashes."""
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float:
        # allow_nan=False below rejects NaN and infinities.
        return
    if isinstance(value, list):
        for item in value:
            _assert_json(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        for item in value.values():
            _assert_json(item)
        return
    raise ValueError("Inputs must contain JSON objects with string keys and JSON values")


def _canonical_bytes(value: Any) -> bytes:
    try:
        _assert_json(value)
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError(f"Cannot hash valid JSON input: {error}") from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Nonstandard JSON constant: {value}")


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_object,
                          parse_constant=_invalid_constant)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Cannot read valid JSON from {path}: {error}") from error


def load_registry(path: str | Path = REGISTRY) -> dict:
    """Read a registry; validate references separately against the actual catalog."""
    result = _read_json(Path(path))
    if not isinstance(result, dict):
        raise ValueError("Registry must be a JSON object")
    return result


def _inputs(catalog_rows, ticket_rows):
    return (catalog() if catalog_rows is None else catalog_rows,
            _read_json(TICKETS) if ticket_rows is None else ticket_rows)


def validate_registry(registry: dict, catalog_rows=None, ticket_rows=None) -> dict:
    """Check references without inferring source completeness or study acceptance.

    Extra source/bundle metadata is retained unchanged, including incomplete
    review records and source-quality issues. Validation is not a content audit.
    """
    if (not isinstance(registry, dict)
            or type(registry.get("schema_version")) is not int
            or registry["schema_version"] != 1):
        raise ValueError("Registry schema_version must be integer 1")
    _text(registry.get("as_of"), "Registry as_of")
    registry_hash = _sha256(registry)
    catalog_rows, ticket_rows = _inputs(catalog_rows, ticket_rows)
    cards = _records(catalog_rows, "catalog")
    tickets = _records(ticket_rows, "ticket")
    _canonical_bytes(catalog_rows)
    _canonical_bytes(ticket_rows)
    sources = _records(registry.get("sources"), "source")
    bundles = _records(registry.get("bundles"), "bundle")

    def references(value, label, known, *, empty=False):
        values = _strings(value, label, empty=empty)
        missing = sorted(set(values) - set(known))
        if missing:
            raise ValueError(f"{label} contains unknown references: {', '.join(missing)}")
        return values

    for source in sources.values():
        sid = source["id"]
        for field in ("title", "kind", "source_review_status", "coverage_status"):
            _text(source.get(field), f"Source {sid} {field}")
        if "library_file_id" not in source:
            raise ValueError(f"Source {sid} must declare library_file_id or null")
        if source["library_file_id"] is not None:
            _text(source["library_file_id"], f"Source {sid} library_file_id")
        pages = source.get("consulted_pdf_pages")
        if not isinstance(pages, list) or any(type(page) is not int or page < 1 for page in pages):
            raise ValueError(f"Source {sid} consulted_pdf_pages must contain positive integers")
        if len(pages) != len(set(pages)):
            raise ValueError(f"Source {sid} consulted_pdf_pages must be unique")
        references(source.get("existing_card_ids"), f"Source {sid} existing_card_ids", cards, empty=True)
        references(source.get("related_ticket_ids"), f"Source {sid} related_ticket_ids", tickets, empty=True)
        _strings(source.get("limitations"), f"Source {sid} limitations", empty=True)

    for bundle in bundles.values():
        bid = bundle["id"]
        for field in ("title", "objective", "next_action"):
            _text(bundle.get(field), f"Bundle {bid} {field}")
        references(bundle.get("skill_ids"), f"Bundle {bid} skill_ids", cards)
        references(bundle.get("related_ticket_ids"), f"Bundle {bid} related_ticket_ids", tickets)
        for field in ("required_evidence", "deliverables"):
            _strings(bundle.get(field), f"Bundle {bid} {field}")
        roles = bundle.get("source_roles")
        if not isinstance(roles, list) or not roles:
            raise ValueError(f"Bundle {bid} source_roles must be a nonempty list")
        role_sources = set()
        for role in roles:
            if not isinstance(role, dict):
                raise ValueError(f"Bundle {bid} source roles must be objects")
            source_id = _text(role.get("source_id"), f"Bundle {bid} source_id")
            if source_id not in sources:
                raise ValueError(f"Bundle {bid} contains unknown source {source_id}")
            if source_id in role_sources:
                raise ValueError(f"Bundle {bid} source-role IDs must be unique")
            role_sources.add(source_id)
            for field in ("role", "application_scope"):
                _text(role.get(field), f"Bundle {bid} source role {field}")

    return {
        "schema_version": 1,
        "mode": "LOCAL_METHOD_PREPARATION",
        "validation": "VALID_STRUCTURAL_REFERENCES_ONLY",
        "source_count": len(sources),
        "bundle_count": len(bundles),
        "catalog_card_count": len(cards),
        "canonical_ticket_count": len(tickets),
        "registry_canonical_sha256": registry_hash,
        "source_contents_verified": False,
        "complete_book_coverage_verified": False,
        "independent_acceptance_verified": False,
        "studies_created": 0,
        "statuses_changed": 0,
        "models_executed": 0,
        "external_actions_performed": 0,
    }


def _curriculum_links(skill_ids: list[str]) -> list[dict]:
    groups: dict[str | None, list[str]] = {}
    for skill_id in skill_ids:
        curriculum = CURRICULA.get(skill_id.split("-", 1)[0])
        groups.setdefault(curriculum, []).append(skill_id)
    return [{
        "curriculum": curriculum,
        "skill_ids": ids,
        "route": "existing_study_curriculum" if curriculum else "catalog_only_or_unmapped",
        "study_id": None,
        "study_created": False,
        "study_state": "NOT_READ",
        "instruction": (
            "Link the existing study in this curriculum; preserve its frozen specification and independent review state."
            if curriculum else
            "Keep this card as a catalog reference; no standalone study curriculum is inferred."
        ),
    } for curriculum, ids in groups.items()]


def build_method_packet(bundle_id: str, registry=None, catalog_rows=None, ticket_rows=None) -> dict:
    """Return a deterministic preparation packet, not a new combined study."""
    _text(bundle_id, "bundle_id")
    registry = load_registry() if registry is None else registry
    catalog_rows, ticket_rows = _inputs(catalog_rows, ticket_rows)
    validation = validate_registry(registry, catalog_rows, ticket_rows)
    bundles = {row["id"]: row for row in registry["bundles"]}
    if bundle_id not in bundles:
        raise ValueError(f"Unknown bundle: {bundle_id}")
    source_map = {row["id"]: row for row in registry["sources"]}
    card_map = {row["id"]: row for row in catalog_rows}
    ticket_map = {row["id"]: row for row in ticket_rows}
    bundle = deepcopy(bundles[bundle_id])
    selected_sources = [deepcopy(source_map[role["source_id"]]) for role in bundle["source_roles"]]
    selected_cards = [deepcopy(card_map[key]) for key in bundle["skill_ids"]]
    ticket_ids = list(dict.fromkeys(bundle["related_ticket_ids"] + [
        key for source in selected_sources for key in source["related_ticket_ids"]
    ]))
    ticket_links = [{"id": key, "manifest_status": deepcopy(ticket_map[key].get("status")),
                     "status_origin": "SUPPLIED_CANONICAL_REGISTER", "status_changed": False}
                    for key in ticket_ids]
    return {
        "schema_version": 1,
        "mode": "LOCAL_METHOD_PREPARATION",
        "as_of": registry["as_of"],
        "registry_metadata": deepcopy({key: value for key, value in registry.items()
                                       if key not in {"sources", "bundles"}}),
        "registry_metadata_is_unverified_input": True,
        "bundle": bundle,
        "sources": selected_sources,
        "skills": selected_cards,
        "curriculum_links": _curriculum_links(bundle["skill_ids"]),
        "ticket_links": ticket_links,
        "input_hashes": {
            "registry_canonical_sha256": validation["registry_canonical_sha256"],
            "selected_catalog_spec_canonical_sha256": _sha256(selected_cards),
            "selected_ticket_records_canonical_sha256": _sha256([ticket_map[key] for key in ticket_ids]),
        },
        "hash_basis": "SHA-256 of UTF-8 JSON with sorted keys, compact separators, preserved array order and no nonfinite numbers; not raw file-byte hashes.",
        "evidence_boundary": {
            "source_role": "Method and research references only; not evidence of current site facts.",
            "source_review_depth": [{"source_id": source["id"],
                                     "source_review_status": source["source_review_status"],
                                     "coverage_status": source["coverage_status"],
                                     "consulted_pdf_pages": deepcopy(source["consulted_pdf_pages"]),
                                     "limitations": deepcopy(source["limitations"])}
                                    for source in selected_sources],
            "review_records_are_declarations": True,
            "full_book_reading_verified_by_this_module": False,
            "site_evidence_verified": False,
            "missing_methods_synthesized": False,
            "book_instructions_are_execution_authority": False,
        },
        "authority": {
            "external": False, "financial": False, "contractual": False,
            "ticket_closure": False, "study_acceptance": False,
            "worker_dispatch": False, "model_execution": False,
        },
        "effects": {
            "studies_created": 0, "statuses_changed": 0, "tickets_created": 0,
            "models_executed": 0, "workers_dispatched": 0,
            "external_actions_performed": 0, "evidence_accepted": 0,
        },
        "independent_acceptance_verified": False,
        "interpretation": "A linked reading and work packet. Use existing studies and their separate review histories; no catalog status or source claim establishes completion of the selected real-world task.",
    }


def _protected_output(path: Path, registry_path: Path) -> None:
    inputs = [registry_path, TICKETS, Path(__file__), Path(__file__).with_name("__init__.py"),
              Path(__file__).with_name("runner.py"),
              *(Path(__file__).with_name(name) for name in CATALOG_FILES)]
    for source in inputs:
        if path.resolve() == source.resolve() or (
                path.exists() and source.exists() and path.samefile(source)):
            raise ValueError("Output must not overwrite the registry, canonical inputs or existing workflow code")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--validate", action="store_true")
    operation.add_argument("--bundle")
    parser.add_argument("--registry", type=Path, default=REGISTRY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    registry = load_registry(args.registry)
    result = validate_registry(registry) if args.validate else build_method_packet(args.bundle, registry)
    encoded = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        _protected_output(args.output, args.registry)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects unenumerated study databases and other
        # existing operator files, and closes the check/write race. Regeneration
        # should use a new revision path rather than clobbering an earlier packet.
        with args.output.open("x", encoding="utf-8") as output:
            output.write(encoded)
        print(json.dumps({"mode": "LOCAL_METHOD_PREPARATION", "output": str(args.output),
                          "registry_canonical_sha256": _sha256(registry)}, indent=2))
    else:
        print(encoded, end="")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
