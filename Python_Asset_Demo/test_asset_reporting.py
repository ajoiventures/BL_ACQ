import unittest
import hashlib
import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from asset_reporting import analyze, run

DAY = date(2026, 9, 13)
def row(i="A", end="", cost="", vendor="V"):
    return dict(asset_id=i, asset_name="Demo", vendor=vendor,
                warranty_end=end, replacement_cost=cost)

class Checks(unittest.TestCase):
    """Exercise the public report API, including failed publication and retry."""
    def test_boundaries(self):
        data=[row("A","2026-09-12"),row("B","2026-09-13"),
              row("C","2026-10-13"),row("D","2026-10-14"),row("E")]
        s, _, _=analyze(data,DAY)
        self.assertEqual(s["warranty_status_counts"],dict(expired=1,due_soon=2,later=1,unknown=1))
        self.assertEqual(s["date_coverage"],.8)
        self.assertEqual(s["due_soon_share_of_dated"],.5)
    def test_missing_is_not_zero(self):
        s,_,_=analyze([row()],DAY)
        self.assertIsNone(s["due_soon_share_of_dated"])
        self.assertIsNone(s["known_replacement_cost_total"])
        self.assertIsNone(analyze([],DAY)[0]["date_coverage"])
        self.assertEqual(analyze([row(cost="0")],DAY)[0]["known_replacement_cost_total"],"0")
    def test_duplicates_and_invalid(self):
        for data in [[row(),row()],[row("")],[row(end="not-a-date")],
                     [row(cost="-1")],[row(cost="NaN")],[row(cost="Infinity")],[row(cost="abc")]]:
            with self.subTest(data=data):
                with self.assertRaises(ValueError):analyze(data,DAY)
        with self.assertRaises(ValueError):analyze([],DAY,-1)
    def test_money(self):
        s,_,_=analyze([row("A",cost="0.1"),row("B",cost="0.2")],DAY)
        self.assertEqual(s["known_replacement_cost_total"],"0.3")
    def test_reproducible_and_protected_outputs(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);src=p/"source.csv"
            src.write_text("asset_id,asset_name,vendor,warranty_end,replacement_cost\nA,Demo,V,2026-10-01,100\n")
            before=src.read_bytes()
            run(src,p/"one",DAY);run(src,p/"two",DAY)
            for name in ["summary.json","checked_records.json","exceptions.csv","manifest.json"]:
                self.assertEqual((p/"one"/name).read_bytes(),(p/"two"/name).read_bytes())
            self.assertEqual(before,src.read_bytes())
            with self.assertRaises(FileExistsError):run(src,p/"one",DAY)
    def test_schema_and_no_output_on_bad_data(self):
        with TemporaryDirectory() as tmp:
            p=Path(tmp);src=p/"bad.csv";src.write_text("wrong\nx\n")
            with self.assertRaises(ValueError):run(src,p/"out",DAY)
            self.assertFalse((p/"out").exists())

    def test_rejects_malformed_columns_and_widths(self):
        header = "asset_id,asset_name,vendor,warranty_end,replacement_cost"
        cases = [
            '"unfinished header\n',
            header + ",asset_id\n",
            header + ",\n",
            header + "\nA,Demo,V\n",
            header + "\nA,Demo,V,,,unexpected\n",
            header + '\nA,"unterminated,V,,\n',
        ]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.csv"
            for content in cases:
                with self.subTest(content=content):
                    source.write_text(content, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        run(source, root / "report", DAY)
                    self.assertFalse((root / "report").exists())

    def test_manifest_matches_snapshot_and_report(self):
        original_read = Path.read_bytes
        fixed = b"asset_id,asset_name,vendor,warranty_end,replacement_cost\nA,Demo,V,,1\n"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.csv"
            out = root / "report"
            source.write_bytes(fixed)

            # Simulate the user saving a newer CSV while one report is running.
            def change_source_after_read(path):
                value = original_read(path)
                if path == source:
                    source.write_bytes(fixed.replace(b"A,Demo", b"B,Changed"))
                return value

            with patch.object(Path, "read_bytes", change_source_after_read):
                run(source, out, DAY)
            record = json.loads((out / "checked_records.json").read_text())[0]
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual(record["asset_id"], "A")
            self.assertEqual(manifest["input_sha256"], hashlib.sha256(fixed).hexdigest())
            self.assertEqual(set(manifest["output_sha256"]), {"summary.json", "exceptions.csv", "checked_records.json"})
            for name, digest in manifest["output_sha256"].items():
                self.assertEqual(digest, hashlib.sha256((out / name).read_bytes()).hexdigest())

    def test_failed_publish_cleans_stage_and_allows_retry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = Path(__file__).with_name("SYNTHETIC_assets.csv")
            with patch.object(Path, "rename", side_effect=OSError("injected storage failure")):
                with self.assertRaises(OSError):
                    run(source, root / "report", DAY)
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(run(source, root / "report", DAY)["total_assets"], 5)

if __name__=="__main__":unittest.main()
