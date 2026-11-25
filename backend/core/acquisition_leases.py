"""Persistent leases for bounded acquisition workers."""
import time

MAX_LEASE_SECONDS = 120
MAX_LEASE_BATCHES = 100


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS acq_worker_leases (
        run_id TEXT PRIMARY KEY REFERENCES acq_runs(id),
        lease_id TEXT NOT NULL,
        expires_at REAL NOT NULL,
        budget INTEGER NOT NULL,
        remaining INTEGER NOT NULL
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS acq_worker_claims (
        lease_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL REFERENCES acq_runs(id),
        seconds INTEGER NOT NULL
    )""")


def claim(db, run, lease_id, seconds, batches):
    if run["state"] not in {"READY", "RUNNING"}:
        raise ValueError("Run must be ready or running to claim a worker lease")
    if not 1 <= seconds <= MAX_LEASE_SECONDS or not 1 <= batches <= MAX_LEASE_BATCHES:
        raise ValueError("Invalid worker lease bounds")
    prior = db.execute("SELECT run_id,seconds FROM acq_worker_claims WHERE lease_id=?", (lease_id,)).fetchone()
    existing = current(db, run["id"])
    if existing:
        if (existing["lease_id"] != lease_id or existing["budget"] != batches
                or prior is None or tuple(prior) != (run["id"], seconds)):
            raise ValueError("Run already has an active worker lease")
        return {**existing, "replay": True}
    if prior is not None:
        raise ValueError("Worker lease ID was already used")
    db.execute("INSERT INTO acq_worker_claims VALUES(?,?,?)", (lease_id, run["id"], seconds))
    expires = time.time() + seconds
    db.execute("""INSERT INTO acq_worker_leases VALUES(?,?,?,?,?)
        ON CONFLICT(run_id) DO UPDATE SET lease_id=excluded.lease_id,
        expires_at=excluded.expires_at,budget=excluded.budget,remaining=excluded.remaining""",
        (run["id"], lease_id, expires, batches, batches))
    return {"run_id": run["id"], "lease_id": lease_id, "expires_at": expires,
            "budget": batches, "remaining": batches, "replay": False}


def current(db, run_id):
    row = db.execute("SELECT * FROM acq_worker_leases WHERE run_id=?", (run_id,)).fetchone()
    return dict(row) if row is not None and row["expires_at"] > time.time() else None


def require_advance(db, run_id, lease_id):
    active = current(db, run_id)
    if active is None and lease_id is None:
        return
    if active is None or active["lease_id"] != lease_id:
        raise ValueError("Active worker lease is required for this advance")
    if active["remaining"] <= 0:
        raise ValueError("Worker lease batch budget exhausted")


def after_step(db, run_id, state, action, lease_id):
    if state not in {"READY", "RUNNING"}:
        db.execute("DELETE FROM acq_worker_leases WHERE run_id=?", (run_id,))
    elif action == "advance" and lease_id is not None:
        db.execute("UPDATE acq_worker_leases SET remaining=remaining-1 WHERE run_id=?", (run_id,))


def release(db, run_id, lease_id):
    row = db.execute("SELECT lease_id FROM acq_worker_leases WHERE run_id=?", (run_id,)).fetchone()
    if row is None:
        return False
    if row[0] != lease_id:
        raise ValueError("Lease holder changed")
    db.execute("DELETE FROM acq_worker_leases WHERE run_id=?", (run_id,))
    return True
