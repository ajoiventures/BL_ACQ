"""Adverse and precision cases for the document-neutral Doc AI contracts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pilot.document_contracts import (
    CLASS_FIELDS, DEFAULT_LIMITS, DOCUMENT_CLASSES, SCHEMA_VERSION, canonical_json,
    sha256_text, validate_candidate, validate_context, validate_document,
    validate_extraction, validate_limits, validate_review,
)


ROOT = Path(__file__).resolve().parents[1]


class DocAIContractChecks(unittest.TestCase):
    def setUp(self):
        data = json.loads((ROOT / "schemas/docai/examples.json").read_text())
        self.doc, self.run, self.claim, self.review = (data[key] for key in ("document", "extraction", "candidate", "review"))

    def test_examples_roundtrip_without_financial_deal_and_without_transport(self):
        with patch("socket.socket", side_effect=AssertionError("Network construction is forbidden")):
            doc = validate_document(self.doc)
            run = validate_extraction(self.run, doc)
            claim = validate_candidate(self.claim, doc, run)
            review = validate_review(self.review, claim)
        self.assertNotIn("deal_id", doc)
        self.assertEqual(doc["context"]["domain"], "family")
        self.assertEqual(claim["value"], 12500)
        self.assertEqual(review["decision"], "accept")
        doc["context"]["subject_id"] = "different"
        run["pages"][0]["text"] = "changed"
        self.assertEqual(self.doc["context"]["subject_id"], "home-services")
        self.assertNotEqual(self.run["pages"][0]["text"], "changed")

    def test_unknown_versions_fields_and_non_json_values_fail(self):
        for extra in ({"schema_version": "1.0"}, {"schema_version": "br.docai.v2"}, {"deal_id": "fabricated"}, {"verified": True}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_document(self.doc | extra)
        for value in (float("nan"), float("inf"), ("tuple",), {1: "nonstring-key"}, b"bytes"):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                canonical_json({"value": value})

    def test_context_requires_subject_tenant_and_valid_domain(self):
        for ctx in ({"tenant_id": "one", "domain": "family"}, self.doc["context"] | {"domain": "all"},
                    self.doc["context"] | {"tenant_id": "../other"}, self.doc["context"] | {"roles": ["admin"]}):
            with self.subTest(ctx=ctx), self.assertRaises(ValueError):
                validate_context(ctx)
        self.assertIsNone(validate_context({"tenant_id": "one", "domain": "civic", "subject_id": "record"})["case_id"])

    def test_document_version_links_and_asset_links_are_explicit(self):
        with self.assertRaises(ValueError):
            validate_document(self.doc | {"version": 2})
        with self.assertRaises(ValueError):
            validate_document(self.doc | {"version": 2, "predecessor_document_id": self.doc["document_id"]})
        self.assertEqual(validate_document(self.doc | {"version": 2, "document_id": "invoice-v2", "predecessor_document_id": "invoice-v1"})["version"], 2)
        duplicate = [{"kind": "property", "id": "site-1"}] * 2
        with self.assertRaises(ValueError):
            validate_document(self.doc | {"asset_links": duplicate})

    def test_uri_and_utc_timestamp_boundaries(self):
        for uri in ("file:///tmp/source", "https://name:password@example.com/source", "https://example.com/a?access_token=secret", "https://example.com/a b", "https://example.com/a\nb"):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                validate_document(self.doc | {"source_uri": uri})
        for stamp in ("2026-11-22", "2026-11-22T12:00:00", "2026-11-22T12:00:00+00:00", "2026-02-30T12:00:00Z"):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                validate_document(self.doc | {"received_at": stamp})
        self.assertEqual(validate_document(self.doc | {"received_at": "2026-11-22T12:00:00Z"})["received_at"], "2026-11-22T12:00:00.000000Z")

    def test_source_hash_context_and_version_bind_extraction(self):
        mutations = [{"source_sha256": "0" * 64}, {"document_version": 2}, {"document_id": "other"},
                     {"context": self.doc["context"] | {"tenant_id": "other"}}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_extraction(self.run | mutation, self.doc)

    def test_partial_or_unknown_coverage_cannot_be_complete(self):
        for change in ({"processed_bytes": 1}, {"total_pages": None}, {"complete": False}, {"truncated": True}, {"processed_pages": 0}):
            run = deepcopy(self.run)
            run["coverage"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_extraction(run, self.doc)
        run = deepcopy(self.run)
        run["status"] = "partial"
        run["coverage"].update(complete=False, truncated=True, notes=["Input reached byte limit."])
        self.assertEqual(validate_extraction(run, self.doc)["status"], "partial")
        run["coverage"]["complete"] = True
        with self.assertRaises(ValueError):
            validate_extraction(run, self.doc)

    def test_limits_are_actual_typed_bounds(self):
        with self.assertRaises(ValueError):
            validate_limits(DEFAULT_LIMITS | {"max_text_bytes": True})
        with self.assertRaises(ValueError):
            validate_limits(DEFAULT_LIMITS | {"unlimited": True})
        run = deepcopy(self.run)
        run["coverage"]["limits"]["max_input_bytes"] = 1
        with self.assertRaises(ValueError):
            validate_extraction(run, self.doc)
        run = deepcopy(self.run)
        run["coverage"]["limits"]["max_text_bytes"] = 1
        with self.assertRaises(ValueError):
            validate_extraction(run, self.doc)

    def test_page_hash_order_and_count_are_checked(self):
        run = deepcopy(self.run)
        run["pages"][0]["text"] += "extra"
        with self.assertRaises(ValueError):
            validate_extraction(run, self.doc)
        run = deepcopy(self.run)
        run["pages"] *= 2
        run["coverage"].update(total_pages=2, processed_pages=2)
        with self.assertRaises(ValueError):
            validate_extraction(run, self.doc)

    def test_disabled_run_cannot_claim_execution_or_candidates(self):
        run = deepcopy(self.run)
        run.update(method="provider", backend="none", status="disabled", pages=[], errors=[])
        run["coverage"].update(processed_bytes=0, processed_pages=0, total_pages=None, complete=False, notes=["Provider disabled."])
        checked = validate_extraction(run, self.doc)
        self.assertEqual(checked["backend"], "none")
        with self.assertRaises(ValueError):
            validate_candidate(self.claim, self.doc, checked)
        run["coverage"]["processed_bytes"] = 1
        with self.assertRaises(ValueError):
            validate_extraction(run, self.doc)

    def test_provider_output_requires_its_provenance_and_cannot_self_accept(self):
        run = deepcopy(self.run)
        run.update(method="provider", backend="remote", provider="example-provider", model="example-model",
                   model_version="test-only-1", api_version="test-only-api-1",
                   raw_response={"source_uri": "fixture://docai/raw-response.json", "sha256": "1" * 64})
        claim = self.claim | {"method": "provider", "confidence": 0.8}
        self.assertEqual(validate_candidate(claim, self.doc, run)["confidence"], 0.8)
        for key in ("model_version", "api_version", "raw_response"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_extraction(run | {key: None}, self.doc)
        with self.assertRaises(ValueError):
            validate_candidate(claim | {"accepted": True}, self.doc, run)
        with self.assertRaises(ValueError):
            validate_candidate(claim | {"confidence": True}, self.doc, run)
        with self.assertRaises(ValueError):
            validate_candidate(claim | {"method": "native", "confidence": None}, self.doc, run)
        with self.assertRaises(ValueError):
            validate_extraction(run | {"method": "native"}, self.doc)

    def test_wrong_or_byte_based_spans_are_rejected(self):
        claim = deepcopy(self.claim)
        claim["spans"][0]["quote"] = "999.00"
        with self.assertRaises(ValueError):
            validate_candidate(claim, self.doc, self.run)
        claim = deepcopy(self.claim)
        claim["spans"][0]["text_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            validate_candidate(claim, self.doc, self.run)
        text = "🌿 Total: USD 125.00\n"
        doc = self.doc | {"byte_count": len(text.encode()), "content_sha256": hashlib.sha256(text.encode()).hexdigest()}
        run = deepcopy(self.run)
        run["source_sha256"] = doc["content_sha256"]
        run["pages"] = [{"page": 1, "text": text, "text_sha256": sha256_text(text)}]
        run["coverage"].update(input_bytes=doc["byte_count"], processed_bytes=doc["byte_count"])
        start = text.index("125.00")
        claim["spans"] = [{"page": 1, "text_sha256": sha256_text(text), "start": start, "end": start+6, "quote": "125.00"}]
        validate_candidate(claim, doc, run)
        claim["spans"][0].update(start=len(text[:start].encode()), end=len(text[:start].encode())+6)
        with self.assertRaises(ValueError):
            validate_candidate(claim, doc, run)

    def test_money_avoids_float_and_boolean_coercion(self):
        exact = (1 << 53) + 1
        result = validate_candidate(self.claim | {"value": exact}, self.doc, self.run)
        self.assertEqual(json.loads(canonical_json(result))["value"], exact)
        for value in (12500.0, True, "12500", 1 << 63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_candidate(self.claim | {"value": value}, self.doc, self.run)
        for change in ({"unit": "dollars"}, {"currency": None}, {"currency": "usd"}, {"confidence": 0.9}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_candidate(self.claim | change, self.doc, self.run)

    def test_unknown_class_and_unregistered_fields_remain_held(self):
        doc = self.doc | {"document_class": "UNKNOWN"}
        validate_document(doc)
        with self.assertRaises(ValueError):
            validate_candidate(self.claim, doc, self.run)
        with self.assertRaises(ValueError):
            validate_candidate(self.claim | {"field": "closing_probability"}, self.doc, self.run)
        with self.assertRaises(ValueError):
            validate_candidate(self.claim | {"value_type": "integer"}, self.doc, self.run)

    def test_decimal_measurements_require_exact_text_and_units(self):
        doc = self.doc | {"document_class": "SURVEY_PLAT"}
        claim = self.claim | {"field": "area_square_feet", "value_type": "decimal", "value": "125.00", "currency": None, "unit": "square_feet"}
        self.assertEqual(validate_candidate(claim, doc, self.run)["value"], "125.00")
        for value in (125.0, "1.25e2", "NaN", "-0.00"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_candidate(claim | {"value": value}, doc, self.run)
        with self.assertRaises(ValueError):
            validate_candidate(claim | {"unit": None}, doc, self.run)

    def test_review_binds_target_and_cannot_change_value(self):
        for change in ({"claim_id": "another"}, {"document_version": 2}, {"run_id": "another"},
                       {"value": 99900}, {"reviewed_at": "2026-11-22T00:00:00Z"},
                       {"context": self.doc["context"] | {"domain": "civic"}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_review(self.review | change, self.claim)
        with self.assertRaises(ValueError):
            validate_review(self.review, {k:v for k,v in self.claim.items() if k != "spans"})

    def test_registry_declares_twelve_classes_without_claiming_twelve_parsers(self):
        registry = json.loads((ROOT / "schemas/docai/document-classes.json").read_text())
        self.assertEqual(len(registry["classes"]), 12)
        self.assertEqual({item["document_class"] for item in registry["classes"]}, set(CLASS_FIELDS))
        self.assertEqual(DOCUMENT_CLASSES - set(CLASS_FIELDS), {"UNKNOWN"})
        implemented = [item["document_class"] for item in registry["classes"] if item["native_parser_status"] == "limited_declared_profile"]
        self.assertEqual(implemented, ["MEP_INVOICE"])
        for item in registry["classes"]:
            self.assertEqual({row["field"]:row["value_type"] for row in item["fields"]}, CLASS_FIELDS[item["document_class"]])


if __name__ == "__main__":
    unittest.main()
