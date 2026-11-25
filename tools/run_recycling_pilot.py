"""Reproduce synthetic capital recycling scenarios from the 137E pilot."""
import json
from pathlib import Path
from backend.core.recycling import simulate
ROOT=Path(__file__).resolve().parents[1]
ASSUMPTIONS=dict(horizon_years=10,action_year=5,initial_liquid_cash_cents=16000000,liquidity_floor_cents=2000000,initial_market_value_cents=20000000,annual_value_growth_bps=200,annual_revenue_growth_bps=200,annual_opex_growth_bps=300,stress_revenue_bps=1000,stress_opex_bps=1000,sale_cost_bps=600,sale_fixed_cost_cents=100000,sale_tax_provision_cents=2000000,refi_ltv_bps=7500,refi_cap_cents=30000000,refi_rate_bps=650,refi_term_months=360,refi_cost_bps=300,refi_fixed_cost_cents=100000,refi_min_dscr_bps=12500,renovation_cost_cents=2500000,renovation_annual_revenue_delta_cents=600000,renovation_annual_opex_delta_cents=100000,renovation_value_delta_cents=4000000)
def main():
    option=json.loads((ROOT/'docs/acquisition/strategy-library/portfolio-pilot-137E.json').read_text())['options'][0]
    scenarios=[]
    for label,delta in [('moderate',{}),('flat_value',{'annual_value_growth_bps':0}),('severe',{'stress_revenue_bps':2500,'stress_opex_bps':2000,'annual_value_growth_bps':-300})]:
        a={**ASSUMPTIONS,**delta};scenarios.append({'label':label,'assumptions':a,'alternatives':simulate(option['inputs'],option['best'],a)})
    print(json.dumps({'scope':'SYNTHETIC_HYPOTHETICAL_ONLY','option':option,'scenarios':scenarios},indent=2))
if __name__=='__main__':main()
