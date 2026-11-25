"""Local filing agent. Changes to filing/routes.json take effect on the next intake."""
import argparse
import base64
import binascii
from contextlib import closing
import csv
from email import policy
from email.parser import BytesParser
from itertools import islice
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import wave
import zipfile
from xml.etree import ElementTree

CONFIG = Path(__file__).with_name('routes.json')
MAX_ATTACHMENT_BYTES = 32 * 1024 * 1024

def extract(path):
    if path.suffix.lower() in {'.txt','.md','.csv'}:
        return path.read_bytes()[:150000].decode('utf-8',errors='replace')
    if path.suffix.lower() == ".eml":
        # Trusted local export. Skip attached messages, attachments and HTML.
        with path.open("rb") as stream:
            raw = stream.read(1_000_001)
        return extract_eml(raw)
    if path.suffix.lower()=='.docx':
        with zipfile.ZipFile(path) as archive:
            info=archive.getinfo('word/document.xml')
            if info.file_size>2000000:
                return ''
            return ' '.join(ElementTree.fromstring(archive.read(info)).itertext())
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        return ' '.join((page.extract_text() or '')[:20000] for page in PdfReader(path).pages[:5])
    return ''

def extract_eml(raw: bytes) -> str:
    if len(raw) > 1_000_000:
        return ""
    try:
        email = BytesParser(policy=policy.default).parsebytes(raw)
        body = email.get_body(preferencelist=("plain",))
        if body is None or body.get_content_disposition() == "attachment" or body.get_filename():
            return ""
        return body.get_content()[:150_000]
    except (LookupError, UnicodeError, RecursionError):
        return ""


def encode_source_locator(locator):
    """Retain structured coordinates while preserving legacy labels."""
    if locator is None or isinstance(locator, str):
        return locator
    if not isinstance(locator, dict):
        raise ValueError("Source locator must be a label or an object")
    coordinate_fields = {
        "PAGE": ("page",),
        "TEXT_SPAN": ("page", "start", "end"),
        "EXCERPT_SPAN": ("start", "end"),
        "TABLE_CELL": ("page", "table", "row", "column"),
        "MEDIA_INTERVAL": ("start_ms", "end_ms"),
    }.get(locator.get("kind") if isinstance(locator.get("kind"), str) else None)
    if coordinate_fields is None or set(locator) != {"kind", *coordinate_fields}:
        raise ValueError("Source locator has an unknown kind or incorrect fields")
    if any(type(locator[key]) is not int or locator[key] < 0 for key in coordinate_fields):
        raise ValueError("Source coordinates must be nonnegative integers")
    if "page" in locator and locator["page"] == 0:
        raise ValueError("Source page numbering starts at one")
    if any(start in locator and locator[end] <= locator[start]
           for start, end in (("start", "end"), ("start_ms", "end_ms"))):
        raise ValueError("Source interval end must follow its start")
    return json.dumps(locator, sort_keys=True, separators=(",", ":"))


def read_capture(root, capture_id):
    """Read verified attachment bytes from an archive already authorized by the caller."""
    if not isinstance(capture_id, str) or len(capture_id) != 64:
        raise ValueError("Invalid capture ID")
    database = root / "filing.sqlite"
    if not database.is_file():
        raise FileNotFoundError("Capture not found")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        row = db.execute(
            """SELECT c.path, c.source_name, c.source_revision, c.source_locator,
                      c.capture_kind, r.hash
               FROM filing_captures c JOIN receipts r ON r.path = c.path
               WHERE c.capture_id = ?""",
            (capture_id,),
        ).fetchone()
    if row is None:
        raise FileNotFoundError("Capture not found")
    relative, name, revision, locator, kind, digest = row
    expected_id = hashlib.sha256(
        json.dumps((relative, name, revision, locator, kind), ensure_ascii=False).encode()
    ).hexdigest()
    if kind == "QUARANTINED":
        raise FileNotFoundError("Capture not found")
    target = (root / relative).resolve()
    if expected_id != capture_id or not target.is_relative_to(root.resolve()):
        raise ValueError("Capture receipt integrity check failed")
    with target.open("rb") as stream:
        content = stream.read(MAX_ATTACHMENT_BYTES + 1)
    if len(content) > MAX_ATTACHMENT_BYTES or hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Attachment integrity check failed")
    return {"capture_id": capture_id, "source_name": name, "source_revision": revision,
            "source_locator": locator, "capture_kind": kind, "sha256": digest, "content": content}


