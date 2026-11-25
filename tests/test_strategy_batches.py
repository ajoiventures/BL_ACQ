import pytest, sqlite3
from test_strategy_cases import client,case_input
from test_api import F,A,O,conn
from test_acquisition_runs import start,step
from backend import main
from backend.core import acquisition_runs, strategy_batches, strategy_cases, unit_evidence

@pytest.fixture(scope="module", autouse=True)
def isolated_strategy_batch_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("strategy-batches") / "command.db"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(main, "DB", str(path))
        main.initialize()
        with conn() as db:
            for module in (acquisition_runs, strategy_batches, strategy_cases, unit_evidence):
                module.initialize(db)
        yield


@pytest.fixture(scope='module')
def completed():
    r=start(size=1000).json()
    while r['state']!='COMPLETED':r=step(r).json()
    return r

def test_batch_replay_and_permissions(completed):
    b={'run_id':completed['id'],'offset':0,'limit':10}
    assert client.post('/api/strategy-batches',headers=A,json=b).status_code==403
    assert client.post('/api/strategy-batches',headers=O,json=b).status_code==403
    r=client.post('/api/strategy-batches',headers=F,json=b).json();v=r['receipt']
    assert v['evaluated_pairs']==830 and v['gate_counts']=={'NEEDS_LEGAL_UNIT_EVIDENCE':20,'RESEARCH_DEFERRED':810}
    assert v['next_offset']==10 and v['offer_ready']==0 and v['executor']=='CPU_RULE_REFERENCE'
    assert client.post('/api/strategy-batches',headers=F,json=b).json()=={'receipt':v,'replay':True}
    assert client.get('/api/strategy-batches/'+v['id'],headers=A).json()['catalog_current']
    with conn() as db:
        with pytest.raises(sqlite3.IntegrityError):db.execute('DELETE FROM strategy_batch_receipts WHERE id=?',(v['id'],))

def test_batch_bounds_and_stale(completed,monkeypatch):
    b={'run_id':completed['id'],'offset':6960,'limit':10}
    r=client.post('/api/strategy-batches',headers=F,json=b).json()['receipt'];assert len(r['records'])==5 and r['next_offset'] is None
    assert client.post('/api/strategy-batches',headers=F,json={**b,'offset':6965}).status_code==409
    assert client.post('/api/strategy-batches',headers=F,json={**b,'limit':1001}).status_code==422
    assert client.post('/api/strategy-batches',headers=F,json={**b,'run_id':start().json()['id']}).status_code==409
    c=strategy_cases.load_catalog();c['limits']=['changed'];monkeypatch.setattr(strategy_cases,'load_catalog',lambda:c)
    assert not client.get('/api/strategy-batches/'+r['id'],headers=A).json()['catalog_current']

def test_purchase_model(case_input):
    cid=client.post('/api/strategy-cases',headers=F,json=case_input).json()['receipt']['id']
    ops={'revenue_cents':6000000,'operating_cost_cents':2000000,'debt_service_cents':2400000,'reserve_contribution_cents':400000,'cash_capex_cents':500000}
    fid=client.post(f'/api/strategy-cases/{cid}/finance',headers=F,json={'as_of':'2026-11-23','operations':ops}).json()['receipt']['id']
    inputs={'price_cents':30000000,'loan_cents':20000000,'closing_cents':1000000,'initial_repair_cents':1000000,'initial_reserve_cents':500000,'cash_budget_cents':15000000,'min_yield_bps':500}
    url=f'/api/strategy-cases/{cid}/purchase';b={'finance_id':fid,'inputs':inputs}
    r=client.post(url,headers=F,json=b).json()['receipt'];assert r['initial_cash_required_cents']==12500000 and r['conditional_price_ceiling_cents']==31500000
    assert r['annual_cash_cents']==700000 and r['downside_annual_cash_cents']==100000 and r['financial_authority_cents']==0
    assert client.post(url,headers=F,json=b).json()['replay']
    assert client.post(url,headers=A,json=b).status_code==403
    assert client.post(url,headers=F,json={**b,'inputs':{**inputs,'price_cents':100}}).status_code==409
    assert client.post(url,headers=F,json={**b,'inputs':{**inputs,'cash_budget_cents':None}}).json()['receipt']['conditional_price_ceiling_cents'] is None
