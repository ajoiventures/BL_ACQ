"""Independent arithmetic and adverse-input checks for the Doc AI scorer."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import docai_metrics as metrics


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "docai"


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def small_corpus() -> dict:
    """Two documents, two answerable and two abstention labels, written by hand."""
    source = "Total 12.50\nDue 2027-01-02\n"
    source_hash = digest(source)
    total_span = {"page": 1, "text_sha256": source_hash,
                  "start": 6, "end": 11, "quote": "12.50"}
    date_span = {"page": 1, "text_sha256": source_hash,
                 "start": 16, "end": 26, "quote": "2027-01-02"}
    doc_a = {"document_id": "A", "split": "holdout", "origin": "synthetic",
             "source_file": "a.txt", "source_sha256": source_hash,
             "expected_processing_status": "complete",
             "reference_texts": [{"page": 1, "path": "a.txt", "sha256": source_hash}],
             "fields": [
                 {"field": "total_cents", "expectation": "value", "canonical_value": "1250",
                  "critical": True, "allowed_spans": [total_span]},
                 {"field": "due_date", "expectation": "value", "canonical_value": "2027-01-02",
                  "critical": True, "allowed_spans": [date_span]}]}
    doc_b = {"document_id": "B", "split": "holdout", "origin": "synthetic",
             "source_file": "b.txt", "source_sha256": digest("No supported values.\n"),
             "expected_processing_status": "complete", "reference_texts": [],
             "fields": [
                 {"field": name, "expectation": "abstain", "canonical_value": None,
                  "critical": True, "allowed_spans": [], "reason": "No supported value."}
                 for name in ("total_cents", "due_date")]}
    return {"schema_version": metrics.CORPUS_SCHEMA, "corpus_id": "independent-arithmetic",
            "version": 1, "scope": "native_invoice_contract_v1",
            "offset_unit": "unicode_codepoints", "documents": [doc_a, doc_b]}


def envelope(corpus: dict, documents: list | None = None) -> dict:
    return {"schema_version": metrics.PREDICTION_SCHEMA, "corpus_id": corpus["corpus_id"],
            "corpus_sha256": metrics.corpus_fingerprint(corpus), "scope": corpus["scope"],
            "documents": documents or []}


def proposed(name: str, value: str, span: dict | None, review: str = "pending") -> dict:
    return {"field": name, "decision": "propose", "canonical_value": value,
            "span": deepcopy(span), "review_decision": review}


def row(doc_id: str, fields: list, **usage) -> dict:
    return {"document_id": doc_id, "processing_status": "complete", "fields": fields, **usage}


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.corpus = small_corpus()
        self.spans = [field["allowed_spans"][0] for field in self.corpus["documents"][0]["fields"]]

    def test_hand_calculated_mixed_results(self):
        output = envelope(self.corpus, [
            row("A", [proposed("total_cents", "1250", self.spans[0]),
                      proposed("due_date", "2027-01-03", self.spans[1], "rejected")],
                latency_ms=10, review_ms=7, reported_cost_usd="0.003"),
            row("B", [proposed("total_cents", "999", None, "accepted"),
                      {"field": "due_date", "decision": "abstain"}],
                latency_ms=30, review_ms=None, reported_cost_usd="0.007")])
        report = metrics.evaluate(self.corpus, output)
        counts = report["counts"]
        expected_counts = {"documents": 2, "reported_documents": 2, "labeled_fields": 4,
                           "answerable_fields": 2, "abstention_required_fields": 2,
                           "proposals": 3, "answerable_proposals": 2, "correct_values": 1,
                           "correct_spans": 2, "grounded_correct_values": 1,
                           "abstentions": 1, "correct_abstentions": 1, "false_proposals": 2,
                           "claimed_accepted_fields": 1, "false_accepts": 1,
                           "critical_false_accepts": 1}
        for name, expected in expected_counts.items():
            self.assertEqual(counts[name], expected, name)
        # These fractions are manual calculations, not sums of scorer case output.
        expected_rates = {"field_precision": (2, 3), "field_recall": (2, 2),
                          "exact_value_accuracy": (1, 2), "value_precision": (1, 3),
                          "value_recall": (1, 2), "span_fidelity": (2, 3),
                          "grounded_value_recall": (1, 2), "required_abstention_accuracy": (1, 2),
                          "proposal_coverage": (3, 4)}
        for name, (numerator, denominator) in expected_rates.items():
            self.assertEqual(report["metrics"][name],
                             {"numerator": numerator, "denominator": denominator,
                              "value": numerator / denominator}, name)
        self.assertEqual(report["latency"], {"reported_documents": 2, "total_ms": 40.0,
                                            "mean_ms": 20.0, "median_ms": 20.0})
        self.assertEqual(report["review_time"]["reported_documents"], 1)
        self.assertEqual(report["review_time"]["total_ms"], 7.0)
        self.assertEqual(report["reported_cost"]["total"], "0.010")
        self.assertEqual(report["calibration"]["status"], "not_evaluated")
        self.assertEqual(report["artifact_integrity"]["status"], "not_checked_by_pure_scorer")

    def test_value_and_source_correctness_are_separate(self):
        alternatives = [None, {**self.spans[0], "text_sha256": "0" * 64},
                        {**self.spans[0], "quote": "13.50"},
                        {**self.spans[0], "page": 2},
                        {**self.spans[0], "start": 7, "end": 12}]
        for span in alternatives:
            with self.subTest(span=span):
                report = metrics.evaluate(self.corpus, envelope(self.corpus, [
                    row("A", [proposed("total_cents", "1250", span, "accepted")])]))
                self.assertEqual(report["counts"]["correct_values"], 1)
                self.assertEqual(report["counts"]["correct_spans"], 0)
                self.assertEqual(report["counts"]["grounded_correct_values"], 0)
                self.assertEqual(report["counts"]["critical_false_accepts"], 1)

    def test_correct_value_is_not_silently_normalized(self):
        for value in ("12.50", "01250", "1250.0", "1250 "):
            with self.subTest(value=value):
                result = metrics.evaluate(self.corpus, envelope(self.corpus, [
                    row("A", [proposed("total_cents", value, self.spans[0])])]))
                self.assertEqual(result["counts"]["correct_values"], 0)
                self.assertEqual(result["counts"]["correct_spans"], 1)

    def test_missing_output_is_not_an_abstention(self):
        result = metrics.evaluate(self.corpus, envelope(self.corpus))
        self.assertEqual(result["counts"]["missing_documents"], 2)
        self.assertEqual(result["counts"]["missing_fields"], 4)
        self.assertEqual(result["counts"]["correct_abstentions"], 0)
        self.assertEqual(result["metrics"]["value_recall"]["value"], 0)
        self.assertEqual(result["metrics"]["required_abstention_accuracy"]["value"], 0)
        self.assertIsNone(result["metrics"]["value_precision"]["value"])
        self.assertIsNone(result["latency"]["mean_ms"])
        self.assertIsNone(result["reported_cost"]["total"])

    def test_abstaining_everywhere_cannot_establish_extraction_quality(self):
        output = envelope(self.corpus, [row(doc_id, [
            {"field": name, "decision": "abstain"} for name in ("total_cents", "due_date")])
            for doc_id in ("A", "B")])
        report = metrics.evaluate(self.corpus, output)
        self.assertEqual(report["metrics"]["required_abstention_accuracy"]["value"], 1)
        self.assertEqual(report["metrics"]["grounded_value_recall"]["value"], 0)
        self.assertIsNone(report["metrics"]["exact_value_accuracy"]["value"])

    def test_empty_selected_split_has_undefined_rates(self):
        report = metrics.evaluate(self.corpus, envelope(self.corpus), split="development")
        self.assertEqual(report["counts"]["documents"], 0)
        self.assertTrue(all(rate["value"] is None for rate in report["metrics"].values()))

    def test_unexpected_abstention_does_not_produce_negative_coverage(self):
        report = metrics.evaluate(self.corpus, envelope(self.corpus, [
            row("A", [{"field": "unregistered", "decision": "abstain"}])]))
        self.assertEqual(report["counts"]["unexpected_fields"], 1)
        self.assertEqual(report["metrics"]["proposal_coverage"]["value"], 0)
        self.assertEqual(report["counts"]["missing_fields"], 4)

    def test_unknown_accepted_field_is_a_false_accept(self):
        report = metrics.evaluate(self.corpus, envelope(self.corpus, [
            row("A", [proposed("unregistered", "anything", None, "accepted")])]))
        self.assertEqual(report["counts"]["unexpected_fields"], 1)
        self.assertEqual(report["counts"]["false_proposals"], 1)
        self.assertEqual(report["counts"]["false_accepts"], 1)
        self.assertEqual(report["metrics"]["value_precision"]["value"], 0)

    def test_error_does_not_count_as_correct_abstention(self):
        report = metrics.evaluate(self.corpus, envelope(self.corpus, [
            row("B", [{"field": "due_date", "decision": "error"}])]))
        self.assertEqual(report["counts"]["errors"], 1)
        self.assertEqual(report["counts"]["correct_abstentions"], 0)

    def test_wrong_processing_status_is_scored_separately(self):
        output = envelope(self.corpus, [row("A", [proposed("total_cents", "1250", self.spans[0])])])
        output["documents"][0]["processing_status"] = "partial"
        report = metrics.evaluate(self.corpus, output)
        self.assertEqual(report["counts"]["processing_status_correct"], 0)
        self.assertEqual(report["counts"]["correct_values"], 1)

    def test_development_output_cannot_inflate_holdout_counts(self):
        self.corpus["documents"][0]["split"] = "development"
        output = envelope(self.corpus, [row("A", [proposed("total_cents", "1250", self.spans[0])])])
        report = metrics.evaluate(self.corpus, output)
        self.assertEqual(report["counts"]["documents"], 1)
        self.assertEqual(report["counts"]["proposals"], 0)
        self.assertEqual(report["counts"]["missing_documents"], 1)

    def test_report_uses_cpu_without_network_or_runtime_provider_imports(self):
        with patch("socket.socket", side_effect=AssertionError("Network forbidden")):
            report = metrics.evaluate(self.corpus, envelope(self.corpus))
        self.assertEqual(report["runtime"], {"backend": "cpu_reference", "network_used": False,
                                              "inference_performed": False})


class InvalidInputTests(unittest.TestCase):
    def setUp(self):
        self.corpus = small_corpus()

    def test_wrong_binding_scope_and_unknown_document_are_rejected(self):
        for key, value in (("schema_version", "future"), ("corpus_sha256", "0" * 64),
                           ("corpus_id", "other"), ("scope", "provider_quality_v1")):
            with self.subTest(key=key):
                output = envelope(self.corpus)
                output[key] = value
                with self.assertRaises(metrics.EvaluationError):
                    metrics.evaluate(self.corpus, output)
        with self.assertRaises(metrics.EvaluationError):
            metrics.evaluate(self.corpus, envelope(self.corpus, [row("not_registered", [])]))

    def test_duplicate_documents_and_fields_are_rejected(self):
        field = {"field": "total_cents", "decision": "abstain"}
        for rows in ([row("A", []), row("A", [])], [row("A", [field, field])]):
            with self.subTest(rows=rows), self.assertRaises(metrics.EvaluationError):
                metrics.evaluate(self.corpus, envelope(self.corpus, rows))

    def test_bad_value_and_span_shapes_are_rejected(self):
        span = self.corpus["documents"][0]["fields"][0]["allowed_spans"][0]
        fields = [proposed("total_cents", 1250, span),
                  proposed("total_cents", "1250", {**span, "end": 12}),
                  proposed("total_cents", "1250", {**span, "page": True}),
                  proposed("total_cents", "1250", {**span, "start": -1}),
                  {"field": "total_cents", "decision": "abstain", "canonical_value": "1"},
                  {"field": "total_cents", "decision": "error", "review_decision": "accepted"},
                  {"field": "total_cents", "decision": "abstain", "confidence": 0.99},
                  {"field": "total_cents", "decision": []},
                  {"field": "total_cents", "decision": "abstain", "review_decision": []}]
        for field in fields:
            with self.subTest(field=field), self.assertRaises(metrics.EvaluationError):
                metrics.evaluate(self.corpus, envelope(self.corpus, [row("A", [field])]))

    def test_invalid_operational_values_fail_cleanly(self):
        bad_values = {"latency_ms": [-1, True, float("inf"), float("nan"), 10 ** 400, "1"],
                      "review_ms": [-1, False, float("inf")],
                      "reported_cost_usd": [-1, 0.1, "-1", "NaN", "Infinity", "1e2",
                                            "0e999999999", "0.0000000000001", "1000000000001"]}
        for key, values in bad_values.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(metrics.EvaluationError):
                    metrics.evaluate(self.corpus, envelope(self.corpus, [row("A", [], **{key: value})]))

    def test_malformed_corpus_enums_duplicates_and_missing_spans_are_rejected(self):
        changes = [lambda c: c["documents"].append(deepcopy(c["documents"][0])),
                   lambda c: c["documents"][0].update(split=[]),
                   lambda c: c["documents"][0].update(expected_processing_status="malformed"),
                   lambda c: c["documents"][0].update(origin="private"),
                   lambda c: c["documents"][0]["fields"][0].update(allowed_spans=[]),
                   lambda c: c["documents"][0]["fields"][0].update(expectation=[]),
                   lambda c: c["documents"][0]["fields"][0].update(critical=1)]
        for change in changes:
            corpus = deepcopy(self.corpus)
            change(corpus)
            with self.subTest(corpus=corpus), self.assertRaises(metrics.EvaluationError):
                metrics.validate_corpus(corpus)

    def test_duplicate_json_keys_and_nonfinite_constants_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.json"
            for text in ('{"documents": [], "documents": []}', '{"cost": NaN}', '{"cost": Infinity}'):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(metrics.EvaluationError):
                    metrics.load_json(path)


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.corpus = metrics.load_json(FIXTURES / "manifest.json")

    def test_checked_in_originals_hashes_spans_splits_and_counts(self):
        self.assertEqual(metrics.verify_corpus(self.corpus, FIXTURES),
                         {"status": "verified", "documents": 9, "files": 11, "field_labels": 54})
        docs = self.corpus["documents"]
        self.assertEqual(sum(doc["split"] == "development" for doc in docs), 5)
        self.assertEqual(sum(doc["split"] == "holdout" for doc in docs), 4)
        self.assertEqual(sum(field["expectation"] == "value" for doc in docs for field in doc["fields"]), 32)
        self.assertEqual({doc["document_class"] for doc in docs}, {"MEP_INVOICE"})
        self.assertEqual(len({doc["source_sha256"] for doc in docs}), 9)
        self.assertEqual(metrics.corpus_fingerprint(self.corpus),
                         "f313e2d6599680333afa2a4d188f0dd9603765be16e309829b0405653d8a4378")

    def test_plain_invoice_cents_and_offsets_have_literal_reference_checks(self):
        doc = self.corpus["documents"][0]
        total = next(field for field in doc["fields"] if field["field"] == "total_cents")
        self.assertEqual(total["canonical_value"], "125000")
        self.assertEqual(total["allowed_spans"][0]["start"], 166)
        self.assertEqual(total["allowed_spans"][0]["end"], 174)
        self.assertEqual((FIXTURES / "invoice_native.txt").read_text()[166:174], "1,250.00")

    def test_unicode_offsets_count_codepoints_not_utf8_bytes(self):
        doc = next(doc for doc in self.corpus["documents"] if doc["document_id"] == "DOC-SYN-105")
        source = (FIXTURES / doc["source_file"]).read_text(encoding="utf-8")
        field = next(field for field in doc["fields"] if field["field"] == "invoice_number")
        span = field["allowed_spans"][0]
        self.assertEqual((span["start"], span["end"]), (80, 91))
        self.assertEqual(source[80:91], "SYN-INV-105")
        self.assertNotEqual(source.encode("utf-8")[80:91].decode("utf-8"), "SYN-INV-105")

    @unittest.skipUnless(importlib.util.find_spec("fitz"), "PyMuPDF required for PDF-native fixture check")
    def test_native_pdf_matches_authored_reference_and_scan_has_no_text(self):
        import fitz
        with fitz.open(FIXTURES / "invoice_native.pdf") as pdf:
            self.assertEqual(len(pdf), 1)
            self.assertEqual(pdf[0].get_text(), (FIXTURES / "invoice_native_pdf.reference.txt").read_text())
        with fitz.open(FIXTURES / "invoice_scan.pdf") as pdf:
            self.assertEqual(len(pdf), 1)
            self.assertEqual(pdf[0].get_text(), "")
            self.assertEqual(len(pdf[0].get_images()), 1)

    def test_missing_fields_are_complete_but_observed_limit_is_partial(self):
        indexed = {doc["document_id"]: doc for doc in self.corpus["documents"]}
        missing = indexed["DOC-SYN-005"]
        limited = indexed["DOC-SYN-108"]
        self.assertEqual(missing["expected_processing_status"], "complete")
        self.assertEqual(limited["expected_processing_status"], "partial")
        self.assertEqual(limited["read_limits"], {"max_text_bytes": 150000})
        original = (FIXTURES / limited["source_file"]).read_bytes()
        self.assertGreater(len(original), 150000)
        self.assertNotIn(b"Total due:", original[:150000])
        self.assertIn(b"Total due:", original[150000:])

    def test_artifact_tampering_and_bad_gold_quote_are_rejected(self):
        corpus = small_corpus()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.txt").write_text("Total 12.50\nDue 2027-01-02\n")
            (root / "b.txt").write_text("No supported values.\n")
            metrics.verify_corpus(corpus, root)
            (root / "a.txt").write_text("Tampered content\n")
            with self.assertRaisesRegex(metrics.EvaluationError, "hash mismatch"):
                metrics.verify_corpus(corpus, root)
            (root / "a.txt").write_text("Total 12.50\nDue 2027-01-02\n")
            corpus["documents"][0]["fields"][0]["allowed_spans"][0]["quote"] = "13.50"
            with self.assertRaisesRegex(metrics.EvaluationError, "quote mismatch"):
                metrics.verify_corpus(corpus, root)

    def test_path_traversal_and_external_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            root = parent / "corpus"
            root.mkdir()
            (parent / "outside.txt").write_text("Total 12.50\nDue 2027-01-02\n")
            (root / "outside_link.txt").symlink_to(parent / "outside.txt")
            for path in ("../outside.txt", str(parent / "outside.txt"), "outside_link.txt"):
                corpus = small_corpus()
                corpus["documents"][0]["source_file"] = path
                with self.subTest(path=path), self.assertRaises(metrics.EvaluationError):
                    metrics.verify_corpus(corpus, root)

    def test_fingerprint_ignores_json_whitespace_but_binds_labels(self):
        reformatted = json.loads(json.dumps(self.corpus, indent=4, ensure_ascii=True))
        self.assertEqual(metrics.corpus_fingerprint(self.corpus), metrics.corpus_fingerprint(reformatted))
        reformatted["documents"][0]["fields"][0]["canonical_value"] = "Different vendor"
        self.assertNotEqual(metrics.corpus_fingerprint(self.corpus), metrics.corpus_fingerprint(reformatted))


class CommandTests(unittest.TestCase):
    def test_cli_verifies_artifacts_and_refuses_to_overwrite_a_report(self):
        corpus = metrics.load_json(FIXTURES / "manifest.json")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            predictions = root / "predictions.json"
            predictions.write_text(json.dumps(envelope(corpus)))
            output = root / "report.json"
            command = [sys.executable, str(ROOT / "tools/docai_metrics.py"),
                       "--corpus", str(FIXTURES / "manifest.json"),
                       "--predictions", str(predictions), "--split", "holdout"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["artifact_integrity"]["status"], "verified")
            self.assertEqual(report["counts"]["missing_documents"], 4)
            self.assertIsNone(report["metrics"]["value_precision"]["value"])
            first = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stderr)
            previous = output.read_bytes()
            repeated = subprocess.run(command + ["--output", str(output)], capture_output=True, text=True, check=False)
            self.assertEqual(repeated.returncode, 2)
            self.assertEqual(output.read_bytes(), previous)
            predictions.write_text('{"documents": [], "documents": []}')
            invalid = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("Duplicate JSON key", invalid.stderr)


if __name__ == "__main__":
    unittest.main()
