import pytest,sqlite3
from fastapi.testclient import TestClient
from test_api import app,F,A,O,conn
from test_acquisition_runs import start,step
from backend.core import strategy_cases as s
client=TestClient(app)

@pytest.fixture(scope='module')
def case_input():
    r=start(size=10).json()
    p=client.get('/api/acquisition-runs/'+r['id']+'/properties',headers=F).json()['items'][0]['parcel_key']
    b={'run_id':r['id'],'parcel_key':p,'strategy_id':'SMF-01'}
    assert client.post('/api/strategy-cases',headers=F,json=b).status_code==404
    r=step(r).json()
    return b

def test_catalog_permissions():
    assert client.get('/api/strategy-library').status_code==401
    assert client.get('/api/strategy-library',headers=O).status_code==403
    d=client.get('/api/strategy-library',headers=A).json();assert d['total']==d['matches']==83 and len(d['flywheels'])==5
    source=s.load_catalog()
    assert d['catalog_schema_version']==source['schema_version'] and d['source_hashes']==source['source_hashes']
    d=client.get('/api/strategy-library?q=legacy%20fourplex',headers=F).json();assert [x['source']['ID'] for x in d['records']]==['SMF-01']

def test_pilot_unit_gates():
    assert s.unit_fit('SMF-01')=='NEEDS_LEGAL_UNIT_EVIDENCE'
    for n in (2,3,4):
        assert s.unit_fit('SMF-02',n,n,hypothetical=True)=='HYPOTHETICAL_UNIT_GATE_MATCH_ONLY'
    assert s.unit_fit('SMF-01',3,3,hypothetical=True)=='OUTSIDE_PILOT_UNIT_RANGE'
    assert s.unit_fit('SMF-01',3,4,hypothetical=True)=='CONFLICTING_UNIT_COUNTS'
    assert s.unit_fit('SMF-04')=='RESEARCH_DEFERRED'
    with pytest.raises(ValueError):s.unit_fit('SMF-01',4,4)

def test_real_case_replay_permissions_and_immutability(case_input):
    b=case_input
    assert client.post('/api/strategy-cases',headers=A,json=b).status_code==403
    assert client.post('/api/strategy-cases',headers=F,json={**b,'legal_units':4}).status_code==422
    a=client.post('/api/strategy-cases',headers=F,json=b).json();r=a['receipt']
    assert not a['replay'] and r['unit_gate']=='NEEDS_LEGAL_UNIT_EVIDENCE' and len(r['work_packages'])==4
    assert set(r['decision_gates'].values())=={'UNKNOWN'} and r['financial_authority_cents']==0 and not r['dispatch_performed']
    replay=client.post('/api/strategy-cases',headers=F,json=b).json();assert replay['replay'] and replay['receipt']==r
    assert client.get('/api/strategy-cases/'+r['id'],headers=A).json()['catalog_current']
    with conn() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM strategy_case_receipts WHERE id=?',(r['id'],))

def test_financial_review_and_no_generic_substitution(case_input):
    r=client.post('/api/strategy-cases',headers=F,json=case_input).json()['receipt'];url='/api/strategy-cases/'+r['id']+'/finance'
    ops={'revenue_cents':6000000,'operating_cost_cents':2000000,'debt_service_cents':2400000,'reserve_contribution_cents':400000,'cash_capex_cents':500000}
    body={'as_of':'2026-11-23','operations':ops,'capital':{}}
    a=client.post(url,headers=F,json=body).json();rpt=a['receipt']['report'];assert rpt['operating_review']['distributable_cash_cents']==700000 and rpt['scenarios'][0]['result']['distributable_cash_cents']==100000
    assert rpt['financial_authority_cents']==0 and rpt['operating_review']['ending_unrestricted_cash_before_distributions_cents'] is None
    assert client.post(url,headers=F,json=body).json()['replay']
    assert client.post(url,headers=A,json=body).status_code==403
    assert client.post(url,headers=F,json={**body,'operations':{'revenue_cents':True}}).status_code==422
    missing=client.post(url,headers=F,json={'as_of':'2026-11-23'}).json()['receipt']['report'];assert missing['operating_review']['distributable_cash_cents'] is None
    other=client.post('/api/strategy-cases',headers=F,json={**case_input,'strategy_id':'SMF-02'}).json()['receipt'];assert client.post('/api/strategy-cases/'+other['id']+'/finance',headers=F,json=body).status_code==409

def test_catalog_change_marks_case_stale(case_input,monkeypatch):
    r=client.post('/api/strategy-cases',headers=F,json=case_input).json()['receipt'];catalog=s.load_catalog();catalog['limits']=['Changed test catalog revision']
    monkeypatch.setattr(s,'load_catalog',lambda:catalog)
    assert not client.get('/api/strategy-cases/'+r['id'],headers=A).json()['catalog_current']
    assert client.post('/api/strategy-cases/'+r['id']+'/finance',headers=F,json={'as_of':'2026-11-23'}).status_code==409
