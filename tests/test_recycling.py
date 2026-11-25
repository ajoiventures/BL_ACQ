import pytest
from backend.core.recycling import simulate,loan,advance,FIELDS
from backend.core.financing import evaluate
from test_financing import BASE
from test_api import client,F,A,O
from test_acquisition_runs import start,step

A0=dict(horizon_years=10,action_year=5,initial_liquid_cash_cents=16000000,liquidity_floor_cents=2000000,initial_market_value_cents=30000000,annual_value_growth_bps=200,annual_revenue_growth_bps=200,annual_opex_growth_bps=300,stress_revenue_bps=1000,stress_opex_bps=1000,sale_cost_bps=600,sale_fixed_cost_cents=100000,sale_tax_provision_cents=2000000,refi_ltv_bps=7500,refi_cap_cents=30000000,refi_rate_bps=650,refi_term_months=360,refi_cost_bps=300,refi_fixed_cost_cents=100000,refi_min_dscr_bps=12500,renovation_cost_cents=2500000,renovation_annual_revenue_delta_cents=600000,renovation_annual_opex_delta_cents=100000,renovation_value_delta_cents=4000000)

def models(**changes):
    return {r['strategy']:r for r in simulate(BASE,evaluate(BASE,'SMF-01')['best'],{**A0,**changes})}

def test_accounting_and_maturity():
    d=loan(1234,0,13);paid1,i=advance(d);paid2,j=advance(d);assert paid1+paid2==1234 and d[0]==0 and i+j==0
    x=models();assert set(x)=={'HOLD','RENOVATE','REFINANCE','SELL'}
    for r in x.values():
        for row in r['years']:
            assert row['operating_cash_cents']==row['operating_noi_cents']-row['debt_service_cents']-row['reserve_contribution_cents']-row['cash_capex_cents']
            assert row['ending_liquid_cash_cents']==row['starting_liquid_cash_cents']+row['operating_cash_cents']+row['transaction_cash_cents']
    sale=x['SELL']['years'][4];d=sale['action_details'];assert sale['transaction_cash_cents']==d['gross_sale_cents']-d['selling_cost_cents']-d['debt_payoff_cents']-d['assumed_tax_provision_cents']
    assert all(row['operating_cash_cents']==row['ending_debt_cents']==0 for row in x['SELL']['years'][5:])
    assert x['SELL']['terminal_unrealized_equity_cents']==0
    assert x['SELL']['years'][4]['segregated_reserves_cents']==x['SELL']['terminal_segregated_reserves_cents']
    ref=x['REFINANCE']['years'][4];d=ref['action_details'];assert d['executed_in_scenario'] and ref['transaction_cash_cents']==d['new_loan_cents']-d['old_payoff_cents']-d['fees_cents'] and ref['ending_debt_cents']==d['new_loan_cents']
    ren=x['RENOVATE']['years'][4];assert ren['operating_cash_cents']==x['HOLD']['years'][4]['operating_cash_cents'] and ren['transaction_cash_cents']==-A0['renovation_cost_cents']
    assert x['RENOVATE']['years'][5]['operating_cash_cents']>x['HOLD']['years'][5]['operating_cash_cents']

def test_fail_closed():
    assert models(refi_min_dscr_bps=100000)['REFINANCE']['status']=='CONDITIONAL_FAIL'
    assert models(initial_liquid_cash_cents=0)['SELL']['terminal_redeployment_ceiling_cents'] is None
    assert models(renovation_annual_revenue_delta_cents=-100000000)['RENOVATE']['status']=='CONDITIONAL_FAIL'
    with pytest.raises(ValueError):models(action_year=10)
    with pytest.raises(ValueError):models(stress_opex_bps=True)
    a=A0.copy();a.pop('sale_tax_provision_cents')
    with pytest.raises(ValueError):simulate(BASE,evaluate(BASE,'SMF-01')['best'],a)

def test_api_replay_rights():
    r=start(size=10).json();r=step(r).json();parcel=client.get('/api/acquisition-runs/'+r['id']+'/properties',headers=F).json()['items'][0]['parcel_key']
    c=client.post('/api/strategy-cases',headers=F,json={'run_id':r['id'],'parcel_key':parcel,'strategy_id':'SMF-01'}).json()['receipt']
    f=client.post('/api/strategy-cases/'+c['id']+'/financing-grid',headers=F,json={'inputs':BASE}).json()['receipt']
    url='/api/strategy-recycling';body={'finance_id':f['id'],'assumptions':A0}
    assert client.post(url,headers=A,json=body).status_code==403
    assert client.post(url,headers=O,json=body).status_code==403
    res=client.post(url,headers=F,json=body);assert res.status_code==200,res.text
    out=res.json();assert out['receipt']['financial_authority_cents']==0 and not out['replay']
    assert client.post(url,headers=F,json=body).json()=={'receipt':out['receipt'],'replay':True}
    assert client.post(url,headers=F,json={**body,'finance_id':'0'*64}).status_code==404
