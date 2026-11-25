"""Reproduce a synthetic site discovery / preliminary feasibility receipt."""
import json
import sqlite3
from backend.core import investment_paths, site_paths

def run():
    def f(i,topic,scope=(),state='OBSERVED'):
        return {'finding_id':i,'topic':topic,'state':state,'source_ref':'synthetic://'+i,'source_date':'2026-11-23','summary':'Illustrative assertion, not actual property evidence','strategy_ids':list(scope)}
    findings=[f('LOT','deep_lot_opportunity'),f('UPPER','underused_upper_floor'),f('LAYOUT','owner_occupancy_layout'),f('ACCESS','access_constraint',['SMF-07']),f('MARKET','market_support',['SMF-08']),f('COST','cost_support')]
    # A deliberately complete set of supplied assertions tests the difference between review readiness and approval.
    findings.extend(f('OWNER-'+factor,factor+'_support',['SMF-02']) for factor in site_paths.FACTORS)
    with sqlite3.connect(':memory:') as db:
        investment_paths.initialize(db)
        args={'site_id':'SYNTHETIC-PLACE','boundary_revision':'SYNTHETIC-V1','findings':findings}
        r=site_paths.discover(db,**args)
        assert site_paths.discover(db,**{**args,'findings':list(reversed(findings))})=={'receipt':r['receipt'],'replay':True}
        return {'data_class':'SYNTHETIC_ONLY','receipt':r['receipt'],'replay_verified':True}
if __name__=='__main__':
    print(json.dumps(run(),indent=2,ensure_ascii=False))
