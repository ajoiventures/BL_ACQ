import pytest
from backend.core.financing import evaluate, loan_year
from test_api import F,A,O,client
from test_acquisition_runs import start,step

BASE=dict(price_min_cents=20000000,price_max_cents=40000000,price_step_cents=100000,cash_budget_cents=10000000,ltv_bps=7500,loan_cap_cents=30000000,annual_rate_bps=600,term_months=360,closing_bps=300,fixed_closing_cents=0,initial_repair_cents=1000000,initial_reserve_cents=500000,annual_revenue_cents=6000000,annual_opex_cents=2000000,annual_reserves_cents=400000,annual_capex_cents=200000,revenue_stress_bps=1000,min_dscr_bps=12500,min_yield_bps=500,max_owner_outlay_cents=None,assumed_units=4)

def test_amortization_and_rounding():
    v=loan_year(20000000,600,360)
    assert v['monthly_payment_cents']==119911
    assert v['year_one_debt_service_cents']==v['year_one_interest_cents']+v['year_one_principal_cents']
    assert v['year_end_balance_cents']==20000000-v['year_one_principal_cents']
    assert loan_year(1200,0,12)['year_end_balance_cents']==0
    assert loan_year(0,600,360)['year_one_debt_service_cents']==0
    assert loan_year(1,0,12)['year_one_debt_service_cents']==1

def test_grid_constraints_missing_and_bounds():
    r=evaluate(BASE,'SMF-01');b=r['best'];assert r['evaluated_prices']==201 and b
    assert b['initial_cash_required_cents']<=BASE['cash_budget_cents']
    assert b['stress_dscr_bps']>=12500 and b['stress_cash_yield_bps']>=500
    assert evaluate({**BASE,'price_min_cents':b['price_cents']+100000},'SMF-01')['best'] is None
    assert evaluate({**BASE,'annual_revenue_cents':None},'SMF-01')['status']=='MISSING_ASSUMPTIONS'
    assert evaluate({**BASE,'cash_budget_cents':0},'SMF-01')['status']=='NO_GRID_MATCH'
    with pytest.raises(ValueError):evaluate({**BASE,'price_step_cents':1},'SMF-01')
    with pytest.raises(ValueError):evaluate({**BASE,'ltv_bps':10001},'SMF-01')
    with pytest.raises(ValueError):evaluate(BASE,'SMF-01',3)
    with pytest.raises(ValueError):evaluate(BASE,'SMF-04')
    with pytest.raises(ValueError):evaluate({**BASE,'term_months':11},'SMF-01')

def test_owner_constraints_are_separate():
    a={**BASE,'assumed_units':3,'annual_revenue_cents':3000000,'min_dscr_bps':None,'min_yield_bps':None,'max_owner_outlay_cents':1800000}
    r=evaluate(a,'SMF-02');assert r['best'] and r['best']['stress_owner_outlay_cents']<=1800000
    assert r['best']['stress_cash_yield_bps'] is None and r['best']['stress_dscr_bps'] is None
    with pytest.raises(ValueError):evaluate({**a,'min_yield_bps':500},'SMF-02')
    assert evaluate({**a,'max_owner_outlay_cents':None},'SMF-02')['status']=='MISSING_ASSUMPTIONS'

def test_api_financing_receipt_replay_and_permissions():
    r=start(size=10).json();r=step(r).json();p=client.get('/api/acquisition-runs/'+r['id']+'/properties',headers=F).json()['items'][0]['parcel_key']
    c=client.post('/api/strategy-cases',headers=F,json={'run_id':r['id'],'parcel_key':p,'strategy_id':'SMF-01'}).json()['receipt']
    url='/api/strategy-cases/'+c['id']+'/financing-grid'
    assert client.post(url,headers=A,json={'inputs':BASE}).status_code==403
    assert client.post(url,headers=O,json={'inputs':BASE}).status_code==403
    a=client.post(url,headers=F,json={'inputs':BASE});assert a.status_code==200,a.text
    out=a.json();assert not out['replay'] and out['receipt']['financial_authority_cents']==0
    assert set(out['receipt']['decision_gates'].values())=={'UNKNOWN'}
    b=client.post(url,headers=F,json={'inputs':BASE}).json();assert b['replay'] and b['receipt']==out['receipt']
