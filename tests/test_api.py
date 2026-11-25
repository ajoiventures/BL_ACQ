import os,tempfile
from pathlib import Path
import pytest
os.environ['BR_DB']=tempfile.mktemp(suffix='.db')
os.environ['BR_FOUNDER_TOKEN']='test-founder'
os.environ['BR_AUDIT_TOKEN']='test-audit'
os.environ['BR_OPERATIONS_TOKEN']='test-ops'
from fastapi.testclient import TestClient
from backend.main import app,conn,DB,initialize
client=TestClient(app)
F={'Authorization':'Bearer test-founder'}; A={'Authorization':'Bearer test-audit'}; O={'Authorization':'Bearer test-ops'}
def post(path,data,headers=F):return client.post('/api/'+path,json=data,headers=headers)
def get(path,headers=F):return client.get('/api/'+path,headers=headers)
def new():return post('records',{'module':'home','kind':'Maintenance','title':'Test maintained asset'}).json()['id']
def ev(rid,source='simulation://one',content='independent inspection content'):
 return post(f'objects/{rid}/evidence',{'source_uri':source,'source_date':'2026-11-18','content':content}).json()['id']
def test_auth_required():assert client.get('/api/bootstrap').status_code==401
def test_financial_unknown_and_zero_authority():
 d=get('bootstrap').json();assert d['financials']['cash'] is None and d['financials']['authority']==0
 assert len([d for d in d['decisions'] if d['state']=='PENDING'])==3
 assert len(d['agents'])==14 and len(d['leaders'])==4
 assert d['skill_count']>300

def test_persistence_and_domain_permissions():
 rid=new();initialize();assert any(r['id']==rid for r in get('bootstrap').json()['records'])
 assert get('ontology?domain=COMMERCIAL',O).status_code==403
 assert not any(r['domain']=='COMMERCIAL' for r in get('bootstrap',O).json()['records'])
 assert post('records',{'module':'commercial','kind':'Client','title':'Private company'},O).status_code==403

def test_state_machine_independent_completion_and_conflict():
 rid=new()
 assert post(f'records/{rid}/transition',{'target':'COMPLETED_SIMULATION','version':1}).status_code==409
 assert post(f'records/{rid}/transition',{'target':'IN_PROGRESS','version':1}).status_code==200
 assert post(f'records/{rid}/transition',{'target':'REVIEW_REQUIRED','version':1,'evidence':'prepared'}).status_code==409
 assert post(f'records/{rid}/transition',{'target':'REVIEW_REQUIRED','version':2}).status_code==422
 assert post(f'records/{rid}/transition',{'target':'REVIEW_REQUIRED','version':2,'evidence':'simulation artifact prepared'}).status_code==200
 body={'target':'COMPLETED_SIMULATION','version':3,'evidence':'independent artifact review'}
 assert post(f'records/{rid}/transition',body).status_code==403
 assert post(f'records/{rid}/transition',body,A).status_code==200

def test_source_assertion_and_independent_review():
 rid=new();eid=ev(rid)
 b={'evidence_id':'missing','value':'maintenance candidate','context':'simulation','authority':'source author'}
 assert post(f'objects/{rid}/assertions',b).status_code==422
 b['evidence_id']=eid;sid=post(f'objects/{rid}/assertions',b).json()['id']
 assert post(f'assertions/{sid}/review',{'decision':'VERIFIED','independent_evidence_id':eid}).status_code==403
 assert post(f'assertions/{sid}/review',{'decision':'VERIFIED','independent_evidence_id':eid},A).status_code==422
 duplicate=ev(rid,'simulation://two');assert post(f'assertions/{sid}/review',{'decision':'VERIFIED','independent_evidence_id':duplicate},A).status_code==422
 second=ev(rid,'simulation://independent-review','separate reviewer source artifact')
 assert post(f'assertions/{sid}/review',{'decision':'VERIFIED','independent_evidence_id':second},A).status_code==200

def test_expiration_and_cross_subject_evidence():
 rid=new();eid=ev(rid);other=new()
 b={'evidence_id':eid,'value':'candidate','context':'simulation','authority':'institution','expires_at':'2020-01-01T00:00:00+00:00'}
 assert post(f'objects/{other}/assertions',b).status_code==422
 sid=post(f'objects/{rid}/assertions',b).json()['id']
 status=next(s for s in get('ontology').json()['statuses'] if s['id']==sid)
 assert status['effective_verification']=='EXPIRED'

