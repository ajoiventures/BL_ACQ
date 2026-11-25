"""Run bounded actual snapshot reconciliation and synthetic numeric load tests."""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, re, time, platform, sys
from pathlib import Path
import numpy as np

try:
    import resource
except ImportError:
    resource = None
from backend.core.acquisition_batch import FIELDS, MAX_BATCH, VERSION, screen, summarize, BackendUnavailable
ROOT=Path(__file__).resolve().parents[1]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def reconcile():
    orange=ROOT/'docs/orange-parcels.csv'; cp=ROOT/'docs/acquisition/college-park-parcel-spine.csv'
    groups=collections.defaultdict(list); features=set()
    with orange.open(newline='') as f:
        for row in csv.DictReader(f):
            if not re.fullmatch(r'\d{15}',row['PARCEL']) or row['OBJECTID'] in features:
                raise ValueError('invalid parcel or duplicate feature ID')
            features.add(row['OBJECTID']); groups['12095:'+row['PARCEL']].append(row)
    with cp.open(newline='') as f: cprows=list(csv.DictReader(f))
    if any(not re.fullmatch(r'\d{15}',r['parcel_id']) for r in cprows): raise ValueError('invalid corridor parcel ID')
    cpid={'12095:'+r['parcel_id'] for r in cprows}
    overlap=sorted(cpid & groups.keys())
    # Both retained snapshots are screening sources, not legal evidence or complete parcel universe.
    records=[{'parcel_key':k,'source_feature_ids':sorted(r['OBJECTID'] for r in v),
              'source_use_codes':sorted({r['DOR_CODE'] for r in v}),
              'source_observations':[{'feature_id':r['OBJECTID'],'situs':r['SITUS'],'city':r['SITUS_CITY'],'zip':r['SITUS_ZIP'],'use_code':r['DOR_CODE']} for r in sorted(v,key=lambda x:x['OBJECTID'])],
              'college_park_spine_match':k in cpid,'reported_units':None,'legal_units':None,
              'status':'HOLD','reason':'No accepted legal unit count or financial evidence'} for k,v in sorted(groups.items())]
    totals={'feature_rows':len(features),'distinct_parcels':len(groups),'extra_geometry_observations':len(features)-len(groups),
            'corridor_spine_rows':len(cprows),'corridor_spine_distinct':len(cpid),'exact_parcel_overlap':len(overlap),
            'overlap_keys':overlap,'legal_unit_count_unknown':len(groups), 'code_prefix_counts':dict(collections.Counter(r['DOR_CODE'][:2] for v in groups.values() for r in v)),
            'sources':[{'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in (orange,cp)],
            'limitations':['Retained November 18 Orange County 03/08 extract, not live or statewide.','Exact ID join only; no district boundary, route or title inference.','Parcel counts are not confirmed property or building counts.']}
    return records,totals

def synthetic_batch(start,n,all_eligible=False):
    idx=np.arange(start,start+n,dtype=np.int64)
    # 6 repeating cases: duplex/triplex/fourplex, unverified, conflicting, and excluded.
    case=idx%(3 if all_eligible else 6)
    r=np.choose(case,[2,3,4,2,4,5]).astype(np.int64)
    l=np.choose(case,[2,3,4,-1,2,5]).astype(np.int64)
    inc=np.choose(case,[3600000,4800000,6000000,-1,4200000,6000000]).astype(np.int64)
    op=np.full(n,1800000,dtype=np.int64); debt=np.full(n,2000000,dtype=np.int64)
    reserve=np.where(case==0,-1,300000).astype(np.int64)
    return dict(zip(FIELDS,(r,l,inc,op,debt,reserve)))

def benchmark(n, batch, name, all_eligible=False):
    if n<1 or not 1<=batch<=MAX_BATCH: raise ValueError('invalid size')
    t=time.perf_counter(); counts=collections.Counter(); hash_=hashlib.sha256(); receipts=[]
    for start in range(0,n,batch):
        arrays=synthetic_batch(start,min(batch,n-start),all_eligible); out, timing=screen(arrays,name)
        s=summarize(out); counts.update(s)
        # Per batch result fingerprint with explicit index range, not a real property dataset.
        input_h=hashlib.sha256()
        for k in FIELDS: input_h.update(k.encode()); input_h.update(arrays[k].tobytes())
        h=hashlib.sha256()
        for k in sorted(out): h.update(k.encode()); h.update(out[k].tobytes())
        hash_.update(h.digest()); receipts.append({'start':start,'end_exclusive':start+len(arrays['legal_units']), 'input_sha256':input_h.hexdigest(),'result_sha256':h.hexdigest(), 'counts':s,**timing})
    assert sum(counts[k] for k in ('eligible','unknown','excluded'))==n
    elapsed=time.perf_counter()-t
    return {'version':VERSION,'runtime':{'python':sys.version.split()[0],'numpy':np.__version__,'platform':platform.platform(),'machine':platform.machine()},'synthetic':True,'synthetic_case_mix':'all_eligible_2_4' if all_eligible else 'mixed','requested_backend':name,'actual_backend':name,'records':n,'max_batch':batch,'batches':len(receipts),'elapsed_s':elapsed,'records_per_s':n/elapsed,'process_peak_rss_kib':(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource is not None else None),'counts':dict(counts),'batch_result_sha256':hash_.hexdigest(),'receipts':receipts,'limitations':['Numeric classification and scenario worker only. No persistent real property ingestion, spatial workload, interface concurrency or crash recovery in this benchmark.','Legal count inputs are synthetic. No acquisition or offer authority.']}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--records',type=int,default=2_000_000);p.add_argument('--batch',type=int,default=100_000);p.add_argument('--backend',choices=['cpu_reference','cuda'],default='cpu_reference');p.add_argument('--all-eligible',action='store_true');a=p.parse_args()
    if a.records<1 or not 1<=a.batch<=MAX_BATCH: p.error('invalid record or batch size')
    a.output.mkdir(parents=True,exist_ok=False)
    records,totals=reconcile(); (a.output/'snapshot_reconciliation.json').write_text(json.dumps(totals,indent=2)+'\n')
    with (a.output/'parcel_screen.jsonl').open('x') as f:
        for row in records: f.write(json.dumps(row)+'\n')
    # Actual snapshot: missing legal and economic inputs stay unknown, no invented reported units.
    actual=collections.Counter()
    try:
        for start in range(0,len(records),a.batch):
            arr={k:np.full(min(a.batch,len(records)-start),-1,dtype=np.int64) for k in FIELDS}
            out,_=screen(arr,a.backend);actual.update(summarize(out))
        report=benchmark(a.records,a.batch,a.backend,a.all_eligible);report['actual_snapshot_screen_counts']=dict(actual)
    except BackendUnavailable as e:
        report={'requested_backend':a.backend,'actual_backend':None,'status':'BACKEND_UNAVAILABLE','error':str(e),'records_processed':0}
    (a.output/'batch_report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='receipts'},indent=2))
    return 2 if report.get('status')=='BACKEND_UNAVAILABLE' else 0
if __name__=='__main__':raise SystemExit(main())
