"""Local evidence and handoff queue for a site-study team. Python standard library."""
import argparse
import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path

# A planning workflow dependency, independent of the order readers study chapters.
PRIOR = {1: (), 2: (1,), 3: (1, 2), 4: (1,), 5: (2, 3), 6: (2, 3),
         7: (2, 3), 8: (4, 5, 6, 7), 9: (8,), 10: (9,), 11: (10,)}
REGISTRY = Path(__file__).with_name("skills.json")

URBAN_PRIOR = {
    0: (), 1: (), 2: (0, 1), 3: (2,), 4: (2, 3), 5: (3, 4),
    6: (0, 1), 7: (6,), 8: (6,), 9: (7, 8), 10: (0, 1),
    11: (10,), 12: (8,), 13: (8,), 14: (6, 8), 15: (9, 14),
    16: (0, 1), 17: (16,),
}
PREREQUISITES = {"site": PRIOR, "urban": URBAN_PRIOR, "planning": {chapter: () for chapter in range(1, 24)}}
PREREQUISITES["acquisition"] = {
    1: (), 2: (1,), 3: (1,), 4: (2, 3), 5: (2,),
    6: (5,), 7: (3, 4), 8: (3, 4), 9: (4, 5, 6, 8),
    10: (), 11: (), 12: (2,), 13: (10,), 14: (10, 13),
    15: (1, 2), 16: (3, 15), 17: (), 18: (1, 15), 19: (1, 15),
}
REGISTRIES = {
    "acquisition": (REGISTRY.with_name("acquisition.json"),),
    "site": (REGISTRY,),
    "planning": (REGISTRY.with_name("planning.json"),),
    "urban": tuple(REGISTRY.with_name(f"econ{i}.json") for i in (1, 2, 3)),
}

def load_skills(curriculum):
    if curriculum not in REGISTRIES:
        raise ValueError("Unknown curriculum")
    return [skill for path in REGISTRIES[curriculum] for skill in json.loads(path.read_text(encoding="utf-8"))]

STUDY_COLUMNS = """(id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                    curriculum TEXT NOT NULL DEFAULT 'site', UNIQUE(name,curriculum))"""


def migrate_studies(db):
    columns = {row["name"] for row in db.execute("PRAGMA table_info(studies)")}
    if not columns or "curriculum" in columns:
        return
    # Rebuild only the legacy parent table; preserve task/event keys, indexes and triggers.
    # SQLite permits toggling foreign-key enforcement only outside a transaction.
    with db:
        db.execute("BEGIN IMMEDIATE")
        if "curriculum" in {row["name"] for row in db.execute("PRAGMA table_info(studies)")}:
            return
        db.execute("CREATE TABLE studies_new " + STUDY_COLUMNS)
        db.execute("INSERT INTO studies_new(id,name) SELECT id,name FROM studies")
        db.execute("DROP TABLE studies")
        db.execute("ALTER TABLE studies_new RENAME TO studies")
        if db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("Foreign-key integrity check failed during study migration")


