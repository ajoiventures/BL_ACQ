"""Exercise learning retrieval against disposable, staged repository snapshots."""
from pathlib import Path
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
