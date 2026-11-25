"""Reproduce the 138T research-only planning and transport packet."""
import json, hashlib
from pathlib import Path
from backend.core.transportation import assess_phase
from backend.core.transportation_funding import reconcile_funding


def build(path):
    raw=path.read_bytes(); data=json.loads(raw)
    source_ids={s['id'] for s in data['sources']}
    if len(source_ids)!=len(data['sources']): raise ValueError('duplicate source')
    if any(x['source_id'] not in source_ids for x in data['funding']+data['phases']): raise ValueError('unlinked observation')
    return {'source_sha256':hashlib.sha256(raw).hexdigest(),'mode':data['mode'],
            'funding':reconcile_funding(data['funding']), 'phases':[assess_phase(**p) for p in data['phases']],
            'parcel_entitlement':'UNKNOWN','network_promotion':False,'unverified':data['unverified']}

if __name__=='__main__':
    folder=Path('docs/acquisition/run/138T')
    (folder/'receipt.json').write_text(json.dumps(build(folder/'observations.json'),indent=2)+'\n')
