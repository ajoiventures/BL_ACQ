"""Rehearse a complete bounded cohort strategy matrix on disposable local API database."""
import argparse,json,os,tempfile,uuid,time
from pathlib import Path
from collections import Counter

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipts',type=Path,required=True);a=p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        os.environ.update(BR_DB=str(Path(tmp)/'pilot.db'),BR_FOUNDER_TOKEN=uuid.uuid4().hex,BR_AUDIT_TOKEN=uuid.uuid4().hex,BR_OPERATIONS_TOKEN=uuid.uuid4().hex)
        from backend.main import app,conn
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            def call(method,url,body=None):
                r=client.request(method,'/api/'+url,json=body,headers={'Authorization':'Bearer '+os.environ['BR_FOUNDER_TOKEN']});r.raise_for_status();return r.json()
            base=call('POST','acquisition-runs',{'request_id':'base','backend':'cpu_reference','batch_size':250})
            co=call('POST','acquisition-cohorts',{'run_id':base['id'],'city':'Orlando','use_code':'0304'})
            r=call('POST','acquisition-runs',{'request_id':'cohort','backend':'cpu_reference','batch_size':250,'cohort_id':co['id']})
            while r['state']!='COMPLETED':
                r=call('POST',f'acquisition-runs/{r["id"]}/step',{'version':r['version'],'action':'advance'})
                if r['state']=='FAILED':raise RuntimeError(r['error'])
            offset=0;receipts=[];seen=set();counts=Counter();pairs=0;t=time.perf_counter()
            while offset is not None:
                body={'run_id':r['id'],'offset':offset,'limit':250};x=call('POST','strategy-batches',body);v=x['receipt'];assert not x['replay']
                assert call('POST','strategy-batches',body)=={'receipt':v,'replay':True}
                keys={row['parcel_key'] for row in v['records']};assert not seen&keys;seen.update(keys);counts.update(v['gate_counts']);pairs+=v['evaluated_pairs'];receipts.append(v);offset=v['next_offset']
            elapsed=time.perf_counter()-t
            assert len(seen)==1697 and pairs==len(seen)*83 and sum(counts.values())==pairs
            cid=call('POST','strategy-cases',{'run_id':r['id'],'parcel_key':receipts[0]['records'][0]['parcel_key'],'strategy_id':'SMF-01'})['receipt']['id']
            fin=call('POST',f'strategy-cases/{cid}/finance',{'as_of':'2026-11-23','operations':{'revenue_cents':6000000,'operating_cost_cents':2000000,'debt_service_cents':2400000,'reserve_contribution_cents':400000,'cash_capex_cents':500000}})['receipt']
            body={'finance_id':fin['id'],'inputs':{'price_cents':30000000,'loan_cents':20000000,'closing_cents':1000000,'initial_repair_cents':1000000,'initial_reserve_cents':500000,'cash_budget_cents':15000000,'min_yield_bps':500}}
            purchase=call('POST',f'strategy-cases/{cid}/purchase',body)['receipt'];assert purchase['conditional_price_ceiling_cents']==31500000
            assert call('POST',f'strategy-cases/{cid}/purchase',body)['replay']
            result={'scope':'DISPOSABLE_LOCAL_CPU_GATE_MATRIX','parcel_count':len(seen),'strategy_count':83,'gate_pairs':pairs,'gate_counts':dict(counts),'batches':len(receipts),'replayed_batches':len(receipts),'elapsed_seconds_including_replay':elapsed,'offer_ready':0,'gpu_records':0,'purchase_example':purchase,'batch_receipts':receipts}
            with a.receipts.open('x') as f:json.dump(result,f,indent=2)
            print(json.dumps({k:v for k,v in result.items() if k not in ('batch_receipts','purchase_example')},indent=2))
if __name__=='__main__':main()
