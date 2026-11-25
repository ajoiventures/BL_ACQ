"""Run a bounded API pilot on a fresh disposable DB. No external or financial actions."""
import argparse, json, os, tempfile, uuid
from pathlib import Path
from collections import Counter

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--receipts",type=Path);args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='br-strategy-pilot-') as tmp:
        os.environ['BR_DB']=str(Path(tmp)/'pilot.db')
        token=uuid.uuid4().hex;os.environ['BR_FOUNDER_TOKEN']=token
        os.environ['BR_AUDIT_TOKEN']=uuid.uuid4().hex;os.environ['BR_OPERATIONS_TOKEN']=uuid.uuid4().hex
        from backend.main import app,conn
        from fastapi.testclient import TestClient
        headers={'Authorization':'Bearer '+token}
        with TestClient(app) as client:
            def call(method,url,body=None):
                res=client.request(method,'/api/'+url,json=body,headers=headers);res.raise_for_status();return res.json()
            full=call('POST','acquisition-runs',{'request_id':'strategy-base','backend':'cpu_reference','batch_size':250})
            co=call('POST','acquisition-cohorts',{'run_id':full['id'],'city':'Orlando','use_code':'0304'})
            r=call('POST','acquisition-runs',{'request_id':'strategy-cohort','backend':'cpu_reference','batch_size':250,'cohort_id':co['id']})
            while r['state']!='COMPLETED':
                r=call('POST',f'acquisition-runs/{r["id"]}/step',{'version':r['version'],'action':'advance'})
                if r['state']=='FAILED':raise RuntimeError(r['error'])
            page=call('GET',f'acquisition-runs/{r["id"]}/properties?limit=3');parcel=page['items'][0]['parcel_key']
            catalog=call('GET','strategy-library');receipts=[]
            for s in catalog['records']:
                sid=s['source']['ID'];body={'run_id':r['id'],'parcel_key':parcel,'strategy_id':sid}
                a=call('POST','strategy-cases',body);b=call('POST','strategy-cases',body)
                assert not a['replay'] and b['replay'] and a['receipt']==b['receipt']
                assert len(a['receipt']['work_packages'])==4 and set(a['receipt']['decision_gates'].values())=={'UNKNOWN'}
                receipts.append(a['receipt'])
            pilot=receipts[0];ops={'revenue_cents':6000000,'operating_cost_cents':2000000,'debt_service_cents':2400000,'reserve_contribution_cents':400000,'cash_capex_cents':500000}
            fin=call('POST',f'strategy-cases/{pilot["id"]}/finance',{'as_of':'2026-11-23','operations':ops,'capital':{}})
            assert call('POST',f'strategy-cases/{pilot["id"]}/finance',{'as_of':'2026-11-23','operations':ops,'capital':{}})['replay']
            report=fin['receipt']['report']
            with conn() as db:
                count=db.execute('SELECT COUNT(*) FROM strategy_case_receipts').fetchone()[0]
                fcount=db.execute('SELECT COUNT(*) FROM strategy_financial_receipts').fetchone()[0]
            assert count==83 and fcount==1
            result={'status':'PASSED_LOCAL_REHEARSAL','source_catalog_sha256':catalog['catalog_sha256'],'source_snapshot_id':r['snapshot_id'],'cohort_id':co['id'],'cohort_records_processed':r['cursor'],'batches':len(r['batches']),'executor':r['actual_backend'],'parcel_cases_evaluated':1,'strategy_receipts':count,'work_package_instances':sum(len(s['work_packages']) for s in receipts),'replayed_strategy_requests':83,'unit_gate_counts':dict(Counter(s['unit_gate'] for s in receipts)),'offer_ready':0,'financial_receipts':fcount,'hypothetical_annual_noi_cents':report['operating_review']['noi_cents'],'hypothetical_annual_cash_cents':report['operating_review']['distributable_cash_cents'],'hypothetical_downside_cash_cents':report['scenarios'][0]['result']['distributable_cash_cents'],'all_external_authority':False,'independent_review':'PENDING','limits':['Retained data, not statewide inventory. Only one processed parcel used for all 83 strategy preparations. Not 83 approved investment choices.','Case-specific preparation, not autonomous specialist execution. Disposable database removed. Annual scenario is hypothetical. GPU, real accepted evidence, full model family coverage and browser acceptance pending.']}
            if args.receipts:
                with args.receipts.open("x",encoding="utf-8") as out:
                    json.dump({"scope":"DISPOSABLE_LOCAL_REHEARSAL","run":r,"strategy_receipts":receipts,"financial_receipt":fin["receipt"]},out,ensure_ascii=False,indent=2)
            print(json.dumps(result,indent=2))
if __name__=='__main__':main()
