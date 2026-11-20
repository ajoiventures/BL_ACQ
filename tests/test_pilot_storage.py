"""Regression cases for SQLite pilot contracts, migration and lease ownership."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest

from pilot.contracts import Deal, Decision, Evidence, Parcel
from pilot.storage import MIGRATIONS, Store


class StorageTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = Path(directory.name) / "pilot.sqlite"
        self.now = 1000

    def open(self, actor="operator", scope="commercial"):
        return Store(self.db, scope=scope, actor=actor, clock=lambda: self.now)

    def seed(self, store):
        store.save(Parcel("parcel-1", "County A", "001"))
        return store.save(Deal("deal-1", "parcel-1", "Synthetic opportunity"))

    def test_clean_and_populated_migrations(self):
        # Create a populated v1 fixture. A foreign application owns its own table.
        with sqlite3.connect(self.db) as legacy:
            legacy.execute("CREATE TABLE other_application(x)")
            legacy.execute("INSERT INTO other_application VALUES(123)")
            legacy.execute("CREATE TABLE pilot_core_migrations(version INTEGER PRIMARY KEY)")
            for statement in MIGRATIONS[0]:
                legacy.execute(statement)
            legacy.execute("INSERT INTO pilot_core_migrations VALUES(1)")
            legacy.execute("INSERT INTO pilot_parcels VALUES('commercial','p','County A','01','older')")
            legacy.execute("INSERT INTO pilot_deals VALUES('commercial','d','p','Existing deal','older')")
        legacy.close()
        for _ in range(2):
            with self.open() as store:
                self.assertEqual(store.get_deal("d").title, "Existing deal")
                self.assertEqual(store.connection.execute("SELECT x FROM other_application").fetchone()[0], 123)
                self.assertEqual(store.connection.execute("SELECT count(*) FROM pilot_core_migrations").fetchone()[0], len(MIGRATIONS))
                task = store.enqueue("old-deal-task", "d", "review")
                self.assertEqual(task.attempt, 0)
                self.assertEqual(len(store.history(task.task_id)), 1)

    def test_newer_version_is_preserved(self):
        with self.open() as store:
            store.connection.execute("INSERT INTO pilot_core_migrations VALUES (?)", (len(MIGRATIONS) + 1,))
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            self.open()
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT max(version) FROM pilot_core_migrations").fetchone()[0], len(MIGRATIONS) + 1)

    def test_failed_migration_rolls_back_ddl_and_version(self):
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE pilot_deals(existing TEXT)")
        conn.commit()
        with self.assertRaises(sqlite3.OperationalError):
            self.open()
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertEqual(tables, ["pilot_deals"])

    def test_records_and_cross_domain_boundaries(self):
        evidence = Evidence("e1", "deal-1", "sales", "fixture-001", "2026-11-19", "three sales")
        decision = Decision("d1", "deal-1", "review", "Check recorded sales", "e1")
        with self.open() as store:
            deal = self.seed(store)
            store.save(evidence)
            store.save(evidence)
            store.save(decision)
            store.save(Deal("another", "parcel-1", "Synthetic comparison"))
            with self.assertRaises(sqlite3.IntegrityError):
                store.save(Decision("d2", "another", "review", "Wrong evidence", "e1"))
            with self.assertRaises(ValueError):
                store.save(Deal(deal.deal_id, deal.parcel_id, "Conflicting replay"))
            with self.assertRaises(ValueError):
                store.save(Evidence("e2", deal.deal_id, "permit", "fixture", "yesterday", "received"))
        with self.open("reviewer") as reopened:
            self.assertEqual(reopened.get_deal("deal-1"), deal)
            self.assertEqual(reopened.evidence_for("deal-1"), [evidence])
            self.assertEqual(reopened.decisions_for("deal-1"), [decision])
            self.assertEqual(reopened.connection.execute("SELECT created_by FROM pilot_decisions").fetchone()[0], "operator")
        with self.open(scope="family") as other:
            self.assertIsNone(other.get_deal("deal-1"))
            self.assertEqual(other.evidence_for("deal-1"), [])
            with self.assertRaises(sqlite3.IntegrityError):
                other.save(evidence)
            self.seed(other)
            with self.assertRaises(sqlite3.IntegrityError):
                other.save(decision)

    def test_transaction_rolls_back_seed_and_checkpoint(self):
        with self.open() as store:
            store.connection.execute("CREATE TABLE synthetic_checkpoint(marker TEXT)")
            with self.assertRaises(ValueError):
                with store.transaction():
                    self.seed(store)
                    store.connection.execute("INSERT INTO synthetic_checkpoint VALUES ('checkpoint-1')")
                    raise ValueError("Abort both")
            self.assertIsNone(store.get_deal("deal-1"))
            self.assertEqual(store.connection.execute("SELECT count(*) FROM synthetic_checkpoint").fetchone()[0], 0)

    def test_only_one_concurrent_claim_and_one_concurrent_enqueue(self):
        with self.open() as store:
            self.seed(store)
        barrier = Barrier(4)

        def worker(i):
            with self.open(f"worker-{i}") as store:
                barrier.wait(timeout=8)
                store.enqueue("job", "deal-1", "screen")
                return store.claim()

        with ThreadPoolExecutor(max_workers=4) as executor:
            leases = [x for x in executor.map(worker, range(4)) if x]
        self.assertEqual(len(leases), 1)
        with self.open(leases[0].claimed_by) as store:
            self.assertEqual([e["event"] for e in store.history("job")], ["queued", "claimed"])
            with self.assertRaises(ValueError):
                store.enqueue("job", "deal-1", "different")
            store.complete(leases[0], "passed")
            store.complete(leases[0], "passed")  # duplicate acknowledgement
            with self.assertRaises(ValueError):
                store.complete(leases[0], "different")
            self.assertEqual(store.get_task("job").state, "completed")
            self.assertIsNone(store.claim())

    def test_retry_and_expiry_keep_attempt_history(self):
        with self.open("first") as first, self.open("second") as second:
            self.seed(first)
            first.enqueue("job", "deal-1", "screen")
            lease = first.claim(lease_seconds=2)
            with self.assertRaises(ValueError):
                second.complete(lease)
            first.retry(lease, "input unavailable")
            renewed = second.claim(lease_seconds=5)
            first.retry(lease, "input unavailable")  # receipt replay after re-claim
            with self.assertRaises(ValueError):
                first.complete(lease)
            self.now += 5
            with self.assertRaises(ValueError):
                second.complete(renewed)
            final = first.claim()
            self.assertEqual(final.attempt, 3)
            with self.assertRaises(ValueError):
                second.retry(renewed, "late retry")
            first.complete(final)
            history = first.history("job")
            self.assertEqual([x["event"] for x in history],
                             ["queued", "claimed", "retry", "claimed", "expired", "claimed", "completed"])
            self.assertEqual([e["actor"] for e in history if e["event"] == "claimed"], ["first", "second", "first"])
            with self.assertRaises(sqlite3.IntegrityError):
                first.connection.execute("DELETE FROM pilot_task_events")
        with self.open() as reopened:
            self.assertEqual(len(reopened.history("job")), 7)

    def test_task_isolation_and_validation(self):
        with self.open() as store, self.open(scope="civic") as civic:
            self.seed(store)
            store.enqueue("job", "deal-1", "screen")
            with self.assertRaises(ValueError):
                store.claim(lease_seconds=0)
            lease = store.claim()
            self.assertIsNone(civic.claim())
            self.assertEqual(civic.history("job"), [])
            with self.assertRaises(ValueError):
                civic.complete(lease)

    def test_claim_request_replay_never_takes_another_job(self):
        with self.open() as first:
            self.seed(first)
            self.assertIsNone(first.claim(request_id="empty"))
            first.enqueue("a", "deal-1", "screen")
            first.enqueue("b", "deal-1", "screen")
            self.assertIsNone(first.claim(request_id="empty"))
            lease = first.claim(request_id="poll-1")
        with self.open() as reopened:
            self.assertEqual(reopened.claim(request_id="poll-1"), lease)
            self.assertEqual(len(reopened.history("a")), 2)
            reopened.complete(lease)
            self.assertIsNone(reopened.claim(request_id="poll-1"))
            self.assertEqual(reopened.claim(request_id="poll-2").task_id, "b")


if __name__ == "__main__":
    unittest.main()
