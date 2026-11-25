"""Durable, operator-enqueued acquisition work bound to one run and batch budget."""
from . import acquisition_leases as leases

def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS acq_worker_tasks (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES acq_runs(id),
        requested_batches INTEGER NOT NULL,
        committed_batches INTEGER NOT NULL DEFAULT 0,
        initial_cursor INTEGER NOT NULL,
        state TEXT NOT NULL,
        lease_id TEXT
    )""")
    if "context_sha256" not in {row[1] for row in db.execute("PRAGMA table_info(acq_worker_tasks)")}:
        db.execute("ALTER TABLE acq_worker_tasks ADD COLUMN context_sha256 TEXT")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS acq_one_active_task_per_run
        ON acq_worker_tasks(run_id) WHERE state IN ('QUEUED','RUNNING','PAUSED')""")


def public(row):
    value = dict(row)
    value.pop("lease_id")
    value["remaining_batches"] = value["requested_batches"] - value["committed_batches"]
    return value


def active(db, run_id):
    return db.execute("""SELECT * FROM acq_worker_tasks WHERE run_id=?
        AND state IN ('QUEUED','RUNNING','PAUSED')""", (run_id,)).fetchone()


def latest(db, run_id):
    row = db.execute("SELECT * FROM acq_worker_tasks WHERE run_id=? ORDER BY rowid DESC LIMIT 1",
                     (run_id,)).fetchone()
    return public(row) if row else None


def enqueue(db, run, task_id, batches, *, expected_version=None,
            context_sha256=None, current_context_sha256=None):
    if not 1 <= batches <= leases.MAX_LEASE_BATCHES:
        raise ValueError("Invalid scheduled batch budget")
    existing = db.execute("SELECT * FROM acq_worker_tasks WHERE id=?", (task_id,)).fetchone()
    if existing:
        if (existing["run_id"], existing["requested_batches"], existing["context_sha256"]) != (
                run["id"], batches, context_sha256):
            raise ValueError("Task ID reused with different inputs")
        return {**public(existing), "replay": True}
    if expected_version is not None and expected_version != run["version"]:
        raise ValueError("Stale run version; reload before scheduling")
    if context_sha256 is not None and context_sha256 != current_context_sha256:
        raise ValueError("Stale preparation context; preview again before scheduling")
    if run["state"] not in {"READY", "RUNNING"}:
        raise ValueError("Run must be ready or running before scheduling")
    if active(db, run["id"]) or leases.current(db, run["id"]):
        raise ValueError("Run already has an active task or lease")
    db.execute("""INSERT INTO acq_worker_tasks(id,run_id,requested_batches,initial_cursor,state,context_sha256)
                  VALUES(?,?,?,?,'QUEUED',?)""", (task_id, run["id"], batches, run["cursor"], context_sha256))
    return {**latest(db, run["id"]), "replay": False}


def bind_lease(db, run, task_id, lease_id, seconds, batches):
    task = active(db, run["id"])
    if task is None:
        if task_id is not None:
            raise ValueError("Scheduled task is no longer active")
        return leases.claim(db, run, lease_id, seconds, batches)
    if task_id != task["id"] or task["state"] == "PAUSED":
        raise ValueError("Select the active scheduled task")
    current = leases.current(db, run["id"])
    remaining = task["requested_batches"] - task["committed_batches"]
    if current is None and batches > remaining:
        raise ValueError("Lease exceeds the remaining scheduled budget")
    result = leases.claim(db, run, lease_id, seconds, batches)
    if not result["replay"]:
        db.execute("UPDATE acq_worker_tasks SET state='RUNNING',lease_id=? WHERE id=?",
                   (lease_id, task["id"]))
    return result


def require_task_advance(db, run_id, lease_id):
    task = active(db, run_id)
    if task is not None and (lease_id is None or task["lease_id"] != lease_id):
        raise ValueError("Scheduled advance requires a task-bound lease")


def after_step(db, run_id, state, action, lease_id, progressed):
    task = active(db, run_id)
    if task is None:
        return
    completed = task["committed_batches"] + int(progressed)
    if state in {"FAILED", "CANCELLED", "PAUSED"}:
        task_state = state
    elif state == "COMPLETED" or completed == task["requested_batches"]:
        task_state = "COMPLETED"
    elif action == "resume":
        task_state = "QUEUED"
    else:
        task_state = task["state"]
    if task_state == "COMPLETED" and state != "COMPLETED":
        leases.release(db, run_id, lease_id)
    db.execute("UPDATE acq_worker_tasks SET state=?,committed_batches=?,lease_id=? WHERE id=?",
               (task_state, completed, lease_id if task_state == "RUNNING" else None, task["id"]))


def release(db, run_id, lease_id):
    removed = leases.release(db, run_id, lease_id)
    if removed:
        db.execute("""UPDATE acq_worker_tasks SET state='QUEUED',lease_id=NULL
                      WHERE run_id=? AND state='RUNNING' AND lease_id=?""", (run_id, lease_id))
    return removed


def dispatchable(db, *, limit, include_quarantined, now):
    """Read the durable task outbox without granting a lease."""
    rows = db.execute("""
        SELECT t.id AS task_id,t.run_id,r.version AS run_version,r.backend AS requested_backend,
               t.requested_batches-t.committed_batches AS remaining_batches,t.context_sha256
        FROM acq_worker_tasks t
        JOIN acq_runs r ON r.id=t.run_id
        JOIN acq_snapshots s ON s.id=r.snapshot_id
        LEFT JOIN acq_worker_leases l ON l.run_id=t.run_id
        WHERE t.state IN ('QUEUED','RUNNING') AND r.state IN ('READY','RUNNING')
          AND t.committed_batches<t.requested_batches
          AND (l.run_id IS NULL OR l.expires_at<=?)
          AND (? OR NOT coalesce(json_extract(s.manifest,'$.research_quarantine_required'),0))
        ORDER BY t.rowid LIMIT ?
    """, (now, include_quarantined, limit)).fetchall()
    return [dict(row) for row in rows]
