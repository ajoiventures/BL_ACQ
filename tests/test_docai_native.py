"""Adverse-case checks for local native intake and source-bound extraction."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from filing import inbox
from pilot.document_contracts import SCHEMA_VERSION
from pilot.document_native import extract_document


class NativeDocuments(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.archive = self.folder / "archive"
        self.routes = self.folder / "routes.json"
        self.routes.write_text(json.dumps({"Review": [], "Invoices": ["invoice", "total due"]}), encoding="utf-8")
        self.config = mock.patch.object(inbox, "CONFIG", self.routes)
        self.config.start()
        self.addCleanup(self.config.stop)

    def source(self, name="invoice.txt", raw=b"Invoice: TEST-001\nTotal due: 1.00\n"):
        path = self.folder / name
        path.write_bytes(raw)
        return path

    def document(self, path, raw=None):
        raw = path.read_bytes() if raw is None else raw
        return {"schema_version": SCHEMA_VERSION, "document_id": "test-document",
                "context": {"tenant_id": "test", "domain": "commercial", "subject_id": "test", "case_id": None},
                "version": 1, "source_uri": "fixture://native/" + path.name,
                "title": "Synthetic native test", "media_type": "application/octet-stream",
                "document_class": "MEP_INVOICE", "content_sha256": hashlib.sha256(raw).hexdigest(),
                "byte_count": len(raw), "received_at": "2026-01-01T00:00:00Z", "source_status": "synthetic"}

    def run_source(self, path, **kwargs):
        return extract_document(path, self.document(path), "test-run", **kwargs)

    def docx(self, xml, extras=None):
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", xml)
            for name, value in (extras or {}).items():
                archive.writestr(name, value)
        return self.source("invoice.docx", raw.getvalue())

    def test_snapshot_survives_source_change_and_uses_actual_bytes(self):
        path = self.source()
        original = path.read_bytes()
        original_extract = inbox.extract

        def change_original_after_snapshot(snapshot):
            path.write_bytes(b"Changed source after snapshot\n")
            return original_extract(snapshot)

        with mock.patch.object(inbox, "extract", side_effect=change_original_after_snapshot):
            receipt = inbox.file_document(path, self.archive)
        self.assertEqual(set(receipt), {"destination", "file", "sha256", "reason"})
        self.assertTrue(Path(receipt["file"]).is_absolute())
        self.assertEqual(Path(receipt["file"]).read_bytes(), original)
        self.assertEqual(receipt["sha256"], hashlib.sha256(original).hexdigest())
        self.assertNotEqual(path.read_bytes(), original)
        second = inbox.file_document(path, self.archive)
        self.assertNotEqual(second["sha256"], receipt["sha256"])
        self.assertTrue(Path(receipt["file"]).exists())

    def test_duplicate_is_idempotent_and_preserves_old_receipt(self):
        path = self.source()
        first = inbox.file_document(path, self.archive)
        with sqlite3.connect(self.archive / "filing.sqlite") as db:
            db.execute("UPDATE receipts SET reason='historic reason', filed_at='2020-01-02 03:04:05'")
            old = db.execute("SELECT * FROM receipts").fetchall()
        again = inbox.file_document(path, self.archive)
        self.assertEqual(first, again)
        with sqlite3.connect(self.archive / "filing.sqlite") as db:
            self.assertEqual(db.execute("SELECT * FROM receipts").fetchall(), old)
        self.assertEqual(len(list((self.archive / "Invoices").iterdir())), 1)

    def test_archive_orphan_replay_repairs_receipt(self):
        path = self.source()
        with mock.patch.object(inbox.sqlite3, "connect", side_effect=sqlite3.OperationalError("test interruption")):
            with self.assertRaises(sqlite3.OperationalError):
                inbox.file_document(path, self.archive)
        archived = list((self.archive / "Invoices").iterdir())
        self.assertEqual(len(archived), 1)
        receipt = inbox.file_document(path, self.archive)
        self.assertEqual(Path(receipt["file"]), archived[0])
        with sqlite3.connect(self.archive / "filing.sqlite") as db:
            self.assertEqual(db.execute("SELECT count(*) FROM receipts").fetchone(), (1,))

    def test_conflicting_archive_or_receipt_fails_without_rewrite(self):
        path = self.source()
        receipt = inbox.file_document(path, self.archive)
        archived = Path(receipt["file"])
        archived.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "integrity"):
            inbox.file_document(path, self.archive)
        self.assertEqual(archived.read_bytes(), b"corrupt")
        archived.write_bytes(path.read_bytes())
        with sqlite3.connect(self.archive / "filing.sqlite") as db:
            db.execute("UPDATE receipts SET hash=?", ("0" * 64,))
        with self.assertRaisesRegex(ValueError, "receipt hash"):
            inbox.file_document(path, self.archive)

    def test_old_receipt_table_and_other_rows_survive(self):
        self.archive.mkdir(mode=0o700)
        with sqlite3.connect(self.archive / "filing.sqlite") as db:
            db.execute("CREATE TABLE receipts(path TEXT PRIMARY KEY, hash TEXT, reason TEXT, filed_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("INSERT INTO receipts VALUES('Historic/old.txt', 'historical-hash', 'old reason', '2001-01-01 01:01:01')")
        inbox.file_document(self.source(), self.archive)
        with sqlite3.connect(self.archive / "filing.sqlite") as db:
            old = db.execute("SELECT * FROM receipts WHERE path='Historic/old.txt'").fetchone()
        self.assertEqual(old, ("Historic/old.txt", "historical-hash", "old reason", "2001-01-01 01:01:01"))

    def test_routes_are_generic_explicit_and_confined(self):
        path = self.source()
        explicit = inbox.file_document(path, self.archive, "Review")
        self.assertEqual(explicit["destination"], "Review")
        for name in ("../escape", "/escape", "A/../escape", "A\\escape", "C:escape"):
            with self.subTest(name=name):
                self.routes.write_text(json.dumps({name: []}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    inbox.file_document(path, self.archive, name)
        self.assertFalse((self.folder / "escape").exists())

    def test_symlink_source_root_route_archive_and_database_are_rejected(self):
        path = self.source()
        alias = self.folder / "alias.txt"
        alias.symlink_to(path)
        with self.assertRaises(ValueError):
            inbox.file_document(alias, self.archive)
        real = self.folder / "real"
        real.mkdir(mode=0o700)
        root_alias = self.folder / "root-alias"
        root_alias.symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            inbox.file_document(path, root_alias)
        self.archive.mkdir(mode=0o700, exist_ok=True)
        (self.archive / "Invoices").symlink_to(real, target_is_directory=True)
        with self.assertRaises(ValueError):
            inbox.file_document(path, self.archive)
        (self.archive / "Invoices").unlink()
        receipt = inbox.file_document(path, self.archive)
        target = Path(receipt["file"])
        target.unlink()
        target.symlink_to(path)
        with self.assertRaises(ValueError):
            inbox.file_document(path, self.archive)
        target.unlink()
        (self.archive / "filing.sqlite").unlink()
        (self.archive / "filing.sqlite").symlink_to(path)
        with self.assertRaises(ValueError):
            inbox.file_document(path, self.archive)
        self.assertEqual(path.read_bytes(), b"Invoice: TEST-001\nTotal due: 1.00\n")

    def test_long_unicode_filename_keeps_suffix_and_bounded_component(self):
        path = self.source("é" * 100 + ".txt")
        receipt = inbox.file_document(path, self.archive)
        archived = Path(receipt["file"])
        self.assertEqual(archived.suffix, ".txt")
        self.assertLessEqual(len(archived.name.encode("utf-8")), 255)
        self.assertEqual(archived.read_bytes(), path.read_bytes())

    def test_oversize_source_rejected_before_archive(self):
        path = self.source()
        with path.open("r+b") as output:
            output.truncate(inbox.MAX_ARCHIVE_BYTES + 1)
        with self.assertRaisesRegex(ValueError, "16 MiB"):
            inbox.file_document(path, self.archive)
        self.assertFalse((self.archive / "filing.sqlite").exists())

    def test_plain_text_is_exact_hashed_and_native_cpu(self):
        raw = "SYNTHETIC\nVendor: Café HVAC 🏠\n".encode("utf-8")
        result = self.run_source(self.source(raw=raw))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["pages"][0]["text"], raw.decode("utf-8"))
        self.assertEqual(result["pages"][0]["text_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual((result["method"], result["backend"], result["provider"]), ("native", "cpu", None))
        self.assertEqual(result["coverage"]["processed_bytes"], len(raw))

    def test_utf8_truncation_preserves_codepoints_and_is_partial(self):
        path = self.source(raw="Aé🏠Z".encode("utf-8"))
        for limit, expected in ((2, "A"), (3, "Aé"), (5, "Aé"), (7, "Aé🏠")):
            with self.subTest(limit=limit):
                result = self.run_source(path, limits={"max_text_bytes": limit})
                self.assertEqual(result["status"], "partial")
                self.assertEqual(result["pages"][0]["text"], expected)
                self.assertTrue(result["coverage"]["truncated"])
                self.assertEqual(result["coverage"]["processed_bytes"], len(expected.encode("utf-8")))
        result = self.run_source(path, limits={"max_chars_per_page": 2})
        self.assertEqual(result["pages"][0]["text"], "Aé")
        self.assertEqual(result["status"], "partial")

    def test_invalid_utf8_is_an_error_without_replacement_text(self):
        result = self.run_source(self.source(raw=b"Invoice: \xff\n"))
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "INVALID_UTF8")
        self.assertEqual(result["pages"], [])

    def test_empty_unsupported_and_declared_input_limit_are_distinct(self):
        cases = (("empty.txt", b"", "error", "EMPTY_DOCUMENT"),
                 ("unknown.xlsx", b"unknown", "unsupported", "UNSUPPORTED_FORMAT"))
        for name, raw, status, code in cases:
            result = self.run_source(self.source(name, raw))
            self.assertEqual((result["status"], result["errors"][0]["code"]), (status, code))
        result = self.run_source(self.source(), limits={"max_input_bytes": 1})
        self.assertEqual(result["errors"][0]["code"], "INPUT_LIMIT_EXCEEDED")
        self.assertFalse(result["coverage"]["complete"])

    def test_source_hash_or_byte_count_mismatch_is_rejected(self):
        path = self.source()
        document = self.document(path)
        document["content_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source bytes"):
            extract_document(path, document, "test-run")
        document = self.document(path)
        document["byte_count"] += 1
        with self.assertRaisesRegex(ValueError, "source bytes"):
            extract_document(path, document, "test-run")

    def test_docx_main_xml_and_additional_content_coverage(self):
        path = self.docx('<document><p>Invoice:</p><p>Café</p></document>')
        result = self.run_source(path)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["pages"][0]["text"], "Invoice: Café")
        path = self.docx('<document><p>Invoice</p></document>', {"word/header1.xml": "ignored header"})
        result = self.run_source(path)
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["coverage"]["complete"])

    def test_docx_malformed_unsafe_and_xml_limit(self):
        malformed = self.run_source(self.source("broken.docx", b"bad zip"))
        self.assertEqual(malformed["errors"][0]["code"], "MALFORMED_DOCX")
        malformed = self.run_source(self.docx("<document>unclosed"))
        self.assertEqual(malformed["errors"][0]["code"], "MALFORMED_DOCX")
        unsafe = self.run_source(self.docx('<!DOCTYPE d [<!ENTITY x "secret">]><d>&x;</d>'))
        self.assertEqual(unsafe["errors"][0]["code"], "UNSAFE_XML")
        limited = self.run_source(self.docx("<d>Invoice</d>"), limits={"max_xml_bytes": 4})
        self.assertEqual(limited["status"], "partial")
        self.assertTrue(limited["coverage"]["truncated"])
        self.assertEqual(limited["pages"], [])

    def test_worker_timeout_and_bad_exit_are_structured(self):
        path = self.source("invoice.pdf", b"%PDF-fake")
        with mock.patch.object(inbox.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 10)):
            result = self.run_source(path)
        self.assertEqual(result["errors"][0]["code"], "PROCESSING_TIMEOUT")
        with mock.patch.object(inbox.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, b"")):
            result = self.run_source(path)
        self.assertEqual(result["errors"][0]["code"], "PROCESSING_FAILED")

    def test_missing_pdf_dependency_has_a_distinct_error(self):
        # A real isolated interpreter with site-packages disabled exercises the
        # optional dependency boundary without changing the test environment.
        result = subprocess.run([sys.executable, "-S", str(Path(inbox.__file__).resolve()),
                                 "--extract-worker", ".pdf", json.dumps(inbox.DEFAULT_LIMITS)],
                                input=b"%PDF-fake", capture_output=True, check=True, timeout=15)
        parsed = json.loads(result.stdout)
        self.assertEqual(parsed["status"], "error")
        self.assertEqual(parsed["errors"][0]["code"], "DEPENDENCY_MISSING")

    def test_pdf_malformed_blank_and_page_budget(self):
        try:
            import pypdf
        except ImportError:
            self.skipTest("optional pypdf is not installed")
        malformed = self.run_source(self.source("broken.pdf", b"%PDF-fake"))
        self.assertEqual(malformed["errors"][0]["code"], "MALFORMED_PDF")
        writer = pypdf.PdfWriter()
        for _ in range(3):
            writer.add_blank_page(width=72, height=72)
        raw = io.BytesIO()
        writer.write(raw)
        path = self.source("blank.pdf", raw.getvalue())
        result = self.run_source(path)
        self.assertEqual(result["status"], "needs_ocr")
        self.assertEqual(result["coverage"]["total_pages"], 3)
        self.assertEqual([page["text"] for page in result["pages"]], ["", "", ""])
        self.assertIn("pypdf=" + pypdf.__version__, result["processor_version"])
        result = self.run_source(path, limits={"max_pages": 1})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["coverage"]["processed_pages"], 1)
        self.assertTrue(result["coverage"]["truncated"])

    def test_scan_pdf_and_native_pdf_fixture_have_distinct_coverage(self):
        try:
            __import__("pypdf")
        except ImportError:
            self.skipTest("optional pypdf is not installed")
        fixture_folder = Path(__file__).parent / "fixtures" / "docai"
        scan = self.run_source(fixture_folder / "invoice_scan.pdf")
        self.assertEqual(scan["status"], "needs_ocr")
        native = self.run_source(fixture_folder / "invoice_native.pdf")
        self.assertEqual(native["status"], "complete")
        self.assertIn("Invoice", native["pages"][0]["text"])

    def test_pdf_mixed_native_text_and_image_content_is_partial(self):
        try:
            import pypdf
            from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, NumberObject
        except ImportError:
            self.skipTest("optional pypdf is not installed")
        source = Path(__file__).parent / "fixtures" / "docai" / "invoice_native.pdf"
        writer = pypdf.PdfWriter()
        page = writer.add_page(pypdf.PdfReader(source).pages[0])
        picture = DecodedStreamObject()
        picture.set_data(b"\xff\x00\x00")
        picture.update({NameObject("/Type"): NameObject("/XObject"),
                        NameObject("/Subtype"): NameObject("/Image"),
                        NameObject("/Width"): NumberObject(1), NameObject("/Height"): NumberObject(1),
                        NameObject("/ColorSpace"): NameObject("/DeviceRGB"),
                        NameObject("/BitsPerComponent"): NumberObject(8)})
        page["/Resources"][NameObject("/XObject")] = DictionaryObject({NameObject("/TestImage"): writer._add_object(picture)})
        drawing = DecodedStreamObject()
        drawing.set_data(b"q 10 0 0 10 10 10 cm /TestImage Do Q")
        previous = page["/Contents"]
        page[NameObject("/Contents")] = ArrayObject([previous, writer._add_object(drawing)])
        raw = io.BytesIO()
        writer.write(raw)
        result = self.run_source(self.source("mixed.pdf", raw.getvalue()))
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["coverage"]["complete"])
        self.assertTrue(any("XObjects" in note for note in result["coverage"]["notes"]))
        self.assertIn("Invoice", result["pages"][0]["text"])

    def test_image_signature_requires_ocr_without_image_decode_claim(self):
        result = self.run_source(self.source("scan.png", b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(result["status"], "needs_ocr")
        self.assertEqual(result["coverage"]["page_basis"], "logical")
        self.assertFalse(result["coverage"]["complete"])
        malformed = self.run_source(self.source("bad.png", b"not a png"))
        self.assertEqual(malformed["errors"][0]["code"], "MALFORMED_IMAGE")

    def test_unknown_and_unbounded_limits_are_rejected(self):
        path = self.source()
        for limits in ({"unknown": 3}, {"max_text_bytes": True}, {"max_pages": 101}, {"max_input_bytes": 1 << 30}):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                self.run_source(path, limits=limits)


if __name__ == "__main__":
    unittest.main()