def test_link_domain_boundary():
 rid=new()
 assert post(f'objects/{rid}/links',{'destination':'BR-010','kind':'RELATES_TO'}).status_code==403
 assert post(f'objects/{rid}/links',{'destination':'BR-001','kind':'RELATES_TO'}).status_code==200
 assert post(f'objects/{rid}/links',{'destination':'BR-001','kind':'OWNED_BY'}).status_code==403

def test_approval_scope_and_no_execution():
 d=get('bootstrap').json()['decisions'][0]
 assert post('decisions/'+d['id'],{'decision':'APPROVED'},A).status_code==403
 assert post('decisions/'+d['id'],{'decision':'APPROVED'}).json()['external_authority']==0
 assert post('decisions/'+d['id'],{'decision':'APPROVED'}).status_code==409
 assert post('external-actions',{}).status_code==403

def test_job_handoff_and_retry():
 jid=post('jobs',{'domain':'FAMILY_OFFICE','leader':'L4','specialist':'SW-09','question':'Prepare an inspection checklist'}).json()['id']
 assert post('jobs/'+jid+'/run',{}).json()['handoff']=='SW-13'
 assert post('jobs/'+jid+'/run',{}).status_code==409
 assert get('jobs').json()[0]['state']=='NEEDS_EVIDENCE'

def test_checkpoint_and_hash_chain():
 assert client.put('/api/context',json={'note':'Resume maintenance'},headers=F).status_code==200
 assert get('bootstrap').json()['context']['note']=='Resume maintenance'
 assert get('audit').json()['integrity']
 with conn() as c:
  import sqlite3,pytest
  with pytest.raises(sqlite3.IntegrityError):c.execute("UPDATE audit SET action='tampered'")

def test_balanced_financial_simulation_is_separate_from_actuals():
 b={'entity':'Simulation household','debit_account':'Cash','credit_account':'Owner equity','cents':10000,'evidence':'Synthetic opening capital for test only'}
 assert post('ledger',b).status_code==200
 bad=dict(b,credit_account='Cash');assert post('ledger',bad).status_code==422
 negative=dict(b,cents=-1);assert post('ledger',negative).status_code==422
 d=get('ledger').json();assert d['balanced'] and d['summary_cents']['net_worth']==10000
 assert get('bootstrap').json()['financials']['cash'] is None
 assert get('ledger?domain=COMMERCIAL',O).status_code==403

def test_skill_assessment_needs_independent_auditor():
 sid=get('skills').json()[0]['id'];b={'evidence':'Independent controlled test artifact and acceptance review','verdict':'PASS_SIMULATION'}
 assert post('skills/'+sid+'/assess',b).status_code==403
 assert post('skills/'+sid+'/assess',b,A).json()['live_authority']==0
 assert get('skills?q='+sid).json()[0]['maturity']=='TESTED_SIMULATION'

def test_record_edit_and_scoped_approval_queue():
 rid=new();b={'title':'Updated simulation asset','notes':'Updated context','version':1,'due':'2026-12-01'}
 assert client.put('/api/records/'+rid,json=b,headers=F).status_code==200
 assert client.put('/api/records/'+rid,json=b,headers=F).status_code==409
 assert post('records/'+rid+'/request-approval',{}).json()['scope']['external_execution'] is False
 assert post('records/'+rid+'/request-approval',{}).status_code==409

def test_deadline_exceptions_respect_local_day_completion_and_access():
 from backend.main import overdue_records
 from datetime import date
 rows=[dict(id=str(i),due=due,state=state,priority=2) for i,(due,state) in enumerate([
  ('2026-11-17','IN_PROGRESS'),('2026-11-18','DRAFT'),(None,'DRAFT'),
  ('2026-11-15','COMPLETED_SIMULATION'),('2026-11-16','REVIEW_REQUIRED')])]
 assert [r['id'] for r in overdue_records(rows,date(2026,11,18))]==['4','0']
 rid=post('records',{'module':'commercial','kind':'Client','title':'Exception access test','due':'2001-01-01'}).json()['id']
 assert rid in [r['id'] for r in get('bootstrap').json()['overdue']]
 assert rid not in [r['id'] for r in get('bootstrap',O).json()['overdue']]


