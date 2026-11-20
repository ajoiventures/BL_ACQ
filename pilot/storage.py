"""SQLite storage and a leased task queue for the local synthetic pilot."""
from contextlib import contextmanager
from dataclasses import astuple, fields
from datetime import date
import sqlite3
import time

from .contracts import Deal, Decision, Evidence, Parcel, Task


SCOPES = {"commercial", "family", "civic"}
TABLES = {Parcel: "pilot_parcels", Deal: "pilot_deals", Evidence: "pilot_evidence",
          Decision: "pilot_decisions"}
MIGRATIONS = (
    (
        """CREATE TABLE pilot_parcels(
            scope TEXT NOT NULL, parcel_id TEXT NOT NULL, jurisdiction TEXT NOT NULL,
            apn TEXT NOT NULL, created_by TEXT NOT NULL, PRIMARY KEY(scope,parcel_id),
            UNIQUE(scope,jurisdiction,apn))""",
        """CREATE TABLE pilot_deals(
            scope TEXT NOT NULL, deal_id TEXT NOT NULL, parcel_id TEXT NOT NULL,
            title TEXT NOT NULL, created_by TEXT NOT NULL, PRIMARY KEY(scope,deal_id),
            FOREIGN KEY(scope,parcel_id) REFERENCES pilot_parcels(scope,parcel_id))""",
        """CREATE TABLE pilot_evidence(
            scope TEXT NOT NULL, evidence_id TEXT NOT NULL, deal_id TEXT NOT NULL,
            kind TEXT NOT NULL, source TEXT NOT NULL, observed_on TEXT NOT NULL,
            value TEXT NOT NULL, created_by TEXT NOT NULL, PRIMARY KEY(scope,evidence_id),
            UNIQUE(scope,deal_id,evidence_id),
            FOREIGN KEY(scope,deal_id) REFERENCES pilot_deals(scope,deal_id))""",
        """CREATE TABLE pilot_decisions(
            scope TEXT NOT NULL, decision_id TEXT NOT NULL, deal_id TEXT NOT NULL,
            outcome TEXT NOT NULL, rationale TEXT NOT NULL, evidence_id TEXT NOT NULL,
            created_by TEXT NOT NULL, PRIMARY KEY(scope,decision_id),
            FOREIGN KEY(scope,deal_id,evidence_id) REFERENCES pilot_evidence(scope,deal_id,evidence_id))""",
    ),
    (
        """CREATE TABLE pilot_tasks(
            scope TEXT NOT NULL, task_id TEXT NOT NULL, deal_id TEXT NOT NULL, kind TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','claimed','completed')),
            attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt>=0), claimed_by TEXT, lease_until INTEGER,
            CHECK((state='claimed' AND claimed_by IS NOT NULL AND lease_until IS NOT NULL)
               OR (state!='claimed' AND claimed_by IS NULL AND lease_until IS NULL)),
            PRIMARY KEY(scope,task_id),
            FOREIGN KEY(scope,deal_id) REFERENCES pilot_deals(scope,deal_id))""",
        "CREATE INDEX pilot_claim_queue ON pilot_tasks(scope,state,lease_until)",
        """CREATE TABLE pilot_task_events(
            seq INTEGER PRIMARY KEY, scope TEXT NOT NULL, task_id TEXT NOT NULL, attempt INTEGER NOT NULL,
            event TEXT NOT NULL, actor TEXT NOT NULL, at INTEGER NOT NULL, detail TEXT NOT NULL,
            UNIQUE(scope,task_id,attempt,event),
            FOREIGN KEY(scope,task_id) REFERENCES pilot_tasks(scope,task_id))""",
        """CREATE TRIGGER pilot_history_immutable_update BEFORE UPDATE ON pilot_task_events
           BEGIN SELECT RAISE(ABORT,'Task history is append-only'); END""",
        """CREATE TRIGGER pilot_history_immutable_delete BEFORE DELETE ON pilot_task_events
           BEGIN SELECT RAISE(ABORT,'Task history is append-only'); END""",
    ),
    (
        """CREATE TABLE pilot_claim_receipts(
            scope TEXT NOT NULL, actor TEXT NOT NULL, request_id TEXT NOT NULL,
            task_id TEXT, attempt INTEGER, PRIMARY KEY(scope,actor,request_id),
            CHECK((task_id IS NULL) = (attempt IS NULL)),
            FOREIGN KEY(scope,task_id) REFERENCES pilot_tasks(scope,task_id))""",
    ),
)


