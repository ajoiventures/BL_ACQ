"""Reproduce the synthetic portfolio pilot. No real parcel or financing data."""
import json
from pathlib import Path
from backend.core.financing import evaluate
from backend.core.portfolio import optimize
ROOT=Path(__file__).resolve().parents[1]
def main():
    a=json.loads((ROOT/'docs/acquisition/strategy-library/financing-pilot-137D.json').read_text())['scenarios'][1]['inputs']
    options=[]
    for name,price,revenue,years in [('A',20000000,5200000,[1,2]),('B',25000000,6000000,[2,3]),('C',26000000,5900000,[3])]:
        inputs={**a,'price_min_cents':price,'price_max_cents':price,'annual_revenue_cents':revenue}
        result=evaluate(inputs,'SMF-01');assert result['best']
        for year in years:options.append({'finance_id':'SYNTHETIC-'+name,'parcel_key':'SYNTHETIC-'+name,'year':year,'inputs':inputs,'best':result['best']})
    assumptions=dict(initial_cash_cents=16000000,liquidity_floor_cents=2000000,max_managed_units=12,existing_managed_units=0,horizon_years=5,stress_revenue_bps=1000,stress_opex_bps=1000,stress_extra_capex_per_unit_cents=0)
    scenarios=[]
    for label,overrides in [('base-stress',{}),('severe-common-shock',{'stress_revenue_bps':2000,'stress_opex_bps':2000,'stress_extra_capex_per_unit_cents':50000}),('management-capacity',{'max_managed_units':4}),('higher-liquidity-floor',{'liquidity_floor_cents':5000000})]:
        v={**assumptions,**overrides};scenarios.append({'label':label,'assumptions':v,'result':optimize(options,**v)})
    print(json.dumps({'scope':'SYNTHETIC_HYPOTHETICAL_ONLY','options':options,'scenarios':scenarios},indent=2))
if __name__=='__main__':main()
