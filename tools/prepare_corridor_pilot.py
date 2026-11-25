"""Read-only research preparation: source-bound district and attribute leads.

No spatial membership, legal use, market value, finance or external action is inferred.
"""
import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('OBJECTID','PARCEL','SITUS','SITUS_CITY','SITUS_ZIP','DOR_CODE')


def prepare(snapshot, boundary, *, snapshot_sha256, boundary_sha256):
    raw, boundary_raw = Path(snapshot).read_bytes(), Path(boundary).read_bytes()
    if hashlib.sha256(raw).hexdigest() != snapshot_sha256 or hashlib.sha256(boundary_raw).hexdigest() != boundary_sha256:
        raise ValueError('source digest mismatch')
    b = json.loads(boundary_raw)
    if b.get('type') != 'FeatureCollection' or len(b.get('features', [])) != 1:
        raise ValueError('expected one research district feature')
    feature = b['features'][0]
    if feature.get('geometry', {}).get('type') != 'MultiPolygon' or feature.get('properties', {}).get('study_id') != 'BR-CP-DISTRICT-2024-PILOT':
        raise ValueError('unexpected research district')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True)
    if tuple(reader.fieldnames or ()) != FIELDS:
        raise ValueError('unexpected source schema; owner/contact fields not allowed')
    groups = defaultdict(list); total = 0; seen_objects = set()
    for row in reader:
        if None in row or any(row.get(k) is None for k in FIELDS):
            raise ValueError('malformed row')
        if not re.fullmatch(r'[0-9]{15}', row['PARCEL']) or not re.fullmatch(r'[0-9]+', row['OBJECTID']):
            raise ValueError('invalid source identity')
        if row['OBJECTID'] in seen_objects:
            raise ValueError('duplicate observation identity')
        seen_objects.add(row['OBJECTID']); total += 1
        groups[row['PARCEL']].append(row)
    leads = []
    for pid, rows in sorted(groups.items()):
        # Text match only. Do not label a parcel inside or outside the official polygon.
        if not any(re.search(r'\bEDGEWATER\s+DR\b', r['SITUS'], re.I) and r['SITUS_CITY'].strip().casefold() == 'orlando' for r in rows):
            continue
        leads.append({'parcel_id':pid,'observation_ids':sorted(r['OBJECTID'] for r in rows),
                      'source_use_codes':sorted(set(r['DOR_CODE'] for r in rows)),
                      'source_situs_values':sorted(set(r['SITUS'] for r in rows)),
                      'source_locality_values':sorted(set(r['SITUS_CITY'] for r in rows)),
                      'identity_conflict':len({(r['SITUS'],r['SITUS_CITY'],r['DOR_CODE']) for r in rows}) > 1,
                      'district_membership':'UNKNOWN_NO_PARCEL_GEOMETRY',
                      'reported_units':None,'legal_units':None,'investment_path':None,'decision':'HOLD'})
    return {'mode':'RESEARCH_PREPARATION_ONLY','snapshot_sha256':snapshot_sha256,'boundary_sha256':boundary_sha256,
            'study_id':feature['properties']['study_id'],'snapshot_observations':total,'snapshot_distinct_parcels':len(groups),
            'street_text_leads':len(leads),'source_use_code_observation_counts':dict(sorted(Counter(r['DOR_CODE'] for x in leads for r in groups[x['parcel_id']]).items())),
            'verified_district_memberships':0,'verified_legal_unit_counts':0,'offer_ready':0,
            'limits':['Retained November 18 source selected use-code prefixes 03 and 08 only; no total corridor denominator.', 'Text filter is not a spatial join; district and accessibility membership remain unknown.', 'No private Main Street register used; public source extract only.', 'Boundary version/area reconciliation, geometry, legal units and financing remain outstanding.'],
            'leads':leads}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',type=Path,default=ROOT/'docs/orange-parcels.csv')
    p.add_argument('--boundary',type=Path,default=ROOT/'docs/acquisition/run/137L/college-park-boundary.geojson')
    p.add_argument('--snapshot-sha256',required=True);p.add_argument('--boundary-sha256',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=prepare(a.snapshot,a.boundary,snapshot_sha256=a.snapshot_sha256,boundary_sha256=a.boundary_sha256)
    with a.output.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2);f.write('\n')

if __name__=='__main__':main()