def file_untrusted_document(path, root, destination=None, *, scanner=None,
                            source_revision=None, source_locator=None):
    """File an attachment only after the configured scanner clears its staged bytes."""
    return _file_document(path, root, destination, source_revision, source_locator,
                          untrusted=True, scanner=scanner)


def file_document(path, root, destination=None, *, source_revision=None, source_locator=None):
    return _file_document(path, root, destination, source_revision, source_locator)


def defender_scan(executable, snapshot):
    """Require a confirmed clean custom scan with remediation disabled."""
    result = subprocess.run(
        [str(executable.resolve(strict=True)), "-Scan", "-ScanType", "3",
         "-File", str(snapshot.resolve(strict=True)), "-DisableRemediation"],
        capture_output=True, text=True, errors="replace", timeout=60, check=False,
    )
    confirmation = f"Scanning {snapshot.resolve()} found no threats."
    if result.returncode != 0:
        return False
    return confirmation.casefold() in {line.strip().casefold() for line in result.stdout.splitlines()}


def _scan_attachment(snapshot, scanner):
    with snapshot.open("rb") as stream:
        header = stream.read(8192)
    suffix = snapshot.suffix.lower()
    if suffix in {".txt", ".md", ".csv"}:
        allowed = b"\x00" not in header
    elif suffix == ".pdf":
        allowed = header.startswith(b"%PDF-")
    elif suffix == ".docx":
        allowed = header.startswith(b"PK\x03\x04")
    else:
        allowed = False
    if not allowed:
        return "unsupported attachment type"
    if scanner is None:
        return "attachment scanner unavailable"
    try:
        if scanner(snapshot) is True:
            return None
    except Exception:
        return "attachment scanner failed"
    return "attachment not cleared"


