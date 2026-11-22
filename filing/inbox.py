"""Bounded local intake, original-byte archive and native text extraction.

Additive port of the audited generic filing/inbox.py, source SHA-256
7dac3fae6722ed660f4d4c9be66df16cfc59932eb15688226c724c9322aa7b0a.
No private routing configuration is imported. Public filing signature, four
receipt keys, archive naming and the existing SQLite receipts table survive.
This is a local OS-user boundary, not a hostile multi-user filesystem sandbox.
"""
import argparse
import codecs
import hashlib
import io
import json
import logging
import os
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree


CONFIG = Path(__file__).with_name("routes.json")
PARSER_VERSION = "1.0.0"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_OUTPUT_BYTES = 512000
WORKER_TIMEOUT_SECONDS = 10
WORKER_MEMORY_BYTES = 512 * 1024 * 1024
DEFAULT_LIMITS = {"max_input_bytes": MAX_ARCHIVE_BYTES, "max_text_bytes": 150000,
                  "max_pages": 5, "max_chars_per_page": 20000, "max_xml_bytes": 2000000}


def _limits(overrides=None):
    """Operational bounds only; the application owns the shared record schema."""
    limits = dict(DEFAULT_LIMITS)
    if overrides is not None:
        if type(overrides) is not dict or set(overrides) - set(limits):
            raise ValueError("Unknown native extraction limit")
        limits.update(overrides)
    ceilings = {"max_input_bytes": MAX_ARCHIVE_BYTES, "max_text_bytes": MAX_OUTPUT_BYTES,
                "max_pages": 100, "max_chars_per_page": MAX_OUTPUT_BYTES, "max_xml_bytes": 2000000}
    for key, value in limits.items():
        if type(value) is not int or not 1 <= value <= ceilings[key]:
            raise ValueError(f"{key} must be a positive integer no greater than {ceilings[key]}")
    return limits


