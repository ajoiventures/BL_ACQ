"""Prepare a per-program planning coverage overlay, not a new ticket board.
All assignments require evidence; no site or investment conclusions are asserted.
"""
import argparse, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def prepare(queue, catalog, tickets):
    t={x['id']:x for x in tickets}; pillars=catalog['pillars']; ids=[p['id'] for p in pillars]
    if ids!=[f'UP-{i:02d}' for i in range(1,19)]:raise ValueError('invalid pillar catalog')
    for p in pillars:
        if p['primary_ticket'] not in t or any(x not in t for x in p['supporting_tickets']) or p['owner']!=t[p['primary_ticket']]['owner']:raise ValueError('invalid ticket routing')
    if len({r['program_key'] for r in queue['records']})!=len(queue['records']):raise ValueError('duplicate program key')
    results=[]
    for r in queue['records']:
        eligible=r['designation'] in {'Accredited','Affiliate'}
        results.append({'program_key':r['program_key'],'name':r['name'],'state':r['state'],'designation':r['designation'],'district_ids':r['district_ids'],'scope':'DISTRICT_RESEARCH' if eligible else 'IDENTITY_SCOPE_REVIEW_ONLY','pillar_reports':[{'pillar_id':p['id'],'primary_ticket':p['primary_ticket'],'owner':p['owner'],'review_owner':p['review_owner'],'status':'WAITING_FOR_EVIDENCE','required_evidence':p['required_evidence'],'output':p['output'],'study_revision':None,'accepted_findings':[]} for p in pillars] if eligible else [],'investment_authorized':False})
    return {'mode':'PLANNING_PREPARATION_ONLY','catalog_revision':catalog['catalog_revision'],'queue_sha256':hashlib.sha256(json.dumps(queue,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),'records':results,'program_count':len(results),'pillar_report_count':sum(len(x['pillar_reports']) for x in results),'accepted_pillar_reports':0,'dispatch_performed':False}
def main():
    a=argparse.ArgumentParser();a.add_argument('--queue',type=Path,required=True);a.add_argument('--output',type=Path,required=True);p=a.parse_args();load=lambda x:json.loads(x.read_text());r=prepare(load(p.queue),load(ROOT/'docs/cities-planning/urban-pillars.json'),load(ROOT/'docs/session-tickets.json'))
    with p.output.open('x') as f:json.dump(r,f,indent=2,ensure_ascii=False)
    print({k:v for k,v in r.items() if k!='records'})
if __name__=='__main__':main()
