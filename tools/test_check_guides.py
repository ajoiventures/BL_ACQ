"""Exercise the learning map on a tiny temporary workspace."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_guides import check


class GuideChecks(unittest.TestCase):
    def test_a_distinct_guide_for_each_source(self):
        # Build two source files and a valid map, then break one condition at a time.
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            docs = root / "docs"
            docs.mkdir()
            entries = []
            for name in ("one", "two"):
                (root / f"{name}.py").write_text('"""Example module."""', encoding="utf-8")
                (docs / f"{name}.md").write_text(f"# Guide to {name}", encoding="utf-8")
                entries.append(f"| [{name}](../{name}.py) | [guide]({name}.md) |")
            index = docs / "code-map.md"
            valid = "\n".join(entries)
            index.write_text(valid, encoding="utf-8")
            self.assertEqual(check(root)[2], [])
            for title, mapping, expected in [
                ("missing", entries[0], "Missing guide"),
                ("duplicate", valid.replace("(two.md)", "(one.md)"), "Duplicate guide"),
                ("outside", valid.replace("(two.md)", "(../../outside.md)"), "out-of-workspace"),
                ("dead link", valid + "\n[missing](missing.md)", "Broken local link"),
            ]:
                with self.subTest(title=title):
                    index.write_text(mapping, encoding="utf-8")
                    self.assertTrue(any(expected in error for error in check(root)[2]))
            index.write_text(valid, encoding="utf-8")
            (docs / "two.md").write_text(" ", encoding="utf-8")
            self.assertTrue(any("Empty guide" in error for error in check(root)[2]))