def _no_symlinks(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError("Symlinks are not accepted in intake or archive paths")
    return path


def _read_snapshot(path):
    path = _no_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            before = os.fstat(source.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("Source must be a regular file")
            if before.st_size > MAX_ARCHIVE_BYTES:
                raise ValueError("Source exceeds the hard 16 MiB intake limit")
            raw = source.read(MAX_ARCHIVE_BYTES + 1)
            after = os.fstat(source.fileno())
            def identity(value):
                return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)
            if len(raw) > MAX_ARCHIVE_BYTES or identity(before) != identity(after):
                raise ValueError("Source changed during the bounded snapshot read")
            if len(raw) != before.st_size:
                raise ValueError("Source byte count changed during intake")
            return raw
    except OSError as exc:
        raise ValueError("Source could not be read as a regular local file") from exc


def _report(raw, suffix, limits):
    return {"source_sha256": hashlib.sha256(raw).hexdigest(), "input_bytes": len(raw),
            "processor": "black-river-native", "processor_version": PARSER_VERSION + ";python=" + sys.version.split()[0],
            "status": "error", "coverage": {"input_bytes": len(raw), "processed_bytes": 0,
            "total_pages": None, "processed_pages": 0, "complete": False, "truncated": False,
            "page_basis": "physical" if suffix == ".pdf" else "logical",
            "limits": limits, "notes": []}, "pages": [], "errors": []}


def _error(result, code, message, page=None):
    result["errors"].append({"code": code, "message": message, "page": page})
    return result


def _retain_text(text, byte_budget, char_budget):
    """Retain a Unicode prefix without splitting a UTF-8 code point."""
    prefix = text[:char_budget]
    encoded = prefix.encode("utf-8")
    if len(encoded) > byte_budget:
        prefix = codecs.getincrementaldecoder("utf-8")("strict").decode(encoded[:byte_budget], final=False)
    return prefix, prefix != text


def _add_page(result, page, text):
    result["pages"].append({"page": page, "text": text,
                            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
    result["coverage"]["processed_pages"] = len(result["pages"])


def _finish(result):
    coverage = result["coverage"]
    if result["status"] in {"needs_ocr", "unsupported"}:
        return result
    if result["errors"] and not result["pages"]:
        result["status"] = "error"
    elif coverage["truncated"] or result["errors"] or coverage["notes"]:
        result["status"] = "partial"
    else:
        result["status"] = "complete"
        coverage["complete"] = True
        coverage["processed_bytes"] = coverage["input_bytes"]
    return result


def _parse_bytes(raw, suffix, limits):
    result = _report(raw, suffix, limits)
    coverage = result["coverage"]
    if len(raw) > limits["max_input_bytes"]:
        return _error(result, "INPUT_LIMIT_EXCEEDED", "Source exceeds the declared input byte limit")
    if not raw:
        return _error(result, "EMPTY_DOCUMENT", "Source has no bytes")
    if suffix in {".txt", ".md", ".csv"}:
        coverage["total_pages"] = 1
        selected = raw[:limits["max_text_bytes"]]
        cut = len(selected) < len(raw)
        try:
            text = codecs.getincrementaldecoder("utf-8")("strict").decode(selected, final=not cut)
        except UnicodeDecodeError:
            return _error(result, "INVALID_UTF8", "Native text must be valid UTF-8; replacement decoding is disabled")
        text, clipped = _retain_text(text, limits["max_text_bytes"], limits["max_chars_per_page"])
        _add_page(result, 1, text)
        coverage["processed_bytes"] = len(text.encode("utf-8"))
        coverage["truncated"] = cut or clipped
        if coverage["truncated"]:
            coverage["notes"].append("Only the bounded UTF-8 text prefix was extracted")
        return _finish(result)
    if suffix == ".docx":
        coverage["total_pages"] = 1
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > limits["max_xml_bytes"]:
                    coverage["truncated"] = True
                    coverage["notes"].append("DOCX main XML exceeds its uncompressed byte limit; no body text was parsed")
                    return _finish(result)
                with archive.open(info) as member:
                    xml = member.read(limits["max_xml_bytes"] + 1)
                if len(xml) > limits["max_xml_bytes"]:
                    return _error(result, "XML_LIMIT_EXCEEDED", "DOCX main XML exceeds its bounded read")
                # ElementTree must never expand document-supplied DTD entities.
                xml_text = xml.decode("utf-8-sig", errors="strict")
                upper = xml_text.upper()
                if "<!DOCTYPE" in upper or "<!ENTITY" in upper:
                    return _error(result, "UNSAFE_XML", "DTD and entity declarations are not supported")
                body = ElementTree.fromstring(xml_text)
                text = " ".join(body.itertext())
                extras = [name for name in archive.namelist() if name.startswith(
                    ("word/header", "word/footer", "word/footnotes", "word/endnotes", "word/comments", "word/media/"))]
                nontext = any(node.tag.rsplit("}", 1)[-1] in {"drawing", "pict", "object", "altChunk"}
                              for node in body.iter())
                if extras or nontext:
                    coverage["notes"].append("DOCX body text only: headers, footnotes, comments or embedded media are not extracted")
            text, clipped = _retain_text(text, limits["max_text_bytes"], limits["max_chars_per_page"])
            coverage["truncated"] = clipped
            if clipped:
                coverage["notes"].append("DOCX body text reached the retained text budget")
            _add_page(result, 1, text)
            coverage["processed_bytes"] = len(raw)
            return _finish(result)
        except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, UnicodeError, OSError, RuntimeError, NotImplementedError):
            return _error(result, "MALFORMED_DOCX", "DOCX archive or main document XML could not be parsed")
    if suffix == ".pdf":
        try:
            import pypdf
        except ImportError:
            return _error(result, "DEPENDENCY_MISSING", "Optional pypdf dependency is unavailable; install requirements-docai.txt")
        result["processor_version"] += ";pypdf=" + pypdf.__version__
        logging.getLogger("pypdf").setLevel(logging.CRITICAL)
        try:
            reader = pypdf.PdfReader(io.BytesIO(raw), strict=True)
            if reader.is_encrypted:
                return _error(result, "ENCRYPTED_PDF", "Encrypted PDF requires an authorized decrypted source")
            coverage["total_pages"] = len(reader.pages)
            if coverage["total_pages"] == 0:
                return _error(result, "EMPTY_PDF", "PDF has no physical pages")
            budget = limits["max_text_bytes"]
            has_xobjects = False
            text_clipped = False
            for index in range(min(coverage["total_pages"], limits["max_pages"])):
                if budget == 0:
                    coverage["truncated"] = True
                    coverage["notes"].append("Remaining PDF pages were not extracted after the text byte budget")
                    break
                pdf_page = reader.pages[index]
                resources = pdf_page.get("/Resources")
                if resources is not None:
                    # Check resource presence only. Never decode images or walk
                    # potentially recursive Form graphs to assert coverage.
                    resources = resources.get_object()
                    has_xobjects = has_xobjects or bool(resources.get("/XObject"))
                page_text = pdf_page.extract_text() or ""
                text, clipped = _retain_text(page_text, budget, limits["max_chars_per_page"])
                _add_page(result, index + 1, text)
                budget -= len(text.encode("utf-8"))
                if clipped:
                    coverage["truncated"] = True
                    text_clipped = True
            coverage["processed_bytes"] = len(raw)
            if text_clipped:
                coverage["notes"].append("Some PDF page text reached its retained text budget")
            if has_xobjects:
                coverage["notes"].append("Native text only: image/Form XObjects were not visually interpreted; review their unexamined content")
            if coverage["processed_pages"] < coverage["total_pages"]:
                coverage["truncated"] = True
                coverage["notes"].append("Only a prefix of the physical PDF pages was processed")
            empty_pages = [p["page"] for p in result["pages"] if not p["text"].strip()]
            if empty_pages and not coverage["truncated"]:
                if len(empty_pages) == len(result["pages"]):
                    result["status"] = "needs_ocr"
                    coverage["notes"].append("No native readable text; image OCR or manual transcription may be required")
                else:
                    coverage["notes"].append("Some physical PDF pages have no native text; review image-only or blank pages")
            return _finish(result)
        except MemoryError:
            return _error(result, "PROCESSING_MEMORY_LIMIT", "PDF parsing exceeded the worker memory allowance")
        except Exception:
            # Parser diagnostics can contain source text or filesystem locations.
            result["status"] = "partial" if result["pages"] else "error"
            _error(result, "MALFORMED_PDF", "PDF structure or page content could not be parsed")
            return _finish(result)
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        signatures = {".png": raw.startswith(b"\x89PNG\r\n\x1a\n"),
                      ".jpg": raw.startswith(b"\xff\xd8\xff"), ".jpeg": raw.startswith(b"\xff\xd8\xff"),
                      ".tif": raw.startswith((b"II*\x00", b"MM\x00*")),
                      ".tiff": raw.startswith((b"II*\x00", b"MM\x00*"))}
        if not signatures[suffix]:
            return _error(result, "MALFORMED_IMAGE", "Source signature does not match its declared image suffix")
        coverage["total_pages"] = 1
        _add_page(result, 1, "")
        result["status"] = "needs_ocr"
        coverage["notes"].append("Image signature recognized only; image validity and physical page count were not decoded")
        return result
    result["status"] = "unsupported"
    return _error(result, "UNSUPPORTED_FORMAT", "No native reader is registered for this file suffix")


def extract_details(path, *, limits=None):
    """Return source-bound pages and coverage; no field inference or approval."""
    limits = _limits(limits)
    path = Path(path)
    raw = _read_snapshot(path)
    suffix = path.suffix.lower()
    if suffix not in {".pdf", ".docx"} or len(raw) > limits["max_input_bytes"] or not raw:
        return _parse_bytes(raw, suffix, limits)
    result = _report(raw, suffix, limits)
    command = [sys.executable, str(Path(__file__).resolve()), "--extract-worker", suffix,
               json.dumps(limits, separators=(",", ":"))]
    try:
        worker = subprocess.run(command, input=raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=WORKER_TIMEOUT_SECONDS, check=False)
    except subprocess.TimeoutExpired:
        return _error(result, "PROCESSING_TIMEOUT", "Native parser exceeded the bounded worker time")
    except OSError:
        return _error(result, "PROCESSING_UNAVAILABLE", "Native parser worker could not start")
    if worker.returncode != 0 or len(worker.stdout) > 4 * 1024 * 1024:
        return _error(result, "PROCESSING_FAILED", "Native parser exited without a bounded usable result")
    try:
        parsed = json.loads(worker.stdout)
        if parsed["source_sha256"] != result["source_sha256"] or parsed["input_bytes"] != len(raw):
            raise ValueError("Worker source identity mismatch")
        return parsed
    except (ValueError, KeyError, TypeError):
        return _error(result, "PROCESSING_FAILED", "Native parser returned an invalid result")


def extract(path):
    """Legacy text-only helper; structured consumers must use extract_details."""
    result = extract_details(path)
    return " ".join(page["text"] for page in result["pages"])


def _route(name):
    if type(name) is not str or not name or "\\" in name or ":" in name:
        raise ValueError("Route must be a nonempty relative folder path")
    parts = PurePosixPath(name).parts
    if name.startswith("/") or any(part in {".", ".."} for part in name.split("/")) or not parts:
        raise ValueError("Route must stay within the archive root")
    if any(not part or any(ord(char) < 32 for char in part) for part in name.split("/")):
        raise ValueError("Route contains an empty or control-character component")
    return name


def _routes():
    config = _no_symlinks(CONFIG)
    with config.open("rb") as source:
        raw = source.read(65537)
    if len(raw) > 65536:
        raise ValueError("Routing configuration exceeds its byte limit")
    routes = json.loads(raw.decode("utf-8", errors="strict"))
    if type(routes) is not dict or len(routes) > 100:
        raise ValueError("Routing configuration must be a bounded object")
    for name, terms in routes.items():
        _route(name)
        if type(terms) is not list or len(terms) > 100 or any(
            type(term) is not str or not term.strip() or len(term) > 200 for term in terms
        ):
            raise ValueError("Route terms must be bounded nonempty strings")
    return routes


def _archive_root(root):
    root = _no_symlinks(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not root.is_dir():
        raise ValueError("Archive root must be a directory")
    if os.name == "posix":
        info = root.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o022:
            raise ValueError("Archive must be owned by the current OS user and not writable by other users")
    return root


def file_document(path, root, destination=None):
    """Archive one bounded original and append/replay its legacy receipt."""
    path = Path(path)
    routes = _routes()
    if destination is not None and destination not in routes:
        raise ValueError("Unknown destination. Choose an exact route from routes.json.")
    root = _archive_root(root)
    raw = _read_snapshot(path)
    digest = hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(dir=root) as staging:
        snapshot = Path(staging) / path.name
        with snapshot.open("xb") as output:
            os.chmod(snapshot, 0o600)
            output.write(raw)
        if destination is not None:
            folder, reason = destination, "explicit instruction"
        else:
            try:
                body = extract(snapshot).casefold()
            except (ValueError, OSError):
                body = ""
            matches = [name for name, terms in routes.items()
                       if any(term.casefold() in body for term in terms)]
            folder, reason = (matches[0], "content match") if len(matches) == 1 else ("Review", "ambiguous or unreadable")
        _route(folder)
        # Preserve ordinary legacy names while keeping long/Unicode names within
        # filesystem byte limits and retaining the suffix used by native readers.
        suffix = path.suffix
        stem = path.name[:-len(suffix)] if suffix else path.name
        short_stem, _ = _retain_text(stem, max(1, 180 - len(suffix.encode("utf-8"))), max(1, 120 - len(suffix)))
        target = root / folder / (digest + "--" + short_stem + suffix)
        _no_symlinks(target)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not target.parent.resolve().is_relative_to(root.resolve()):
            raise ValueError("Archive destination escaped the configured root")
        try:
            os.link(snapshot, target, follow_symlinks=False)
        except FileExistsError:
            if hashlib.sha256(_read_snapshot(target)).hexdigest() != digest:
                raise ValueError("Destination integrity check failed")
        database = root / "filing.sqlite"
        for candidate in (database, *(root / ("filing.sqlite" + ending) for ending in ("-journal", "-wal", "-shm"))):
            _no_symlinks(candidate)
            if candidate.exists() and not candidate.is_file():
                raise ValueError("Receipt database paths must be regular files")
        try:
            descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        relative = str(target.relative_to(root))
        with sqlite3.connect(database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS receipts(path TEXT PRIMARY KEY, hash TEXT, reason TEXT, filed_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            previous = db.execute("SELECT hash FROM receipts WHERE path=?", (relative,)).fetchone()
            if previous is not None and previous[0] != digest:
                raise ValueError("Existing receipt hash conflicts with archived content")
            db.execute("INSERT OR IGNORE INTO receipts(path,hash,reason) VALUES(?,?,?)", (relative, digest, reason))
        return {"destination": folder, "file": str(target), "sha256": digest, "reason": reason}


def _worker_main(suffix, encoded_limits):
    limits = _limits(json.loads(encoded_limits))
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (WORKER_MEMORY_BYTES, WORKER_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (WORKER_TIMEOUT_SECONDS, WORKER_TIMEOUT_SECONDS))
    except (ImportError, OSError, ValueError):
        # Do not pretend resource confinement exists on unsupported systems.
        raw = sys.stdin.buffer.read(MAX_ARCHIVE_BYTES + 1)
        result = _report(raw, suffix, limits)
        _error(result, "RESOURCE_LIMIT_UNAVAILABLE", "Native PDF/DOCX worker requires enforceable OS memory and CPU limits")
    else:
        raw = sys.stdin.buffer.read(MAX_ARCHIVE_BYTES + 1)
        try:
            result = _parse_bytes(raw, suffix, limits)
        except MemoryError:
            result = _error(_report(raw, suffix, limits), "PROCESSING_MEMORY_LIMIT", "Native parser exceeded the worker memory allowance")
        except Exception:
            result = _error(_report(raw, suffix, limits), "PROCESSING_FAILED", "Native parser could not produce a result")
    sys.stdout.write(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--extract-worker":
        _worker_main(sys.argv[2], sys.argv[3])
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("source", type=Path, help="Document or direct intake folder")
        parser.add_argument("--root", type=Path, required=True, help="Private local archive directory")
        parser.add_argument("--to", help="Exact configured destination")
        args = parser.parse_args()
        files = sorted(p for p in args.source.iterdir() if p.is_file()) if args.source.is_dir() else [args.source]
        for source in files:
            print(json.dumps(file_document(source, args.root, args.to)))
