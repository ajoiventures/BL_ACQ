"""Adverse cases for the first native document/review/export application."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pilot.document_application import DocumentApplication, invoice_candidates
from pilot.document_contracts import validate_candidate
from pilot.document_vault import DocumentVault, utc_now


FIXTURES = Path(__file__).parent / "fixtures" / "docai"
CONTEXT = {"tenant_id": "test-tenant", "domain": "commercial", "subject_id": "invoice-001", "case_id": None}


class DocumentApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "runtime"
        self.app = DocumentApplication(self.root, context=CONTEXT, actor="reviewer-a")

    def tearDown(self):
        self.app.__exit__()
        self.temp.cleanup()

    def ingest(self, name="invoice_native.txt", **kwargs):
        return self.app.ingest(FIXTURES / name, document_class="MEP_INVOICE", source_status="synthetic", **kwargs)

    def accept_all(self, snapshot):
        for claim in snapshot["candidates"]:
            current = self.app.inspect(snapshot["document"]["document_id"])
            self.app.review(claim["claim_id"], review_id="accept-" + claim["claim_id"], decision="accept",
                            reason="Synthetic field checked against its exact source text.", expected_revision=current["revision"])
        return self.app.inspect(snapshot["document"]["document_id"])

    def test_complete_local_path_preserves_evidence_and_synthetic_status(self):
        with patch("socket.create_connection", side_effect=AssertionError("Network use forbidden in native path")):
            snapshot = self.ingest()
            self.assertEqual(len(snapshot["candidates"]), 6)
            self.assertFalse(snapshot["ready_for_export"])
            with self.assertRaisesRegex(ValueError, "held"):
                self.app.export(snapshot["document"]["document_id"])
            accepted = self.accept_all(snapshot)
            self.assertTrue(accepted["ready_for_export"])
            export = self.app.export(snapshot["document"]["document_id"])
        self.assertEqual(export["fields"]["total_cents"]["candidate"]["value"], 125000)
        self.assertEqual(export["fields"]["total_cents"]["candidate"]["spans"][0]["quote"], "1,250.00")
        self.assertEqual(export["source_status"], "synthetic")
        self.assertEqual(export["execution_authority"], "none")
        self.assertEqual(export["extractions"][0]["backend"], "cpu")
        self.assertIsNone(export["extractions"][0]["provider"])
        self.assertEqual(export["extractions"][0]["source_sha256"], export["document"]["content_sha256"])
        self.assertEqual(len(export["extractions"][0]["configuration_sha256"]), 64)
        self.assertEqual(export["identity_assurance"], "trusted_local_os_actor_labels")
        self.assertEqual(accepted["provider_connection"], "disabled")
        self.assertFalse(accepted["product_agents"])

    def test_repeated_intake_preserves_run_review_and_revision(self):
        original = self.ingest()
        reviewed = self.accept_all(original)
        replayed = self.ingest()
        self.assertEqual(replayed, reviewed)

    def test_review_retry_is_exact_and_changed_request_is_rejected(self):
        snapshot = self.ingest()
        claim = snapshot["candidates"][0]
        request = dict(review_id="stable-request", decision="accept", reason="Checked exact source.", expected_revision=snapshot["revision"])
        first = self.app.review(claim["claim_id"], **request)
        self.assertEqual(first, self.app.review(claim["claim_id"], **request))
        with self.assertRaisesRegex(ValueError, "Idempotency"):
            self.app.review(claim["claim_id"], **{**request, "reason": "Changed reason."})
        with DocumentApplication(self.root, context=CONTEXT, actor="reviewer-b") as other:
            with self.assertRaisesRegex(ValueError, "actor"):
                other.review(claim["claim_id"], **request)

    def test_stale_revision_cannot_accept_second_field(self):
        snapshot = self.ingest()
        first, second = snapshot["candidates"][:2]
        self.app.review(first["claim_id"], review_id="first", decision="accept", reason="Checked.", expected_revision=snapshot["revision"])
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.app.review(second["claim_id"], review_id="stale", decision="accept", reason="Checked.", expected_revision=snapshot["revision"])

    def test_review_reversal_requires_current_predecessor(self):
        snapshot = self.ingest()
        claim = snapshot["candidates"][0]
        accepted = self.app.review(claim["claim_id"], review_id="accepted", decision="accept", reason="First check.", expected_revision=1)
        with self.assertRaisesRegex(ValueError, "explicitly supersede"):
            self.app.review(claim["claim_id"], review_id="reject-without-link", decision="reject", reason="Rechecked.", expected_revision=accepted["revision"])
        self.app.review(claim["claim_id"], review_id="rejected", decision="reject", reason="Rechecked.",
                        expected_revision=accepted["revision"], supersedes_review_id="accepted")
        current = self.app.inspect(snapshot["document"]["document_id"])
        self.assertEqual(len(current["reviews"]), 2)
        self.assertNotIn(claim["field"], current["accepted_fields"])

    def test_manual_correction_invalidates_old_acceptance_and_preserves_history(self):
        original = self.ingest()
        reviewed = self.accept_all(original)
        old = next(c for c in reviewed["candidates"] if c["field"] == "total_cents")
        correction = {**deepcopy(old), "claim_id": "manual-amount", "method": "manual", "created_at": utc_now(),
                      "proposed_by": "reviewer-a", "supersedes_claim_id": old["claim_id"]}
        result = self.app.correct(correction, expected_revision=reviewed["revision"])
        self.assertEqual(result, self.app.correct(correction, expected_revision=reviewed["revision"]))
        pending = self.app.inspect(original["document"]["document_id"])
        self.assertFalse(pending["ready_for_export"])
        self.assertEqual(len(pending["candidates"]), 7)
        self.assertEqual(len(pending["reviews"]), 6)
        with self.assertRaisesRegex(ValueError, "proposer"):
            self.app.review("manual-amount", review_id="self", decision="accept", reason="Checked.", expected_revision=result["revision"])
        with DocumentApplication(self.root, context=CONTEXT, actor="reviewer-b") as reviewer:
            reviewer.review("manual-amount", review_id="independent-label", decision="accept", reason="Synthetic replacement checked.", expected_revision=result["revision"])
            export = reviewer.export(original["document"]["document_id"])
            self.assertEqual(export["fields"]["total_cents"]["candidate"]["claim_id"], "manual-amount")

    def test_correction_with_wrong_quote_rolls_back(self):
        snapshot = self.ingest()
        old = snapshot["candidates"][0]
        correction = {**deepcopy(old), "claim_id": "wrong-quote", "method": "manual", "created_at": utc_now(),
                      "proposed_by": "reviewer-a", "supersedes_claim_id": old["claim_id"]}
        correction["spans"][0]["quote"] = "Unrelated words"
        with self.assertRaisesRegex(ValueError, "exact"):
            self.app.correct(correction, expected_revision=snapshot["revision"])
        self.assertEqual(snapshot, self.app.inspect(snapshot["document"]["document_id"]))

    def test_additional_pending_candidate_blocks_accepted_field(self):
        reviewed = self.accept_all(self.ingest())
        old = reviewed["candidates"][0]
        extra = {**deepcopy(old), "claim_id": "competing", "method": "manual", "created_at": utc_now(),
                 "proposed_by": "reviewer-a", "supersedes_claim_id": None}
        self.app.correct(extra, expected_revision=reviewed["revision"])
        current = self.app.inspect(reviewed["document"]["document_id"])
        self.assertFalse(current["ready_for_export"])
        self.assertNotIn(old["field"], current["accepted_fields"])

    def test_context_cannot_read_review_or_export_another_context(self):
        snapshot = self.ingest()
        database = self.app.context_root / "documents.sqlite3"
        with DocumentVault(database, context={**CONTEXT, "tenant_id": "another-tenant"}, actor="reviewer-a") as other:
            self.assertIsNone(other.document(snapshot["document"]["document_id"]))
            with self.assertRaisesRegex(ValueError, "absent"):
                other.inspect(snapshot["document"]["document_id"])
            with self.assertRaisesRegex(ValueError, "absent"):
                other.review(snapshot["candidates"][0]["claim_id"], review_id="cross", decision="accept", reason="No access.", expected_revision=1)

    def test_history_cannot_be_updated_or_deleted(self):
        self.ingest()
        for statement in ("UPDATE br_docai_records SET record_json='{}'", "DELETE FROM br_docai_records"):
            with self.assertRaises(sqlite3.IntegrityError):
                self.app.vault.connection.execute(statement)

    def test_reopen_preserves_reviewed_state(self):
        reviewed = self.accept_all(self.ingest())
        with DocumentApplication(self.root, context=CONTEXT, actor="reviewer-b") as reopened:
            self.assertEqual(reviewed, reopened.inspect(reviewed["document"]["document_id"]))

    def test_successor_holds_old_export_and_prevents_version_forks(self):
        reviewed = self.accept_all(self.ingest())
        old = reviewed["document"]
        document = {**deepcopy(old), "document_id": "source-v2", "version": 2,
                    "predecessor_document_id": old["document_id"]}
        run = {**deepcopy(reviewed["extractions"][0]), "run_id": "run-v2",
               "document_id": "source-v2", "document_version": 2}
        self.app.vault.add_bundle(document, run, [], archive=reviewed["archive"])
        stale = self.app.inspect(old["document_id"])
        self.assertFalse(stale["ready_for_export"])
        self.assertEqual(stale["revision"], reviewed["revision"] + 1)
        with self.assertRaisesRegex(ValueError, "superseded"):
            self.app.export(old["document_id"])
        with self.assertRaisesRegex(ValueError, "superseded"):
            self.app.review(reviewed["candidates"][0]["claim_id"], review_id="late-v1", decision="reject", reason="Late.",
                            expected_revision=stale["revision"])
        fork = {**deepcopy(document), "document_id": "source-v2-fork"}
        fork_run = {**deepcopy(run), "document_id": "source-v2-fork", "run_id": "run-v2-fork"}
        with self.assertRaisesRegex(ValueError, "superseded"):
            self.app.vault.add_bundle(fork, fork_run, [], archive=reviewed["archive"])
        self.assertIsNone(self.app.vault.document("source-v2-fork"))

    def test_corrupt_original_blocks_inspection_review_and_export(self):
        snapshot = self.accept_all(self.ingest())
        original = Path(snapshot["archive"]["file"])
        original.write_bytes(original.read_bytes() + b"changed")
        for operation in (lambda: self.app.inspect(snapshot["document"]["document_id"]),
                          lambda: self.app.export(snapshot["document"]["document_id"]),
                          lambda: self.app.review(snapshot["candidates"][0]["claim_id"], review_id="late", decision="reject",
                                                  reason="Changed original.", expected_revision=snapshot["revision"])):
            with self.assertRaisesRegex(ValueError, "changed"):
                operation()

    def test_failure_after_archival_rolls_back_bundle_and_retry_recovers(self):
        original_insert = self.app.vault._insert
        def fail_on_candidate(kind, identity, document_id, record):
            if kind == "candidate":
                raise RuntimeError("Injected DB failure after filing")
            return original_insert(kind, identity, document_id, record)
        with patch.object(self.app.vault, "_insert", side_effect=fail_on_candidate):
            with self.assertRaises(RuntimeError):
                self.ingest()
        self.assertEqual(self.app.vault.connection.execute("SELECT COUNT(*) FROM br_docai_records").fetchone()[0], 0)
        self.assertEqual(self.app.vault.connection.execute("SELECT COUNT(*) FROM br_docai_revisions").fetchone()[0], 0)
        recovered = self.ingest()
        self.assertEqual(len(recovered["candidates"]), 6)
        self.assertEqual(recovered["revision"], 1)

    def test_partial_extraction_never_creates_native_candidates(self):
        snapshot = self.ingest(limits={"max_text_bytes": 100})
        self.assertEqual(snapshot["extractions"][0]["status"], "partial")
        self.assertEqual(snapshot["candidates"], [])
        self.assertFalse(snapshot["ready_for_export"])

    def test_duplicate_label_causes_field_abstention(self):
        snapshot = self.ingest("invoice_ambiguous.txt")
        self.assertNotIn("total_cents", {c["field"] for c in snapshot["candidates"]})
        self.assertFalse(snapshot["ready_for_export"])

    def test_unknown_class_can_archive_but_cannot_propose_or_export(self):
        snapshot = self.app.ingest(FIXTURES / "invoice_native.txt", document_class="UNKNOWN", source_status="synthetic")
        self.assertEqual(snapshot["candidates"], [])
        self.assertFalse(snapshot["ready_for_export"])

    def test_exact_quote_validation_does_not_claim_semantic_truth(self):
        snapshot = self.ingest()
        candidate = deepcopy(next(c for c in snapshot["candidates"] if c["field"] == "total_cents"))
        candidate["value"] += 1
        # This layer establishes type and provenance. Review must check whether
        # the quoted source actually supports the proposed normalized value.
        validated = validate_candidate(candidate, snapshot["document"], snapshot["extractions"][0])
        self.assertEqual(validated["value"], 125001)
        self.assertFalse(snapshot["ready_for_export"])

    def test_label_parser_rejects_unsafe_numeric_forms_without_rounding(self):
        snapshot = self.ingest()
        for invalid in ("1,25.00", "1250.001", "NaN", "-10.00", "1e3", "999999999999999999.00"):
            run = deepcopy(snapshot["extractions"][0])
            run["pages"][0]["text"] = run["pages"][0]["text"].replace("1,250.00", invalid)
            from pilot.document_contracts import sha256_text
            run["pages"][0]["text_sha256"] = sha256_text(run["pages"][0]["text"])
            candidates = invoice_candidates(snapshot["document"], run)
            self.assertNotIn("total_cents", {c["field"] for c in candidates})


if __name__ == "__main__":
    unittest.main()
