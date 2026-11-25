import csv
import hashlib
import pytest
from backend.core.nal_intake import probe_nal


def row(units='4'):
    r=['']*92
    for n,v in {1:'58',2:'000123',3:'R',4:'2026',5:'008',8:'250000',41:'8000',47:'2500',48:'1',49:units,51:'OWNER FIELD NOT EXPORTED'}.items():r[n-1]=v
    return r


def probe(tmp_path, rows):
    p=tmp_path/'nal.csv'
    with p.open('w', newline='', encoding='utf-8') as f:csv.writer(f).writerows(rows)
    return probe_nal(p,expected_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),encoding='utf-8',county='58',year=2026)


def test_reported_units_only(tmp_path):
    out=probe(tmp_path,[row('2'),row('3'),row('4'),row(''),row('0')])
    assert [r['reported_units'] for r in out['rows']]==[2,3,4,None,0]
    assert all(r['legal_units'] is None and r['parcel_id']=='000123' for r in out['rows'])
    assert 'OWNER FIELD' not in repr(out) and not out['production_accepted']


def test_reject_bad_sensitive_and_wrong_scope(tmp_path):
    a,b,c,d=row(),row(),row(),row('x')
    a[69]='1'; b[66]='123456789'; c[0]='57'
    out=probe(tmp_path,[a,b,c,d,['short'],row()])
    assert len(out['rows'])==1 and out['records_seen']==6
    assert [r['reason'] for r in out['rejected']]==['RESTRICTED_OR_UNEXPECTED_SENSITIVE_FIELD']*2+['SCOPE_OR_FILE_TYPE','INVALID_SELECTED_FIELD','FIELD_COUNT']
    assert '123456789' not in repr(out)


def test_digest_and_malformed_csv_fail_closed(tmp_path):
    p=tmp_path/'nal.csv';p.write_bytes(b'"unclosed')
    with pytest.raises(ValueError,match='digest mismatch'):probe_nal(p,expected_sha256='0'*64,encoding='utf-8',county='58',year=2026)
    with pytest.raises(ValueError,match='Malformed CSV'):probe_nal(p,expected_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),encoding='utf-8',county='58',year=2026)
