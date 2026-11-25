import numpy as np
from backend.core.acquisition_batch import BackendUnavailable
from tools import verify_acquisition_cuda as v

def test_parity_checks_dtype_shape_and_values():
    a={'x':np.array([1,2],dtype=np.int64)}
    assert v.compare(a,{'x':a['x'].copy()})==[]
    assert v.compare(a,{'x':a['x'].astype(np.float64)})==['x']
    assert v.compare(a,{'x':np.array([1,3])})==['x']

def test_unavailable_is_not_cpu_success(monkeypatch):
    def fail(_):raise BackendUnavailable('no device')
    monkeypatch.setattr(v,'backend',fail)
    r=v.verify(10,5)
    assert r['status']=='BACKEND_UNAVAILABLE' and r['gpu_records_compared']==0 and r['actual_backend'] is None
