import pytest
from tools.prepare_national_atlas import prepare,digest
HEADER='program_key,name,city,state,designation\n'
def run(s,old=None):
    raw=s.encode();return prepare(raw,source_url='https://example.org/roster',observed_date='2026-11-23',source_sha256=digest(raw),previous_raw=old.encode() if old else None)
def test_scope_collision_and_growth():
    a=HEADER+'local:fl,College Park,Orlando,FL,Accredited\nlocal:ga,College Park,College Park,GA,Affiliate\n'
    b=HEADER+'local:fl,College Park,Orlando,FL,Affiliate\nlocal:tx,New Program,Austin,TX,Partner\n'
    r=run(b,a);assert r['changed_keys']==['local:fl'] and r['added_keys']==['local:tx'] and r['not_observed_keys']==['local:ga']
    assert not r['removal_inferred'] and not r['publisher_roster_complete'] and r['offer_ready']==0
    assert len(run(a)['records'])==2
    assert all(len(x['stages'])==(1 if x['designation']=='Partner' else 12) and x['district_ids']==[] for x in r['records'])
def test_duplicates_and_malformed():
    s=HEADER+'local:x,X,Y,FL,Accredited\n'
    with pytest.raises(ValueError):run(s+'local:x,X,Y,FL,Affiliate\n')
    with pytest.raises(ValueError):run(HEADER+'local:x,X,Y,XX,Accredited\n')
    with pytest.raises(ValueError):prepare(s.encode(),source_url='https://example.org',observed_date='2026-11-23',source_sha256='x')
def test_growing_roster_no_fixed_cap():
    s=HEADER+''.join(f'local:{i},Program {i},City,FL,Accredited\n' for i in range(1500)); r=run(s);assert len(r['records'])==1500 and sum(len(x['stages']) for x in r['records'])==18000
