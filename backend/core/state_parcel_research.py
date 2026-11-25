"""Bounded Orange County state-roll reconciliation. Research quarantine only.
No imported ownership/contact data, legal units, district acceptance or release authority.
"""
from collections import Counter
from hashlib import sha256
import json
import re
from pathlib import Path
from .acquisition_source_gate import route, Purpose

SOURCE = 'https://services9.arcgis.com/Gh9awoU677aKree0/ArcGIS/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query'
FIELDS = ('OBJECTID','CO_NO','PARCEL_ID','PARCELNO','ASMNT_YR','FILE_T','DOR_UC','JV','LND_SQFOOT','TOT_LVG_AR','NO_BULDNG','NO_RES_UNT','PHY_ADDR1')


def load_pinned(path, expected):
    with Path(path).open('rb') as f:
        raw = f.read(2*1024*1024+1)
    if len(raw)>2*1024*1024 or sha256(raw).hexdigest()!=expected:
        raise ValueError('artifact size or digest mismatch')
    return json.loads(raw)


def orange_id_candidate(value):
    """Observed Orange-only representation crosswalk; not a statewide rule."""
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]{15}',value):
        raise ValueError('invalid Orange identifier')
    return value[4:6]+value[2:4]+value[:2]+value[6:]


def norm_situs(s):
    return ' '.join(s.upper().split())


def reconcile_excerpt(excerpt, pilot, *, source_key='FDOR'):
    gate = route(source_key, Purpose.COMMERCIAL_RESEARCH)
    # The local diagnostic is not a released commercial dataset or training input.
    if source_key != 'FDOR' or gate['disposition'] != 'HOLD' or excerpt.get('source') != SOURCE:
        raise ValueError('source route not permitted for this quarantined diagnostic')
    if excerpt.get('fields') != list(FIELDS) or not isinstance(excerpt.get('rows'),list) or len(excerpt['rows'])>100:
        raise ValueError('unexpected fields or bounded batch limit')
    leads = pilot['leads']
    mapping = {orange_id_candidate(x['parcel_id']): x for x in leads}
    if len(mapping)!=len(leads): raise ValueError('duplicate candidate parcel')
    seen=set(); oids=set(); results=[]
    for values in excerpt['rows']:
        if not isinstance(values,list) or len(values)!=len(FIELDS): raise ValueError('field count')
        row=dict(zip(FIELDS,values))
        oid,pid=row['OBJECTID'],row['PARCEL_ID']
        if type(oid) is not int or oid<=0 or oid in oids or pid not in mapping or pid in seen or row['PARCELNO']!=pid:
            raise ValueError('unexpected or duplicate source identity')
        if row['CO_NO']!=58 or row['ASMNT_YR']!=2026 or row['FILE_T']!='R' or not isinstance(row['DOR_UC'],str) or not re.fullmatch(r'[0-9]{3,4}',row['DOR_UC']): raise ValueError('unexpected source scope')
        for field in ('JV','LND_SQFOOT','TOT_LVG_AR','NO_BULDNG','NO_RES_UNT'):
            n=row[field]
            if n is not None and (type(n) is not int or n<0): raise ValueError('invalid numeric field')
        lead=mapping[pid]
        matches={norm_situs(s) for s in lead['source_situs_values']}
        corroborated=not lead['identity_conflict'] and isinstance(row['PHY_ADDR1'],str) and norm_situs(row['PHY_ADDR1']) in matches and len(matches)==1
        seen.add(pid);oids.add(oid)
        units=row['NO_RES_UNT'] if corroborated else None
        results.append({'parcel_key':'12095:'+lead['parcel_id'],'state_parcel_id':pid,'state_object_id':oid,'identity_status':'CANDIDATE_CORROBORATED_BY_SITUS' if corroborated else 'HOLD_IDENTITY_CONFLICT','source_reported_units':row['NO_RES_UNT'],'reported_units_for_diagnostic':units,'reported_buildings':row['NO_BULDNG'],'reported_just_value':row['JV'],'reported_land_sqft':row['LND_SQFOOT'],'reported_living_area_sqft':row['TOT_LVG_AR'],'assessment_year':row['ASMNT_YR'],'state_use_code':row['DOR_UC'],'legal_units':None,'accepted_district_membership':None,'decision':'HOLD'})
    return {'mode':'QUARANTINED_RESEARCH_DIAGNOSTIC','source_gate':gate,'records':results,'requested_count':len(mapping),'returned_count':len(results),'missing_state_ids':sorted(set(mapping)-seen),'corroborated_count':sum(x['identity_status']=='CANDIDATE_CORROBORATED_BY_SITUS' for x in results),'reported_unit_counts':dict(Counter(str(x['reported_units_for_diagnostic']) for x in results)),'accepted_legal_units_count':0,'offer_ready':0,'released_to_production':False,'training_authorized':False}
