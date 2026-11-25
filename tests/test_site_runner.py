import pytest
from site_academy.runner import act, connect, start

def test_gated_handoff_and_resumption(tmp_path, monkeypatch):
    for key, value in {"BR_FOUNDER_TOKEN":"operator","BR_AUDIT_TOKEN":"auditor","BR_SITE_CALLER_TOKEN":"operator"}.items():
        monkeypatch.setenv(key,value)
    path = tmp_path/"jobs.sqlite3"
    db = connect(path)
    specs = [{"id":"one","chapter":1},{"id":"two","chapter":2}]
    study = start(db,"College Park",specs)
    assert start(db,"College Park",specs) == study
    evidence = tmp_path/"field.txt"
    evidence.write_text("field observation")
    def step(skill, action, source="field notebook"):
        return act(db,study,skill,action,evidence,source,"checked field notes")
    with pytest.raises(ValueError):
        step("two","submit")
    assert step("one","submit") == "pending_review"
    with pytest.raises(PermissionError):
        step("one","accept")
    monkeypatch.setenv("BR_SITE_CALLER_TOKEN","auditor")
    with pytest.raises(ValueError):
        step("one","accept","review")
    assert step("one","return","review") == "ready"
    monkeypatch.setenv("BR_SITE_CALLER_TOKEN","operator")
    step("one","submit")
    monkeypatch.setenv("BR_SITE_CALLER_TOKEN","auditor")
    evidence.write_text("independent review")
    assert step("one","accept","review") == "accepted"
    db.close()
    db = connect(path)
    assert db.execute("SELECT state FROM tasks WHERE skill='two'").fetchone()[0] == "ready"
    assert db.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 4
    db.close()

def test_membership_and_api_credentials(tmp_path, monkeypatch):
    from site_academy.runner import status
    monkeypatch.setenv("BR_FOUNDER_TOKEN", "one")
    monkeypatch.setenv("BR_AUDIT_TOKEN", "two")
    monkeypatch.delenv("BR_SITE_CALLER_TOKEN", raising=False)
    db = connect(tmp_path/"api.sqlite3")
    with pytest.raises(PermissionError):
        start(db, "fieldwork", [{"id":"s","chapter":1}], caller_token="two")
    skills = [{"id":"skill-%d"%i,"chapter":1,"owner":"SW-02","title":"Field task"} for i in range(14)]
    study = start(db,"fieldwork",skills,caller_token="one")
    overview = status(db,study,caller_token="two")
    assert overview["counts"]["ready"] == 14
    assert len(overview["ready"]) == 12
    assert overview["ready"][0]["owner"] == "SW-02"
    with pytest.raises(PermissionError):
        status(db,study,caller_token="bad")
    db.close()

def test_byte_submission_is_stored_verbatim(tmp_path, monkeypatch):
    monkeypatch.setenv("BR_FOUNDER_TOKEN","op")
    monkeypatch.setenv("BR_AUDIT_TOKEN","rev")
    db = connect(tmp_path/"uploads.sqlite3")
    study = start(db,"ingest",[{"id":"a","chapter":1}],caller_token="op")
    with pytest.raises(ValueError):
        act(db,study,"a","submit",b"","survey:01","preflight",caller_token="op")
    raw = b"\x00binary\xffsurvey"
    assert act(db,study,"a","submit",raw,"survey:01","field log",caller_token="op") == "pending_review"
    assert db.execute("SELECT artifact FROM events").fetchone()[0] == raw
    db.close()

def test_urban_parallel_chapters_and_shared_study_name(tmp_path, monkeypatch):
    from site_academy.runner import status
    monkeypatch.setenv("BR_FOUNDER_TOKEN","founder")
    monkeypatch.setenv("BR_AUDIT_TOKEN","review")
    db = connect(tmp_path/"multi.sqlite")
    skills = [{"id":f"econ-{i}", "chapter":i} for i in range(18)]
    site = start(db,"Downtown",[{"id":"site","chapter":1}],caller_token="founder")
    econ = start(db,"Downtown",skills,curriculum="urban",caller_token="founder")
    assert site != econ
    assert start(db,"Downtown",skills,curriculum="urban",caller_token="founder") == econ
    def overview():
        return status(db,econ,caller_token="founder")
    assert overview()["curriculum"] == "urban"
    assert {r["chapter"] for r in overview()["ready"]} == {0,1}
    for i in (0,1):
        act(db,econ,f"econ-{i}","submit",b"draft","district archive","source analysis",caller_token="founder")
        act(db,econ,f"econ-{i}","accept",b"review","audit log","replicated",caller_token="review")
    assert {r["chapter"] for r in overview()["ready"]} == {2,6,10,16}
    assert status(db,site,caller_token="founder")["counts"]["ready"] == 1
    db.close()

def test_legacy_migration_keeps_review_and_study_id(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.setenv("BR_FOUNDER_TOKEN","founder")
    monkeypatch.setenv("BR_AUDIT_TOKEN","review")
    path = tmp_path/"legacy.sqlite"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE studies(id INTEGER PRIMARY KEY,name TEXT NOT NULL UNIQUE);
        CREATE TABLE tasks(study INTEGER REFERENCES studies,skill TEXT,chapter INTEGER,
             spec TEXT,state TEXT,PRIMARY KEY(study,skill));
        CREATE TABLE events(id INTEGER PRIMARY KEY,study INTEGER,skill TEXT,action TEXT,
             actor TEXT,source TEXT,digest TEXT,artifact BLOB,reason TEXT,created TEXT,
             FOREIGN KEY(study,skill) REFERENCES tasks(study,skill));
        INSERT INTO studies VALUES(49,'Original');
        INSERT INTO tasks VALUES(49,'s',1,'{}','accepted');
        INSERT INTO events(id,study,skill,action,artifact) VALUES(10,49,'s','accept',X'61');
    """)
    db.close()
    db=connect(path)
    assert tuple(db.execute("SELECT id,name,curriculum FROM studies").fetchone()) == (49,"Original","site")
    assert db.execute("SELECT artifact FROM events WHERE id=10").fetchone()[0] == b"a"
    assert not db.execute("PRAGMA foreign_key_check").fetchall()
    assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert start(db,"Original",[{"id":"u","chapter":0}],curriculum="urban",caller_token="founder") != 49
    db.close()