def test_renewal_to_founder_queue():
    rid=post('records',{'module':'mail','kind':'Physical mail','title':'Simulation renewal'}).json()['id']
    b=dict(version=1,reference='simulation://renewal',document='Renew by 2026-10-01.',issued='2026-09-01',deadline='2026-10-01',quotation='Unrelated text')
    assert post(f'records/{rid}/renewal',b).status_code==422
    b['quotation']=b['document']
    assert post(f'records/{rid}/renewal',b,A).status_code==403
    eid=post(f'records/{rid}/renewal',b).json()['evidence_id']
    assert any(e['id']==eid for e in get('ontology').json()['evidence'])
    assert post(f'records/{rid}/renewal',b).status_code==409
    decision=post(f'records/{rid}/request-approval',{}).json()['id']
    assert post('decisions/'+decision,{'decision':'APPROVED'}).json()['external_authority']==0

def test_site_study_academy_handoff():
 name={'name':'Simulation study of site access'}
 assert post('site-studies',name,O).status_code==403
 assert post('site-studies',name,A).status_code==403
 packet=post('site-studies',name).json()
 key=packet['study']
 assert post('site-studies',name).json()['study']==key
 assert packet['counts']['blocked']>0
 task=packet['ready'][0]
 assert get('skills?q='+task['id']).json()[0]['owner']==task['owner']
 path=f"site-studies/{key}/tasks/{task['id']}"
 evidence={'action':'submit','text':'Site context exercise','source':'simulation://field-1','reason':'Test evidence submission'}
 assert post(path,evidence).json()['state']=='pending_review'
 evidence.update(action='accept',text='Independent comparison',source='simulation://review-1')
 assert post(path,evidence).status_code==403
 assert post(path,evidence,A).json()['state']=='accepted'
 assert get(f'site-studies/{key}',A).json()['counts']['accepted']==1
 assert get(f'site-studies/{key}',O).status_code==403

def test_urban_curriculum_with_same_study_name():
 name={'name':'Simulation study of site access','curriculum':'urban'}
 study=post('site-studies',name).json()
 assert study['curriculum']=='urban'
 assert sum(study['counts'].values())==sum(r['id'].startswith('UE-') for r in get('skills?q=UE-').json())
 assert all(r['id'].startswith('UE-') for r in study['ready'])
 assert post('site-studies',{'name':name['name']}).json()['study']!=study['study']
 assert post('site-studies',{'name':'invalid curriculum','curriculum':'other'}).status_code==422

def test_project_ticket_register():
 items=get('tickets').json()
 assert len(items)>=42 and len({row['id'] for row in items})==len(items)
 assert get('tickets',O).status_code==403
 row=get('tickets?q=Asher').json()[0]
 assert row['id']=='BR-T028' and row['status']=='in_progress'
 assert get(f"tickets/{row['id']}/history",A).json()[0]['action']=='TICKET_IMPORT'


def test_garden_cycle_traces_plant_care_and_propagation_to_estate():
    def record(module, kind, title, due=None):
        response = post("records", dict(module=module, kind=kind, title=title, due=due), O)
        assert response.status_code == 200
        return response.json()["id"]

    def connect(source, destination, kind, evidence_id=None):
        response = post(f"objects/{source}/links", dict(
            destination=destination, kind=kind, evidence_id=evidence_id,
        ), O)
        assert response.status_code == 200
        return response.json()["id"]

    estate = record("property", "Facility", "Simulation garden estate")
    plan = record("garden", "Estate plan", "Simulation growing plan")
    plant = record("garden", "Plant", "Simulation basil parent")
    offspring = record("garden", "Plant", "Simulation basil cutting")
    edges = {
        connect(plan, estate, "LOCATED_IN"),
        connect(plant, plan, "GOVERNED_BY"),
        connect(offspring, plan, "GOVERNED_BY"),
    }
    care = [
        ("Pruning", "Prune parent plant", "2026-10-01", "Recorded two stems pruned"),
        ("Watering", "Water parent plant, first occurrence", "2026-10-02", "Recorded watering after soil check"),
        ("Watering", "Water parent plant, second occurrence", "2026-10-09", "Recorded follow-up watering"),
        ("Fertilization", "Feed parent plant", "2026-10-10", "Recorded measured feed application"),
        ("Propagation", "Take a cutting", "2026-10-11", "Recorded cutting from the identified parent"),
        ("Harvest", "Harvest parent plant", "2026-10-15", "Recorded 10 grams of harvested leaves"),
    ]
    actions = {}
    for kind, title, due, note in care:
        action = record("garden", kind, title, due)
        source = post(f"objects/{action}/evidence", dict(
            source_uri=f"simulation://garden/{action}", source_date=due, content=note,
        ), O)
        assert source.status_code == 200
        eid = source.json()["id"]
        edges.add(connect(action, plant, "RELATES_TO", eid))
        actions[action] = (due, eid)
        for version, state, actor in (
            (1, "IN_PROGRESS", O),
            (2, "REVIEW_REQUIRED", O),
            (3, "COMPLETED_SIMULATION", A),
        ):
            response = post(f"records/{action}/transition", dict(
                version=version, target=state, evidence=f"Simulation record {eid}: {note}",
            ), actor)
            assert response.json() == {"state": state}
        if kind == "Propagation":
            edges.add(connect(offspring, action, "SOURCED_FROM"))

    initialize()
    graph = get("ontology", O).json()
    assert edges <= {row["id"] for row in graph["links"]}
    assert {eid for _, eid in actions.values()} <= {row["id"] for row in graph["evidence"]}
    records = {row["id"]: row for row in get("bootstrap", O).json()["records"]}
    for action, (due, _) in actions.items():
        assert records[action]["due"] == due
        assert records[action]["state"] == "COMPLETED_SIMULATION"
    assert get("audit", A).json()["integrity"]


