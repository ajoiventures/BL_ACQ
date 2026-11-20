"""Fingerprint source trees and ZIP members without importing or extracting them."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import zipfile


SOURCE_EXTENSIONS = set(
    ".py .pyi .js .jsx .mjs .cjs .ts .tsx .html .htm .css .scss .vue .svelte "
    ".sql .sh .bash .zsh .bat .cmd .ps1 .psm1 .rb .cs .fs .cpp .c .h .hpp "
    ".java .kt .swift .go .rs .r .ipynb .tf .gd .lua .mod .kit .usda".split()
)
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".dependencies", ".next"}
MAX_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 20000
MAX_ARCHIVE_SOURCE_BYTES = 256 * 1024 * 1024


def is_source(path):
    return path.suffix.lower() in SOURCE_EXTENSIONS or path.name.lower() in {
        "dockerfile", "makefile", "jenkinsfile"
    } or (".github/workflows" in path.parent.as_posix() and path.suffix in {".yml", ".yaml"})


def digest(stream):
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        result.update(block)
    return result.hexdigest()


def source_record(key, data):
    # Hash the unmodified bytes. Relative paths identify occurrences; the
    # digest identifies identical content even when packaging changes a name.
    record = {"path": key, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
              "lines": len(data.splitlines())}
    if PurePosixPath(key).suffix.lower() in {".py", ".pyi"}:
        try:
            tree = ast.parse(data, filename="<source>")
            record["python_syntax"] = "parsed"
            record["functions"] = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                                      for node in ast.walk(tree))
        except (SyntaxError, ValueError, RecursionError) as exc:
            record["python_syntax"] = "failed"
            record["syntax_error"] = type(exc).__name__
            record["line"] = getattr(exc, "lineno", None)
    return record


def inspect_archive(file, key, report, skips):
    # The archive digest identifies the handoff. Member digests identify
    # individual source versions. Parse members in memory without extracting.
    with file.open("rb") as stream:
        archive = {"path": key, "sha256": digest(stream)}
    report["archives"].append(archive)
    with zipfile.ZipFile(file) as package:
        members = package.infolist()
        archive["members"] = len(members)
        if len(members) > MAX_MEMBERS:
            report["limitations"].append({"path": key, "reason": "member limit"})
            return
        source_bytes = 0
        for member in members:
            path = PurePosixPath(member.filename.replace("\\", "/"))
            label = f"{key}!{path.as_posix()}"
            if member.is_dir() or skips.intersection(path.parts):
                continue
            if path.suffix.lower() == ".zip":
                report["limitations"].append({"path": label, "reason": "nested archive"})
            if not is_source(path):
                continue
            if member.file_size > MAX_BYTES:
                report["limitations"].append({"path": label, "reason": "source size limit"})
                continue
            source_bytes += member.file_size
            if source_bytes > MAX_ARCHIVE_SOURCE_BYTES:
                report["limitations"].append({"path": key, "reason": "archive source byte limit"})
                break
            try:
                report["sources"].append(source_record(label, package.read(member)))
            except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
                report["limitations"].append({"path": label, "reason": type(exc).__name__})


def inspect_file(file, key, report, skips):
    try:
        if file.is_symlink():
            report["limitations"].append({"path": key, "reason": "symbolic link"})
        elif file.suffix.lower() == ".zip":
            inspect_archive(file, key, report, skips)
        elif is_source(file):
            if file.stat().st_size <= MAX_BYTES:
                report["sources"].append(source_record(key, file.read_bytes()))
            else:
                report["limitations"].append({"path": key, "reason": "source size limit"})
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        report["limitations"].append({"path": key, "reason": type(exc).__name__})


def inspect(root, name, skips):
    # Keep limitations beside each root so a partial result can be inspected.
    report = {"name": name, "sources": [], "archives": [], "limitations": []}
    if root.is_file():
        inspect_file(root, root.name, report, skips)
    elif root.is_dir():
        def walk_error(error):
            report["limitations"].append({"path": os.path.relpath(error.filename, root),
                                          "reason": type(error).__name__})

        for current, directories, files in os.walk(root, onerror=walk_error):
            base = Path(current)
            directories[:] = sorted(d for d in directories if d not in skips and
                                    not (base / d).is_symlink() and
                                    not getattr(base / d, "is_junction", lambda: False)())
            for filename in sorted(files):
                file = base / filename
                inspect_file(file, file.relative_to(root).as_posix(), report, skips)
    else:
        report["limitations"].append({"path": ".", "reason": "missing source root"})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", required=True, metavar="NAME=PATH",
                        help="Repeat for each named file, directory or ZIP.")
    parser.add_argument("--exclude-dir", action="append", default=[], metavar="NAME")
    parser.add_argument("--output", type=Path, help="Destination JSON. Defaults to stdout.")
    args = parser.parse_args()
    reports = []
    names = set()
    inputs = []
    skips = SKIP_DIRS.union(args.exclude_dir)
    output = args.output.resolve() if args.output else None
    if output and args.output.exists():
        parser.error("The output already exists. Choose a new file.")
    for declaration in args.source:
        name, sep, location = declaration.partition("=")
        if not sep or not name or not location or name in names:
            parser.error("Use a unique NAME=PATH for each source.")
        names.add(name)
        root = Path(location)
        if output and output.is_relative_to(root.resolve()):
            relative = output.relative_to(root.resolve())
            if not skips.intersection(relative.parts[:-1]):
                parser.error("Place the output outside scanned source paths.")
        inputs.append((name, root))
    for name, root in inputs:
        reports.append(inspect(root, name, skips))
    records = [record for report in reports for record in report["sources"]]
    result = {"schema_version": 1, "roots": reports, "source_occurrences": len(records),
              "unique_source_hashes": len({r["sha256"] for r in records})}
    payload = json.dumps(result, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        # Exclusive creation also protects a file created after the CLI checks.
        try:
            with args.output.open("x", encoding="utf-8") as destination:
                destination.write(payload)
        except OSError as exc:
            parser.exit(2, f"Could not create the inventory output: {exc}\n")
    else:
        sys.stdout.write(payload)
    return 1 if any(r["limitations"] for r in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
