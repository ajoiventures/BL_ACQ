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

def test_boundary_binding_and_atomic_validation(tmp_path):
    from copy import deepcopy
    from tools.prepare_national_atlas import attach_boundary_evidence

    queue = run(HEADER + 'local:fl,College Park,Orlando,FL,Accredited\n')
    original = deepcopy(queue)
    geometry = tmp_path / 'geometry.json'
    geometry.write_bytes(b'{}')
    evidence = {
        'program_key': 'local:fl',
        'name': 'College Park',
        'city': 'Orlando',
        'state': 'FL',
        'geometry_path': geometry.name,
        'geometry_sha256': digest(geometry.read_bytes()),
    }
    manifest = {
        'roster_sha256': queue['normalized_excerpt_sha256'],
        'verified_program_vectors': [evidence],
    }

    for bad_evidence, error in [
        ({**evidence, 'city': 'Ames'}, 'identity mismatch'),
        ({**evidence, 'geometry_sha256': digest(b'changed')}, 'geometry digest mismatch'),
        ({**evidence, 'geometry_path': '../outside.json'}, 'outside workspace'),
        (evidence, 'duplicate boundary program key'),
    ]:
        invalid = {**manifest, 'verified_program_vectors': [bad_evidence, evidence]}
        with pytest.raises(ValueError, match=error):
            attach_boundary_evidence(queue, invalid, workspace=tmp_path)
        assert queue == original

    with pytest.raises(ValueError, match='roster digest mismatch'):
        attach_boundary_evidence(queue, {**manifest, 'roster_sha256': 'wrong'}, workspace=tmp_path)
    assert queue == original
    attach_boundary_evidence(queue, manifest, workspace=tmp_path)

    assert queue['verified_publisher_program_vectors'] == 1
    assert queue['accepted_district_boundaries'] == queue['offer_ready'] == 0
    record, = queue['records']
    stage, = [s for s in record['stages'] if s['stage'] == 'boundary_and_jurisdiction']
    assert stage['program_boundary_evidence'] == evidence
    assert stage['status'] == 'WAITING_FOR_INPUTS'
    assert record['decision'] == 'HOLD'
