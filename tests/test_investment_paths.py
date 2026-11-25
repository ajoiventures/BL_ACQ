import pytest
from backend.core.investment_paths import schedule
from backend.core.financing import evaluate
from test_financing import BASE
from test_recycling import A0
from test_api import client,F,A,O
from test_acquisition_runs import start,step


def test_mandate_before_parcel_and_replay():
    url='/api/investment-paths/identify';body={'objective':'RECURRING_INCOME','horizon_years':10,'unit_counts':[2,3,4]}
    assert client.post(url,headers=A,json=body).status_code==403
    assert client.post(url,headers=O,json=body).status_code==403
    res=client.post(url,headers=F,json=body);assert res.status_code==200,res.text
    r=res.json()['receipt'];assert len(r['catalog_dispositions'])==83 and r['context'] is None and r['hypothetical_capital_cents'] is None
    assert {p['path_id'] for p in r['candidate_paths']}=={'SMF-01-'+x for x in ('HOLD','RENOVATE','REFINANCE','SELL')}|{'NO_ACQUISITION'}
    assert r['financial_authority_cents']==0
    assert client.post(url,headers=F,json=body).json()=={'receipt':r,'replay':True}
    h=client.post(url,headers=F,json={**body,'objective':'OWNER_HOUSING'}).json()['receipt'];assert {p['path_id'] for p in h['candidate_paths']}=={'SMF-02-HOLD','NO_ACQUISITION'}
    assert client.post(url,headers=F,json={**body,'unit_counts':[2,2]}).status_code==409
    run=start(size=10).json();run=step(run).json();parcel=client.get('/api/acquisition-runs/'+run['id']+'/properties',headers=F).json()['items'][0]['parcel_key']
    p=client.post(url,headers=F,json={**body,'run_id':run['id'],'parcel_key':parcel}).json()['receipt'];assert p['context']['parcel_key']==parcel
    assert p['candidate_paths'][0]['unit_gate']=='NEEDS_LEGAL_UNIT_EVIDENCE'


def option(parcel,year):return {'parcel_key':parcel,'finance_id':parcel,'year':year,'inputs':BASE,'best':evaluate(BASE,'SMF-01')['best'],'assumptions':{**A0,'action_year':2}}
P=dict(initial_cash_cents=16000000,liquidity_floor_cents=2000000,max_managed_units=8,horizon_years=10,stress_revenue_bps=1000,stress_opex_bps=1000)

def test_shared_ledger_and_frontier():
    opts=[option('A',1),option('B',4)];r=schedule(opts,**P);assert r['evaluated']<=25 and r['feasible']>0
    cash=P['initial_cash_cents'];seen=set()
    for row in r['best']['years']:
        cash=cash-row['acquisition_cash_cents']+row['operating_cash_cents']+row['transaction_out_cents']+row['transaction_in_cents'];assert cash==row['ending_cash_cents']>=P['liquidity_floor_cents'];assert row['owned_units']<=8
    for i,a in enumerate(r['pareto_frontier']):
        for j,b in enumerate(r['pareto_frontier']):
            if i!=j:assert not all(x>=y for x,y in zip(a['terminal_metrics'],b['terminal_metrics']))
    with pytest.raises(ValueError):schedule([opts[0],opts[0]],**P)
    r=schedule(opts,**{**P,'max_managed_units':0});assert r['best']['selected']==[] and r['best']['years'][-1]['ending_cash_cents']==P['initial_cash_cents']
    r=schedule(opts,**{**P,'initial_cash_cents':0});assert r['best'] is None


def test_compound_api():
    run=start(size=10).json();run=step(run).json();parcel=client.get('/api/acquisition-runs/'+run['id']+'/properties',headers=F).json()['items'][0]['parcel_key'];c=client.post('/api/strategy-cases',headers=F,json={'run_id':run['id'],'parcel_key':parcel,'strategy_id':'SMF-01'}).json()['receipt'];f=client.post('/api/strategy-cases/'+c['id']+'/financing-grid',headers=F,json={'inputs':BASE}).json()['receipt'];url='/api/investment-paths/compound';body={'dated_options':[{'finance_id':f['id'],'year':1,'recycling_assumptions':{**A0,'action_year':2}}],'assumptions':P}
    assert client.post(url,headers=A,json=body).status_code==403
    res=client.post(url,headers=F,json=body);assert res.status_code==200,res.text
    r=res.json()['receipt'];assert r['financial_authority_cents']==0 and r['result']['best']
    assert client.post(url,headers=F,json=body).json()=={'receipt':r,'replay':True}
