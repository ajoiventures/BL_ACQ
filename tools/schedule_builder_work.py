"""Plan builder tickets offline with dependency, ownership and resource limits.

This is development tooling. It never creates agents, calls a model, accesses
the network, or executes tickets. Relative minutes are planning assumptions,
not measured work durations, calendar bookings, or delivery commitments.
"""

import argparse
from copy import deepcopy
import hashlib
import heapq
import json
from pathlib import Path, PurePosixPath
import re


ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = "br.build-ticket-plan.v1"
REPORT_SCHEMA = "br.builder-schedule.v1"
RESOURCES = ("agent_worker", "integrator", "cuda_device", "r_runtime")
STATUSES = {"planned", "in_progress", "completed", "blocked", "deferred"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,99}")


def _integer(value, name, low=0, high=1_000_000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _text(value, name, maximum=4000):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be nonempty text of at most {maximum} characters")
    return value


def _id(value, name):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid {name}")
    return value


def _string_list(value, name, maximum=2000, allow_empty=True):
    if type(value) is not list or len(value) > maximum or (not allow_empty and not value):
        raise ValueError(f"{name} must be a bounded array")
    for entry in value:
        _text(entry, name)
    if len(set(value)) != len(value):
        raise ValueError(f"{name} contains duplicate values")
    return value


def _scope(value):
    _text(value, "write scope", 1000)
    if any(character in value for character in ("\\", "\x00", "\n", "\r", "*", "?", "[", "]")):
        raise ValueError("Write scopes must be relative POSIX path prefixes, without globs")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or any(":" in part for part in path.parts):
        raise ValueError("Write scopes must stay within a relative repository namespace")
    return str(path)


def scopes_conflict(left, right):
    """True when equal or ancestor/descendant scopes would share written files."""
    for a in left:
        for b in right:
            if a == "." or b == "." or a == b or a.startswith(b+"/") or b.startswith(a+"/"):
                return True
    return False


def _validate(plan):
    if type(plan) is not dict or plan.get("schema_version") != PLAN_SCHEMA:
        raise ValueError(f"Plan schema_version must be {PLAN_SCHEMA}")
    capacities = plan.get("resource_profile")
    if type(capacities) is not dict or set(capacities) != set(RESOURCES):
        raise ValueError("resource_profile must specify agent_worker, integrator, cuda_device and r_runtime")
    capacities = {name: _integer(capacities[name], f"resource_profile.{name}", high=1000) for name in RESOURCES}
    if capacities["agent_worker"] > 3 or capacities["integrator"] != 1:
        raise ValueError("This planner supports up to three workers and one separately reserved integrator")
    policy = plan.get("scheduling_policy")
    if type(policy) is not dict or policy.get("reserved_integrator") != 1 or type(policy.get("reserved_integrator")) is not int:
        raise ValueError("scheduling_policy must reserve exactly one integrator")
    enabled = set(_string_list(policy.get("enabled_phases"), "enabled_phases", allow_empty=False))
    _text(policy.get("estimate_basis"), "estimate_basis")
    entries = plan.get("tickets")
    if type(entries) is not list or not 1 <= len(entries) <= 2000:
        raise ValueError("tickets must contain between 1 and 2000 records")
    jobs = {}
    for ticket in entries:
        if type(ticket) is not dict:
            raise ValueError("Every ticket must be an object")
        required = {"id", "title", "owner", "phase", "dependencies", "status", "priority",
                    "estimated_minutes", "required_resources", "write_scopes", "acceptance_criteria", "blockers"}
        if required-set(ticket):
            raise ValueError(f"Ticket is missing fields: {', '.join(sorted(required-set(ticket)))}")
        identity = _id(ticket["id"], "ticket id")
        if identity in jobs:
            raise ValueError("Duplicate ticket id")
        for key in ("title", "owner", "phase"):
            _text(ticket[key], f"{identity}.{key}")
        if not isinstance(ticket["status"], str) or ticket["status"] not in STATUSES:
            raise ValueError(f"{identity}: unknown ticket status")
        _integer(ticket["priority"], f"{identity}.priority", high=1000)
        _integer(ticket["estimated_minutes"], f"{identity}.estimated_minutes", low=1)
        deps = _string_list(ticket["dependencies"], f"{identity}.dependencies")
        for dep in deps:
            _id(dep, "dependency id")
        _string_list(ticket["acceptance_criteria"], f"{identity}.acceptance_criteria", allow_empty=False)
        _string_list(ticket["blockers"], f"{identity}.blockers")
        scopes = [_scope(scope) for scope in _string_list(ticket["write_scopes"], f"{identity}.write_scopes")]
        if len(scopes) != len(set(scopes)):
            raise ValueError(f"{identity}: duplicate normalized write scopes")
        resources = ticket["required_resources"]
        if type(resources) is not dict or set(resources)-set(RESOURCES):
            raise ValueError(f"{identity}: unknown required resource")
        resources = {name: _integer(resources.get(name, 0), f"{identity}.{name}", high=1000) for name in RESOURCES}
        if (resources["agent_worker"], resources["integrator"]) not in ((1, 0), (0, 1)):
            raise ValueError(f"{identity}: consume exactly one worker OR one integrator")
        jobs[identity] = {"id": identity, "title": ticket["title"], "owner": ticket["owner"],
                          "phase": ticket["phase"], "status": ticket["status"], "priority": ticket["priority"],
                          "duration": ticket["estimated_minutes"], "dependencies": set(deps),
                          "explicit_dependencies": list(deps), "resources": resources, "scopes": scopes,
                          "blockers": list(ticket["blockers"]), "acceptance_criteria": list(ticket["acceptance_criteria"])}
    phases = {job["phase"] for job in jobs.values()}
    if enabled-phases:
        raise ValueError("enabled_phases references an unknown phase")
    gates = policy.get("phase_gates", {})
    if type(gates) is not dict:
        raise ValueError("phase_gates must map phase names to prerequisite ticket IDs")
    if set(gates)-phases:
        raise ValueError("phase_gates references an unknown phase")
    for phase, ids in gates.items():
        _string_list(ids, f"phase_gates.{phase}")
        if any(identity not in jobs for identity in ids):
            raise ValueError("phase_gates references an unknown ticket")
    for job in jobs.values():
        job["dependencies"].update(gates.get(job["phase"], []))
        if job["id"] in job["dependencies"]:
            raise ValueError("Ticket cannot depend on itself, including through a phase gate")
        if job["dependencies"]-jobs.keys():
            raise ValueError(f"{job['id']}: unknown dependency")
    if sum(len(job["dependencies"]) for job in jobs.values()) > 100_000:
        raise ValueError("Too many dependency edges")
    # Kahn's algorithm gives stable ordering and detects cycles without recursion.
    children = {identity: [] for identity in jobs}
    indegree = {identity: len(job["dependencies"]) for identity, job in jobs.items()}
    for identity, job in jobs.items():
        for dependency in job["dependencies"]:
            children[dependency].append(identity)
    ready = [identity for identity, count in indegree.items() if count == 0]
    heapq.heapify(ready)
    topology = []
    while ready:
        identity = heapq.heappop(ready)
        topology.append(identity)
        for child in sorted(children[identity]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(ready, child)
    if len(topology) != len(jobs):
        raise ValueError("Dependency or phase-gate cycle detected")
    return jobs, capacities, policy, enabled, gates, topology, children


def schedule_plan(plan: dict) -> dict:
    """Return a bounded, deterministic list schedule; execute nothing.

    Priority is ordered first, then longest downstream dependency path, then
    stable ticket ID. This is a transparent heuristic, not an optimal solver.
    Nonempty blockers are active holds even if the ticket is marked planned.
    """
    jobs, capacities, policy, enabled, gates, topology, children = _validate(plan)
    try:
        canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Plan metadata must be finite JSON-compatible values") from exc
    completed = {identity for identity, job in jobs.items() if job["status"] == "completed"}
    excluded, blocked = {}, {}
    for identity in topology:
        job = jobs[identity]
        if identity in completed:
            continue
        reasons = []
        if job["phase"] not in enabled:
            reasons.append({"code": "phase_disabled", "phase": job["phase"]})
        if job["status"] == "deferred":
            reasons.append({"code": "deferred", "detail": "Ticket is deliberately outside the active build scope"})
        if reasons:
            excluded[identity] = reasons
            continue
        if job["status"] == "blocked":
            reasons.append({"code": "declared_blocked", "detail": "Ticket is marked blocked in the supplied plan"})
        for detail in job["blockers"]:
            reasons.append({"code": "declared_blocker", "detail": detail})
        for resource, quantity in job["resources"].items():
            if quantity > capacities[resource]:
                reasons.append({"code": "resource_unavailable" if capacities[resource] == 0 else "insufficient_resource_capacity",
                                "resource": resource, "required": quantity, "capacity": capacities[resource]})
        unavailable_deps = sorted(dep for dep in job["dependencies"] if dep in blocked or dep in excluded)
        if unavailable_deps:
            reasons.append({"code": "dependency_blocked", "dependencies": unavailable_deps})
        if reasons:
            blocked[identity] = reasons
    running = {identity for identity, job in jobs.items() if job["status"] == "in_progress"}
    if running & (blocked.keys() | excluded.keys()):
        raise ValueError("An in-progress ticket has an unresolved blocker, unavailable resource or disabled phase")
    for identity in running:
        if not jobs[identity]["dependencies"] <= completed:
            raise ValueError("In-progress ticket prerequisites must already be completed")
    for identity in completed:
        if jobs[identity]["blockers"]:
            raise ValueError("Completed ticket still lists unresolved blockers")
        if not jobs[identity]["dependencies"] <= completed:
            raise ValueError("Completed ticket prerequisites must also be completed")
    runnable = set(jobs)-completed-set(blocked)-set(excluded)
    tails = {}
    next_path = {}
    for identity in reversed(topology):
        if identity not in runnable:
            continue
        descendants = [child for child in children[identity] if child in runnable]
        next_id = min(descendants, key=lambda child: (-tails[child], child)) if descendants else None
        tails[identity] = jobs[identity]["duration"]+(tails[next_id] if next_id else 0)
        next_path[identity] = next_id
    first = min(runnable, key=lambda identity: (-tails[identity], identity)) if runnable else None
    critical_ids, next_id = [], first
    while next_id is not None:
        critical_ids.append(next_id)
        next_id = next_path[next_id]
    def order(identity):
        return jobs[identity]["priority"], -tails[identity], identity
    dependency_ready = sorted((identity for identity in runnable-running if jobs[identity]["dependencies"] <= completed), key=order)
    used = {resource: 0 for resource in RESOURCES}
    active = {}
    proposed = []
    timeline = []
    done = set(completed)
    pending = set(runnable)-running
    ready_at = {}
    waits = {}

    def allocation_conflicts(identity):
        job = jobs[identity]
        conflicts = {}
        busy_resources = {resource for resource in RESOURCES
                          if used[resource]+job["resources"][resource] > capacities[resource]}
        if busy_resources:
            conflicts["resource_busy"] = busy_resources
        if any(job["owner"] == jobs[other]["owner"] for other in active):
            conflicts["owner_busy"] = {job["owner"]}
        conflicting_writers = {other for other in active
                               if scopes_conflict(job["scopes"], jobs[other]["scopes"])}
        if conflicting_writers:
            conflicts["write_scope_conflict"] = conflicting_writers
        return conflicts

    def allocate(identity, minute, already_running=False):
        if allocation_conflicts(identity):
            raise ValueError("In-progress tickets overcommit resources, duplicate an owner or have overlapping write scopes")
        job = jobs[identity]
        end = minute+job["duration"]
        active[identity] = end
        for resource in RESOURCES:
            used[resource] += job["resources"][resource]
        proposed.append({"id": identity, "title": job["title"], "owner": job["owner"],
                         "phase": job["phase"], "priority": job["priority"],
                         "start_minute": minute, "end_minute": end,
                         "estimated_minutes": job["duration"], "already_in_progress": already_running,
                         "time_basis": "assumed remaining effort" if already_running else "assumed future effort",
                         "required_resources": dict(job["resources"]), "write_scopes": list(job["scopes"]),
                         "effective_dependencies": sorted(job["dependencies"]),
                         "dependency_ready_minute": ready_at.get(identity, 0),
                         "ready_wait_minutes": minute-ready_at.get(identity, 0),
                         "wait_reasons": [{"code": code, "values": sorted(values)}
                                          for code, values in sorted(waits.get(identity, {}).items())],
                         "remaining_critical_path_minutes": tails[identity]})

    for identity in sorted(running, key=order):
        allocate(identity, 0, already_running=True)
    minute = 0
    while pending or active:
        finished = [identity for identity, end in active.items() if end <= minute]
        for identity in finished:
            for resource in RESOURCES:
                used[resource] -= jobs[identity]["resources"][resource]
            del active[identity]
            done.add(identity)
        ready = sorted((identity for identity in pending if jobs[identity]["dependencies"] <= done), key=order)
        for identity in ready:
            ready_at.setdefault(identity, minute)
            conflicts = allocation_conflicts(identity)
            if not conflicts:
                allocate(identity, minute)
                pending.remove(identity)
            else:
                for code, values in conflicts.items():
                    waits.setdefault(identity, {}).setdefault(code, set()).update(values)
        timeline.append({"minute": minute, "active_ticket_ids": sorted(active), "used_resources": dict(used)})
        if not active:
            if pending:
                raise ValueError("Remaining tickets cannot be scheduled under the supplied constraints")
            break
        minute = min(active.values())
    proposed.sort(key=lambda job: (job["start_minute"], job["priority"], job["id"]))
    make_record = lambda identity, reasons: {"id": identity, "title": jobs[identity]["title"],
                                            "phase": jobs[identity]["phase"], "reasons": reasons}
    return {
        "schema_version": REPORT_SCHEMA, "plan_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "build_time_only": True, "runtime_agents_enabled": False, "spawns_agents": False,
        "executes_tickets": False, "network_used": False,
        "estimate_basis": policy["estimate_basis"], "time_unit": "relative planning minutes",
        "algorithm": "bounded list scheduling: priority, remaining critical path, stable ID; no optimality claim",
        "resource_profile": capacities, "resource_basis": "Declared planning capacities; not hardware discovery",
        "owner_concurrency_limit": 1,
        "owner_assignment_basis": "Each named owner is one builder lane; pooled worker capacity does not duplicate that owner",
        "reserved_integrator": 1, "enabled_phases": sorted(enabled), "phase_gates": deepcopy(gates),
        "quality_gate_basis": "Gate ticket completion is asserted by plan status. This planner does not execute acceptance checks or certify quality.",
        "completed": sorted(completed),
        "dependency_ready_now": dependency_ready,
        "proposed_starts_at_zero": [job["id"] for job in proposed if job["start_minute"] == 0 and not job["already_in_progress"]],
        "scheduled": proposed,
        "blocked": [make_record(identity, blocked[identity]) for identity in sorted(blocked)],
        "excluded": [make_record(identity, excluded[identity]) for identity in sorted(excluded)],
        "critical_path_lower_bound_minutes": tails[first] if first else 0,
        "critical_path_ticket_ids": critical_ids,
        "critical_path_scope": "Remaining schedulable work only; ignores resource, owner and write contention, excludes blocked and future work",
        "estimated_makespan_minutes": max((job["end_minute"] for job in proposed), default=0),
        "current_enabled_scope_fully_schedulable": not blocked and not any(jobs[identity]["phase"] in enabled for identity in excluded),
        "resource_timeline": timeline,
        "counts": {"tickets": len(jobs), "completed": len(completed), "scheduled": len(proposed),
                   "blocked": len(blocked), "excluded": len(excluded)},
        "limitations": ["Durations are estimates; no calendar commitment is made",
                        "Completion statuses require independent acceptance evidence",
                        "The planner models declared resources and path ownership, not every real-world bottleneck",
                        "No product runtime AI or autonomous transaction capability is installed or enabled"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=ROOT/"config/build-ticket-plan.json")
    parser.add_argument("--output", type=Path, help="Write a new JSON file; existing output is protected")
    args = parser.parse_args()
    if args.output and args.output.exists():
        parser.error("Output exists; choose a new output path")
    report = schedule_plan(json.loads(args.plan.read_text(encoding="utf-8")))
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(payload)
        print(str(args.output.resolve()))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
