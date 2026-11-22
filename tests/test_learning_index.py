"""Exercise learning retrieval against disposable, staged repository snapshots."""
from pathlib import Path
import hashlib
import json
import sqlite3
import subprocess
from tempfile import TemporaryDirectory
import unittest

from tools.learning_index import build, read, search


class LearningIndexTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name) / "repo"
        self.repo.mkdir()
        self.db = Path(temp.name) / "index.sqlite3"
        self.git("init", "--quiet")
        self.stage("README.md", "# Operating notes\nStart with the fixture.\n")
        self.stage("docs/guides/receipts.md",
                   "# Reconciliation\n\nSeparate receipt evidence prevents duplicate settlement.\n")
        self.stage("docs/learning/settlement.md",
                   "# Verified settlement lesson\nReview: accepted\nReviewed by: fixture reviewer\n"
                   "Source: docs/guides/receipts.md\n\n## Result\nZephyr receipts preserve audit history.\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def stage(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.git("add", "--", name)

    def test_citations_scores_provenance_and_stability(self):
        result = build(self.repo, self.db)
        self.assertEqual(result["documents"], 3)
        hits = search(self.db, "zephyr")
        self.assertEqual(len(hits), 1)
        citation = hits[0]
        self.assertEqual((citation["path"], citation["start_line"], citation["end_line"]),
                         ("docs/learning/settlement.md", 6, 7))
        self.assertEqual(citation["lesson"]["reviewer"], "fixture reviewer")
        self.assertEqual(citation["lesson"]["source"], "docs/guides/receipts.md")
        body = read(self.db, citation["chunk_id"])
        self.assertEqual(body["text"], "## Result\nZephyr receipts preserve audit history.")
        self.assertGreater(citation["score"], 0)
        self.assertLessEqual(citation["score"], 1)
        self.assertEqual(search(self.db, "unmatchedquux"), [])
        def stored_vectors():
            conn = sqlite3.connect(self.db)
            try:
                return conn.execute("SELECT id,vector FROM chunks ORDER BY id").fetchall()
            finally:
                conn.close()
        original = stored_vectors()
        self.assertEqual(build(self.repo, self.db), result)
        self.assertEqual(stored_vectors(), original)
        self.assertEqual(search(self.db, "zephyr"), hits)

    def test_update_and_deletion_remove_stale_hits(self):
        build(self.repo, self.db)
        old = search(self.db, "duplicate")[0]["chunk_id"]
        self.stage("docs/guides/receipts.md", "# Reconciliation\nUse immutable approvals.\n")
        self.git("rm", "--force", "docs/learning/settlement.md")
        build(self.repo, self.db)
        self.assertEqual(search(self.db, "zephyr duplicate"), [])
        self.assertEqual(search(self.db, "immutable")[0]["path"], "docs/guides/receipts.md")
        with self.assertRaisesRegex(ValueError, "Unknown chunk"):
            read(self.db, old)

    def test_only_published_scopes_and_reviewed_lessons_are_ingested(self):
        self.stage("attachments/private.md", "# Classified word\nquasar\n")
        self.stage("docs/learning/proposal.md", "# Proposal\nReview: draft\nquasar\n")
        untracked = self.repo / "docs/guides/private.md"
        untracked.write_text("# Personal draft\nquasar\n", encoding="utf-8")
        # The working copy can differ from the staged snapshot while the author edits.
        (self.repo / "README.md").write_text("quasar\n", encoding="utf-8")
        result = build(self.repo, self.db)
        self.assertEqual(result["skipped_unreviewed_lessons"], ["docs/learning/proposal.md"])
        self.assertEqual(search(self.db, "quasar"), [])

    def test_invalid_lesson_provenance_keeps_last_good_index(self):
        build(self.repo, self.db)
        before = search(self.db, "zephyr")
        self.stage("docs/learning/bad.md", "# Claim\nReview: accepted\nReviewed by: test reviewer\nSource: ../outside.md\n")
        with self.assertRaisesRegex(ValueError, "tracked"):
            build(self.repo, self.db)
        self.assertEqual(search(self.db, "zephyr"), before)
        self.stage("attachments/private.md", "Personal notes")
        self.stage("docs/learning/bad.md", "# Claim\nReview: accepted\nReviewed by: test reviewer\nSource: attachments/private.md\n")
        with self.assertRaisesRegex(ValueError, "maintained"):
            build(self.repo, self.db)
        self.assertEqual(search(self.db, "zephyr"), before)

    def test_registered_builder_sources_are_searchable(self):
        registrations = [
            "config/builder-skills.json", "config/build-ticket-plan.json",
            "config/docai-ticket-plan.json", "config/swarm-library-extension.json",
            ".codex/agents/br-product-integrator.toml",
            ".codex/agents/br-evidence-builder.toml",
            ".codex/agents/br-quant-builder.toml",
            ".codex/agents/br-quality-builder.toml",
            "docs/plans/document-roadmap.md",
        ]
        for number, name in enumerate(registrations):
            marker = f"registeredbuilder{number}"
            if name.endswith(".json"):
                body = json.dumps({"description": marker}) + "\n"
            elif name.endswith(".toml"):
                body = f'description = "{marker}"\n'
            else:
                body = f"# Builder roadmap\n{marker}\n"
            self.stage(name, body)
        result = build(self.repo, self.db)
        self.assertEqual(result["documents"], 12)
        for number, name in enumerate(registrations):
            hits = search(self.db, f"registeredbuilder{number}")
            self.assertEqual([hit["path"] for hit in hits], [name])

    def test_structured_artifact_citations_resolve_to_staged_content(self):
        name = "config/docai-ticket-plan.json"
        original = json.dumps({"schema_version": "docai.fixture.v1", "tickets": [
            {"id": "DOC-AI-001", "title": "Orchid provider connection", "state": "unconnected"}
        ]}, indent=2) + "\n"
        self.stage(name, original)
        # An author can change the working copy without publishing that draft.
        (self.repo / name).write_text('{"private_draft": "unpublishedorchid"}\n', encoding="utf-8")
        blob = self.git("rev-parse", ":" + name).stdout.decode().strip()
        build(self.repo, self.db)
        hit = search(self.db, "orchid")[0]
        self.assertEqual(hit["path"], name)
        self.assertEqual(hit["git_blob"], blob)
        self.assertEqual(hit["source_sha256"], hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual((hit["start_line"], hit["end_line"]), (1, len(original.splitlines())))
        self.assertEqual(read(self.db, hit["chunk_id"])["text"], original.rstrip("\n"))
        self.assertEqual(self.git("cat-file", "blob", blob).stdout.decode(), original)
        self.assertEqual(search(self.db, "unpublishedorchid"), [])

    def test_builder_registration_does_not_expand_private_or_recursive_scope(self):
        for name in (
            "config/private.json", "config/nested/docai-ticket-plan.json",
            ".codex/agents/unregistered-agent.toml",
            "docs/plans/private/notes.md",
            "personal-skills/skill-private/SKILL.md",
        ):
            self.stage(name, "privatebuildermarker\n")
        for name in ("config/docai-ticket-plan.json", "docs/plans/untracked.md"):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("untrackedbuildermarker\n", encoding="utf-8")
        build(self.repo, self.db)
        self.assertEqual(search(self.db, "privatebuildermarker untrackedbuildermarker"), [])

    def test_registered_symlink_is_not_followed(self):
        outside = self.repo.parent / "outside-plan.json"
        outside.write_text('{"private": "outsidebuildermarker"}\n', encoding="utf-8")
        link = self.repo / "config/docai-ticket-plan.json"
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"Symbolic links unavailable: {exc}")
        self.git("add", "--", "config/docai-ticket-plan.json")
        build(self.repo, self.db)
        self.assertEqual(search(self.db, "outsidebuildermarker"), [])

    def test_foreign_database_is_preserved(self):
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE legacy(value TEXT)")
        conn.execute("INSERT INTO legacy VALUES('retained')")
        conn.commit()
        conn.close()
        with self.assertRaisesRegex(ValueError, "compatible"):
            build(self.repo, self.db)
        conn = sqlite3.connect(self.db)
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT value FROM legacy").fetchone()[0], "retained")


if __name__ == "__main__":
    unittest.main()