def require_text(*values):
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError("Expected nonempty text")


def migrate(connection):
    """Apply each missing version in one serialized transaction shared by all openers."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute("CREATE TABLE IF NOT EXISTS pilot_core_migrations(version INTEGER PRIMARY KEY)")
        versions = [row[0] for row in connection.execute(
            "SELECT version FROM pilot_core_migrations ORDER BY version")]
        if versions != list(range(1, len(versions) + 1)) or len(versions) > len(MIGRATIONS):
            raise ValueError("Unsupported pilot storage migration history")
        for number, statements in enumerate(MIGRATIONS[len(versions):], len(versions) + 1):
            for statement in statements:
                connection.execute(statement)
            connection.execute("INSERT INTO pilot_core_migrations VALUES (?)", (number,))
        connection.commit()
    except BaseException:
        connection.rollback()
        raise


class Store:
    """One actor and domain per connection. Use a separate instance per thread."""
    def __init__(self, db_path, *, scope, actor, clock=time.time):
        require_text(actor)
        if scope not in SCOPES:
            raise ValueError("Unknown pilot scope")
        self.scope, self.actor, self.clock = scope, actor, clock
        self.connection = sqlite3.connect(db_path, timeout=10, isolation_level=None)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA foreign_keys=ON")
            migrate(self.connection)
        except BaseException:
            self.connection.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.connection.close()

    @contextmanager
    def transaction(self):
        # A caller may combine a core decision with an application checkpoint.
        # A nested savepoint rolls back its own failed operation even if the caller catches it.
        if self.connection.in_transaction:
            self.connection.execute("SAVEPOINT pilot_operation")
            try:
                yield
            except BaseException:
                self.connection.execute("ROLLBACK TO pilot_operation")
                raise
            finally:
                self.connection.execute("RELEASE pilot_operation")
            return
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def save(self, record):
        table = TABLES.get(type(record))
        if table is None:
            raise TypeError("Expected a Parcel, Deal, Evidence or Decision")
        values = astuple(record)
        require_text(*values)
        if isinstance(record, Evidence):
            observed = date.fromisoformat(record.observed_on)
            if observed.isoformat() != record.observed_on:
                raise ValueError("Use YYYY-MM-DD for observed_on")
        names = [field.name for field in fields(record)]
        columns = ",".join(names)
        with self.transaction():
            existing = self.connection.execute(
                f"SELECT {columns} FROM {table} WHERE scope=? AND {names[0]}=?",
                (self.scope, values[0])).fetchone()
            if existing is not None:
                if tuple(existing) != values:
                    raise ValueError(f"Conflicting replay for {names[0]}")
            else:
                placeholders = ",".join("?" for _ in values)
                self.connection.execute(
                    f"INSERT INTO {table}(scope,{columns},created_by) VALUES (?,{placeholders},?)",
                    (self.scope, *values, self.actor))
        return record

    def get_deal(self, deal_id):
        rows = self._deal_records(Deal, deal_id)
        return rows[0] if rows else None

    def _deal_records(self, cls, deal_id):
        names = ",".join(field.name for field in fields(cls))
        cursor = self.connection.execute(
            f"SELECT {names} FROM {TABLES[cls]} WHERE scope=? AND deal_id=? ORDER BY rowid",
            (self.scope, deal_id))
        return [cls(*row) for row in cursor]

    def evidence_for(self, deal_id):
        return self._deal_records(Evidence, deal_id)

    def decisions_for(self, deal_id):
        return self._deal_records(Decision, deal_id)

    def get_task(self, task_id):
        names = ",".join(field.name for field in fields(Task))
        row = self.connection.execute(
            f"SELECT {names} FROM pilot_tasks WHERE scope=? AND task_id=?",
            (self.scope, task_id)).fetchone()
        return Task(*row) if row else None

    def _event(self, task_id, attempt, event, now, detail=""):
        self.connection.execute(
            "INSERT INTO pilot_task_events(scope,task_id,attempt,event,actor,at,detail) VALUES(?,?,?,?,?,?,?)",
            (self.scope, task_id, attempt, event, self.actor, now, detail))

    def history(self, task_id):
        return [dict(row) for row in self.connection.execute(
            "SELECT seq,attempt,event,actor,at,detail FROM pilot_task_events "
            "WHERE scope=? AND task_id=? ORDER BY seq", (self.scope, task_id))]

    def enqueue(self, task_id, deal_id, kind):
        """The task ID is the idempotency key within the domain."""
        require_text(task_id, deal_id, kind)
        with self.transaction():
            old = self.get_task(task_id)
            if old:
                if (old.deal_id, old.kind) != (deal_id, kind):
                    raise ValueError("Task ID already belongs to another request")
                return old
            self.connection.execute(
                "INSERT INTO pilot_tasks(scope,task_id,deal_id,kind) VALUES(?,?,?,?)",
                (self.scope, task_id, deal_id, kind))
            self._event(task_id, 0, "queued", int(self.clock()))
            return self.get_task(task_id)

    def claim(self, lease_seconds=60, *, request_id=None):
        """Reserve one eligible task and return its attempt number as a fencing token."""
        if type(lease_seconds) is not int or lease_seconds <= 0:
            raise ValueError("lease_seconds must be a positive integer")
        if request_id is not None:
            require_text(request_id)
        with self.transaction():
            now = int(self.clock())
            if request_id is not None:
                receipt = self.connection.execute(
                    """SELECT task_id,attempt FROM pilot_claim_receipts
                       WHERE scope=? AND actor=? AND request_id=?""",
                    (self.scope, self.actor, request_id)).fetchone()
                if receipt is not None:
                    task = self.get_task(receipt["task_id"])
                    if (task and task.state == "claimed" and task.attempt == receipt["attempt"]
                            and task.lease_until > now):
                        return task
                    return None
            row = self.connection.execute(
                """SELECT task_id,state,attempt FROM pilot_tasks
                   WHERE scope=? AND (state='queued' OR (state='claimed' AND lease_until<=?))
                   ORDER BY rowid LIMIT 1""", (self.scope, now)).fetchone()
            if request_id is not None:
                assignment = (row["task_id"], row["attempt"] + 1) if row else (None, None)
                self.connection.execute(
                    "INSERT INTO pilot_claim_receipts(scope,actor,request_id,task_id,attempt) VALUES(?,?,?,?,?)",
                    (self.scope, self.actor, request_id, *assignment))
            if row is None:
                return None
            task_id, state, attempt = row
            if state == "claimed":
                self._event(task_id, attempt, "expired", now)
            self.connection.execute(
                """UPDATE pilot_tasks SET state='claimed',attempt=?,claimed_by=?,lease_until=?
                   WHERE scope=? AND task_id=?""",
                (attempt + 1, self.actor, now + lease_seconds, self.scope, task_id))
            self._event(task_id, attempt + 1, "claimed", now)
            return self.get_task(task_id)

    def complete(self, task, detail=""):
        self._finish(task, "completed", detail)

    def retry(self, task, detail):
        require_text(detail)
        self._finish(task, "retry", detail)

    def _finish(self, task, event, detail):
        if not isinstance(task, Task) or task.scope != self.scope or task.claimed_by != self.actor:
            raise ValueError("Caller does not own this attempt")
        if not isinstance(detail, str):
            raise ValueError("Expected text detail")
        with self.transaction():
            now = int(self.clock())
            previous = self.connection.execute(
                """SELECT actor,detail FROM pilot_task_events
                   WHERE scope=? AND task_id=? AND attempt=? AND event=?""",
                (self.scope, task.task_id, task.attempt, event)).fetchone()
            if previous is not None:
                if tuple(previous) != (self.actor, detail):
                    raise ValueError("Conflicting completion or retry receipt")
                return
            updated = self.connection.execute(
                """UPDATE pilot_tasks SET state=?,claimed_by=NULL,lease_until=NULL
                   WHERE scope=? AND task_id=? AND attempt=? AND state='claimed'
                   AND claimed_by=? AND lease_until>?""",
                ("completed" if event == "completed" else "queued", self.scope, task.task_id,
                 task.attempt, self.actor, now))
            if updated.rowcount != 1:
                raise ValueError("Attempt expired or no longer owns this task")
            self._event(task.task_id, task.attempt, event, now, detail)