def test_household_cycle_links_routine_inventory_and_procurement():
    def create(module, kind, title, notes="", due=None):
        response = post("records", dict(module=module, kind=kind, title=title, notes=notes, due=due), O)
        assert response.status_code == 200
        return response.json()["id"]

    asset = create("property", "Asset", "Simulation air handler")
    vendor = create("home", "Vendor", "Simulation filter supplier")
    plan = create("home", "Routine", "Monthly filter inspection", "Inspect every month and replenish when stock reaches zero.")
    stock = create("home", "Inventory", "Filter inventory", "Opening balance: one compatible filter.")
    work = create("home", "Maintenance", "November filter replacement", due="2026-11-10")
    next_work = create("home", "Maintenance", "December filter inspection", due="2026-12-10")
    request = create("home", "Procurement", "Draft request for two replacement filters")
    inspection = ev(work, "simulation://home/november-inspection", "Test inspection: the identified air handler received one filter.")
    usage = ev(stock, "simulation://home/filter-count", "Test stock count: one opening filter, one consumed, zero remaining.")
    quote = ev(request, "simulation://home/draft-filter-quote", "Test quote: two compatible filters from the identified supplier.")

    expected_links = [
        (plan, asset, "RELATES_TO", None),
        (work, plan, "GOVERNED_BY", inspection),
        (next_work, plan, "GOVERNED_BY", None),
        (stock, work, "RELATES_TO", usage),
        (request, stock, "SOURCED_FROM", quote),
        (request, vendor, "ASSIGNED_TO", quote),
    ]
    link_ids = set()
    for source, dest, kind, evidence_id in expected_links:
        response = post(f"objects/{source}/links", dict(
            destination=dest, kind=kind, evidence_id=evidence_id,
        ), O)
        assert response.status_code == 200
        link_ids.add(response.json()["id"])

    for record_id, evidence_id in [(work, inspection), (request, quote)]:
        for version, target, actor in (
            (1, "IN_PROGRESS", O),
            (2, "REVIEW_REQUIRED", O),
            (3, "COMPLETED_SIMULATION", A),
        ):
            response = post(f"records/{record_id}/transition", dict(
                version=version, target=target, evidence=f"Reviewed simulation source {evidence_id}",
            ), actor)
            assert response.json() == {"state": target}

    initialize()
    graph = get("ontology", O).json()
    links = {(row["src"], row["dst"], row["type"], row["source_id"])
             for row in graph["links"] if row["id"] in link_ids}
    assert links == set(expected_links)
    records = {row["id"]: row for row in get("bootstrap", O).json()["records"]}
    assert records[work]["state"] == records[request]["state"] == "COMPLETED_SIMULATION"
    assert records[next_work]["state"] == "DRAFT"
    assert records[next_work]["due"] == "2026-12-10"
    assert get("audit", A).json()["integrity"]


