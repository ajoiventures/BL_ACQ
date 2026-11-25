"""Queue one acquisition worker task on the local API after reviewing a run."""
import argparse
import json
import os
from uuid import UUID

import httpx

from backend.core.acquisition_leases import MAX_LEASE_BATCHES


def queue_task(port, token, run_id, task_id, batches, expected_version, context_sha256=None, parcel_key=None, site_receipt_id=None):
    if not (1 <= port <= 65535 and 1 <= batches <= MAX_LEASE_BATCHES and expected_version >= 1):
        raise ValueError("Invalid port, batch budget or reviewed run version")
    path = f"/api/acquisition-runs/{UUID(str(run_id))}/worker-task"
    body = {"task_id": str(UUID(str(task_id))), "batches": batches,
            "expected_version": expected_version, "context_sha256": context_sha256, "parcel_key": parcel_key, "site_receipt_id": site_receipt_id}
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        return client.post(path, json=body).raise_for_status().json()


def preview_task(port, token, run_id, parcel_key=None, site_receipt_id=None):
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    path = f"/api/acquisition-runs/{UUID(str(run_id))}/preparation-context"
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, timeout=30,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        params = {key: value for key, value in {"parcel_key": parcel_key, "site_receipt_id": site_receipt_id}.items() if value}
        return client.get(path, params=params).raise_for_status().json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=UUID)
    parser.add_argument("task_id", type=UUID, nargs="?")
    parser.add_argument("--preview", action="store_true", help="Show run context without scheduling")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--batches", type=int)
    parser.add_argument("--expected-version", type=int)
    parser.add_argument("--context-sha256", help="Digest returned by --preview")
    parser.add_argument("--parcel-key", help="Include evidence for one parcel from the run")
    parser.add_argument("--site-receipt-id", help="Include a retained parcel site discovery receipt")
    args = parser.parse_args()
    scheduling_fields = (args.task_id, args.batches, args.expected_version)
    if args.preview and any(value is not None for value in (*scheduling_fields, args.context_sha256)):
        parser.error("--preview cannot be combined with scheduling arguments")
    if not args.preview and any(value is None for value in scheduling_fields):
        parser.error("Scheduling requires task_id, --batches and --expected-version")
    token = os.environ.get("BR_FOUNDER_TOKEN")
    if not token:
        parser.error("BR_FOUNDER_TOKEN is required")
    try:
        if args.preview:
            result = preview_task(args.port, token, args.run_id, args.parcel_key, args.site_receipt_id)
        else:
            result = queue_task(args.port, token, args.run_id, args.task_id,
                                args.batches, args.expected_version, args.context_sha256, args.parcel_key, args.site_receipt_id)
    except httpx.HTTPStatusError as exc:
        parser.exit(2, f"Request rejected with HTTP {exc.response.status_code}\n")
    print(json.dumps(result, indent=2))
