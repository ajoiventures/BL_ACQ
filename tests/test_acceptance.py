"""Check settlement authorization and replay across a backup restore."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pilot.acceptance import acceptance, recovery_snapshot, settle
from pilot.founder_service import RECORD, SCOPE, prepare
from pilot.storage import Store


class AcceptanceChecks(unittest.TestCase):
    def test_unapproved_deal_has_no_settlement_side_effect(self):
        with TemporaryDirectory() as temp:
            db = Path(temp) / "pilot.sqlite3"
            prepare(db)
            with Store(db, scope=SCOPE, actor="pilot-reconciler") as store:
                before = store.evidence_for(RECORD)
                with self.assertRaisesRegex(RuntimeError, "approval"):
                    settle(store)
                self.assertEqual(store.evidence_for(RECORD), before)
                self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM pilot_tasks").fetchone()[0], 0)

    def test_recovered_service_has_distinct_sources_and_replays_once(self):
        with TemporaryDirectory() as temp:
            result = acceptance(temp)
            self.assertTrue(result["restored"])
            self.assertEqual(result["settled_invoices"], 2)
            with Store(Path(temp) / "restored.sqlite3", scope=SCOPE, actor="pilot-reconciler") as store:
                approval, = [d for d in store.decisions_for(RECORD) if d.outcome == "approve"]
                key = approval.decision_id + "/settlement"
                before = recovery_snapshot(store, key)
                self.assertEqual(len(before["founder"]["founder_drafts"]), 1)
                self.assertEqual(len(before["founder"]["founder_receipts"]), 3)
                self.assertEqual(len(before["ledger"]["entries"]), 6)
                self.assertEqual(settle(store), (key, before["ledger"]))
                self.assertEqual(recovery_snapshot(store, key), before)


if __name__ == "__main__":
    unittest.main()