def test_estate_lifecycle_links_property_records_and_reviewed_maintenance():
    records = {}
    for kind, title in [
        ("Facility", "Sample estate"),
        ("Grounds", "Sample fenced paddock"),
        ("Animal", "Sample resident animal"),
        ("Construction", "Draft shelter repair scope"),
        ("Asset", "Sample grounds shelter"),
        ("Maintenance", "Sample shelter inspection"),
    ]:
        response = post("records", dict(module="property", kind=kind, title=title), O)
        assert response.status_code == 200
        records[kind] = response.json()["id"]

    maintenance = records["Maintenance"]
    inspection = ev(maintenance, "simulation://estate/shelter-inspection",
                    "Sample inspection linked to the shelter and describing a loose board.")
    relationships = [
        ("Grounds", "Facility", "LOCATED_IN", None),
        ("Animal", "Grounds", "LOCATED_IN", None),
        ("Asset", "Grounds", "LOCATED_IN", None),
        ("Construction", "Asset", "RELATES_TO", None),
        ("Maintenance", "Asset", "RELATES_TO", inspection),
        ("Maintenance", "Construction", "RELATES_TO", inspection),
    ]
    expected = set()
    for source, destination, kind, evidence in relationships:
        src, dst = records[source], records[destination]
        response = post(f"objects/{src}/links", dict(destination=dst, kind=kind, evidence_id=evidence), O)
        assert response.status_code == 200
        expected.add((src, dst, kind, evidence))

    for version, target, actor in (
        (1, "IN_PROGRESS", O), (2, "REVIEW_REQUIRED", O), (3, "COMPLETED_SIMULATION", A),
    ):
        result = post(f"records/{maintenance}/transition", dict(
            version=version, target=target, evidence=f"Fixture inspection {inspection}",
        ), actor)
        assert result.json() == {"state": target}

    initialize()
    graph = get("ontology", O).json()
    assert expected <= {(row["src"], row["dst"], row["type"], row["source_id"]) for row in graph["links"]}
    assert any(row["id"] == inspection and row["object_id"] == maintenance for row in graph["evidence"])
    current = {row["id"]: row for row in get("bootstrap", O).json()["records"]}
    assert all(current[key]["module"] == "property" for key in records.values())
    assert current[maintenance]["state"] == "COMPLETED_SIMULATION"
    assert current[records["Construction"]]["state"] == "DRAFT"
    assert get("audit", A).json()["integrity"]


def test_academy_review_links_executed_pattern_to_release(tmp_path, monkeypatch):
    import hashlib
    import json

    from backend import main
    from backend.core import release_sync, tickets
    from backend.core.acquisition_patterns import DecisionReceipts, screen_rule

    db_path = tmp_path / "academy-release.db"
    monkeypatch.setattr(main, "DB", str(db_path))
    main.initialize()
    rule = {
        "schema_version": 1, "pattern_id": "RELEASE-PRACTICE", "version": 1,
        "taxonomy_path": "SPATIAL.MS.REVIEW.UPLAND", "kind": "POLICY", "lifecycle": "DRAFT",
        "jurisdictions": ["US-FL"], "tracks": ["MS"], "effective_from": "2026-11-23",
        "effective_to": None, "title": "Release rehearsal exercise", "source_refs": ["simulation://academy"],
        "predicate": {"field": "contiguous_upland_acres", "op": "lt", "value": "35", "unit": "acre"},
    }
    result = screen_rule(rule, {}, jurisdiction="US-FL", track="MS", as_of="2026-11-24")
    store = DecisionReceipts(str(db_path))
    try:
        receipt = store.append("academy-release-rehearsal", result)
        assert store.verify()
    finally:
        store.close()

    skill_id = get("skills", A).json()[0]["id"]
    evidence = f"Reviewed the local execution and its output.\nreceipt_sha256:{receipt['receipt_hash']}"
    assert post(f"skills/{skill_id}/assess", {"evidence": evidence, "verdict": "PASS_SIMULATION"}, F).status_code == 403
    assessment = post(f"skills/{skill_id}/assess", {"evidence": evidence, "verdict": "PASS_SIMULATION"}, A)
    assert assessment.status_code == 200
    assert assessment.json()["live_authority"] == 0
    rows = json.loads(tickets.SEED.read_bytes())
    ticket = next(row for row in rows if row["area"] == "Acquisition")
    ticket["reviewed_execution_links"] = [{
        "assessment_id": assessment.json()["id"], "operation_id": "academy-release-rehearsal",
    }]
    sha = hashlib.sha256(release_sync.canonical(rows).encode()).hexdigest()
    with main.conn() as db:
        tickets.import_manifest(db, main.event)
    assert get("tickets", F).status_code == 200
    with main.conn() as db:
        db.execute("BEGIN IMMEDIATE")
        before = tickets.get(db, ticket["id"])
        release = release_sync.synchronize(db, main.event, rows, sha)
        assert release["reviewed_execution_links"][0]["receipt_sha256"] == receipt["receipt_hash"]
        assert tickets.get(db, ticket["id"]) == before
        assert release_sync.synchronize(db, main.event, rows, sha)["replay"]
    readback = get(f"tickets/{ticket['id']}/release-evidence", A).json()["release_evidence"]
    assert readback["reviewed_execution_links"] == release["reviewed_execution_links"]


