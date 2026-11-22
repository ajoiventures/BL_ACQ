"""Safety and scheduling semantics for the offline builder planner."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.schedule_builder_work import schedule_plan


ROOT = Path(__file__).resolve().parents[1]


def ticket(identity, duration=5, **changes):
    value = {"id": identity, "title": f"Build {identity}", "owner": f"builder_{identity}",
             "phase": "foundation", "dependencies": [], "status": "planned", "priority": 0,
             "estimated_minutes": duration, "required_resources": {"agent_worker": 1},
             "write_scopes": [f"work/{identity}"], "acceptance_criteria": ["Independent review passed"],
             "blockers": []}
    value.update(changes)
    return value


def plan(*tickets, workers=3, enabled=None, gates=None):
    return {"schema_version": "br.build-ticket-plan.v1",
            "resource_profile": {"agent_worker": workers, "integrator": 1, "cuda_device": 0, "r_runtime": 0},
            "scheduling_policy": {"reserved_integrator": 1,
                                  "enabled_phases": enabled or ["foundation"],
                                  "estimate_basis": "Assumed effort, not measured or promised time",
                                  "phase_gates": gates or {}},
            "tickets": list(tickets)}


def rows(report):
    return {row["id"]: row for row in report["scheduled"]}


class BuilderScheduleChecks(unittest.TestCase):
    def assert_safe(self, report):
        jobs = rows(report)
        for job in jobs.values():
            for dependency in job["effective_dependencies"]:
                if dependency in jobs:
                    self.assertLessEqual(jobs[dependency]["end_minute"], job["start_minute"])
                else:
                    self.assertIn(dependency, report["completed"])
        for point in report["resource_timeline"]:
            active = [jobs[identity] for identity in point["active_ticket_ids"]]
            self.assertEqual(len({job["owner"] for job in active}), len(active))
            for resource, capacity in report["resource_profile"].items():
                usage = sum(job["required_resources"][resource] for job in active)
                self.assertLessEqual(usage, capacity)
                self.assertEqual(usage, point["used_resources"][resource])
            for i, left in enumerate(active):
                for right in active[i+1:]:
                    for a in left["write_scopes"]:
                        for b in right["write_scopes"]:
                            a_parts, b_parts = Path(a).parts, Path(b).parts
                            self.assertFalse(a_parts == b_parts[:len(a_parts)] or b_parts == a_parts[:len(b_parts)])
        self.assertGreaterEqual(report["estimated_makespan_minutes"], report["critical_path_lower_bound_minutes"])
        self.assertEqual(sum(report["counts"][k] for k in ("completed", "scheduled", "blocked", "excluded")),
                         report["counts"]["tickets"])

    def test_three_workers_plus_reserved_integrator(self):
        report = schedule_plan(plan(ticket("A", 10), ticket("B", 5), ticket("C", 5), ticket("D", 1),
                                    ticket("I", 7, required_resources={"integrator": 1})))
        result = rows(report)
        self.assertEqual({identity: result[identity]["start_minute"] for identity in result},
                         {"A": 0, "B": 0, "C": 0, "I": 0, "D": 5})
        self.assertEqual(result["D"]["ready_wait_minutes"], 5)
        self.assertIn({"code": "resource_busy", "values": ["agent_worker"]}, result["D"]["wait_reasons"])
        self.assertEqual(report["resource_timeline"][0]["used_resources"]["integrator"], 1)
        self.assert_safe(report)

    def test_owner_is_one_lane_even_with_free_worker_capacity(self):
        report = schedule_plan(plan(ticket("A", 10, owner="quant_builder"),
                                    ticket("B", 8, owner="quant_builder"), ticket("C", 5)))
        result = rows(report)
        self.assertEqual(result["B"]["start_minute"], 10)
        self.assertEqual(result["B"]["wait_reasons"], [{"code": "owner_busy", "values": ["quant_builder"]}])
        self.assertEqual(result["C"]["start_minute"], 0)
        self.assertEqual(report["owner_concurrency_limit"], 1)
        self.assert_safe(report)

    def test_ancestor_write_scopes_serialize_but_similar_names_do_not(self):
        report = schedule_plan(plan(ticket("A", 10, write_scopes=["pilot/core/"]),
                                    ticket("B", 5, write_scopes=["./pilot/core/file.py"]),
                                    ticket("C", 7, write_scopes=["pilot/core2/file.py"])))
        result = rows(report)
        self.assertEqual(result["B"]["start_minute"], 10)
        self.assertEqual(result["C"]["start_minute"], 0)
        self.assertEqual(result["B"]["wait_reasons"], [{"code": "write_scope_conflict", "values": ["A"]}])
        self.assert_safe(report)

    def test_repository_root_scope_blocks_every_writer(self):
        report = schedule_plan(plan(ticket("A", 10, write_scopes=["."]), ticket("B", 1)))
        self.assertEqual(rows(report)["B"]["start_minute"], 10)
        self.assert_safe(report)

    def test_phase_gate_is_a_real_prerequisite(self):
        report = schedule_plan(plan(ticket("A", 5), ticket("G", 7, dependencies=["A"]),
                                    ticket("E", 9, phase="engine"),
                                    enabled=["foundation", "engine"], gates={"engine": ["G"]}))
        self.assertEqual(rows(report)["E"]["start_minute"], 12)
        self.assertEqual(rows(report)["E"]["effective_dependencies"], ["G"])
        self.assertEqual(report["dependency_ready_now"], ["A"])
        self.assert_safe(report)

    def test_dependency_join_and_critical_path_have_independent_expected_times(self):
        report = schedule_plan(plan(ticket("A", 5), ticket("B", 7, dependencies=["A"]),
                                    ticket("C", 3, dependencies=["A"]), ticket("D", 2, dependencies=["B", "C"])))
        self.assertEqual(report["critical_path_ticket_ids"], ["A", "B", "D"])
        self.assertEqual(report["critical_path_lower_bound_minutes"], 14)
        self.assertEqual(report["estimated_makespan_minutes"], 14)
        self.assertEqual(rows(report)["D"]["start_minute"], 12)
        self.assert_safe(report)

    def test_priority_precedes_path_length_and_stable_ids_break_ties(self):
        source = plan(ticket("A", 2), ticket("B", 7, priority=1),
                      ticket("C", 2, priority=1, dependencies=["B"]), workers=1)
        self.assertEqual(rows(schedule_plan(source))["A"]["start_minute"], 0)
        source["tickets"][0]["priority"] = 1
        self.assertEqual(rows(schedule_plan(source))["B"]["start_minute"], 0)
        ties = schedule_plan(plan(ticket("B"), ticket("A"), workers=1))
        self.assertEqual(ties["proposed_starts_at_zero"], ["A"])

    def test_zero_gpu_r_and_external_blockers_propagate_without_fake_completion(self):
        report = schedule_plan(plan(
            ticket("A", required_resources={"agent_worker": 1, "cuda_device": 1}),
            ticket("B", dependencies=["A"]),
            ticket("C", required_resources={"agent_worker": 1, "r_runtime": 1}),
            ticket("D", blockers=["Representative evidence is missing"]),
            ticket("E", status="blocked"), ticket("F", status="deferred"),
            ticket("G", phase="assistive_ai"), ticket("H", dependencies=["G"]), ticket("I")))
        self.assertEqual(report["counts"], {"tickets": 9, "completed": 0, "scheduled": 1, "blocked": 6, "excluded": 2})
        blocked = {item["id"]: item["reasons"] for item in report["blocked"]}
        self.assertEqual(blocked["A"][0]["code"], "resource_unavailable")
        self.assertEqual(blocked["A"][0]["resource"], "cuda_device")
        self.assertEqual(blocked["B"][0], {"code": "dependency_blocked", "dependencies": ["A"]})
        self.assertEqual(blocked["H"][0], {"code": "dependency_blocked", "dependencies": ["G"]})
        self.assertFalse(report["current_enabled_scope_fully_schedulable"])
        self.assertEqual(report["critical_path_ticket_ids"], ["I"])
        self.assert_safe(report)

    def test_completed_dependencies_satisfy_gates_without_consuming_capacity(self):
        report = schedule_plan(plan(ticket("A", 99, status="completed"), ticket("B", 7, dependencies=["A"])))
        self.assertEqual(report["completed"], ["A"])
        self.assertEqual(report["critical_path_lower_bound_minutes"], 7)
        self.assertEqual(rows(report)["B"]["start_minute"], 0)
        self.assert_safe(report)
        report = schedule_plan(plan(ticket("A", status="completed")))
        self.assertEqual(report["scheduled"], [])
        self.assertEqual(report["resource_timeline"], [])
        self.assertEqual(report["estimated_makespan_minutes"], 0)

    def test_in_progress_reserves_remaining_effort_at_zero(self):
        report = schedule_plan(plan(ticket("A", 7, status="in_progress", owner="quant_builder"),
                                    ticket("B", 3, owner="quant_builder"),
                                    ticket("I", 2, required_resources={"integrator": 1})))
        result = rows(report)
        self.assertTrue(result["A"]["already_in_progress"])
        self.assertEqual(result["A"]["time_basis"], "assumed remaining effort")
        self.assertEqual(result["B"]["start_minute"], 7)
        self.assertEqual(report["proposed_starts_at_zero"], ["I"])
        self.assert_safe(report)

    def test_in_progress_overcommit_owner_and_write_collisions_reject(self):
        cases = [plan(*(ticket(identity, status="in_progress") for identity in "ABCD")),
                 plan(ticket("A", status="in_progress", owner="same"), ticket("B", status="in_progress", owner="same")),
                 plan(ticket("A", status="in_progress", write_scopes=["pilot"]),
                      ticket("B", status="in_progress", write_scopes=["pilot/a.py"]))]
        for source in cases:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "overcommit"):
                schedule_plan(source)

    def test_invalid_dependencies_cycles_and_phase_gates_reject(self):
        cases = [plan(ticket("A", dependencies=["missing"])),
                 plan(ticket("A", dependencies=["A"])),
                 plan(ticket("A", dependencies=["B"]), ticket("B", dependencies=["A"])),
                 plan(ticket("A"), ticket("A")),
                 plan(ticket("A"), gates={"foundation": ["missing"]}),
                 plan(ticket("A"), gates={"foundation": ["A"]}),
                 plan(ticket("A", dependencies=["B"]), ticket("B", phase="engine"),
                      enabled=["foundation", "engine"], gates={"engine": ["A"]}),
                 plan(ticket("A"), gates={"unknown": []}),
                 plan(ticket("A"), enabled=["typo"])]
        for source in cases:
            with self.subTest(source=source), self.assertRaises(ValueError):
                schedule_plan(source)

    def test_malformed_status_and_integer_fields_reject(self):
        for key, value in (("status", "finished"), ("status", []), ("estimated_minutes", 0),
                           ("estimated_minutes", 2.5), ("estimated_minutes", True),
                           ("priority", -1), ("priority", True), ("owner", ""),
                           ("acceptance_criteria", []), ("blockers", [1])):
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                schedule_plan(plan(ticket("A", **{key: value})))
        for source in ({}, [], {**plan(ticket("A")), "schema_version": "wrong"}):
            with self.assertRaises(ValueError):
                schedule_plan(source)

    def test_resources_are_explicit_and_impossible_requests_are_held(self):
        for request in ({}, {"agent_worker": 2}, {"agent_worker": True},
                        {"agent_worker": 1, "integrator": 1}, {"agent_worker": 1, "unknown": 1},
                        {"agent_worker": 1, "cuda_device": -1}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                schedule_plan(plan(ticket("A", required_resources=request)))
        for resource, quantity in (("agent_worker", 4), ("integrator", 0), ("r_runtime", True)):
            source = plan(ticket("A")); source["resource_profile"][resource] = quantity
            with self.subTest(resource=resource), self.assertRaises(ValueError):
                schedule_plan(source)
        source = plan(ticket("A", required_resources={"agent_worker": 1, "cuda_device": 2}))
        source["resource_profile"]["cuda_device"] = 1
        report = schedule_plan(source)
        self.assertEqual(report["blocked"][0]["reasons"][0]["code"], "insufficient_resource_capacity")
        self.assertEqual(report["scheduled"], [])

    def test_unsafe_ambiguous_and_duplicate_scopes_reject(self):
        for scopes in (["../pilot"], ["/tmp/work"], ["C:\\work"], ["pilot/*"],
                       ["pilot/", "./pilot"], ["pilot\nfile"]):
            with self.subTest(scopes=scopes), self.assertRaises(ValueError):
                schedule_plan(plan(ticket("A", write_scopes=scopes)))

    def test_completed_and_running_statuses_require_consistent_prerequisites(self):
        for status in ("completed", "in_progress"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                schedule_plan(plan(ticket("A"), ticket("B", dependencies=["A"], status=status)))
            with self.subTest(status=status, blockers=True), self.assertRaises(ValueError):
                schedule_plan(plan(ticket("A", status=status, blockers=["Missing evidence"])))
        with self.assertRaises(ValueError):
            schedule_plan(plan(ticket("A", status="in_progress", required_resources={"agent_worker": 1, "cuda_device": 1})))

    def test_determinism_immutable_inputs_and_finite_json(self):
        source = plan(ticket("B"), ticket("A"), ticket("C", dependencies=["A"]))
        before = deepcopy(source)
        report = schedule_plan(source)
        self.assertEqual(source, before)
        self.assertEqual(report, schedule_plan(source))
        source["tickets"].reverse()
        reordered = schedule_plan(source)
        self.assertEqual(report["scheduled"], reordered["scheduled"])
        self.assertEqual(report["resource_timeline"], reordered["resource_timeline"])
        self.assertNotEqual(report["plan_sha256"], reordered["plan_sha256"])
        json.dumps(report, allow_nan=False)
        source["metadata"] = float("nan")
        with self.assertRaises(ValueError):
            schedule_plan(source)

    def test_actual_repository_plan_remains_offline_and_capacity_safe(self):
        source = json.loads((ROOT/"config/build-ticket-plan.json").read_text(encoding="utf-8"))
        report = schedule_plan(source)
        self.assertEqual(report["counts"]["tickets"], len(source["tickets"]))
        self.assertTrue(report["build_time_only"])
        for key in ("spawns_agents", "executes_tickets", "network_used", "runtime_agents_enabled"):
            self.assertFalse(report[key])
        self.assertFalse(any(row["phase"] in ("assistive_ai", "runtime_agents") for row in report["scheduled"]))
        self.assert_safe(report)

    def test_cli_stdout_new_artifact_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory(prefix="br-builder-schedule-") as temporary:
            folder = Path(temporary)
            source = folder/"plan.json"; source.write_text(json.dumps(plan(ticket("A"))), encoding="utf-8")
            output = folder/"schedule.json"
            command = [sys.executable, str(ROOT/"tools/schedule_builder_work.py"), "--plan", str(source)]
            stdout = subprocess.run(command, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(stdout.stdout)["counts"]["scheduled"], 1)
            saved = subprocess.run(command+["--output", str(output)], capture_output=True, text=True, check=True)
            self.assertEqual(saved.stdout.strip(), str(output.resolve()))
            payload = output.read_bytes()
            self.assertEqual(json.loads(payload)["schema_version"], "br.builder-schedule.v1")
            protected = subprocess.run(command+["--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(protected.returncode, 0)
            self.assertIn("Output exists", protected.stderr)
            self.assertEqual(output.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
