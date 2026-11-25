"""Synthetic bounded path comparison using 137E inputs and 137F recycling assumptions."""
import json
from pathlib import Path
from backend.core.investment_paths import schedule
from tools.run_recycling_pilot import ASSUMPTIONS
ROOT=Path(__file__).resolve().parents[1]

def main():
    rows=json.loads((ROOT/'docs/acquisition/strategy-library/portfolio-pilot-137E.json').read_text())['options']
    chosen=[next(r for r in rows if r['parcel_key']=='SYNTHETIC-A' and r['year']==1),next(r for r in rows if r['parcel_key']=='SYNTHETIC-B' and r['year']==3)]
    opts=[{**r,'assumptions':{**ASSUMPTIONS,'action_year':2,'initial_market_value_cents':r['best']['price_cents']}} for r in chosen]
    scenarios=[]
    for label,rv,op in [('moderate',1000,1000),('severe',2500,2000)]:
        a=dict(initial_cash_cents=16000000,liquidity_floor_cents=2000000,max_managed_units=8,horizon_years=10,stress_revenue_bps=rv,stress_opex_bps=op)
        scenarios.append({'label':label,'assumptions':a,'result':schedule(opts,**a)})
    print(json.dumps({'scope':'SYNTHETIC_HYPOTHETICAL_ONLY','options':opts,'scenarios':scenarios},indent=2))
if __name__=='__main__':main()
