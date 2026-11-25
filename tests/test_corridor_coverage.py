import json
from pathlib import Path
import pytest
pytest.importorskip('shapely');pytest.importorskip('pyproj')
from tools.prepare_corridor_coverage import reconcile,sha
R=Path(__file__).resolve().parents[1]/'docs/acquisition/run';C=R/'138H/candidate-ids.json';B=R/'137L/college-park-boundary.geojson';P=R/'138H/sample.geojson';M=R/'138H/batch-manifest.json'
def call(c=C,batches=None):
    return reconcile(c,B,[(P,M,sha(M))] if batches is None else batches,candidate_sha=sha(c),boundary_sha=sha(B))
def test_real_reconciliation():
    r,g=call();assert r['candidate_count']==937 and r['captured_count']==7 and r['remaining_count']==930
    assert len(g['features'])==7 and sum(r['provisional_relations'].values())==7
    assert sum(map(len,r['next_id_batches']))==930 and not r['capture_complete']
    assert r['accepted_membership_count'] is None and all(f['properties']['decision']=='HOLD' for f in g['features'])
def test_bad_candidate_count(tmp_path):
    j=json.loads(C.read_text());j['count']-=1;p=tmp_path/'bad.json';p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='inconsistent'):call(p)
def test_wrong_return_ids(tmp_path):
    j=json.loads(M.read_text());j['requested_ids']=j['requested_ids'][:-1];p=tmp_path/'bad.json';p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='coverage mismatch'):call(batches=[(P,p,sha(p))])
def test_repeated_batch():
    with pytest.raises(ValueError,match='repeated'):call(batches=[(P,M,sha(M)),(P,M,sha(M))])
def test_manifest_hash():
    with pytest.raises(ValueError,match='hash'):call(batches=[(P,M,'0'*64)])
def test_wrong_boundary_binding(tmp_path):
    j=json.loads(C.read_text());j['boundary_sha256']='0'*64;p=tmp_path/'bad.json';p.write_text(json.dumps(j))
    with pytest.raises(ValueError,match='boundary binding'):call(p)
