import hashlib
import sqlite3
from pathlib import Path
import pytest
from backend.core.federal_housing import import_state_excerpt,value_state_po,compare_reported_growth

DATA=Path('docs/acquisition/run/138N/fl-po-state-excerpt.tsv').read_bytes()
def load(db, data=DATA, day='2026-11-24'):
    return import_state_excerpt(db,data,expected_sha256=hashlib.sha256(data).hexdigest(),observed_on=day)
def calc(db,s,**kw):
    args=dict(snapshot_id=s,state='FL',start=(2021,2),end=(2026,2),purchase_price=300000,as_of='2026-11-24'); args.update(kw)
    return value_state_po(db,**args)

def test_real_excerpt_and_replay():
    db=sqlite3.connect(':memory:'); r=load(db)
    assert r['rows']==26 and load(db)['replay']
    result=calc(db,r['snapshot_id'])
    assert result['hpi_start']=='401.34' and result['hpi_end']=='552.02'
    assert result['index_implied_value']=='412632.68'  # independently computed below
    assert result['appraisal'] is False and result['valuation_band'] is None

def test_revision_retention_and_cutoff():
    db=sqlite3.connect(':memory:'); a=load(db)['snapshot_id']; b=load(db,DATA.replace(b'552.02',b'550.00'))['snapshot_id']
    assert a!=b and calc(db,a)['hpi_end']=='552.02' and calc(db,b)['hpi_end']=='550.00'
    with pytest.raises(ValueError,match='look-ahead'): calc(db,a,as_of='2026-11-23')

def test_reject_bad_input_no_loss():
    db=sqlite3.connect(':memory:'); a=load(db)['snapshot_id']
    for invalid in (DATA+DATA.splitlines(keepends=True)[1],DATA.replace(b'552.02',b'NaN'),DATA.replace(b'indx_nsa',b'unknown')):
        with pytest.raises(ValueError): load(db,invalid)
    with pytest.raises(ValueError,match='hash'): import_state_excerpt(db,DATA,expected_sha256='0'*64,observed_on='2026-11-24')
    assert db.execute('SELECT count(*) FROM br_hpi_snapshot').fetchone()[0]==1
    for change in ({'start':(2027,1)},{'purchase_price':float('inf')},{'start':(2021,5)}):
        with pytest.raises(ValueError): calc(db,a,**change)
    with pytest.raises(LookupError): calc(db,a,start=(2010,1))
    assert calc(db,a,start=(2026,2))['cagr_pct'] is None

def test_historical_paper_gap():
    assert compare_reported_growth('121.0','115.7')=='5.3'
    assert compare_reported_growth('77.0','66.2')=='10.8'


def test_geography_match_and_fail_closed():
    import json
    from backend.core.federal_housing import resolve_census_point
    data=json.loads(Path('docs/acquisition/run/138N/census-point-excerpt.json').read_text())
    def resolve(d): return resolve_census_point(d,longitude=-81.3792,latitude=28.5383)
    got=resolve(data)
    assert (got['county_fips'],got['tract_fips'],got['hud_entity'])==('12095','12095018902',None)
    assert resolve({})['status']=='UNKNOWN'
    data['result']['geographies']['Census Tracts'].append({'GEOID':'12095018903'})
    assert resolve(data)['status']=='AMBIGUOUS_OR_CONFLICT'
    assert resolve(data)['tract_fips'] is None
    data['result']['input']['location']['x']=0
    assert resolve(data)['status']=='UNKNOWN'


def test_retained_census_response_binds_hash_and_cutoff():
    import json

    from backend.core.federal_housing import resolve_retained_census_point

    data = Path("docs/acquisition/run/138N/census-point-excerpt.json").read_bytes()
    receipt = json.loads(Path("docs/acquisition/run/138N/pilot-receipt.json").read_bytes())
    source = next(row for row in receipt["sources"] if row["artifact"] == "census-point-excerpt.json")
    payload = dict(expected_sha256=source["sha256"], observed_on=source["observed_on"],
                   as_of="2026-11-24", longitude=-81.3792, latitude=28.5383)
    result = resolve_retained_census_point(data, **payload)
    assert result["tract_fips"] == "12095018902"
    assert result["pha"] is None and result["cbsa"] is None
    assert result["artifact_sha256"] == payload["expected_sha256"]
    historical = resolve_retained_census_point(data, **{**payload, "as_of": "2026-11-23"})
    assert historical["hold_reason"] == "SOURCE_UNAVAILABLE_AT_CUTOFF"
    assert historical["county_candidates"] == [] and historical["tract_candidates"] == []
    with pytest.raises(ValueError, match="digest mismatch"):
        resolve_retained_census_point(data + b" ", **payload)


def test_adjustments_are_explicit_and_never_mix_endpoints():
    import math

    with sqlite3.connect(":memory:") as db:
        snapshot = load(db)["snapshot_id"]
        for mode, start, end in (("NSA", "401.34", "552.02"), ("SA", "398.23", "547.45")):
            result = calc(db, snapshot, adjustment=mode)
            assert (result["adjustment"], result["hpi_start"], result["hpi_end"]) == (mode, start, end)
            expected = (math.pow(float(end) / float(start), 1 / 5) - 1) * 100
            assert float(result["cagr_pct"]) == pytest.approx(expected, abs=0.00005)
            assert calc(db, snapshot, adjustment=mode, end=(2021, 2))["cagr_pct"] is None
        with pytest.raises(ValueError, match="Unknown HPI adjustment"):
            calc(db, snapshot, adjustment="AUTO")
