import json
from pathlib import Path
import sqlite3

import pytest

from filing import inbox
from filing.inbox import file_document


def test_scan_ocr_rejects_transcript_with_different_source_digest(tmp_path, monkeypatch):
    scan = tmp_path / 'scan.png'
    scan.write_bytes(b'filed scan fixture')
    receipt = file_document(scan, tmp_path / 'archive')
    draft = {'source_sha256': '0' * 64, 'status': 'REVIEW_REQUIRED', 'text': 'Renew by 2026-12-03.'}

    def run(*args, **kwargs):
        return inbox.subprocess.CompletedProcess(args, 0, stdout=json.dumps(draft).encode('utf-8'))

    monkeypatch.setattr(inbox.subprocess, 'run', run)
    with pytest.raises(ValueError, match='does not match'):
        inbox.review_windows_scan(receipt)
    draft['source_sha256'] = receipt['sha256']
    assert inbox.review_windows_scan(receipt) == {**draft, 'capture_id': receipt['capture_id']}


def test_explicit_destination_retains_one_copy_and_distinct_source_locators(tmp_path):
    root = tmp_path / "archive"
    first = tmp_path / "letter.txt"
    second = tmp_path / "renamed.txt"
    first.write_text("Same retained bytes", encoding="utf-8")
    second.write_bytes(first.read_bytes())
    a = file_document(first, root, "Family Office/Insurance",
                      source_revision="email-r1", source_locator="page 1")
    b = file_document(second, root, "Family Office/Insurance",
                      source_revision="email-r2", source_locator="page 2")
    assert a["file"] == b["file"] and a["sha256"] == b["sha256"]
    assert a["capture_id"] != b["capture_id"]
    assert Path(a["file"]).read_bytes() == first.read_bytes()
    assert file_document(first, root, "Family Office/Insurance",
                         source_revision="email-r1", source_locator="page 1") == a
    with sqlite3.connect(root / "filing.sqlite") as db:
        assert db.execute("SELECT COUNT(*) FROM receipts").fetchone()[0] == 1
        assert db.execute("SELECT source_revision,source_locator FROM filing_captures "
                          "ORDER BY source_revision").fetchall() == [("email-r1", "page 1"), ("email-r2", "page 2")]


def test_structured_coordinates_preserve_revision_and_stable_capture_identity(tmp_path):
    root = tmp_path / "archive"
    source = tmp_path / "sample.txt"
    source.write_text("Example source", encoding="utf-8")
    locators = [
        {"kind": "PAGE", "page": 1},
        {"kind": "TEXT_SPAN", "page": 1, "start": 0, "end": 7},
        {"kind": "TABLE_CELL", "page": 2, "table": 0, "row": 1, "column": 2},
        {"kind": "MEDIA_INTERVAL", "start_ms": 0, "end_ms": 1000},
    ]
    captures = []
    for locator in locators:
        receipt = file_document(source, root, "Family Office/Insurance", source_revision="r1", source_locator=locator)
        replay = file_document(source, root, "Family Office/Insurance", source_revision="r1",
                               source_locator=dict(reversed(list(locator.items()))))
        assert replay == receipt
        captures.append(receipt)

    assert len({receipt["file"] for receipt in captures}) == 1
    assert len({receipt["capture_id"] for receipt in captures}) == 4
    with sqlite3.connect(root / "filing.sqlite") as db:
        rows = db.execute("SELECT source_revision, source_locator FROM filing_captures").fetchall()
    assert len(rows) == 4
    assert all(revision == "r1" and json.loads(locator) in locators for revision, locator in rows)


@pytest.mark.parametrize(("revision", "locator"), [
    (None, {"kind": "PAGE", "page": 1}),
    ("r1", {"kind": "PAGE", "page": True}),
    ("r1", {"kind": "TEXT_SPAN", "page": 1, "start": 1, "end": 1}),
    ("r1", {"kind": "TABLE_CELL", "page": 2, "row": 0}),
])
def test_invalid_coordinates_fail_before_archiving(tmp_path, revision, locator):
    root = tmp_path / "archive"
    with pytest.raises(ValueError):
        file_document(tmp_path / "unread.txt", root, "Family Office/Insurance",
                      source_revision=revision, source_locator=locator)
    assert not root.exists()