def connect(path):
    db = sqlite3.connect(path, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=OFF")
    migrate_studies(db)
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("CREATE TABLE IF NOT EXISTS studies " + STUDY_COLUMNS)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS tasks(
        study INTEGER REFERENCES studies, skill TEXT, chapter INTEGER NOT NULL,
        spec TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY(study, skill));
    CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY, study INTEGER, skill TEXT, action TEXT, actor TEXT,
        source TEXT, digest TEXT, artifact BLOB, reason TEXT,
        created TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(study,skill) REFERENCES tasks(study,skill));
    CREATE TRIGGER IF NOT EXISTS protect_event_update BEFORE UPDATE ON events
        BEGIN SELECT RAISE(ABORT,'append-only'); END;
    CREATE TRIGGER IF NOT EXISTS protect_event_delete BEFORE DELETE ON events
        BEGIN SELECT RAISE(ABORT,'append-only'); END;
    """)
    return db

def authorize(role, caller_token=None):
    """CLI operator presents a token injected into BR_SITE_CALLER_TOKEN by their shell."""
    founder = os.environ.get("BR_FOUNDER_TOKEN", "")
    reviewer = os.environ.get("BR_AUDIT_TOKEN", "")
    expected = {"FOUNDER": founder, "SW-13": reviewer}[role]
    caller = os.environ.get("BR_SITE_CALLER_TOKEN", "") if caller_token is None else caller_token
    if not expected or founder == reviewer or not hmac.compare_digest(expected.encode(), caller.encode()):
        raise PermissionError(f"{role} credential required")

def release(db, study):
    curriculum = db.execute("SELECT curriculum FROM studies WHERE id=?", (study,)).fetchone()[0]
    prerequisites = PREREQUISITES[curriculum]
    rows = db.execute("SELECT chapter,state FROM tasks WHERE study=?", (study,)).fetchall()
    chapters = {r["chapter"] for r in rows}
    open_chapters = {r["chapter"] for r in rows if r["state"] != "accepted"}
    for chapter in chapters:
        if set(prerequisites[chapter]) <= chapters - open_chapters:
            db.execute("UPDATE tasks SET state='ready' WHERE study=? AND chapter=? AND state='blocked'",
                       (study, chapter))

def start(db, name, skills, *, caller_token=None, curriculum="site"):
    authorize("FOUNDER", caller_token)
    if curriculum not in PREREQUISITES:
        raise ValueError("Unknown curriculum")
    if not name.strip() or not skills:
        raise ValueError("Provide a study name and at least one skill")
    with db:
        db.execute("BEGIN IMMEDIATE")
        current = db.execute("SELECT id FROM studies WHERE name=? AND curriculum=?", (name.strip(),curriculum)).fetchone()
        if current:
            return current[0]
        study = db.execute("INSERT INTO studies(name,curriculum) VALUES (?,?)", (name.strip(),curriculum)).lastrowid
        for s in skills:
            chapter = int(s["chapter"])
            if chapter not in PREREQUISITES[curriculum]:
                raise ValueError(f"Unmapped chapter {chapter}")
            db.execute("INSERT INTO tasks VALUES (?,?,?,?,?)",
                       (study, s["id"], chapter, json.dumps(s, ensure_ascii=False), "blocked"))
        release(db, study)
        return study

def act(db, study, skill, action, path, source, reason, *, caller_token=None):
    if action not in ("submit", "accept", "return"):
        raise ValueError("Unknown action")
    role = "FOUNDER" if action == "submit" else "SW-13"
    authorize(role, caller_token)
    if not source.strip() or not reason.strip():
        raise ValueError("Source locator and rationale are required")
    artifact = path if isinstance(path, bytes) else Path(path).read_bytes()
    if not artifact:
        raise ValueError("Evidence file is empty")
    digest = hashlib.sha256(artifact).hexdigest()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT state FROM tasks WHERE study=? AND skill=?", (study, skill)).fetchone()
        if not row or row["state"] != ("ready" if action == "submit" else "pending_review"):
            raise ValueError("Skill is missing or its current state prohibits this action")
        if action == "accept":
            original = db.execute("""SELECT source,digest FROM events WHERE study=? AND skill=?
                AND action='submit' ORDER BY id DESC LIMIT 1""", (study, skill)).fetchone()
            if source.strip() == original["source"] or digest == original["digest"]:
                raise ValueError("Acceptance requires a separate review artifact and source locator")
        db.execute("""INSERT INTO events(study,skill,action,actor,source,digest,artifact,reason)
            VALUES (?,?,?,?,?,?,?,?)""", (study, skill, action, role, source.strip(), digest, artifact, reason.strip()))
        state = {"submit":"pending_review", "accept":"accepted", "return":"ready"}[action]
        db.execute("UPDATE tasks SET state=? WHERE study=? AND skill=?", (state, study, skill))
        if action == "accept":
            release(db, study)
    return state

def status(db, study, *, caller_token=None):
    try:
        authorize("FOUNDER", caller_token)
    except PermissionError:
        authorize("SW-13", caller_token)
    row = db.execute("SELECT name,curriculum FROM studies WHERE id=?", (study,)).fetchone()
    if row is None:
        raise ValueError("Unknown study")
    counts = {state: 0 for state in ("blocked","ready","pending_review","accepted")}
    for item in db.execute("SELECT state,COUNT(*) AS n FROM tasks WHERE study=? GROUP BY state", (study,)):
        counts[item["state"]] = item["n"]
    ready = []
    for item in db.execute("SELECT spec FROM tasks WHERE study=? AND state='ready' ORDER BY chapter,rowid LIMIT 12", (study,)):
        spec = json.loads(item["spec"])
        ready.append({key:spec.get(key) for key in ("id","title","owner","chapter")})
    return {"study":study,"name":row["name"],"curriculum":row["curriculum"],"counts":counts,"ready":ready}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="site-studies.sqlite3")
    subs = parser.add_subparsers(dest="command", required=True)
    starter = subs.add_parser("start")
    starter.add_argument("name")
    starter.add_argument("--curriculum", choices=PREREQUISITES, default="site")
    for command in ("status", "show", "evidence", "submit", "accept", "return"):
        sub = subs.add_parser(command)
        sub.add_argument("study", type=int)
        if command != "status":
            sub.add_argument("skill")
        if command == "evidence":
            sub.add_argument("event", type=int)
            sub.add_argument("destination", type=Path)
        if command in ("submit", "accept", "return"):
            sub.add_argument("--file", required=True)
            sub.add_argument("--source", required=True)
            sub.add_argument("--reason", required=True)
    args = parser.parse_args()
    with closing(connect(args.db)) as db:
        if args.command == "start":
            specs = load_skills(args.curriculum)
            result = start(db, args.name, specs, curriculum=args.curriculum)
        elif args.command in ("status", "show", "evidence"):
            try:
                authorize("FOUNDER")
            except PermissionError:
                authorize("SW-13")
            if args.command == "evidence":
                event = db.execute("SELECT artifact,digest FROM events WHERE study=? AND skill=? AND id=?",
                                   (args.study,args.skill,args.event)).fetchone()
                if event is None or hashlib.sha256(event["artifact"]).hexdigest() != event["digest"]:
                    raise ValueError("Evidence missing or digest check failed")
                with args.destination.open("xb") as output:
                    output.write(event["artifact"])
                result = {"file":str(args.destination),"sha256":event["digest"]}
            elif args.command == "status":
                result = [dict(row) for row in db.execute(
                    "SELECT chapter,skill,state FROM tasks WHERE study=? ORDER BY chapter,rowid", (args.study,))]
            else:
                row = db.execute("SELECT spec,state FROM tasks WHERE study=? AND skill=?", (args.study,args.skill)).fetchone()
                if not row:
                    raise ValueError("Unknown study or skill")
                result = {"specification":json.loads(row["spec"]), "state":row["state"], "history":[dict(event)
                          for event in db.execute("SELECT id,action,actor,source,digest,reason,created FROM events WHERE study=? AND skill=? ORDER BY id",(args.study,args.skill))]}
        else:
            result = act(db,args.study,args.skill,args.command,args.file,args.source,args.reason)
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except (ValueError, PermissionError, OSError, sqlite3.Error) as exc:
        raise SystemExit(str(exc))
