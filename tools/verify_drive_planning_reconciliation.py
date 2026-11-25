"""Verify that the Drive planning crosswalk resolves against the execution register."""
from collections import Counter
from pathlib import Path

from tools.reconcile_idea_coverage import _read


def verify(register, crosswalk):
    canonical = {row["id"] for row in register}
    records = crosswalk["records"]
    planning = {row["planning_id"] for row in records}
    if len(canonical) != len(register) or len(planning) != len(records):
        raise ValueError("Duplicate canonical or planning ID")
    counts = Counter(row["disposition"] for row in records)
    if (len(planning) != crosswalk["planning_ids_total"]
            or len(canonical) != crosswalk["canonical_ids_total"]
            or counts != crosswalk["disposition_counts"]):
        raise ValueError("Crosswalk counts disagree with register data")
    for row in records:
        identifier = row["planning_id"]
        links = row["canonical_ticket_ids"]
        disposition = row["disposition"]
        if len(links) != len(set(links)) or not set(links) <= canonical:
            raise ValueError(f"{identifier} has duplicate or unknown ticket links")
        if disposition == "OVERLAP_MAPPED":
            if not links or not row["source_rows"]:
                raise ValueError(f"{identifier} is missing links or source rows")
        elif disposition == "REFERENCE_ONLY":
            if links or row["source_rows"]:
                raise ValueError(f"{identifier} has unexpected source rows or links")
        elif disposition == "DELIVERABLE_REVIEW":
            if links or not row["source_rows"]:
                raise ValueError(f"{identifier} has inconsistent pending evidence")
        else:
            raise ValueError(f"{identifier} has an unknown disposition")
    return counts


if __name__ == "__main__":
    docs = Path(__file__).resolve().parents[1] / "docs"
    register, _ = _read(docs / "session-tickets.json")
    crosswalk, _ = _read(docs / "acquisition/drive-planning-reconciliation.json")
    print(dict(verify(register, crosswalk)))
