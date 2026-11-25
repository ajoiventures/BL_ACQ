"""Reconcile a bounded source-ID inventory against captured batches; never infer accepted membership."""
from pathlib import Path
import argparse, hashlib, json
from collections import Counter
from tools.prepare_spatial_evidence import prepare, load, polygon


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def checked_json(path,digest):
    raw=Path(path).read_bytes()
    if len(raw)>16*1024*1024 or hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('manifest hash/size mismatch')
    return json.loads(raw)


def reconcile(candidate, boundary, batches, *, candidate_sha, boundary_sha, chunk_size=50):
    inventory=checked_json(candidate,candidate_sha)
    b=load(boundary,boundary_sha)
    if inventory.get('boundary_sha256')!=boundary_sha or len(b['features'])!=1 or list(polygon(b['features'][0]).bounds)!=inventory.get('envelope_wgs84'):
        raise ValueError('candidate manifest boundary binding mismatch')
    ids=inventory['objectIds'];count=inventory['count']
    if type(count) is not int or not 0<=count<=10000 or not isinstance(ids,list) or any(type(i) is not int or i<=0 for i in ids) or len(set(ids))!=count or len(ids)!=count:
        raise ValueError('candidate count or IDs inconsistent')
    if type(chunk_size) is not int or not 1<=chunk_size<=100: raise ValueError('invalid chunk size')
    expected=set(ids);seen=set();parcel_ids=set();features=[];receipts=[]
    for path,manifest,manifest_sha in batches:
        m=checked_json(manifest,manifest_sha);requested=m['requested_ids']
        if not m.get('source','').startswith(inventory['source']+'?objectIds='): raise ValueError('batch source mismatch')
        if not isinstance(requested,list) or not requested or any(type(i) is not int for i in requested) or len(requested)>100 or len(set(requested))!=len(requested) or not set(requested)<=expected or seen.intersection(requested):
            raise ValueError('invalid or repeated requested IDs')
        raw=load(path,m['sha256']);got=[f['properties']['OBJECTID'] for f in raw['features']]
        if any(type(i) is not int for i in got) or len(got)!=len(set(got)) or set(got)!=set(requested): raise ValueError('batch ID coverage mismatch')
        result=prepare(path,boundary,parcel_sha=m['sha256'],boundary_sha=boundary_sha)
        for f in result['features']:
            pid=f['properties']['county_parcel_id']
            if pid in parcel_ids: raise ValueError('duplicate parcel across batches; reconcile before use')
            parcel_ids.add(pid);features.append(f)
        seen.update(got);receipts.append({'requested_ids':sorted(requested),'source':m['source'],'batch_sha256':m['sha256'],'manifest_sha256':manifest_sha})
    missing=sorted(expected-seen)
    relations=Counter(f['properties']['provisional_boundary_relation'] for f in features)
    report={'mode':'PROVISIONAL_RESEARCH_ONLY','candidate_sha256':candidate_sha,'boundary_sha256':boundary_sha,'candidate_scope':'envelope object IDs, not parcel or district count','candidate_count':count,'captured_object_ids':sorted(seen),'captured_count':len(seen),'remaining_count':len(missing),'next_id_batches':[missing[i:i+chunk_size] for i in range(0,len(missing),chunk_size)],'capture_complete':not missing,'source_snapshot_atomic':False,'provisional_relations':dict(relations),'accepted_membership_count':None,'legal_unit_count':None,'offer_ready_count':0,'batch_receipts':receipts,'limits':['Boundary definition unresolved. Even full envelope retrieval is not accepted district coverage.','Observed service count and ID list are separate responses; effective vintage unknown.','No legal-use, ownership, demand, value or finance inference.']}
    return report,{'type':'FeatureCollection','features':features,'research_manifest':report}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate');p.add_argument('boundary');p.add_argument('--candidate-sha',required=True);p.add_argument('--boundary-sha',required=True);p.add_argument('--batch',nargs=3,action='append',default=[],metavar=('GEOJSON','MANIFEST','MANIFEST_SHA'));p.add_argument('--output',required=True);p.add_argument('--geojson',required=True);a=p.parse_args()
    r,g=reconcile(a.candidate,a.boundary,a.batch,candidate_sha=a.candidate_sha,boundary_sha=a.boundary_sha)
    for name,obj in [(a.output,r),(a.geojson,g)]:
        with open(name,'x') as f: json.dump(obj,f,indent=2);f.write('\n')
if __name__=='__main__':main()