def test_contract_obligation_preparation_separates_source_and_reviewed_dates():
    contract = post("records", {"module": "commercial", "kind": "Contract",
                               "title": "Simulation diligence contract"}).json()["id"]
    evidence = ev(contract, "simulation://contract/rev-1#section-4", "Sample clause gives an initial diligence date.")
    independent = ev(contract, "simulation://review/rev-2#section-4", "Independent sample confirmation of the clause date.")
    body = {"evidence_id": evidence, "value": "2026-12-10", "obligation_clause": "Section 4",
            "context": "Due diligence", "authority": "Simulation authority"}
    url = f"records/{contract}/obligation-preparation"
    assert post(f"objects/{contract}/assertions", {**body, "value": "December 10"}).status_code == 422
    assertion = post(f"objects/{contract}/assertions", body).json()["id"]
    assert get(url, O).status_code == 403
    response = get(url, A)
    assert response.headers["Cache-Control"] == "private, no-store"
    reported = response.json()
    entry = reported["obligations"][0]
    assert entry["clause_locator"] == "Section 4"
    assert entry["evidence_state"] == "SOURCE_REPORTED" and entry["reviewed_due_date"] is None
    assert entry["source_uri"] == "simulation://contract/rev-1#section-4" and len(entry["content_hash"]) == 64
    from uuid import uuid4

    job = {"domain": "COMMERCIAL", "leader": "L4", "specialist": "SW-07",
           "question": "Prepare evidence for the contract date",
           "request_id": str(uuid4()), "contract_record_id": contract,
           "context_sha256": reported["context_sha256"]}
    assert post("jobs", job, O).status_code == 403
    queued = post("jobs", job, F)
    assert queued.status_code == 200
    assert post("jobs", job, F).json() == {"id": queued.json()["id"], "replay": True}
    assert post("jobs", {**job, "question": "Different preparation"}, F).status_code == 409
    review = {"decision": "VERIFIED", "independent_evidence_id": independent}
    assert post(f"assertions/{assertion}/review", review, F).status_code == 403
    assert post(f"assertions/{assertion}/review", review, A).status_code == 200
    reviewed = get(url, F).json()
    assert reviewed["obligations"][0]["reviewed_due_date"] == "2026-12-10"
    assert reviewed["context_sha256"] != reported["context_sha256"]
    assert post(f'jobs/{queued.json()["id"]}/run', {}, F).status_code == 409
    assert post("jobs", {**job, "request_id": str(uuid4())}, F).status_code == 409
    fresh = post("jobs", {**job, "request_id": str(uuid4()), "context_sha256": reviewed["context_sha256"]}, F)
    assert fresh.status_code == 200
    initialize()
    output = post(f'jobs/{fresh.json()["id"]}/run', {}, F).json()
    assert output["contract_preparation"]["context_sha256"] == reviewed["context_sha256"]
    assert output["contract_preparation"]["packet"]["obligations"][0]["reviewed_due_date"] == "2026-12-10"
    assert output["financial_authority"] == 0
    assert get(url, F).json()["context_sha256"] == reviewed["context_sha256"]
    assert post(f"objects/{contract}/assertions", {**body, "value": "2026-12-11"}).status_code == 200
    obligations = get(url, A).json()["obligations"]
    assert all(item["evidence_state"] == "CONFLICT" and item["reviewed_due_date"] is None for item in obligations)


