"""Project retained source records. Reported units never establish legal units."""
import numpy as np
from .acquisition_batch import FIELDS
VERSION='br-property-features/1'

def project(records):
    arrays={k:np.full(len(records),-1,dtype=np.int64) for k in FIELDS}
    features=[]
    for idx,r in enumerate(records):
        obs=r.get('source_observations',[])
        codes=sorted({o['use_code'] for o in obs if o.get('use_code')})
        cities=sorted({o['city'].strip().casefold() for o in obs if o.get('city')})
        n=r.get('reported_units')
        if n is not None and (type(n) is not int or not 1<=n<=100000):raise ValueError('Invalid explicit reported unit count')
        if n is not None:arrays['reported_units'][idx]=n
        features.append({'parcel_key':r['parcel_key'],'reported_units':n,'source_use_codes':codes,'source_city_candidates':cities,'source_observation_count':len(obs),'source_conflict':len(codes)>1 or len(cities)>1,'corridor_spine_match':r.get('college_park_spine_match') is True,'missing_fields':[k for k in FIELDS if arrays[k][idx]==-1]})
    return arrays,features

def result_rows(features,out):
    return [{'parcel_key':f['parcel_key'],'screen':'HOLD','legal_units':None,'annual_cash_cents':None,'reason':'No accepted legal unit count or financial evidence','features':f,'numeric_screen':{'reported_2':bool(out['reported_2'][i]),'reported_3':bool(out['reported_3'][i]),'reported_4':bool(out['reported_4'][i]),'legal_count_unknown':bool(out['unknown'][i])},'feature_contract':VERSION} for i,f in enumerate(features)]
