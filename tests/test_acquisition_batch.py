import numpy as np
import pytest
from backend.core.acquisition_batch import screen,summarize,BackendUnavailable,FIELDS
from tools.run_acquisition_batch import synthetic_batch,benchmark,reconcile

def test_six_case_partition_and_deficit():
    out,_=screen(synthetic_batch(0,6)); s=summarize(out)
    assert (s['eligible'],s['unknown'],s['excluded'],s['conflict'])==(3,2,1,1)
    assert [s[f'eligible_{i}'] for i in (2,3,4)]==[1,1,1]
    assert out['known_deficit'][0] and not out['cash_known'][0]
    assert out['cash_cents'][1]==700000 and out['stress_cash_cents'][1]==220000

def test_null_noi_and_no_conflict():
    a={k:np.full(1,-1,dtype=np.int64) for k in FIELDS};o,_=screen(a)
    assert o['unknown'][0] and not o['noi_known'][0] and not o['cash_known'][0]

def test_invalid_inputs():
    a=synthetic_batch(0,1); a['annual_income_cents'][0]=-2
    with pytest.raises(ValueError):screen(a)
    a=synthetic_batch(0,1);a['reported_units']=a['reported_units'].astype(float)
    with pytest.raises(ValueError):screen(a)

def test_cuda_explicit():
    try: g,_=screen(synthetic_batch(0,6),'cuda')
    except BackendUnavailable:return
    c,_=screen(synthetic_batch(0,6))
    for k in c:np.testing.assert_array_equal(c[k],g[k])

def test_batch_replay():
    a=benchmark(29,7,'cpu_reference');b=benchmark(29,7,'cpu_reference')
    assert a['counts']==b['counts'] and a['batch_result_sha256']==b['batch_result_sha256']
    assert a['counts']['eligible']+a['counts']['unknown']+a['counts']['excluded']==29

def test_actual_retained_sources():
    r,t=reconcile();assert len(r)==6965 and t['feature_rows']==6975 and t['exact_parcel_overlap']==1
    assert all(x['legal_units'] is None and x['status']=='HOLD' for x in r)

def test_all_eligible_fixture():
    result=benchmark(33,8,'cpu_reference',True)
    assert result['counts']['eligible']==33
    assert [result['counts'][f'eligible_{u}'] for u in (2,3,4)]==[11,11,11]
    assert result['counts']['unknown']==0
