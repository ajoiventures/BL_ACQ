"""Corporate case HTTP authorization, source ownership and real-case integration."""

from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pilot.corporate_case import evaluate_case, load_case
from pilot.founder_service import ROOT, Server


class CorporateServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "corporate.sqlite3"
        self.server = Server(self.database)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()

    def call(self, path, cookie="", body=None, *, raw=None, origin=None, content_type="application/json"):
        headers = {"Cookie": cookie, "Content-Type": content_type}
        if origin is not None:
            headers["Origin"] = origin
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        request = Request(f"http://127.0.0.1:{self.server.server_port}" + path, data=data, headers=headers)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            content = response.read().decode()
            result = json.loads(content) if response.headers["Content-Type"].startswith("application/json") else content
            return response.status, result, response.headers

    def session(self, role="reviewer"):
        status, _, headers = self.call("/api/session", body={"actor": role, "token": self.server.keys[role]})
        self.assertEqual(status, 200)
        return headers["Set-Cookie"].split(";")[0]

    def test_both_routes_enforce_current_commercial_identity_and_origin(self):
        self.assertEqual(self.call("/api/corporate/case")[0], 401)
        self.assertEqual(self.call("/api/corporate/evaluate", body={})[0], 401)
        civic = self.session("civic-reader")
        self.assertEqual(self.call("/api/corporate/case", civic)[0], 403)
        self.assertEqual(self.call("/api/corporate/evaluate", civic, {})[0], 403)
        reviewer = self.session()
        self.assertEqual(self.call("/api/corporate/case", reviewer, origin="https://other.example")[0], 403)
        self.assertEqual(self.call("/api/corporate/evaluate", reviewer, {}, origin="https://other.example")[0], 403)
        self.assertEqual(self.call("/api/corporate/evaluate", reviewer, {}, content_type="text/plain")[0], 403)
        status, result, headers = self.call("/api/corporate/case", reviewer)
        self.assertEqual(status, 200)
        self.assertEqual(result["actor"], "reviewer")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.call("/api/corporate/case", self.session("founder"))[0], 200)

    def test_real_cases_link_statements_and_withhold_failed_financing_returns(self):
        case, facts = load_case()
        cookie = self.session()
        results = {}
        for name in ("Base", "Downside", "Upside"):
            request = deepcopy(case)
            request["selected_case"] = name
            with self.subTest(case=name):
                status, bundle, _ = self.call("/api/corporate/evaluate", cookie, request)
                self.assertEqual(status, 200)
                self.assertEqual(bundle["case"], request)
                self.assertEqual(bundle["facts"], facts)
                report = bundle["report"]
                self.assertEqual(report["status"], "research_requires_review")
                self.assertFalse(report["execution_allowed"])
                self.assertTrue(report["historical_checks"]["all_reconciled"])
                self.assertTrue(report["projection"]["checks"]["all_reconciled"])
                self.assertEqual(report["source_balance_date"], "2025-08-31")
                self.assertEqual(report["model_start_date"], "2025-10-31")
                self.assertEqual(report["projection"]["forecast"][0]["period_end"], "2026-10-31")
                self.assertGreater(report["valuation"]["value_per_share"], 0)
                self.assertEqual(len(report["comparables"]["peers"]), 2)
                results[name] = report
        stressed_case = deepcopy(case)
        stressed_case["selected_case"] = "Base"
        stressed_case["acquisition"]["term_interest_rate"] = .50
        stressed_case["acquisition"]["revolver_limit"] = 0
        status, stressed_bundle, _ = self.call("/api/corporate/evaluate", cookie, stressed_case)
        self.assertEqual(status, 200)
        stress = stressed_bundle["report"]["acquisition"]
        self.assertEqual(stress["feasibility"]["status"], "not_feasible")
        self.assertIsNone(stress["returns"]["annual_irr"])
        self.assertIsNone(stress["returns"]["moic"])
        self.assertTrue(stress["feasibility"]["issues"])
        self.assertGreater(results["Upside"]["valuation"]["value_per_share"], results["Base"]["valuation"]["value_per_share"])

    def test_client_cannot_replace_source_facts_and_export_uses_server_evaluation_facts(self):
        cookie = self.session()
        _, original, _ = self.call("/api/corporate/case", cookie)
        case, facts = original["case"], original["facts"]
        client_facts = deepcopy(facts)
        client_facts["periods"]["2025"]["income_statement"]["revenue"] = 1
        self.assertEqual(self.call("/api/corporate/evaluate", cookie, case | {"facts": client_facts})[0], 400)
        self.assertEqual(self.call("/api/corporate/evaluate", cookie, {"case": case, "facts": client_facts})[0], 400)
        updated_facts = deepcopy(facts)
        updated_facts["review_status"] = "Test review metadata updated after the browser GET"
        with patch("pilot.corporate_case.load_case", return_value=(case, updated_facts)):
            status, bundle, _ = self.call("/api/corporate/evaluate", cookie, case)
        self.assertEqual(status, 200)
        self.assertEqual(bundle["facts"], updated_facts)
        self.assertNotEqual(bundle["facts"], original["facts"])
        expected = evaluate_case(case, updated_facts)
        self.assertEqual(bundle["report"]["input_digest"], expected["input_digest"])

    def test_malformed_cases_return_json_errors_without_a_server_failure(self):
        case, _ = load_case()
        cookie = self.session()
        invalid = [
            {}, case | {"case_id": None}, case | {"cases": []},
            case | {"selected_case": None}, case | {"selected_case": "No such case"},
            case | {"valuation": None}, case | {"assumption_notes": "not an array"},
        ]
        wrong_date = deepcopy(case)
        wrong_date["cases"][case["selected_case"]][0]["period_end"] = "2026-08-31"
        invalid.append(wrong_date)
        nonfinite = deepcopy(case)
        nonfinite["valuation"]["equity_beta"] = float("nan")
        invalid.append(nonfinite)
        for request in invalid:
            with self.subTest(request=request):
                status, result, _ = self.call("/api/corporate/evaluate", cookie, request)
                self.assertEqual(status, 400)
                self.assertIsInstance(result["error"], str)
        for raw in (b"null", b"[]", b"not json", b'{"x":' * 1100 + b"0" + b"}" * 1100):
            with self.subTest(raw_prefix=raw[:10]):
                self.assertEqual(self.call("/api/corporate/evaluate", cookie, raw=raw)[0], 400)

    def test_payload_limit_accepts_65536_bytes_and_rejects_one_more(self):
        case, _ = load_case()
        cookie = self.session()
        encoded = json.dumps(case).encode()
        self.assertLess(len(encoded), 65536)
        at_limit = encoded + b" " * (65536 - len(encoded))
        self.assertEqual(self.call("/api/corporate/evaluate", cookie, raw=at_limit)[0], 200)
        status, result, _ = self.call("/api/corporate/evaluate", cookie, raw=at_limit + b" ")
        self.assertEqual(status, 400)
        self.assertEqual(result["error"], "Invalid JSON request.")

    def test_calculation_and_unknown_mutation_routes_do_not_write_records_or_runs(self):
        case, _ = load_case()
        cookie = self.session()
        with sqlite3.connect(self.database) as connection:
            before = [connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                      for name in ("valuation_runs", "pilot_decisions", "pilot_evidence", "pilot_tasks", "founder_actions")]
        self.assertEqual(self.call("/api/corporate/evaluate", cookie, case)[0], 200)
        for path in ("/api/corporate/runs", "/api/corporate/orders", "/api/corporate/approve"):
            self.assertEqual(self.call(path, cookie, case)[0], 404)
        self.assertEqual(self.call("/api/corporate/evaluate", cookie)[0], 404)
        with sqlite3.connect(self.database) as connection:
            after = [connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                     for name in ("valuation_runs", "pilot_decisions", "pilot_evidence", "pilot_tasks", "founder_actions")]
        self.assertEqual(before, after)

    def test_unavailable_source_files_fail_closed_without_exposing_paths(self):
        cookie = self.session()
        with patch("pilot.corporate_case.load_case", side_effect=FileNotFoundError("sensitive-local-path")):
            status, result, _ = self.call("/api/corporate/case", cookie)
        self.assertEqual(status, 503)
        self.assertEqual(result["error"], "Corporate source case is unavailable.")

    def test_static_assets_and_client_dom_references_are_available(self):
        status, html, headers = self.call("/corporate.html")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])

        class Ids(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = set()

            def handle_starttag(self, tag, attrs):
                for key, value in attrs:
                    if key == "id":
                        self.ids.add(value)

        parser = Ids()
        parser.feed(html)
        script = (ROOT / "web/corporate.js").read_text()
        referenced = set(re.findall(r'(?:\$|text|table|statement|summaries|list)\("([^\"]+)"', script))
        self.assertFalse(referenced - parser.ids, referenced - parser.ids)
        for path, mime in (("/corporate.js", "javascript"), ("/corporate.css", "text/css")):
            status, _, headers = self.call(path)
            self.assertEqual(status, 200)
            self.assertIn(mime, headers["Content-Type"])


if __name__ == "__main__":
    unittest.main()
