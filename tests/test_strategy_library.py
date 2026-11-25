import json
import pytest
from backend.core.strategy_cases import catalog_view
from backend.core.strategy_library import load_catalog,prepare_strategy,CATALOG

def test_all_source_strategies_and_work_packages():
    c=load_catalog()
    assert len(c['records'])==83 and len(c['work_packages'])==332 and len(c['flywheels'])==5
    assert all(r['source']['Status']=='Research' and r['source']['Legal Verification']=='Unverified' for r in c['records'])
    assert {r['source']['ID'] for r in c['records'] if r['activation']=='FIRST_PILOT_CANDIDATE'}=={'SMF-01','SMF-02'}

def test_packet_replay_has_no_authority():
    for s in ('SMF-01','SMF-02','SMF-67','SMF-83'):
        p=prepare_strategy(s,'SYNTHETIC-CASE-001')
        assert p==prepare_strategy(s,'SYNTHETIC-CASE-001')
        catalog = catalog_view()
        assert p['catalog_sha256'] == catalog['catalog_sha256']
        assert p['catalog_schema_version'] == catalog['catalog_schema_version']
        assert len(p['work_packages'])==4 and p['eligibility']=='UNKNOWN' and not p['dispatch_performed'] and not p['external_authority'] and not p['financial_authority']
    with pytest.raises(ValueError):prepare_strategy('SMF-999','case')
    with pytest.raises(ValueError):prepare_strategy('SMF-01','')

def test_source_tamper_rejected(tmp_path):
    data=json.loads(CATALOG.read_text(encoding="utf-8"))
    for name in data['source_hashes']:(tmp_path/name).write_bytes((CATALOG.parent/name).read_bytes())
    (tmp_path / 'workflow_extract.json').write_bytes((CATALOG.parent / 'workflow_extract.json').read_bytes())
    p=tmp_path/CATALOG.name;p.write_text(json.dumps(data))
    load_catalog(p)
    (tmp_path/next(iter(data['source_hashes']))).write_text('tampered')
    with pytest.raises(ValueError,match='revision'):load_catalog(p)

def test_catalog_source_row_tamper_rejected(tmp_path):
    data=json.loads(CATALOG.read_text(encoding="utf-8"))
    for name in data['source_hashes']:(tmp_path/name).write_bytes((CATALOG.parent/name).read_bytes())
    data['records'][0]['source']['Strategy']='Altered source thesis'
    (tmp_path / 'workflow_extract.json').write_bytes((CATALOG.parent / 'workflow_extract.json').read_bytes())
    p=tmp_path/CATALOG.name;p.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='source rows'):load_catalog(p)


@pytest.mark.parametrize('section,field,error', [
    ('flywheels', 'Sequence', 'flywheels mismatch'),
    ('work_packages', 'gate', 'assignments mismatch'),
])
def test_rejects_changes_to_workbook_derived_fields(tmp_path, section, field, error):
    data = json.loads(CATALOG.read_bytes())
    for name in data['source_hashes']:
        (tmp_path / name).write_bytes((CATALOG.parent / name).read_bytes())
    (tmp_path / 'workflow_extract.json').write_bytes((CATALOG.parent / 'workflow_extract.json').read_bytes())
    data[section][0][field] = 'Altered text'
    path = tmp_path / CATALOG.name
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match=error):
        load_catalog(path)


def test_catalog_rejects_substituted_sibling_workflow_extract(tmp_path):
    data = json.loads(CATALOG.read_bytes())
    for name in (*data['source_hashes'], 'workflow_extract.json'):
        (tmp_path / name).write_bytes((CATALOG.parent / name).read_bytes())
    path = tmp_path / CATALOG.name
    path.write_bytes(CATALOG.read_bytes())
    assert load_catalog(path) == data
    (tmp_path / 'workflow_extract.json').write_bytes(b'{}')
    with pytest.raises(ValueError, match='workflow extract revision mismatch'):
        load_catalog(path)
