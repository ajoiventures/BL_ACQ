"""Supervise a bounded number of local acquisition dispatch polls."""

import argparse
import json
import os
import time

import httpx

from backend.core.acquisition_leases import MAX_LEASE_BATCHES, MAX_LEASE_SECONDS
from tools.run_leased_acquisition_worker import advance_run


def dispatch_once(port, token, *, tasks, batches, lease_seconds):
    if not (1 <= port <= 65535 and 1 <= tasks <= 100
            and 1 <= batches <= MAX_LEASE_BATCHES and 1 <= lease_seconds <= MAX_LEASE_SECONDS):
        raise ValueError("Invalid dispatcher bounds")
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        queue = client.get("/api/acquisition-worker-dispatch", params={"limit": tasks}).raise_for_status().json()["tasks"]
    reports = []
    for task in queue:
        try:
            report = advance_run(port, token, task["run_id"], batches, lease_seconds, scheduled=True,
                                 expected_task_id=task["task_id"])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 409:
                raise
            report = {"state": "CONFLICT", "committed_batches": None}
        except httpx.TransportError:
            # Leave the durable cursor and lease to the next supervisor poll.
            report = {"state": "TRANSPORT_UNCERTAIN", "committed_batches": None}
        except ValueError as exc:
            if str(exc) not in {"No runnable scheduled task", "Dispatch task was replaced before lease claim"}:
                raise
            report = {"state": "CONFLICT", "committed_batches": None}
        reports.append({"task_id": task["task_id"], "run_id": task["run_id"], **report})
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--tasks", type=int, default=1)
    parser.add_argument("--batches", type=int, default=1)
    parser.add_argument("--lease-seconds", type=int, default=30)
    parser.add_argument("--polls", type=int, choices=range(1, 101), default=1)
    parser.add_argument("--poll-seconds", type=float, default=1)
    args = parser.parse_args()
    if not 0 <= args.poll_seconds <= 60:
        parser.error("--poll-seconds must be between 0 and 60")
    token = os.environ.get("BR_FOUNDER_TOKEN")
    if not token:
        parser.error("BR_FOUNDER_TOKEN is required for local dispatch")
    for poll in range(args.polls):
        if poll:
            time.sleep(args.poll_seconds)
        report = dispatch_once(args.port, token, tasks=args.tasks,
                               batches=args.batches, lease_seconds=args.lease_seconds)
        print(json.dumps({"poll": poll + 1, "tasks": report}), flush=True)


if __name__ == "__main__":
    main()
