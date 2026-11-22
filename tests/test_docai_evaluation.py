"""Fixture-backed tests of real native output crossing the metrics boundary."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.docai_metrics import EvaluationError, corpus_fingerprint, load_json
from tools.evaluate_docai_native import evaluate_native, write_evaluation


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "docai"


class NativeEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = load_json(FIXTURES / "manifest.json")
        cls.results = evaluate_native(cls.corpus, FIXTURES)

    def test_actual_reader_and_candidate_results_have_honest_denominators(self):
        report = self.results["report"]
        expected = {"documents": 9, "reported_documents": 9, "processing_status_correct": 9,
                    "labeled_fields": 54, "answerable_fields": 32, "abstention_required_fields": 22,
                    "proposals": 26, "correct_values": 26, "correct_spans": 26,
                    "grounded_correct_values": 26, "correct_abstentions": 22,
                    "missing_documents": 0, "missing_fields": 0, "unexpected_fields": 0,
                    "false_proposals": 0, "claimed_accepted_fields": 0}
        for name, value in expected.items():
            self.assertEqual(report["counts"][name], value, name)
        self.assertEqual(report["metrics"]["grounded_value_recall"],
                         {"numerator": 26, "denominator": 32, "value": 0.8125})
        self.assertEqual(report["processing_status_counts"],
                         {"complete": 6, "error": 1, "needs_ocr": 1, "partial": 1, "unsupported": 0})
        self.assertEqual(report["artifact_integrity"]["status"], "verified")

    def test_real_adverse_statuses_and_limits_are_retained(self):
        records = {record["document"]["document_id"]: record for record in self.results["execution"]["runs"]}
        malformed = records["DOC-SYN-004"]["extraction"]
        self.assertEqual(malformed["status"], "error")
        self.assertIn("MALFORMED_PDF", [error["code"] for error in malformed["errors"]])
        self.assertEqual(records["DOC-SYN-005"]["extraction"]["status"], "complete")
        self.assertEqual(records["DOC-SYN-107"]["extraction"]["status"], "needs_ocr")
        partial = records["DOC-SYN-108"]["extraction"]
        self.assertEqual(partial["status"], "partial")
        self.assertTrue(partial["coverage"]["truncated"])
        self.assertFalse(partial["coverage"]["complete"])
        self.assertEqual(partial["coverage"]["limits"]["max_text_bytes"], 150000)
        self.assertLessEqual(partial["coverage"]["processed_bytes"], 150000)
        self.assertEqual(records["DOC-SYN-108"]["candidates"], [])

    def test_csv_coverage_gap_is_visible_and_does_not_become_false_success(self):
        prediction = next(row for row in self.results["predictions"]["documents"]
                          if row["document_id"] == "DOC-SYN-002")
        self.assertEqual(prediction["processing_status"], "complete")
        self.assertEqual(len(prediction["fields"]), 6)
        self.assertTrue(all(field["decision"] == "abstain" for field in prediction["fields"]))
        cases = [case for case in self.results["report"]["cases"] if case["document_id"] == "DOC-SYN-002"]
        self.assertTrue(all(case["expected"] == "value" and not case["value_correct"] for case in cases))

    def test_actual_timing_and_unknown_review_cost_are_distinct(self):
        report = self.results["report"]
        self.assertEqual(report["latency"]["reported_documents"], 9)
        self.assertGreater(report["latency"]["total_ms"], 0)
        self.assertEqual(report["review_time"]["reported_documents"], 0)
        self.assertIsNone(report["review_time"]["mean_ms"])
        self.assertEqual(report["reported_cost"]["reported_documents"], 0)
        self.assertIsNone(report["reported_cost"]["total"])
        for row in self.results["predictions"]["documents"]:
            self.assertGreaterEqual(row["latency_ms"], 0)
            self.assertTrue(all(field["review_decision"] == "pending" for field in row["fields"]))

    def test_versioned_execution_evidence_is_native_without_provider_or_model(self):
        execution = self.results["execution"]
        self.assertFalse(execution["review_performed"])
        self.assertEqual(execution["provider_calls"], 0)
        self.assertEqual(execution["model_downloads"], 0)
        self.assertEqual(execution["corpus_sha256"], corpus_fingerprint(self.corpus))
        self.assertEqual(execution["source_sha256"]["tools/evaluate_docai_native.py"],
                         hashlib.sha256((ROOT / "tools/evaluate_docai_native.py").read_bytes()).hexdigest())
        self.assertEqual(execution["source_sha256"]["pilot/document_invoice.py"],
                         hashlib.sha256((ROOT / "pilot/document_invoice.py").read_bytes()).hexdigest())
        for record in execution["runs"]:
            extraction = record["extraction"]
            self.assertEqual(extraction["method"], "native")
            self.assertEqual(extraction["backend"], "cpu")
            self.assertIsNone(extraction["provider"])
            self.assertIsNone(extraction["model"])
            self.assertEqual(extraction["source_sha256"], record["document"]["content_sha256"])

    def test_changing_gold_cannot_supply_the_candidate_value(self):
        altered = deepcopy(self.corpus)
        altered["documents"] = [altered["documents"][0]]
        total = next(field for field in altered["documents"][0]["fields"] if field["field"] == "total_cents")
        total["canonical_value"] = "999"
        with patch("socket.socket", side_effect=AssertionError("No network permitted")):
            result = evaluate_native(altered, FIXTURES)
        total_output = next(field for field in result["predictions"]["documents"][0]["fields"]
                            if field["field"] == "total_cents")
        self.assertEqual(total_output["canonical_value"], "125000")
        self.assertEqual(result["report"]["counts"]["correct_values"], 5)
        self.assertEqual(result["report"]["counts"]["false_proposals"], 1)

    def test_runtime_failure_is_not_converted_into_an_abstention(self):
        single = deepcopy(self.corpus)
        single["documents"] = [single["documents"][0]]
        with patch("tools.evaluate_docai_native.extract_document", side_effect=RuntimeError("unexpected failure")):
            with self.assertRaisesRegex(RuntimeError, "unexpected failure"):
                evaluate_native(single, FIXTURES)

    def test_changed_implementation_during_run_is_rejected(self):
        single = deepcopy(self.corpus)
        single["documents"] = [single["documents"][0]]
        with patch("tools.evaluate_docai_native._source_hashes", side_effect=[{"source": "before"}, {"source": "after"}]):
            with self.assertRaisesRegex(EvaluationError, "changed during evaluation"):
                evaluate_native(single, FIXTURES)

    def test_bad_source_hash_fails_before_extraction(self):
        altered = deepcopy(self.corpus)
        altered["documents"][0]["source_sha256"] = "0" * 64
        with patch("tools.evaluate_docai_native.extract_document") as extract:
            with self.assertRaisesRegex(EvaluationError, "hash mismatch"):
                evaluate_native(altered, FIXTURES)
        extract.assert_not_called()

    def test_output_artifacts_are_replayable_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evaluation"
            write_evaluation(output, self.results)
            self.assertEqual({path.name for path in output.iterdir()},
                             {"predictions.json", "report.json", "execution.json"})
            report_bytes = (output / "report.json").read_bytes()
            self.assertEqual(json.loads(report_bytes), self.results["report"])
            with self.assertRaises(FileExistsError):
                write_evaluation(output, self.results)
            self.assertEqual((output / "report.json").read_bytes(), report_bytes)
            # Re-score measured predictions through the independent public CLI.
            command = [sys.executable, str(ROOT / "tools/docai_metrics.py"), "--corpus",
                       str(FIXTURES / "manifest.json"), "--predictions", str(output / "predictions.json"),
                       "--split", "holdout"]
            scored = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(scored.returncode, 0, scored.stderr)
            held_out = json.loads(scored.stdout)
            self.assertEqual(held_out["counts"]["documents"], 4)
            self.assertEqual(held_out["counts"]["correct_values"], 12)
            self.assertEqual(held_out["counts"]["correct_abstentions"], 12)


if __name__ == "__main__":
    unittest.main()
