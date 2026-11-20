"""Check the code map and its local Markdown links from any working directory."""

from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".js", ".mjs", ".ts", ".tsx", ".css", ".html", ".sql", ".ps1", ".cmd", ".code-workspace"}
HIDDEN = {".git", ".runs", ".venv", ".mypy_cache", ".ruff_cache", "__pycache__", "node_modules"}
LINK = re.compile(r"\[[^\]\n]+\]\((?:<([^>]+)>|([^\s()]+))\)")


def local_links(document, root):
    """Resolve relative file links in the Markdown style used by the workspace."""
    for match in LINK.finditer(document.read_text(encoding="utf-8")):
        target = urlsplit(match.group(1) or match.group(2))
        if target.scheme or target.netloc or not target.path:
            continue
        path = unquote(target.path)
        yield (root / path.lstrip("/") if path.startswith("/") else document.parent / path).resolve()


def check(root):
    # 1. Start from the actual filesystem. A missing map entry must stay visible.
    files = []
    for directory, children, names in root.walk():
        children[:] = [name for name in children if name not in HIDDEN]
        files.extend(directory / name for name in names)
    workflow_dir = root / ".github" / "workflows"
    sources = {
        p for p in files
        if p.suffix.lower() in SUFFIXES
        or (p.parent == workflow_dir and p.suffix in {".yml", ".yaml"})
    }
    docs = [p for p in files if p.suffix.lower() == ".md"]
    errors = []

    # 2. Every map row pairs a source with its own working Markdown guide.
    code_map = root / "docs" / "code-map.md"
    covered = set()
    guides = {}
    if code_map in docs:
        for line in code_map.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            links = [a or b for a, b in LINK.findall(line)]
            if len(links) != 2:
                continue
            source, guide = [(code_map.parent / unquote(path)).resolve() for path in links]
            if source not in sources or not guide.is_relative_to(root):
                errors.append(f"Unknown source or out-of-workspace guide: {links[0]}")
                continue
            if not guide.is_file() or guide.suffix != ".md":
                continue
            if not guide.read_text(encoding="utf-8").strip():
                errors.append(f"Empty guide: {guide.relative_to(root)}")
            if guide in guides or source in covered:
                errors.append(f"Duplicate guide mapping: {guide.relative_to(root)}")
            guides[guide] = source
            covered.add(source)
    else:
        errors.append("Missing docs/code-map.md")
    errors.extend(f"Missing guide for {p.relative_to(root)}" for p in sorted(sources - covered))

    # 3. Follow guide links as a learner would. Track all failures in one run.
    for doc in docs:
        for target in local_links(doc, root):
            if not target.is_relative_to(root) or not target.exists():
                errors.append(f"Broken local link in {doc.relative_to(root)}: {target.name}")
    return len(sources), len(docs), errors


if __name__ == "__main__":
    count, doc_count, failures = check(ROOT)
    for message in failures:
        print(message, file=sys.stderr)
    print(f"Checked {count} source/config files and {doc_count} Markdown documents. {len(failures)} errors.")
    raise SystemExit(bool(failures))
