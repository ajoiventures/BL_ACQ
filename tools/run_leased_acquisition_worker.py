"""Advance one existing loopback acquisition run with a bounded worker lease."""
import argparse
import json
import os
import uuid

import httpx

from backend.core.acquisition_leases import MAX_LEASE_BATCHES, MAX_LEASE_SECONDS


def advance_run(port, token, run_id, batches, seconds, scheduled=False, *, expected_task_id=None):
    if not (1 <= port <= 65535 and (scheduled or 1 <= batches <= MAX_LEASE_BATCHES)
            and 1 <= seconds <= MAX_LEASE_SECONDS):
        raise ValueError("invalid worker bounds")
    run_id = str(uuid.UUID(run_id))
    lease_id = str(uuid.uuid4())
    path = f"/api/acquisition-runs/{run_id}"
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        payload = {
            "lease_id": lease_id, "seconds": seconds, "batches": batches,
        }
        if scheduled:
            task = client.get(path + "/worker-task").raise_for_status().json()["task"]
            if task is None or task["state"] not in {"QUEUED", "RUNNING"}:
                raise ValueError("No runnable scheduled task")
            if expected_task_id is not None and task["id"] != expected_task_id:
                raise ValueError("Dispatch task was replaced before lease claim")
            remaining = task["remaining_batches"]
            payload.update(task_id=task["id"], batches=min(remaining, batches) if batches else remaining)
        claimed = client.post(path + "/worker-lease", json=payload).raise_for_status().json()
        if claimed["lease_id"] != lease_id:
            raise ValueError("API did not return the requested lease")
        advanced = 0
        try:
            run = client.get(path).raise_for_status().json()
            for _ in range(claimed["remaining"]):
                if run["state"] not in {"READY", "RUNNING"}:
                    break
                try:
                    next_run = client.post(path + "/step", json={
                        "version": run["version"], "action": "advance", "lease_id": lease_id,
                    }).raise_for_status().json()
                except httpx.TransportError:
                    # Read the durable cursor before deciding whether the request committed.
                    # Never resubmit an ambiguous mutation.
                    next_run = client.get(path).raise_for_status().json()
                    if (next_run["version"] != run["version"] + 1
                            or next_run["cursor"] <= run["cursor"]):
                        raise
                advanced += int(next_run["cursor"] > run["cursor"])
                run = next_run
        finally:
            try:
                client.delete(path + "/worker-lease/" + lease_id)
            except httpx.TransportError:
                # The durable lease expires if the API is unavailable.
                pass
        return {"run_id": run_id, "committed_batches": advanced, "state": run["state"],
                "cursor": run["cursor"], "total": run["total"],
                "requested_backend": run["backend"], "actual_backend": run["actual_backend"],
                "error": run["error"], "offer_ready": run["offer_ready"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id")
    parser.add_argument("--port", type=int, default=8000)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--batches", type=int)
    mode.add_argument("--scheduled", action="store_true")
    parser.add_argument("--lease-seconds", type=int, default=30)
    args = parser.parse_args()
    token = os.environ.get("BR_ACQ_WORKER_TOKEN") or os.environ.get("BR_FOUNDER_TOKEN")
    if not token:
        parser.error("BR_ACQ_WORKER_TOKEN or BR_FOUNDER_TOKEN is required")
    report = advance_run(args.port, token, args.run_id, args.batches, args.lease_seconds, args.scheduled)
    print(json.dumps(report, indent=2))
    return 2 if report["state"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
