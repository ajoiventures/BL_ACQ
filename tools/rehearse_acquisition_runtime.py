"""Exercise local acquisition persistence against a disposable SQLite database."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
RUNS = "/api/acquisition-runs"


@contextmanager
def server(database, scratch, name, tokens, source, worker_run_id=None):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {**os.environ, "BR_DB": str(database), "BR_FOUNDER_TOKEN": tokens["founder"],
           "BR_AUDIT_TOKEN": tokens["auditor"], "BR_OPERATIONS_TOKEN": tokens["operations"]}
    if source == "orange_2026_final_roll":
        env["BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT"] = "1"
    if worker_run_id is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        env.update(BR_ACQ_WORKER_TOKEN=tokens["worker"], BR_ACQ_WORKER_RUN_ID=worker_run_id,
                   BR_ACQ_WORKER_EXPIRES_AT=expires_at.isoformat())
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (scratch / f"{name}.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
             "--port", str(port)],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, creationflags=flags,
        )
        try:
            url = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"local API exited, see {name}.log")
                try:
                    ready = httpx.get(url + "/api/ready", timeout=1, trust_env=False)
                    if ready.status_code == 200 and ready.json() == {"status": "ready"}:
                        response = httpx.get(url + RUNS, timeout=1, trust_env=False)
                        if response.status_code == 401:
                            break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError(f"local API did not start, see {name}.log")
            yield url
        finally:
            # An abrupt stop after committed work is intentional in this fixture.
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def read_state(database, run_id):
    with sqlite3.connect(database) as conn:
        return {
            "cursor_version": conn.execute(
                "SELECT cursor,version FROM acq_runs WHERE id=?", (run_id,)
            ).fetchone(),
            "batch_rows": conn.execute(
                "SELECT count(*) FROM acq_batches WHERE run_id=?", (run_id,)
            ).fetchone()[0],
            "result_rows": conn.execute(
                "SELECT count(*) FROM acq_results WHERE run_id=?", (run_id,)
            ).fetchone()[0],
            "audit_rows": conn.execute(
                "SELECT count(*) FROM audit WHERE object_id=?", (run_id,)
            ).fetchone()[0],
        }


def start(client, token, mode, source):
    payload = {"request_id": f"local-rehearsal-{mode}", "backend": mode, "batch_size": 1000,
               "snapshot_source": source}
    run = client.post(RUNS, headers=headers(token), json=payload).raise_for_status().json()
    replay = client.post(RUNS, headers=headers(token), json=payload).raise_for_status().json()
    if replay["id"] != run["id"]:
        raise ValueError("start retry did not return the original run")
    return run


def step(client, token, run):
    return client.post(f"{RUNS}/{run['id']}/step", headers=headers(token),
                       json={"version": run["version"], "action": "advance"})


def complete(client, token, run):
    while run["state"] in {"READY", "RUNNING"}:
        run = step(client, token, run).raise_for_status().json()
    if run["state"] != "COMPLETED" or run["cursor"] != run["total"]:
        raise ValueError(f"run failed: {run['error']}")
    return run


def exercise(scratch, source):
    scratch.mkdir(exist_ok=False)
    database = scratch / "acquisition-rehearsal.db"
    tokens = {role: secrets.token_hex(24) for role in ("founder", "auditor", "operations")}
    founder = tokens["founder"]
    with server(database, scratch, "first", tokens, source) as url, httpx.Client(
        base_url=url, timeout=30, trust_env=False
    ) as client:
        run = start(client, founder, "cuda", source)
        if client.get(f"{RUNS}/{run['id']}", headers=headers(tokens["operations"])).status_code != 403:
            raise ValueError("operations user read commercial work")
        if step(client, tokens["auditor"], run).status_code != 403:
            raise ValueError("auditor was allowed to mutate a run")
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: step(client, founder, run), range(2)))
        status = sorted(r.status_code for r in responses)
        if status != [200, 409]:
            raise ValueError(f"same-version race produced unexpected statuses: {status}")
        saved = next(r.json() for r in responses if r.status_code == 200)
        expected = read_state(database, run["id"])
        if expected["batch_rows"] != 1 or expected["result_rows"] != 1000:
            raise ValueError("first batch was not committed exactly once")

    with server(database, scratch, "restart", tokens, source) as url, httpx.Client(
        base_url=url, timeout=30, trust_env=False
    ) as client:
        resumed = client.get(f"{RUNS}/{run['id']}", headers=headers(founder)).raise_for_status().json()
        if resumed != saved or read_state(database, run["id"]) != expected:
            raise ValueError("restart did not preserve the committed batch")
        # Trigger a failure after the batch receipt insert, before the first result insert.
        with sqlite3.connect(database) as conn:
            conn.execute("""CREATE TRIGGER rehearsal_reject_result BEFORE INSERT ON acq_results
                          BEGIN SELECT RAISE(ABORT, 'rehearsal result failure'); END""")
        failed = step(client, founder, resumed)
        if failed.status_code != 500 or read_state(database, run["id"]) != expected:
            raise ValueError("failed batch left partial state or audit history")
        with sqlite3.connect(database) as conn:
            conn.execute("DROP TRIGGER rehearsal_reject_result")
        gpu = complete(client, founder, resumed)
        cpu = complete(client, founder, start(client, founder, "cpu_reference", source))

    if gpu["snapshot_id"] != cpu["snapshot_id"] or gpu["actual_backend"] != "cuda":
        raise ValueError("source snapshot or actual hardware differs")
    fields = ("start", "end", "numeric_input_sha256", "input_sha256", "results_sha256", "counts")
    for a, b in zip(gpu["batches"], cpu["batches"], strict=True):
        if any(a[k] != b[k] for k in fields):
            raise ValueError("CPU and CUDA batch results differ")
    final = read_state(database, gpu["id"])
    if final["result_rows"] != gpu["total"] or gpu["offer_ready"] or cpu["offer_ready"]:
        raise ValueError("unexpected result totals or production authority")
    with sqlite3.connect(database) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity failed")
        previous = "GENESIS"
        audit_count = 0
        for body, prev_hash, sha in conn.execute("SELECT body,prev_hash,hash FROM audit ORDER BY seq"):
            if previous != prev_hash or hashlib.sha256((previous + body).encode()).hexdigest() != sha:
                raise ValueError("audit chain invalid")
            previous = sha
            audit_count += 1
    return {
        "mode": "disposable_loopback_api", "performed_utc": datetime.now(timezone.utc).isoformat(),
        "source_snapshot_id": gpu["snapshot_id"], "snapshot_source": source,
        "retained_source_records": gpu["total"],
        "same_version_concurrent_statuses": status, "abrupt_restart_restored_committed_batch": True,
        "deliberate_result_insert_failure_status": failed.status_code, "failed_batch_rolled_back": True,
        "commercial_operations_denied": True, "auditor_write_denied": True,
        "cpu_cuda_exact_batch_parity": True, "audit_events_verified": audit_count,
        "gpu_batch_receipts": gpu["batches"], "cpu_batch_receipts": cpu["batches"],
        "sqlite_integrity": "ok", "offer_ready": 0,
        "independent_acceptance": False,
    }


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("scratch", type=Path)
    args.add_argument("output", type=Path)
    args.add_argument("--snapshot-source", choices=("retained", "orange_2026_final_roll"), default="retained")
    parsed = args.parse_args()
    report = exercise(parsed.scratch.resolve(), parsed.snapshot_source)
    with parsed.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
    print(f"{report['retained_source_records']} retained rows, exact CPU/CUDA parity")


if __name__ == "__main__":
    main()