def test_readiness_checks_existing_database_without_creating_one(monkeypatch, tmp_path, caplog):
    from backend import main

    assert client.get("/api/ready").json() == {"status": "ready"}
    db_path = tmp_path / "missing.sqlite"
    monkeypatch.setattr(main, "DB", str(db_path))
    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert response.headers["cache-control"] == "no-store"
    assert not db_path.exists()
    assert "Readiness check failed" in caplog.text
    db_path.write_bytes(b"corrupt")
    assert client.get("/api/ready").status_code == 503
    assert client.get("/api/health").status_code == 200


def test_operator_credential_collision_denies_reads_and_writes(monkeypatch):
    monkeypatch.setenv("BR_AUDIT_TOKEN", "test-founder")
    assert get("bootstrap").status_code == 403
    assert post("records", {"module": "home", "kind": "Maintenance", "title": "Collision"}).status_code == 403
    assert get("bootstrap", O).status_code == 200
    monkeypatch.setenv("BR_AUDIT_TOKEN", "replacement-audit")
    assert get("bootstrap").status_code == 200
    assert get("bootstrap", A).status_code == 401
    assert get("bootstrap", {"Authorization": "Bearer replacement-audit"}).status_code == 200


def test_operator_header_requires_single_bearer_credential():
    for malformed in ("test-founder", "Basic test-founder", "Bearer  test-founder",
                      "Bearer test-founder extra"):
        assert get("bootstrap", {"Authorization": malformed}).status_code == 401
    assert get("bootstrap").status_code == 200
    assert client.get("/api/ready").status_code == 200


@pytest.mark.parametrize('format', ['eml', 'png'])
def test_renewal_from_filed_mail_rejects_changed_body(tmp_path, monkeypatch, format):
    from email.message import EmailMessage
    from filing.inbox import file_document

    archive = tmp_path / "family-mail"
    monkeypatch.setenv("BR_FAMILY_MAIL_ARCHIVE", str(archive))
    message = EmailMessage()
    document = "Please renew by 2026-12-03."
    message.set_content(document)
    source = tmp_path / ('notice.' + format)
    if format == 'eml':
        source.write_bytes(message.as_bytes())
    else:
        from filing import inbox
        source.write_bytes(b'bounded scan fixture')
        def recognize(receipt):
            assert Path(receipt['file']).read_bytes() == source.read_bytes()
            return {'status': 'REVIEW_REQUIRED', 'text': document}
        monkeypatch.setattr(inbox, 'review_windows_scan', recognize)
    capture = file_document(source, archive)
    rid = post('records', {'module':'mail','kind':'Document','title':'Sample email renewal'}).json()['id']
    path = f'records/{rid}/renewal'
    body = {"version":1,"reference":"simulation://email-renewal","document":document,
            "issued":"2026-11-25","deadline":"2026-12-03","quotation":document,
            "mail_capture_id":capture["capture_id"]}
    changed = "Please renew by 2026-12-04."
    assert post(path, {**body,"document":changed,"quotation":changed,"deadline":"2026-12-04"}).status_code == 422
    assert post(path, body, A).status_code == 403
    assert post(path, body).json()["deadline"] == "2026-12-03"


def test_mail_forward_preparation_binds_one_recipient_and_filed_email(tmp_path, monkeypatch):
    from filing.inbox import file_document

    archive = tmp_path / 'archive'
    monkeypatch.setenv('BR_FAMILY_MAIL_ARCHIVE', str(archive))
    source = tmp_path / 'notice.eml'
    source.write_bytes(b'Subject: Filing fixture\r\n\r\nReview this notice.\r\n')
    capture = file_document(source, archive)
    record = post('records', {'module': 'mail', 'kind': 'Forwarding', 'title': 'Forwarding fixture'}).json()
    path = f"records/{record['id']}/request-approval"
    body = {'recipient': 'reviewer@example.test', 'mail_capture_id': capture['capture_id']}
    assert post(path, body, A).status_code == 403
    assert post(path, {**body, 'recipient': 'a@example.test,b@example.test'}).status_code == 422
    result = post(path, body).json()
    scope = result['scope']
    assert scope['operation'] == 'PREPARE_MAIL_FORWARD'
    assert scope['mail_sha256'] == capture['sha256'] and scope['recipient'] == body['recipient']
    assert post('decisions/' + result['id'], {'decision': 'APPROVED'}).json()['external_authority'] == 0
    assert post('external-actions', {}).status_code == 403
