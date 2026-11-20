"""File preservation and duplicate source coverage for the inventory CLI."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "inventory.py"


class InventoryTests(unittest.TestCase):
    def test_sources_archives_and_output_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            src = base / "src"
            src.mkdir()
            (src / "demo.py").write_bytes(b"result = 42\n")
            with zipfile.ZipFile(src / "copy.zip", "w") as package:
                package.write(src / "demo.py", "demo.py")

            def run(target):
                return subprocess.run(
                    [sys.executable, str(SCRIPT), "--source", f"sample={src}",
                     "--output", str(target)], capture_output=True, text=True
                )

            existing = base / "existing.json"
            # Try two unsafe destinations before checking the successful inventory.
            existing.write_bytes(b'{"owner":"existing data"}')
            self.assertEqual(run(existing).returncode, 2)
            self.assertEqual(existing.read_bytes(), b'{"owner":"existing data"}')
            nested = src / "manifest.json"
            self.assertEqual(run(nested).returncode, 2)
            self.assertFalse(nested.exists())
            report_path = base / "manifest.json"
            result = run(report_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            # The ZIP member and loose file have different paths and identical bytes.
            self.assertEqual(report["source_occurrences"], 2)
            self.assertEqual(report["unique_source_hashes"], 1)
            self.assertEqual(len(report["roots"][0]["archives"]), 1)
            self.assertEqual(run(report_path).returncode, 2)


if __name__ == "__main__":
    unittest.main()
