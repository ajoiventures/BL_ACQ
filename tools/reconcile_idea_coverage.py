"""Audit a supplied idea index against existing tickets and skills, offline.

Semantic decomposition belongs to the people/agents preparing the index. This
utility validates traceability; it does not discover ideas, create tickets,
execute work, verify delivery, or accept/close tickets.

Run: python -m tools.reconcile_idea_coverage
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from tools.build_acquisition_ticket_plan import VALID_STATES, validate_graph

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/acquisition/idea-system-index.json"
MANIFEST = ROOT / "docs/session-tickets.json"
SKILLS = ROOT / "docs/acquisition/academy-extension.json"
OUTPUT = ROOT / "docs/acquisition/run"
ACTIVATIONS = ("ACTIVE", "NEXT", "LATER", "REVIEW")
DELIVERY_STATES = {"delivered_local", "review_required", "closed"}
DELIVERY_EVIDENCE_CLASS = "MANIFEST_DELIVERY_CLAIM"


def _text(value, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be a {'string' if allow_empty else 'nonempty string'}")
    return value


def _strings(value, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(f"{label} must be a {'list' if allow_empty else 'nonempty list'}")
    for item in value:
        _text(item, f"{label} item")
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must contain unique values")
    return value


def _records(value, label: str) -> dict[str, dict]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a nonempty list")
    records = {}
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"{label} entries must be objects")
        key = _text(row.get("id"), f"{label} ID")
        if key in records:
            raise ValueError(f"Duplicate {label} ID: {key}")
        records[key] = row
    return records


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Nonstandard JSON constant: {value}")


def _read(path: Path) -> tuple[object, str]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_json_object,
                           parse_constant=_reject_constant)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(f"Cannot read valid JSON from {path}: {error}") from error
    return value, hashlib.sha256(raw).hexdigest()


def audit(index_path: Path = INDEX, tickets_path: Path = MANIFEST,
          skills_path: Path = SKILLS) -> dict:
    """Return a deterministic coverage report without writing any files."""
    paths = {"idea_index": Path(index_path), "canonical_tickets": Path(tickets_path),
             "skill_registry": Path(skills_path)}
    inputs = {name: _read(path) for name, path in paths.items()}
    index, rows, registry = (inputs[name][0] for name in paths)
    if not isinstance(index, dict) or type(index.get("schema_version")) is not int or index["schema_version"] != 1:
        raise ValueError("Idea index schema_version must be integer 1")
    _text(index.get("as_of"), "Idea index as_of")
    _text(index.get("limitation"), "Idea index limitation")
    declared_unknowns = _strings(index.get("retained_unknowns", []), "retained_unknowns", allow_empty=True)
    sources = _records(index.get("sources"), "source")
    ideas = _records(index.get("ideas"), "idea")
    tickets = _records(rows, "ticket")
    for ticket in tickets.values():
        _text(ticket.get("status"), f"Ticket {ticket['id']} status")
        _strings(ticket.get("dependencies"), f"Ticket {ticket['id']} dependencies", allow_empty=True)
    # Reuse the canonical validator, including for tickets not linked to an idea.
    dependency_order = validate_graph(rows)
    if not isinstance(registry, dict):
        raise ValueError("Skill registry must be an object")
    skills = set(_strings(registry.get("personal_skills"), "Registry personal_skills", allow_empty=True))
    skills.update(_strings(registry.get("existing_builder_skills"), "Registry existing_builder_skills", allow_empty=True))
    if not skills:
        raise ValueError("Skill registry must contain known skills")

    projected = []
    for idea in ideas.values():
        key = idea["id"]
        _text(idea.get("title"), f"Idea {key} title")
        _text(idea.get("note"), f"Idea {key} note", allow_empty=True)
        activation = _text(idea.get("activation"), f"Idea {key} activation")
        if activation not in ACTIVATIONS:
            raise ValueError(f"Idea {key} has unsupported activation: {activation}")
        for field, known in (("source_ids", sources), ("ticket_ids", tickets), ("personal_skills", skills)):
            links = _strings(idea.get(field), f"Idea {key} {field}")
            unknown = sorted(set(links) - set(known))
            if unknown:
                raise ValueError(f"Idea {key} has unknown {field}: {', '.join(unknown)}")
        subsets = {status: [tid for tid in idea["ticket_ids"] if tickets[tid]["status"] == status]
                   for status in sorted(VALID_STATES)}
        delivered = [tid for tid in idea["ticket_ids"] if tickets[tid]["status"] in DELIVERY_STATES]
        outstanding = [tid for tid in idea["ticket_ids"] if tickets[tid]["status"] not in DELIVERY_STATES]
        projected.append({
            **{field: idea[field] for field in ("id", "title", "source_ids", "ticket_ids", "personal_skills", "activation", "note")},
            "coverage_complete": True,
            "deliverable_specifications": {
                tid: tickets[tid]["acceptance"].strip()
                for tid in idea["ticket_ids"]
                if isinstance(tickets[tid].get("acceptance"), str)
                and tickets[tid]["acceptance"].strip()
            },
            "mapped_without_specification": [
                tid for tid in idea["ticket_ids"]
                if not str(tickets[tid].get("acceptance") or "").strip()
            ],
            "ticket_status_subsets": subsets,
            "ticket_status_counts": {status: len(ids) for status, ids in subsets.items()},
            "delivery_claim": {
                "evidence_class": DELIVERY_EVIDENCE_CLASS,
                "claimed_delivery_ticket_ids": delivered,
                "not_claimed_delivery_ticket_ids": outstanding,
                "all_linked_tickets_claim_delivery": not outstanding,
                "manifest_closed_ticket_ids": subsets["closed"],
                "independent_acceptance_verified": False,
            },
        })

    linked_tickets = {tid for idea in projected for tid in idea["ticket_ids"]}
    linked_sources = {sid for idea in projected for sid in idea["source_ids"]}
    queues = {state: [idea["id"] for idea in projected if idea["activation"] == state] for state in ACTIVATIONS}
    return {
        "schema_version": 1,
        "as_of": index["as_of"],
        "mode": "OFFLINE_IDEA_COVERAGE_AUDIT",
        "input_paths": {name: str(path) for name, path in paths.items()},
        "input_hashes": {name: value[1] for name, value in inputs.items()},
        "coverage_scope": "Valid links for supplied index entries only; unindexed ideas cannot be discovered by this audit.",
        "idea_count": len(projected),
        "covered_idea_count": len(projected),
        "uncovered_idea_count": 0,
        "all_covered": True,
        "source_count": len(sources),
        "sources_without_indexed_ideas": sorted(set(sources) - linked_sources),
        "sources": list(sources.values()),
        "source_provenance_scope": "Input files are hashed; cited source contents are not fetched or independently verified.",
        "ticket_count": len(tickets),
        "linked_ticket_count": len(linked_tickets),
        "canonical_ticket_status_counts": dict(sorted(Counter(row["status"] for row in rows).items())),
        "linked_ticket_status_counts": dict(sorted(Counter(tickets[tid]["status"] for tid in linked_tickets).items())),
        "known_skill_count": len(skills),
        "linked_skill_count": len({skill for idea in projected for skill in idea["personal_skills"]}),
        "dag_valid": True,
        "dependency_order": dependency_order,
        "activation_queues": queues,
        "active_idea_ids": queues["ACTIVE"],
        "delivery_evidence_class": DELIVERY_EVIDENCE_CLASS,
        "delivery_status_basis": sorted(DELIVERY_STATES),
        "delivery_interpretation": "Coverage is traceability only. Delivery and closed states are supplied register claims; no build, deployment, independent acceptance or transaction outcome is verified.",
        "ideas_with_all_tickets_claiming_delivery": sum(i["delivery_claim"]["all_linked_tickets_claim_delivery"] for i in projected),
        "ideas_with_mixed_delivery_claims": sum(bool(i["delivery_claim"]["claimed_delivery_ticket_ids"]) and bool(i["delivery_claim"]["not_claimed_delivery_ticket_ids"]) for i in projected),
        "ideas_without_ticket_delivery_claims": sum(not i["delivery_claim"]["claimed_delivery_ticket_ids"] for i in projected),
        "retained_unknowns": {
            "limitation": index["limitation"],
            "declared": declared_unknowns,
            "idea_notes": [{"idea_id": i["id"], "note": i["note"]} for i in projected],
            "interpretation": "Limitations and notes are retained verbatim; the audit does not classify or resolve them.",
        },
        "ticket_authority": "backend/core/tickets.py; existing independent closure workflow unchanged",
        "external_authority": False,
        "financial_authority": False,
        "closure_authority": False,
        "independent_acceptance_verified": False,
        "worker_process_running": False,
        "external_actions_performed": 0,
        "tickets_created": 0,
        "tickets_closed_by_this_application": 0,
        "ideas": projected,
    }


def _cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_markdown(report: dict) -> str:
    """Render coverage and delivery claims as separate, reviewable observations."""
    lines = ["# Idea-to-ticket coverage audit", "", f"As of {report['as_of']}.", "",
             f"Mode: `{report['mode']}`.", "",
             f"**{report['covered_idea_count']} of {report['idea_count']} indexed ideas have valid source, ticket and skill links.**",
             "", report["coverage_scope"], "", report["delivery_interpretation"], "",
             f"Delivery evidence class: `{report['delivery_evidence_class']}`. The state basis is {', '.join(report['delivery_status_basis'])}.", "",
             "## Activation and coverage", "",
             f"Active idea IDs: {', '.join(report['active_idea_ids']) or 'None declared.'}", "",
             "| Idea | Activation | Source IDs | Ticket IDs | Personal skills |", "|---|---|---|---|---|"]
    for idea in report["ideas"]:
        cells = [f"{idea['id']} — {idea['title']}", idea["activation"], ", ".join(idea["source_ids"]),
                 ", ".join(idea["ticket_ids"]), ", ".join(idea["personal_skills"])]
        lines.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    lines += ["", "## Deliverable specification gaps", ""]
    gaps = sorted({key for idea in report["ideas"] for key in idea["mapped_without_specification"]})
    lines += [", ".join(gaps) or "Every mapped ticket has acceptance criteria.", "",
              "## Ticket-register delivery claims", "",
              f"Ideas with delivery claimed for every linked ticket: {report['ideas_with_all_tickets_claiming_delivery']}. "
              f"Ideas with mixed claims: {report['ideas_with_mixed_delivery_claims']}. "
              f"Ideas with no ticket delivery claim: {report['ideas_without_ticket_delivery_claims']}.", "",
              "| Idea | Canonical status subsets | Delivery claimed for all linked tickets |", "|---|---|---|"]
    for idea in report["ideas"]:
        states = "; ".join(f"{state}: {', '.join(ids)}" for state, ids in idea["ticket_status_subsets"].items() if ids)
        all_claimed = "Yes, register claim only" if idea["delivery_claim"]["all_linked_tickets_claim_delivery"] else "No"
        lines.append(f"| {_cell(idea['id'])} | {_cell(states)} | {all_claimed} |")
    unknowns = report["retained_unknowns"]
    lines += ["", "## Retained limitations and notes", "", unknowns["interpretation"], "", unknowns["limitation"], ""]
    for unknown in unknowns["declared"]:
        lines += [f"- {_cell(unknown)}"]
    lines += [""]
    for row in unknowns["idea_notes"]:
        lines += [f"### {_cell(row['idea_id'])}", "", row["note"] or "No additional note supplied.", ""]
    lines += ["## Source coverage and input hashes", "", report["source_provenance_scope"], "",
              "Sources without indexed ideas: " + (", ".join(report["sources_without_indexed_ideas"]) or "None.") + "",
              "", "| Input | Path | SHA-256 |", "|---|---|---|"]
    for name, digest in report["input_hashes"].items():
        lines.append(f"| {name} | {_cell(report['input_paths'][name])} | `{digest}` |")
    lines += ["", "## Authority", "",
              "This offline audit has no external, financial or ticket-closure authority. It creates no tickets, dispatches no workers and performs no external actions.", "",
              report["ticket_authority"] + ".", ""]
    return "\n".join(lines)


def build(output: Path = OUTPUT, *, index_path: Path = INDEX,
          tickets_path: Path = MANIFEST, skills_path: Path = SKILLS) -> dict:
    """Validate first, then write only the two derived coverage reports."""
    output = Path(output)
    destinations = (output / "idea-coverage-report.json", output / "idea-coverage.md")
    protected = {Path(p).resolve() for p in (index_path, tickets_path, skills_path, MANIFEST)}
    for destination in destinations:
        if any(destination.resolve() == path or
               (destination.exists() and path.exists() and destination.samefile(path)) for path in protected):
            raise ValueError(f"Report output would overwrite a read-only input: {destination}")
    report = audit(index_path=index_path, tickets_path=tickets_path, skills_path=skills_path)
    output.mkdir(parents=True, exist_ok=True)
    destinations[0].write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    destinations[1].write_text(render_markdown(report), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, default=INDEX)
    parser.add_argument("--tickets", type=Path, default=MANIFEST)
    parser.add_argument("--skills", type=Path, default=SKILLS)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        report = build(args.output, index_path=args.index, tickets_path=args.tickets, skills_path=args.skills)
    except ValueError as error:
        parser.error(str(error))
    fields = ("mode", "idea_count", "covered_idea_count", "all_covered", "linked_ticket_count", "dag_valid", "active_idea_ids")
    print(json.dumps({key: report[key] for key in fields}, indent=2))


if __name__ == "__main__":
    main()
