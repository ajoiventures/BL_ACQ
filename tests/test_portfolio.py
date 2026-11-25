import pytest
from backend.core.portfolio import optimize,debt_schedule
from backend.core.financing import evaluate
from test_financing import BASE
from test_api import client,F,A,O
from test_acquisition_runs import start,step

ASSUMPTIONS=dict(initial_cash_cents=15000000,liquidity_floor_cents=2000000,max_managed_units=8,existing_managed_units=0,horizon_years=3,stress_revenue_bps=1000,stress_opex_bps=1000,stress_extra_capex_per_unit_cents=0)

def option(fid,parcel,year,inputs=BASE):
    return dict(finance_id=fid,parcel_key=parcel,year=year,inputs=inputs,best=evaluate(inputs,'SMF-01')['best'])

def test_common_shocks_capacity_and_no_duplicate():
    o=[option('a','1',1),option('a','1',2),option('b','2',3)]
    r=optimize(o,**ASSUMPTIONS);assert r['evaluated_subsets']==8 and r['first_failure_counts']['DUPLICATE_PROPERTY']
    assert len({x['parcel_key'] for x in r['best']['selected']})==len(r['best']['selected'])
    assert all(y['stress_ending_cash_cents']>=ASSUMPTIONS['liquidity_floor_cents'] for y in r['best']['years'])
    cap=optimize(o,**{**ASSUMPTIONS,'max_managed_units':4});assert cap['first_failure_counts']['MANAGEMENT_CAPACITY']>0
    assert max(y['managed_units'] for y in cap['best']['years'])<=4
    assert optimize(o,**{**ASSUMPTIONS,'initial_cash_cents':0})['best'] is None
    assert optimize(o,**{**ASSUMPTIONS,'stress_revenue_bps':10000})['best']['selected']==[]
    assert optimize(o,**{**ASSUMPTIONS,'existing_managed_units':8})['best']['selected']==[]

def test_debt_and_cash_recycling():
    assert debt_schedule(1200,100,0,3)==[1200,0,0]
    a={**BASE,'price_min_cents':20000000,'price_max_cents':20000000}
    o=[option('a','1',1,a),option('b','2',2,a)]
    r=optimize(o,**{**ASSUMPTIONS,'initial_cash_cents':19000000,'stress_opex_bps':0});best=r['best'];assert len(best['selected'])==2
    for y in best['years']:
        assert y['stress_post_purchase_cash_cents']+y['stress_operating_cash_cents']==y['stress_ending_cash_cents']
    with pytest.raises(ValueError):optimize([o[0],o[0]],**ASSUMPTIONS)
    with pytest.raises(ValueError):optimize(o,**{**ASSUMPTIONS,'horizon_years':1})
    assert optimize(o,**ASSUMPTIONS)==optimize(list(reversed(o)),**ASSUMPTIONS)

def test_api_portfolio_replay_and_rights():
    r=start(size=10).json();r=step(r).json();parcel=client.get('/api/acquisition-runs/'+r['id']+'/properties',headers=F).json()['items'][0]['parcel_key']
    c=client.post('/api/strategy-cases',headers=F,json={'run_id':r['id'],'parcel_key':parcel,'strategy_id':'SMF-01'}).json()['receipt']
    f=client.post('/api/strategy-cases/'+c['id']+'/financing-grid',headers=F,json={'inputs':BASE}).json()['receipt']
    url='/api/strategy-portfolio';body={'dated_options':[{'finance_id':f['id'],'year':1}],'assumptions':ASSUMPTIONS}
    assert client.post(url,headers=A,json=body).status_code==403
    assert client.post(url,headers=O,json=body).status_code==403
    res=client.post(url,headers=F,json=body);assert res.status_code==200,res.text
    out=res.json();assert not out['replay'] and out['receipt']['financial_authority_cents']==0
    again=client.post(url,headers=F,json=body).json();assert again['replay'] and again['receipt']==out['receipt']
    assert client.post(url,headers=F,json={**body,'dated_options':[{'finance_id':'0'*64,'year':1}]}).status_code==404