def _file_document(path, root, destination, source_revision, source_locator, *,
                   untrusted=False, scanner=None):
    routes=json.loads(CONFIG.read_text(encoding="utf-8"))
    if destination and destination not in routes:
        raise ValueError('Unknown destination. Choose an exact route from routes.json.')
    if isinstance(source_locator, dict) and (
        not isinstance(source_revision, str) or not source_revision.strip()
    ):
        raise ValueError("Structured source coordinates require a source revision")
    encoded_locator = encode_source_locator(source_locator)
    root.mkdir(parents=True,exist_ok=True)
    # Snapshot the actual bytes before classification and persistence.
    with tempfile.TemporaryDirectory(dir=root) as staging:
        snapshot=Path(staging)/path.name
        hasher = hashlib.sha256()
        byte_count = 0
        with path.open("rb") as source, snapshot.open("xb") as staged:
            while chunk := source.read(1024 * 1024):
                byte_count += len(chunk)
                if byte_count > MAX_ATTACHMENT_BYTES:
                    raise ValueError("Attachment exceeds the filing size limit")
                hasher.update(chunk)
                staged.write(chunk)
        digest = hasher.hexdigest()
        quarantine = _scan_attachment(snapshot, scanner) if untrusted else None
        if untrusted and scanner is not None:
            with snapshot.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                    raise ValueError("Attachment changed during scanning")
        if (not quarantine and snapshot.suffix.lower() == ".pdf"
                and isinstance(source_locator, dict) and "page" in source_locator):
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError

            try:
                with snapshot.open("rb") as stream:
                    pages = PdfReader(stream).pages
                    page_number = source_locator["page"]
                    if page_number > len(pages):
                        raise ValueError("Source page exceeds the PDF page count")
                    if source_locator["kind"] == "TEXT_SPAN":
                        # Offsets are Unicode code points in pypdf's unmodified page text.
                        text = pages[page_number - 1].extract_text() or ""
                        if not text:
                            raise ValueError("PDF page has no extractable text for the source span")
                        if source_locator["end"] > len(text):
                            raise ValueError("Source span exceeds the PDF page text")
            except PdfReadError as exc:
                raise ValueError("Could not verify the source PDF page") from exc
        if (not quarantine and snapshot.suffix.lower() == ".csv"
                and isinstance(source_locator, dict) and source_locator["kind"] == "TABLE_CELL"):
            # CSV is one table. Row zero is the first record, including any header.
            if source_locator["page"] != 1 or source_locator["table"] != 0:
                raise ValueError("CSV coordinates require page 1 and table 0")
            try:
                with snapshot.open(encoding="utf-8-sig", newline="") as stream:
                    records = csv.reader(stream, strict=True)
                    row = next(islice(records, min(source_locator["row"], byte_count), None), None)
            except (csv.Error, UnicodeError) as exc:
                raise ValueError("Could not verify the source CSV cell") from exc
            if row is None or source_locator["column"] >= len(row):
                raise ValueError("Source cell exceeds the CSV row or column bounds")
        if (not quarantine and snapshot.suffix.lower() == ".wav"
                and isinstance(source_locator, dict) and source_locator["kind"] == "MEDIA_INTERVAL"):
            try:
                with wave.open(str(snapshot), "rb") as audio:
                    frame_bytes = audio.getsampwidth() * audio.getnchannels()
                    frame_count = audio.getnframes()
                    frames_left = frame_count
                    while frames_left:
                        requested = min(frames_left, max(1, 65536 // frame_bytes))
                        if len(audio.readframes(requested)) != requested * frame_bytes:
                            raise ValueError("Source WAV data is truncated")
                        frames_left -= requested
                    if source_locator["end_ms"] * audio.getframerate() > frame_count * 1000:
                        raise ValueError("Source interval exceeds the WAV duration")
            except (wave.Error, EOFError) as exc:
                raise ValueError("Could not verify the source WAV duration") from exc
        capture_kind = "QUARANTINED" if quarantine else "LOCAL_FILE"
        if quarantine:
            folder, reason = ".quarantine", quarantine
        elif destination:
            folder,reason=destination,'explicit instruction'
        else:
            try:
                body=extract(snapshot).casefold()
            except Exception:
                body=''
            matches=[name for name,terms in routes.items() if any(term.casefold() in body for term in terms)]
            folder,reason=(matches[0],'content match') if len(matches)==1 else ('Review','ambiguous or unreadable')
        with closing(sqlite3.connect(root / "filing.sqlite")) as db, db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("""CREATE TABLE IF NOT EXISTS receipts
                (path TEXT PRIMARY KEY, hash TEXT, reason TEXT, filed_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("CREATE INDEX IF NOT EXISTS receipts_hash ON receipts(hash)")
            db.execute("""CREATE TABLE IF NOT EXISTS filing_captures (
                capture_id TEXT PRIMARY KEY, path TEXT NOT NULL, source_name TEXT NOT NULL,
                source_revision TEXT, source_locator TEXT, capture_kind TEXT NOT NULL
            )""")
            prior = next((stored for (stored,) in db.execute(
                "SELECT path FROM receipts WHERE hash=? ORDER BY path", (digest,)
            ) if Path(stored).parent == Path(folder)), None)
            target = root / prior if prior else root / folder / (digest + "--" + path.name[:120])
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.resolve().is_relative_to(root.resolve()):
                raise ValueError("Filing target leaves the private archive")
            try:
                os.link(snapshot, target)
            except FileExistsError:
                with target.open("rb") as existing:
                    if hashlib.file_digest(existing, "sha256").hexdigest() != digest:
                        raise ValueError("Destination integrity check failed")
            relative = str(target.relative_to(root))
            capture = (relative, path.name, source_revision, encoded_locator, capture_kind)
            capture_id = hashlib.sha256(json.dumps(capture, ensure_ascii=False).encode()).hexdigest()
            db.execute("INSERT OR IGNORE INTO receipts(path,hash,reason) VALUES(?,?,?)",
                       (relative, digest, reason))
            db.execute("INSERT OR IGNORE INTO filing_captures VALUES(?,?,?,?,?,?)",
                       (capture_id, *capture))
        return {"destination": folder, "file": None if quarantine else str(target), "sha256": digest,
                "reason": reason, "capture_id": capture_id, "capture_kind": capture_kind}

def review_windows_scan(receipt):
    """Read the retained image and bind draft OCR text to its filing capture."""
    path = Path(receipt['file'])
    if path.suffix.lower() not in {'.png', '.jpg', '.jpeg'}:
        raise ValueError('Scan OCR requires PNG or JPEG')
    script = Path(__file__).with_name('read_scan_windows.ps1')
    powershell = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    try:
        result = subprocess.run(
            [str(powershell), '-NoProfile', '-ExecutionPolicy', 'RemoteSigned',
             '-File', str(script), '-ScanPath', str(path.resolve())],
            capture_output=True, check=True, timeout=30,
        )
        draft = json.loads(result.stdout.decode('utf-8', errors='strict'))
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'capture_id': receipt['capture_id'], 'status': 'OCR_UNAVAILABLE'}
    if (not isinstance(draft, dict) or draft.get('source_sha256') != receipt['sha256']
            or draft.get('status') != 'REVIEW_REQUIRED' or not isinstance(draft.get('text'), str)):
        raise ValueError('OCR receipt does not match the retained scan')
    return {**draft, 'capture_id': receipt['capture_id']}


def extract_filed_mail(capture):
    suffix = Path(capture['source_name']).suffix.lower()
    if suffix == '.eml':
        return extract_eml(capture['content'])
    if suffix not in {'.png', '.jpg', '.jpeg'}:
        raise ValueError('Unsupported filed mail format')
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / ('scan' + suffix)
        path.write_bytes(capture['content'])
        draft = review_windows_scan({**capture, 'file': path})
    if draft['status'] != 'REVIEW_REQUIRED' or not draft['text'].strip():
        raise ValueError('Filed scan has no readable OCR text')
    return draft['text']


def file_gmail_raw(message_id, encoded, root):
    """File an explicitly selected Gmail API raw message without reserializing it."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', message_id):
        raise ValueError('Invalid Gmail message ID')
    if len(encoded) > 1_333_336 or not re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', encoded):
        raise ValueError('Invalid or oversized Gmail raw payload')
    try:
        original = base64.b64decode(encoded + '=' * (-len(encoded) % 4), altchars=b'-_', validate=True)
    except binascii.Error as exc:
        raise ValueError('Invalid Gmail raw payload') from exc
    if len(original) > 1_000_000 or not BytesParser(policy=policy.default).parsebytes(original).keys():
        raise ValueError('Expected a bounded RFC message with headers')
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / f'gmail-{message_id}.eml'
        path.write_bytes(original)
        return file_document(path, root, source_revision=message_id, source_locator=f'gmail:{message_id}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source',nargs='?',type=Path,help='Document or intake folder')
    parser.add_argument('--root',type=Path,required=True,help='Private archive directory')
    parser.add_argument('--to',help='Exact configured destination')
    parser.add_argument('--source-revision', help='Revision of an individual source document')
    parser.add_argument('--source-locator', type=json.loads, help='Source coordinate object or label as JSON')
    parser.add_argument('--untrusted', action='store_true',
                        help='Quarantine external files when no scanner is configured')
    parser.add_argument('--defender', type=Path, help='Trusted MpCmdRun.exe path for untrusted input')
    parser.add_argument('--ocr', action='store_true', help='Read a retained trusted PNG or JPEG for manual review')
    parser.add_argument('--gmail-message-id', help='File the selected Gmail message from base64url raw text on stdin')
    args=parser.parse_args()
    if args.gmail_message_id:
        if any((args.source, args.to, args.source_revision, args.source_locator, args.untrusted, args.defender, args.ocr)):
            parser.error('--gmail-message-id uses stdin and the private archive only')
        encoded = sys.stdin.read(1_333_338)
        if len(encoded) > 1_333_337:
            parser.error('Gmail raw payload exceeds the input limit')
        print(json.dumps(file_gmail_raw(args.gmail_message_id, encoded.strip(), args.root)))
        sys.exit(0)
    if args.source is None:
        parser.error('Provide a document or --gmail-message-id')
    if args.defender and not args.untrusted:
        parser.error('--defender requires --untrusted')
    if args.ocr and (args.untrusted or args.source.suffix.lower() not in {'.png', '.jpg', '.jpeg'} or not args.source.is_file()):
        parser.error('--ocr requires one trusted local PNG or JPEG')
    if args.source.is_dir() and (args.source_revision is not None or args.source_locator is not None):
        parser.error('Source coordinates and revision apply to an individual file')
    files=sorted(p for p in args.source.iterdir() if p.is_file()) if args.source.is_dir() else [args.source]
    intake = file_untrusted_document if args.untrusted else file_document
    options = {"source_revision": args.source_revision, "source_locator": args.source_locator}
    if args.defender:
        from functools import partial
        options["scanner"] = partial(defender_scan, args.defender)
    for file in files:
        receipt = intake(file, args.root, args.to, **options)
        if args.ocr:
            receipt['ocr'] = review_windows_scan(receipt)
        print(json.dumps(receipt))
