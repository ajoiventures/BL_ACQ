"""Bounded, hash-pinned WGS84 parcel/boundary intersection; research only."""
from pathlib import Path
import argparse, hashlib, json, re, math
from shapely.geometry import shape, mapping
from shapely.ops import transform
from shapely import force_2d
from pyproj import Transformer

FIELDS={'OBJECTID','PARCEL','DOR_CODE','ACREAGE','LIVING_AREA','TOTAL_MKT'}

def load(path,digest):
    raw=Path(path).read_bytes()
    if len(raw)>16*1024*1024 or hashlib.sha256(raw).hexdigest()!=digest: raise ValueError('source size/hash mismatch')
    j=json.loads(raw)
    if j.get('type')!='FeatureCollection' or not isinstance(j.get('features'),list) or 'crs' in j: raise ValueError('expected explicit WGS84 GeoJSON collection without CRS override')
    return j

def polygon(feature):
    if feature.get('type')!='Feature': raise ValueError('feature required')
    g=force_2d(shape(feature['geometry']))
    if g.geom_type not in ('Polygon','MultiPolygon') or not g.is_valid or g.is_empty: raise ValueError('invalid polygon')
    x,y,X,Y=g.bounds
    if not (-82<=x<=X<=-80 and 28<=y<=Y<=29): raise ValueError('outside bounded Orange County pilot envelope or wrong CRS')
    return g

def prepare(parcels,boundary,*,parcel_sha,boundary_sha):
    p,b=load(parcels,parcel_sha),load(boundary,boundary_sha)
    if len(b['features'])!=1 or b['features'][0]['properties'].get('study_id')!='BR-CP-DISTRICT-2024-PILOT': raise ValueError('unexpected boundary study')
    if len(p['features'])>1000: raise ValueError('bounded pilot only')
    project=Transformer.from_crs('EPSG:4326','EPSG:2236',always_xy=True).transform
    district=transform(project,polygon(b['features'][0]))
    result=[];seen=set()
    for f in p['features']:
        a=f['properties'];pid=a.get('PARCEL')
        if set(a)!=FIELDS or not isinstance(pid,str) or not re.fullmatch(r'\d{15}',pid) or pid in seen: raise ValueError('unexpected fields or duplicate/invalid parcel identity')
        seen.add(pid)
        if type(a['OBJECTID']) is not int or not isinstance(a['DOR_CODE'],str) or not re.fullmatch(r'\d{4}',a['DOR_CODE']): raise ValueError('invalid source attributes')
        for k in ('ACREAGE','LIVING_AREA','TOTAL_MKT'):
            if a[k] is not None and (type(a[k]) not in (int,float) or not math.isfinite(a[k]) or a[k]<0): raise ValueError('invalid numeric source attribute')
        g=polygon(f);pg=transform(project,g);overlap=pg.intersection(district).area
        if not pg.area>0: raise ValueError('zero parcel area')
        state='OVERLAP' if overlap>0 else ('TOUCH_ONLY' if pg.intersects(district) else 'DISJOINT')
        result.append({'type':'Feature','geometry':mapping(g),'properties':{'county_parcel_id':'FL-58:'+pid,**a,'calculated_area_sqft_us_survey':pg.area,'district_overlap_sqft_us_survey':overlap,'district_overlap_fraction':overlap/pg.area,'provisional_boundary_relation':state,'accepted_district_membership':None,'reported_units':None,'legal_units':None,'decision':'HOLD'}})
    return {'type':'FeatureCollection','features':result,'research_manifest':{'mode':'BOUNDED_RESEARCH_ONLY','input_crs':'EPSG:4326','measurement_crs':'EPSG:2236','parcel_sha256':parcel_sha,'boundary_sha256':boundary_sha,'boundary_status':'PROVISIONAL_UNRECONCILED','source_geometry_z_ignored':True,'coverage':'selected records only; not a district denominator','survey_or_entitlement':False}}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('parcels');p.add_argument('boundary');p.add_argument('--parcel-sha',required=True);p.add_argument('--boundary-sha',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    r=prepare(a.parcels,a.boundary,parcel_sha=a.parcel_sha,boundary_sha=a.boundary_sha)
    with open(a.output,'x') as f:json.dump(r,f,indent=2);f.write('\n')
if __name__=='__main__':main()
