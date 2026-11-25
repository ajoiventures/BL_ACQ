import json
import sqlite3
from contextlib import contextmanager
import pytest
from fastapi import FastAPI, Header
from fastapi.testclient import TestClient
from backend.core.tickets import import_manifest
from backend.intake_routes import register

@pytest.fixture
def setup(tmp_path):
    path = tmp_path/"review.db"
    @contextmanager
    def conn():
        db = sqlite3.connect(path)
        db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally:
            db.close()
    with conn() as db:
        db.execute("CREATE TABLE log(event TEXT,obj TEXT,data TEXT)")
    def event(db,domain,who,action,obj,data):
        db.execute("INSERT INTO log VALUES(?,?,?)",(action,obj,json.dumps(data)))
    with conn() as db:
        import_manifest(db,event)
        db.execute("""INSERT OR IGNORE INTO project_tickets
        (id,area,domain,title,leader,owner,status,acceptance,evidence,dependencies,source)
        VALUES('BR-T043','Governance','PROJECT_INTERNAL','Prompt review','L1','SW-00','open','scope','none','[]','brief')""")
    app = FastAPI()
    def actor(auth:str=Header(default="")): return auth
    register(app,actor,conn,event)
    client=TestClient(app)
    def post(text,key,role="FOUNDER",**extra):
        return client.post("/api/prompt-review",headers={"auth":role},json={"request_id":key,"prompt":text,**extra})
    return client,post,conn


def test_intake_permissions_matching_idempotency_and_privacy(setup):
    client,post,conn=setup
    assert post("Verify Asher","1",role="SW-09").status_code==403
    assert client.get("/api/prompt-review/current",headers={"auth":"SW-13"}).status_code==403
    assert post("Verify Asher","1").json()["ticket_id"]=="BR-T028"
    assert post("Verify Asher and Rhino sketch","2").json()["disposition"]=="needs_clarification"
    assert post("BR-T028 BR-T024","3",ticket_id="BR-T024").json()["ticket_id"]=="BR-T024"
    raw="Create a ventilation checklist for confidential-person@private.test"
    result=post(raw,"4").json()
    assert result["disposition"]=="created"
    assert post(raw,"4").json()==result
    assert post("different","4").status_code==409
    assert post(raw,"5").json()["ticket_id"]==result["ticket_id"]
    with conn() as db:
        shared = list(db.execute("SELECT * FROM project_tickets WHERE id=?",(result["ticket_id"],)).fetchone())
        assert "private.test" not in json.dumps(shared)
        assert not db.execute("SELECT 1 FROM log WHERE data LIKE '%private.test%'").fetchone()
        assert db.execute("SELECT COUNT(*) FROM private_prompt_review WHERE request_id='4'").fetchone()[0]==1
    assert post("Every time, route my prompt to a ticket","6").json()["ticket_id"]=="BR-T043"


def test_side_idea_and_digest_preserve_active_work(setup):
    client,post,conn=setup
    assert post("Track Asher","a").json()["active_ticket_id"]=="BR-T028"
    idea=post("Someday, build a Rhino sketch","b").json()
    assert (idea["disposition"],idea["ticket_id"],idea["workstream"])==("parked_idea","BR-T024","Atlas")
    assert idea["theme"] and idea["active_ticket_id"]=="BR-T028"
    digest=post("What’s left?","c").json()
    assert digest["disposition"]=="informational" and digest["active_ticket_id"]=="BR-T028"
    from backend.core.tickets import canonical_register
    from backend.core.tickets import is_canonically_closed
    planning, _ = canonical_register()
    remaining = sum(not is_canonically_closed(planning, ticket_id) for ticket_id in planning)
    assert digest["next_action"].startswith(f"{remaining} tickets remain.")

    assert post("Continue","d").json()["ticket_id"]=="BR-T028"
    assert client.get("/api/prompt-review/current",headers={"auth":"FOUNDER"}).json()["ticket_id"]=="BR-T028"
    with conn() as db:
        assert not db.execute("SELECT 1 FROM project_tickets WHERE id LIKE 'BR-P%'").fetchone()
    ideas = client.get("/api/prompt-review/ideas",headers={"auth":"FOUNDER"}).json()
    assert len(ideas) == 1 and ideas[0]["request_id"] == "b"
    assert ideas[0]["prompt"] == "Someday, build a Rhino sketch"
    assert ideas[0]["result"]["active_ticket_id"] == "BR-T028"
    assert client.get("/api/prompt-review/ideas",headers={"auth":"SW-13"}).status_code == 403


def test_active_assignment_survives_digest_idea_and_restart(setup):
    client,post,conn=setup
    assert client.get("/api/prompt-review/current",headers={"auth":"FOUNDER"}).json() is None
    assert post("What is left?","empty").json()["disposition"]=="informational"
    assert client.get("/api/prompt-review/current",headers={"auth":"FOUNDER"}).json() is None
    first=post("Review BR-T028","a")
    assert first.json()["ticket_id"]=="BR-T028"
    assert post("Someday, build a Rhino sketch","b").json()["disposition"]=="parked_idea"
    assert post("What is left?","c").json()["disposition"]=="informational"
    assert post("BR-T028 BR-T023","d").json()["disposition"]=="needs_clarification"
    with conn() as db:
        db.execute("UPDATE project_tickets SET status='review_required',version=version+1 WHERE id='BR-T028'")
    # Construct a new application against the same on-disk ledger (no memory cache).
    app=FastAPI()
    def actor(auth:str=Header(default="")): return auth
    def event(db,domain,who,action,obj,data):
        db.execute("INSERT INTO log VALUES(?,?,?)",(action,obj,json.dumps(data)))
    register(app,actor,conn,event)
    restarted=TestClient(app)
    headers={"auth":"FOUNDER"}
    restored=restarted.get("/api/prompt-review/current",headers=headers).json()
    assert restored["ticket_id"]==restored["active_ticket_id"]=="BR-T028"
    assert restored["status"]=="review_required"
    for i,prompt in enumerate(["Continue","Next batch of tickets","Run tickets","Proceed"]):
        body={"prompt":prompt,"request_id":f"resume-{i}"}
        r=restarted.post("/api/prompt-review",headers=headers,json=body)
        assert r.json()["ticket_id"]=="BR-T028" and r.json()["disposition"]=="resumed"
        assert restarted.post("/api/prompt-review",headers=headers,json=body).json()==r.json()
    assert post("Review BR-T028","a").json()==first.json() # immutable historic receipt
    with conn() as db:
        assert not db.execute("SELECT 1 FROM project_tickets WHERE id LIKE 'BR-P%'").fetchone()
        assert db.execute("SELECT COUNT(*) FROM private_prompt_review").fetchone()[0]==9


def test_resuming_canonical_closure_uses_closed_status(setup):
    client, post, conn = setup
    with conn() as db:
        db.execute("UPDATE project_tickets SET status='review_required' WHERE id='BR-T020'")
    assert post('Review BR-T020', 'canonical').json()['status'] == 'closed'
    restored = client.get('/api/prompt-review/current', headers={'auth': 'FOUNDER'}).json()
    assert restored['status'] == 'closed'
    assert restored['next_action'] == 'Open the register to select the next ticket.'


def test_batch_followup_without_active_assignment_does_not_create_ticket(setup):
    client,post,conn=setup
    for i,prompt in enumerate(["Next batch of tickets","Run tickets","Proceed"]):
        assert post(prompt,str(i)).json()["disposition"]=="needs_clarification"
    with conn() as db:
        assert not db.execute("SELECT 1 FROM project_tickets WHERE id LIKE 'BR-P%'").fetchone()
