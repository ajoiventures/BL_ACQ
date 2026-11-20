"""Build and search a cited offline TF-IDF index from the repository's Git index."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
APP_ID = 0x42524C49
FORMAT_VERSION = 1
DIRECTORIES = {"docs", "docs/guides", "docs/architecture", "pilot", "tools", "web", "tests"}
LESSONS = "docs/learning"
MODEL_SKILL = ".agents/skills/black-river-system-modeling/SKILL.md"
# Common grammatical words are poor evidence of topical relevance in short queries.
STOP = set("a an and are as at be by for from in is it of on or the to with".split())


def tokens(text):
    return [word for word in re.findall(r"[^\W_]+", text.casefold()) if word not in STOP]


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True).stdout


def tracked(root):
    """Read stage-zero blob names. Working files and external links are never opened."""
    if Path(git(root, "rev-parse", "--show-toplevel").decode().strip()).resolve() != root.resolve():
        raise ValueError("Expected a repository root")
    result = {}
    for item in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not item:
            continue
        prefix, name = item.split(b"\t", 1)
        mode, oid, stage = prefix.decode("ascii").split()
        path = name.decode("utf-8")
        if stage != "0":
            raise ValueError(f"Resolve index conflicts before indexing: {path}")
        if mode in {"100644", "100755"}:
            result[path] = oid
    return result


def allowed(path):
    target = PurePosixPath(path)
    if path in {"README.md", MODEL_SKILL}:
        return True
    return target.suffix == ".md" and str(target.parent) in DIRECTORIES | {LESSONS}


def lesson_info(lines, files):
    """Review fields must appear in the opening metadata block."""
    fields = {}
    for line in lines[1:]:
        if line.startswith("## "):
            break
        match = re.fullmatch(r"(Review|Reviewed by|Source): (.+)", line)
        if match:
            name, value = match.groups()
            if name in fields:
                raise ValueError(f"Duplicate lesson field {name}")
            fields[name] = value.strip()
    if fields.get("Review") != "accepted":
        return None
    if not fields.get("Reviewed by") or fields.get("Source") not in files:
        raise ValueError("Accepted lesson needs a reviewer and a tracked, repository-relative source")
    return {"reviewer": fields["Reviewed by"], "source": fields["Source"],
            "source_blob": files[fields["Source"]]}


def sections(lines):
    """Use heading boundaries and bounded line groups while retaining exact source positions."""
    start = None
    title = ""
    size = 0
    for number, line in enumerate(lines, 1):
        heading = re.match(r"^#{1,6}\s+(.+)", line)
        if start is not None and (heading or size + len(line) > 1800):
            yield start, number - 1, title
            start, size = None, 0
        if heading:
            title = heading.group(1)
        if start is None:
            if not line.strip():
                continue
            start = number
        size += len(line) + 1
    if start is not None:
        yield start, len(lines), title


def corpus(root):
    files = tracked(root)
    chunks, skipped = [], []
    for path in sorted(p for p in files if allowed(p)):
        original = git(root, "cat-file", "blob", files[path])
        sha = hashlib.sha256(original).hexdigest()
        lines = original.decode("utf-8-sig").splitlines()
        info = None
        if str(PurePosixPath(path).parent) == LESSONS:
            info = lesson_info(lines, files)
            if info is None:
                skipped.append(path)
                continue
        for start, end, title in sections(lines):
            body = "\n".join(lines[start-1:end])
            if not tokens(body):
                continue
            key = hashlib.sha256(f"{path}\0{sha}\0{start}\0{end}".encode()).hexdigest()
            chunks.append((key, path, start, end, title, sha, files[path], body,
                           json.dumps(info, sort_keys=True) if info else None))
    return chunks, skipped


def vector(words, idfs):
    counts = Counter(word for word in words if word in idfs)
    weights = {word: (1 + math.log(counts[word])) * idfs[word] for word in sorted(counts)}
    norm = math.sqrt(math.fsum(weight * weight for weight in weights.values()))
    return {word: weight / norm for word, weight in weights.items()}


def check_database(conn):
    app = conn.execute("PRAGMA application_id").fetchone()[0]
    fmt = conn.execute("PRAGMA user_version").fetchone()[0]
    if (app, fmt) != (APP_ID, FORMAT_VERSION):
        raise ValueError("File is not a compatible Black River learning index")


def build(root, db):
    root, db = Path(root), Path(db)
    chunks, skipped = corpus(root)
    frequencies = Counter()
    for row in chunks:
        frequencies.update(set(tokens(row[7])))
    idfs = {term: math.log((len(chunks) + 1) / (count + 1)) + 1
            for term, count in sorted(frequencies.items())}
    db.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]:
            check_database(conn)
        else:
            if conn.execute("PRAGMA application_id").fetchone()[0] or conn.execute("PRAGMA user_version").fetchone()[0]:
                raise ValueError("Database belongs to another application")
            conn.execute(f"PRAGMA application_id={APP_ID}")
            conn.execute(f"PRAGMA user_version={FORMAT_VERSION}")
            conn.execute("""CREATE TABLE chunks(id TEXT PRIMARY KEY,path TEXT,start INTEGER,end INTEGER,
                         title TEXT,sha TEXT,blob TEXT,body TEXT,lesson TEXT,vector TEXT)""")
            conn.execute("CREATE TABLE vocabulary(term TEXT PRIMARY KEY,idf REAL NOT NULL)")
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM vocabulary")
        conn.executemany("INSERT INTO vocabulary VALUES (?,?)", idfs.items())
        for row in chunks:
            weights = json.dumps(vector(tokens(row[7]), idfs), separators=(",", ":"))
            conn.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)", (*row, weights))
    return {"documents": len({row[1] for row in chunks}), "chunks": len(chunks),
            "terms": len(idfs), "skipped_unreviewed_lessons": skipped}


def citation(row):
    result = {"chunk_id": row["id"], "path": row["path"], "start_line": row["start"],
              "end_line": row["end"], "title": row["title"], "source_sha256": row["sha"],
              "git_blob": row["blob"]}
    if row["lesson"] is not None:
        result["lesson"] = json.loads(row["lesson"])
    return result


def open_reader(db):
    if not Path(db).is_file():
        raise ValueError("Build the learning index first")
    conn = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        check_database(conn)
        # Keep vocabulary and chunks from the same committed generation.
        conn.execute("BEGIN")
    except BaseException:
        conn.close()
        raise
    return conn


def search(db, query, limit=5):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Use a result limit from 1 through 100")
    with closing(open_reader(db)) as conn:
        terms = dict(conn.execute("SELECT term,idf FROM vocabulary"))
        needle = vector(tokens(query), terms)
        if not needle:
            return []
        results = []
        for row in conn.execute("SELECT * FROM chunks ORDER BY path,start"):
            weights = json.loads(row["vector"])
            score = math.fsum(weight * weights.get(term, 0) for term, weight in needle.items())
            if score > 0:
                results.append((score, row))
        results.sort(key=lambda match: (-match[0], match[1]["path"], match[1]["start"]))
        return [citation(row) | {"score": round(score, 8), "snippet": row["body"][:240]}
                for score, row in results[:limit]]


def read(db, chunk_id):
    with closing(open_reader(db)) as conn:
        row = conn.execute("SELECT * FROM chunks WHERE id=?", (chunk_id,)).fetchone()
        if row is None:
            raise ValueError("Unknown chunk in this index revision")
        return citation(row) | {"text": row["body"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("index")
    query = actions.add_parser("search")
    query.add_argument("query")
    query.add_argument("--limit", type=int, default=5)
    get = actions.add_parser("read")
    get.add_argument("chunk_id")
    args = parser.parse_args()
    db = ROOT / ".runs" / "learning.sqlite3"
    try:
        if args.action == "index":
            result = build(ROOT, db)
        elif args.action == "search":
            result = search(db, args.query, args.limit)
        else:
            result = read(db, args.chunk_id)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (ValueError, OSError, sqlite3.Error, subprocess.CalledProcessError) as exc:
        print(f"Learning index: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
