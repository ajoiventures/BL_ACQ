"""Valuation API authorization, immutable replay and preservation of parcel identity."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pilot.founder_service import Server
from pilot.contracts import Deal, Parcel
from pilot.storage import Store
from test_valuation_layer import request_fixture


class ValuationServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "test.sqlite3"
        self.start()

    def start(self):
        self.server = Server(self.database)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()

    def call(self, path, cookie="", body=None, origin=None):
        headers = {"Content-Type": "application/json", "Cookie": cookie}
        if origin:
            headers["Origin"] = origin
        request = Request(f"http://127.0.0.1:{self.server.server_port}" + path,
                          data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    def session(self, role="reviewer"):
        status, _, headers = self.call("/api/session", body={"actor": role, "token": self.server.keys[role]})
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";")[0]

    def test_auth_scope_and_same_origin(self):
        packet = request_fixture()
        self.assertEqual(self.call("/api/valuation/evaluate", body=packet)[0], 401)
        self.assertEqual(self.call("/api/valuation/evaluate", self.session("civic-reader"), packet)[0], 403)
        reviewer = self.session()
        self.assertEqual(self.call("/api/valuation/evaluate", reviewer, packet, "https://other.example")[0], 403)
        status, report, _ = self.call("/api/valuation/evaluate", reviewer, packet)
        self.assertEqual(status, 200)
        self.assertFalse(report["decision"]["execution_allowed"])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_runs").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM pilot_decisions").fetchone()[0], 0)

    def test_save_idempotency_restart_and_frozen_history(self):
        cookie = self.session()
        body = {"request_id": "valuation-save-001", "packet": request_fixture()}
        status, first, _ = self.call("/api/valuation/runs", cookie, body)
        self.assertEqual(status, 200)
        self.assertEqual(first["link_type"], "research_deal")
        self.assertEqual(self.call("/api/valuation/runs", cookie, body)[1], first)
        body["packet"]["market"]["price"] = 80
        self.assertEqual(self.call("/api/valuation/runs", cookie, body)[0], 409)
        body["request_id"] = "valuation-save-002"
        status, changed, _ = self.call("/api/valuation/runs", cookie, body)
        self.assertEqual(status, 200)
        self.assertNotEqual(first["packet_digest"], changed["packet_digest"])
        self.stop()
        self.start()
        self.assertEqual(self.call("/api/valuation/runs", cookie)[0], 401)
        renewed = self.session("founder")
        history = self.call("/api/valuation/runs", renewed)[1]["runs"]
        self.assertEqual(len(history), 2)
        restored = self.call("/api/valuation/runs/" + first["run_id"], renewed)[1]
        self.assertEqual(restored, first)

    def test_existing_deal_keeps_permanent_asset_identity(self):
        cookie = self.session()
        packet = request_fixture()
        packet["deal_id"] = "orchard-01"
        body = {"request_id": "parcel-valuation-001", "packet": packet}
        self.assertEqual(self.call("/api/valuation/runs", cookie, body)[0], 409)
        packet["asset_id"] = "orchard-parcel"
        status, saved, _ = self.call("/api/valuation/runs", cookie, body)
        self.assertEqual(status, 200)
        self.assertEqual(saved["link_type"], "existing_parcel_deal")
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM pilot_evidence WHERE kind='valuation'").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM pilot_decisions").fetchone()[0], 0)

    def test_research_deal_keeps_asset_and_rejected_save_does_not_consume_id(self):
        cookie = self.session()
        packet = request_fixture()
        body = {"request_id": "research-save-001", "packet": packet}
        status, saved, _ = self.call("/api/valuation/runs", cookie, body)
        self.assertEqual(status, 200)
        conflicting = deepcopy(packet)
        conflicting["asset_id"] = "different-asset"
        retry = {"request_id": "research-save-002", "packet": conflicting}
        self.assertEqual(self.call("/api/valuation/runs", cookie, retry)[0], 409)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_receipts").fetchone()[0], 1)
        retry["packet"] = packet
        self.assertEqual(self.call("/api/valuation/runs", cookie, retry)[1], saved)
        # Separate deal analyses may legitimately concern the same asset.
        another_deal = deepcopy(packet)
        another_deal["deal_id"] = "separate-research-deal"
        self.assertEqual(self.call("/api/valuation/runs", cookie,
            {"request_id": "research-save-003", "packet": another_deal})[0], 200)

    def test_idempotent_replay_rechecks_new_canonical_deal_identity(self):
        cookie = self.session()
        packet = request_fixture()
        body = {"request_id": "research-canonical-001", "packet": packet}
        self.assertEqual(self.call("/api/valuation/runs", cookie, body)[0], 200)
        # A canonical deal can be created after the research snapshot. A replay
        # must not bypass a now-observable conflict merely because its receipt exists.
        with Store(self.database, scope="commercial", actor="founder") as store:
            store.save(Parcel("different-canonical-parcel", "test", "different-apn"))
            store.save(Deal(packet["deal_id"], "different-canonical-parcel", "Canonical deal"))
        self.assertEqual(self.call("/api/valuation/runs", cookie, body)[0], 409)
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_receipts").fetchone()[0], 1)

    def test_concurrent_research_saves_serialize_asset_identity(self):
        cookie = self.session()
        one, two = request_fixture(), request_fixture()
        two["asset_id"] = "competing-asset"
        bodies = [{"request_id": "parallel-valuation-001", "packet": one},
                  {"request_id": "parallel-valuation-002", "packet": two}]
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda body: self.call("/api/valuation/runs", cookie, body), bodies))
        self.assertEqual(sorted(response[0] for response in responses), [200, 409])
        with sqlite3.connect(self.database) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_runs").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM valuation_receipts").fetchone()[0], 1)

    def test_request_digest_detects_corruption_without_revaluation(self):
        cookie = self.session()
        body = {"request_id": "integrity-save-001", "packet": request_fixture()}
        status, saved, _ = self.call("/api/valuation/runs", cookie, body)
        self.assertEqual(status, 200)
        url = "/api/valuation/runs/" + saved["run_id"]
        # Historical retrieval is independent of a later engine version or policy.
        with patch("pilot.valuation_layer.MODEL_VERSION", "future-model"), patch(
                "pilot.valuation_store.evaluate", side_effect=AssertionError("Historical runs must not be recalculated")):
            self.assertEqual(self.call(url, cookie)[1], saved)
            self.assertEqual(len(self.call("/api/valuation/runs", cookie)[1]["runs"]), 1)
            altered = deepcopy(saved["request"])
            altered["market"]["price"] += 1
            with sqlite3.connect(self.database) as connection:
                connection.execute("UPDATE valuation_runs SET request_json=? WHERE run_id=?",
                                   (json.dumps(altered), saved["run_id"]))
            self.assertEqual(self.call(url, cookie)[0], 409)
            self.assertEqual(self.call("/api/valuation/runs", cookie)[0], 409)
        # A replay must not quietly return the corrupted frozen row either.
        self.assertEqual(self.call("/api/valuation/runs", cookie, body)[0], 409)

    def test_stored_report_and_row_identity_are_checked(self):
        cookie = self.session()
        _, saved, _ = self.call("/api/valuation/runs", cookie,
                               {"request_id": "metadata-save-001", "packet": request_fixture()})
        url = "/api/valuation/runs/" + saved["run_id"]
        mismatched_report = deepcopy(saved["report"])
        mismatched_report["request"]["asset_id"] = "wrong-report-asset"
        for column, value in (("report_json", json.dumps(mismatched_report)),
                              ("report_json", "not-json"),
                              ("model_version", "unexpected-model"),
                              ("asset_id", "wrong-row-asset")):
            with self.subTest(column=column, value=value):
                with sqlite3.connect(self.database) as connection:
                    connection.execute(
                        "UPDATE valuation_runs SET report_json=?,model_version=?,asset_id=? WHERE run_id=?",
                        (json.dumps(saved["report"]), saved["report"]["model_version"],
                         saved["request"]["asset_id"], saved["run_id"]))
                    # Column names above are fixed test constants, not request input.
                    connection.execute(f"UPDATE valuation_runs SET {column}=? WHERE run_id=?", (value, saved["run_id"]))
                self.assertEqual(self.call(url, cookie)[0], 409)

    def test_receipt_cannot_return_another_valid_snapshot(self):
        cookie = self.session()
        first = {"request_id": "receipt-save-001", "packet": request_fixture()}
        self.assertEqual(self.call("/api/valuation/runs", cookie, first)[0], 200)
        second = deepcopy(first)
        second["request_id"] = "receipt-save-002"
        second["packet"]["market"]["price"] += 1
        _, saved, _ = self.call("/api/valuation/runs", cookie, second)
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE valuation_receipts SET run_id=? WHERE request_id=?",
                               (saved["run_id"], first["request_id"]))
        self.assertEqual(self.call("/api/valuation/runs", cookie, first)[0], 409)

    def test_invalid_model_returns_validation_error_not_server_failure(self):
        cookie = self.session()
        packet = request_fixture()
        packet["assumptions"]["wacc"] = 0
        status, result, _ = self.call("/api/valuation/evaluate", cookie, packet)
        self.assertEqual(status, 400)
        self.assertIn("error", result)
        self.assertEqual(self.call("/api/valuation/runs/VR-" + "0" * 24, cookie)[0], 404)


if __name__ == "__main__":
    unittest.main()