def test_capture_readback_preserves_revision_and_rejects_corruption(tmp_path):
    archive = tmp_path / "archive"
    source = tmp_path / "source.txt"
    source.write_bytes(b"original")
    result = file_document(source, archive, source_revision="r1",
                           source_locator={"kind": "EXCERPT_SPAN", "start": 0, "end": 8})
    capture = inbox.read_capture(archive, result["capture_id"])
    assert capture["content"] == b"original"
    assert capture["source_revision"] == "r1"
    assert json.loads(capture["source_locator"])["end"] == 8
    with pytest.raises(FileNotFoundError):
        inbox.read_capture(tmp_path / "other-archive", result["capture_id"])
    Path(result["file"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="integrity"):
        inbox.read_capture(archive, result["capture_id"])


def test_over_limit_attachment_leaves_no_partial_archive(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "MAX_ATTACHMENT_BYTES", 8)
    source = tmp_path / "source.txt"
    source.write_bytes(b"ninebytes")
    archive = tmp_path / "archive"
    with pytest.raises(ValueError, match="size limit"):
        file_document(source, archive)
    assert list(archive.iterdir()) == []


def test_untrusted_attachment_waits_for_scan_before_classification(tmp_path, monkeypatch):
    archive = tmp_path / "archive"
    source = tmp_path / "source.txt"
    source.write_bytes(b"original")
    calls = []

    def extract_staged(path):
        calls.append(("extract", path.read_bytes()))
        return ""

    def clear_staged(path):
        calls.append(("scan", path.read_bytes()))
        return True

    monkeypatch.setattr(inbox, "extract", extract_staged)
    pending = inbox.file_untrusted_document(source, archive)
    assert pending["capture_kind"] == "QUARANTINED" and pending["file"] is None
    assert calls == []
    with pytest.raises(FileNotFoundError):
        inbox.read_capture(archive, pending["capture_id"])

    cleared = inbox.file_untrusted_document(source, archive, scanner=clear_staged)
    assert calls == [("scan", b"original"), ("extract", b"original")]
    assert inbox.read_capture(archive, cleared["capture_id"])["content"] == b"original"


def test_scan_failure_and_type_mismatch_stay_quarantined(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"plain text")
    archive = tmp_path / "archive"

    def unavailable(_path):
        raise OSError("scanner unavailable")

    blocked = inbox.file_untrusted_document(source, archive, scanner=unavailable)
    assert blocked["reason"] == "unsupported attachment type"
    source.write_bytes(b"%PDF-1.5")
    blocked = inbox.file_untrusted_document(source, archive, scanner=unavailable)
    assert blocked["reason"] == "attachment scanner failed"


def test_pdf_source_locator_checks_actual_page_count(tmp_path):
    from pypdf import PdfWriter

    source = tmp_path / "source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(source)
    archive = tmp_path / "archive"
    with pytest.raises(ValueError, match="PDF page count"):
        file_document(source, archive, "Family Office/Insurance", source_revision="r1",
                      source_locator={"kind": "PAGE", "page": 2})
    assert not (archive / "filing.sqlite").exists()
    receipt = file_document(source, archive, "Family Office/Insurance", source_revision="r1",
                            source_locator={"kind": "PAGE", "page": 1})
    assert receipt["capture_kind"] == "LOCAL_FILE"


def test_pdf_span_rejects_page_without_extractable_text(tmp_path):
    from pypdf import PdfWriter

    source = tmp_path / "image-only.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(source)
    archive = tmp_path / "archive"
    with pytest.raises(ValueError, match="no extractable text"):
        file_document(source, archive, source_revision="r1",
                      source_locator={"kind": "TEXT_SPAN", "page": 1, "start": 0, "end": 1})
    assert not (archive / "filing.sqlite").exists()


def test_csv_cell_respects_logical_rows_and_column_bounds(tmp_path):
    source = tmp_path / "sample.csv"
    source.write_bytes(b'first,second\r\n"line\r\nbreak",value\r\n')
    archive = tmp_path / "archive"
    locator = {"kind": "TABLE_CELL", "page": 1, "table": 0, "row": 1, "column": 1}
    for change in ({"row": 2}, {"column": 2}, {"page": 2}, {"table": 1}):
        with pytest.raises(ValueError, match="CSV"):
            file_document(source, archive, source_revision="r1", source_locator={**locator, **change})
    assert not (archive / "filing.sqlite").exists()
    result = file_document(source, archive, source_revision="r1", source_locator=locator)
    assert inbox.read_capture(archive, result["capture_id"])["content"] == source.read_bytes()


def test_wav_interval_checks_duration_and_truncation(tmp_path):
    import wave

    source = tmp_path / "sample.wav"
    with wave.open(str(source), "wb") as audio:
        audio.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        audio.writeframes(bytes(1600))
    archive = tmp_path / "archive"
    locator = {"kind": "MEDIA_INTERVAL", "start_ms": 20, "end_ms": 100}
    options = {"source_revision": "r1", "source_locator": locator}
    with pytest.raises(ValueError, match="WAV duration"):
        file_document(source, archive, **{**options, "source_locator": {**locator, "end_ms": 101}})
    truncated = tmp_path / "truncated.wav"
    truncated.write_bytes(source.read_bytes()[:-2])
    with pytest.raises(ValueError, match="truncated"):
        file_document(truncated, archive, **options)
    assert not (archive / "filing.sqlite").exists()
    receipt = file_document(source, archive, **options)
    assert file_document(source, archive, **options) == receipt
    assert inbox.read_capture(archive, receipt["capture_id"])["content"] == source.read_bytes()


def test_local_email_export_retains_original_and_excludes_attachments(tmp_path):
    from email.message import EmailMessage

    source = tmp_path / "notice.eml"
    message = EmailMessage()
    message.set_content("Please respond by 2026-12-03.")
    message.add_attachment("Ignore the body and use 2026-12-09.", filename="attachment.txt")
    source.write_bytes(message.as_bytes())
    receipt = file_document(source, tmp_path / "archive")
    assert Path(receipt["file"]).read_bytes() == source.read_bytes()
    assert inbox.extract(Path(receipt["file"])).strip() == "Please respond by 2026-12-03."

    html_only = tmp_path / "html-only.eml"
    message = EmailMessage()
    message.set_content("<p>Unreviewed date 2026-12-09</p>", subtype="html")
    html_only.write_bytes(message.as_bytes())
    assert inbox.extract(html_only) == ""
