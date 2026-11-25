"""Build a dependency-aware team batch from the canonical ticket register."""

import argparse
from collections import Counter, defaultdict
from graphlib import TopologicalSorter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.core.tickets import SEED
from tools.build_acquisition_ticket_plan import VALID_STATES


BATCH_SIZE = 5


def orchestrate(rows, capacity=BATCH_SIZE):
    """Select independent work and summarize observed delivery by role."""
    if not 1 <= capacity <= BATCH_SIZE:
        raise ValueError(f"Capacity must be between 1 and {BATCH_SIZE}")
    tickets = {row["id"]: row for row in rows}
    dependencies = {key: set(row["dependencies"]) for key, row in tickets.items()}
    if len(tickets) != len(rows) or any(
        row["status"] not in VALID_STATES or dependencies[key] - tickets.keys()
        for key, row in tickets.items()
    ):
        raise ValueError("Invalid canonical register")
    order = list(TopologicalSorter(dependencies).static_order())
    closed = {key for key, row in tickets.items() if row["status"] == "closed"}
    descendants = defaultdict(set)
    for key in reversed(order):
        if key not in closed:
            for parent in dependencies[key] - closed:
                descendants[parent].update({key, *descendants[key]})

    role_history = defaultdict(Counter)
    ready, held = [], []
    for row in rows:
        key = row["id"]
        status = row["status"]
        role_history[row["owner"]][status] += 1
        if key in closed:
            continue
        waiting = sorted(dependencies[key] - closed)
        if waiting or status == "blocked" or row.get("blocker"):
            held.append({
                "id": key, "waiting_on": waiting,
                "blocker": row.get("blocker") or ("Marked blocked" if status == "blocked" else ""),
                "open_dependents": len(descendants[key]),
            })
            continue
        ready.append({
            "id": key, "title": row["title"], "owner": row["owner"],
            "leader": row["leader"], "acceptance": row["acceptance"],
            "next_action": row.get("next_action") or row["acceptance"],
            "stage": "verify" if status in {"delivered_local", "review_required"} else "build",
            "open_dependents": len(descendants[key]),
        })

    # Verify evidence already on hand, then prioritize work with downstream impact.
    # Role history informs capacity reviews without treating closures as timing data.
    ready.sort(key=lambda item: (
        item["stage"] != "verify", -item["open_dependents"], item["id"],
    ))
    # The ticket batch is a review cadence. Tickets assigned to the same role
    # can be worked sequentially within it.
    batches = [ready[start:start + capacity] for start in range(0, len(ready), capacity)]
    batch = batches[0] if batches else []
    backlog = ready[capacity:]
    return {
        "coordinator": "SW-00", "capacity": capacity,
        "remaining": len(rows) - len(closed), "batch": batch,
        "ready_backlog": backlog, "ready_batches": batches,
        "held": sorted(held, key=lambda item: (-item["open_dependents"], item["id"])),
        "role_learning": {role: dict(counts) for role, counts in sorted(role_history.items())},
        "timing_measured": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity", type=int, choices=range(1, BATCH_SIZE + 1), default=BATCH_SIZE)
    parser.add_argument("--output", type=Path, help="Atomically refresh a local team batch file")
    args = parser.parse_args()
    raw = SEED.read_bytes()
    rows = json.loads(raw)
    result = orchestrate(rows, args.capacity)
    result["canonical_source_sha256"] = sha256(raw).hexdigest()
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(encoded, end="")
        return
    target = args.output
    if (target.resolve() == SEED.resolve()
            or (target.exists() and target.samefile(SEED))):
        parser.error("Team batch output cannot replace the canonical register")
    with TemporaryDirectory(prefix=".team-batch-", dir=target.parent) as scratch:
        staged = Path(scratch) / target.name
        staged.write_text(encoded, encoding="utf-8")
        staged.replace(target)


if __name__ == "__main__":
    main()
