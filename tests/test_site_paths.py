from test_api import client,F,A,O
URL='/api/investment-paths/from-site'
BASE={'site_id':'SYNTHETIC-STUDY','boundary_revision':'synthetic-boundary-v1','findings':[]}
def finding(i,topic,state='OBSERVED'):
    return dict(finding_id=i,topic=topic,state=state,source_ref='synthetic://'+i,source_date='2026-11-23',summary='Synthetic finding for test only')
def test_no_site_finding_no_candidate_and_replay():
    for headers in (A,O):assert client.post(URL,headers=headers,json=BASE).status_code==403
    r=client.post(URL,headers=F,json=BASE);assert r.status_code==200,r.text
    v=r.json()['receipt'];assert len(v['catalog_dispositions'])==83 and not v['candidate_paths'] and v['no_acquisition_alternative']
    assert client.post(URL,headers=F,json=BASE).json()=={'receipt':v,'replay':True}
def test_site_findings_drive_distinct_paths_and_conflict():
    a=finding('A','deep_lot_opportunity'); b=finding('B','underused_upper_floor'); c=finding('C','utility_constraint');
    body={**BASE,'findings':[a,b,c]};r=client.post(URL,headers=F,json=body).json()['receipt'];assert {x['strategy_id'] for x in r['candidate_paths']}=={'SMF-07','SMF-08'}
    assert all(x['constraint_finding_ids']==['C'] and len(x['work_package_ids'])==4 and set(x['decision_gates'].values())=={'UNKNOWN'} for x in r['candidate_paths'])
    assert client.post(URL,headers=F,json={**body,'findings':[c,b,a]}).json()=={'receipt':r,'replay':True}
    q=client.post(URL,headers=F,json={**body,'findings':[a,b,c,finding('D','deep_lot_opportunity','CONTRARY')]}).json()['receipt'];assert [x['strategy_id'] for x in q['candidate_paths']]==['SMF-08']
    assert next(x for x in q['catalog_dispositions'] if x['strategy_id']=='SMF-07')['status']=='CONFLICT_RESEARCH'
    assert client.post(URL,headers=F,json={**body,'findings':[a,a]}).status_code==409

def test_processed_parcel_binding_and_method_reference():
    import json
    from pathlib import Path
    from test_acquisition_runs import start,step
    run=start(size=10).json();run=step(run).json()
    parcel=client.get('/api/acquisition-runs/'+run['id']+'/properties',headers=F).json()['items'][0]['parcel_key']
    body={**BASE,'site_id':parcel,'run_id':run['id'],'parcel_key':parcel,'findings':[finding('A','existing_fourplex')]}
    out=client.post(URL,headers=F,json=body);assert out.status_code==200,out.text
    r=out.json()['receipt'];assert r['context']['parcel_key']==parcel and r['context']['record_sha256']
    assert r['financial_authority_cents']==0 and r['method_application_status']=='REFERENCE_ONLY_NOT_ASSESSED'
    ids={x['id'] for x in json.loads((Path(__file__).parents[1]/'site_academy/skills.json').read_text())};assert set(r['method_reference_ids'])<=ids
    assert client.post(URL,headers=F,json={**body,'site_id':'OTHER'}).status_code==409
    assert client.post(URL,headers=F,json={**body,'findings':[finding('A','existing_fourplex','UNKNOWN')]}).json()['receipt']['candidate_paths']==[]

def test_program_scoped_multifactor_feasibility_and_graph():
    a=finding('A','deep_lot_opportunity'); b=finding('B','underused_upper_floor')
    c={**finding('C','access_constraint'),'strategy_ids':['SMF-07']}
    d={**finding('D','market_support'),'strategy_ids':['SMF-08']}
    e=finding('E','cost_support') # unscoped support is not program support
    body={**BASE,'findings':[a,b,c,d,e]}
    r=client.post(URL,headers=F,json=body).json()['receipt']; paths={p['strategy_id']:p for p in r['candidate_paths']}
    assert paths['SMF-07']['preliminary_feasibility']['disposition']=='HOLD_CONSTRAINT'
    assert paths['SMF-08']['preliminary_feasibility']['disposition']=='HOLD_MISSING_SUPPORT'
    assert paths['SMF-08']['constraint_finding_ids']==[]
    f={x['factor']:x['state'] for x in paths['SMF-08']['preliminary_feasibility']['factors']}
    assert f['market']=='SUPPORT_REPORTED_UNVERIFIED' and f['cost']=='UNKNOWN' and f['access']=='UNKNOWN'
    g=r['transition_graph'];assert not g['automatically_traversable'];assert len({n['id'] for n in g['nodes']})==len(g['nodes']);assert any(e['condition']=='HUMAN_ACCEPTED_PRELIMINARY_FEASIBILITY' for e in g['edges']);assert any(e['to']=='WAIT' for e in g['edges'])
    assert all(not p['preliminary_feasibility']['design_authorized'] for p in paths.values())
    assert client.post(URL,headers=F,json={**body,'findings':[a,{**c,'strategy_ids':['INVALID']}]}).status_code==409

def test_all_reported_support_not_approval_and_new_mappings():
    from backend.core.site_paths import FACTORS
    a=finding('A','owner_occupancy_layout'); b=finding('B','bedroom_layout_opportunity');c=finding('C','underused_service_space')
    support=[{**finding('S'+str(i),factor+'_support'),'strategy_ids':['SMF-02']} for i,factor in enumerate(FACTORS)]
    r=client.post(URL,headers=F,json={**BASE,'findings':[a,b,c,*support]}).json()['receipt'];p={p['strategy_id']:p for p in r['candidate_paths']}
    assert set(p)=={'SMF-02','SMF-13','SMF-14'}
    assert p['SMF-02']['preliminary_feasibility']['disposition']=='REVIEW_REQUIRED'
    assert not p['SMF-02']['preliminary_feasibility']['design_authorized'] and not p['SMF-02']['preliminary_feasibility']['transaction_authorized']
    assert all(v=='UNKNOWN' for v in p['SMF-02']['decision_gates'].values())
    contrary={**finding('X','market_support','CONTRARY'),'strategy_ids':['SMF-02']}
    r=client.post(URL,headers=F,json={**BASE,'findings':[a,*support,contrary]}).json()['receipt']
    assert r['candidate_paths'][0]['preliminary_feasibility']['disposition']=='HOLD_CONFLICT'
