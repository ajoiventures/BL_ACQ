"""Bounded small-multifamily numeric screen. Research only; no offers.

Inputs are typed integer arrays. -1 means unknown for money or units.
A legal count is supplied by an upstream evidence-reviewed adapter, never inferred
from a tax code. This module does not certify the supplied evidence.
"""
from __future__ import annotations
import numpy as np
from time import perf_counter

VERSION = '0.1.0'
FIELDS = ('reported_units','legal_units','annual_income_cents','annual_opex_cents',
          'annual_debt_cents','annual_reserves_cents')
MAX_CENTS = 10**12  # numerical input guard; not a purchase limit
MAX_BATCH = 100_000

class BackendUnavailable(RuntimeError):
    pass

def backend(name):
    if name == 'cpu_reference':
        return np
    if name != 'cuda':
        raise ValueError('unknown backend')
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError('no CUDA device')
        cp.zeros(1, dtype=cp.int64)
        cp.cuda.get_current_stream().synchronize()
        return cp
    except Exception as exc:
        raise BackendUnavailable(f'CUDA unavailable: {type(exc).__name__}: {exc}') from exc

def validate(arrays):
    if set(arrays) != set(FIELDS):
        raise ValueError('missing or unexpected field')
    n = None
    for k in FIELDS:
        v = arrays[k]
        if not isinstance(v,np.ndarray) or v.ndim != 1 or v.dtype != np.int64:
            raise ValueError(f'{k}: expected 1D int64 array')
        if n is None: n = len(v)
        if len(v) != n or n > MAX_BATCH: raise ValueError('batch size mismatch or limit exceeded')
        cap = 100_000 if k.endswith('units') else MAX_CENTS
        if np.any((v < -1) | (v > cap)) or (k.endswith('units') and np.any(v == 0)):
            raise ValueError(f'{k}: out of bounds')
    return n

def screen(arrays, name='cpu_reference'):
    n = validate(arrays)
    xp = backend(name)
    t0 = perf_counter()
    a = {k:xp.asarray(v) for k,v in arrays.items()}
    if name == 'cuda': xp.cuda.get_current_stream().synchronize()
    t1 = perf_counter()
    r,l,i,o,d,s = (a[k] for k in FIELDS)
    conflict = (r != -1) & (l != -1) & (r != l)
    eligible = (l >= 2) & (l <= 4) & ~conflict
    unknown = (l == -1) | conflict
    # -1 may be a valid signed cash result, so provide a separate known mask.
    noi_known = (i != -1) & (o != -1)
    pre_reserve_known = noi_known & (d != -1)
    full_known = pre_reserve_known & (s != -1)
    noi = xp.where(noi_known, i-o, 0)
    pre = xp.where(pre_reserve_known, noi-d, 0)
    cash = xp.where(full_known, pre-s, 0)
    deficit = (noi_known & (noi < 0)) | (pre_reserve_known & (pre < 0)) | (full_known & (cash < 0))
    # 10% revenue loss, rounded down to cents (conservative).
    stress = xp.where(full_known, (i*9)//10-o-d-s, 0)
    values = dict(eligible=eligible, unknown=unknown, excluded=~(eligible|unknown), conflict=conflict,
                  noi_known=noi_known, noi_cents=noi, pre_reserve_known=pre_reserve_known,
                  pre_reserve_cents=pre, cash_known=full_known, cash_cents=cash,
                  known_deficit=deficit, stress_cash_cents=stress)
    values.update({f'reported_{u}':r==u for u in (2,3,4)})
    values.update({f'eligible_{u}':eligible&(l==u) for u in (2,3,4)})
    if name == 'cuda': xp.cuda.get_current_stream().synchronize()
    t2 = perf_counter()
    out = {k:(xp.asnumpy(v) if name=='cuda' else v) for k,v in values.items()}
    t3 = perf_counter()
    # These arrays are simultaneously live after readback. Intermediate
    # allocations, the CUDA context and the allocator's cache are excluded.
    live_array_bytes = (
        sum(v.nbytes for v in a.values()) + sum(v.nbytes for v in values.values())
        if name == 'cuda' else None
    )
    return out, {'backend':name,'records':n,'transfer_in_s':t1-t0 if name=='cuda' else None,
                 'compute_s':t2-t1,'transfer_out_s':t3-t2 if name=='cuda' else None,
                 'cuda_live_input_output_bytes':live_array_bytes}

def summarize(out):
    masks=('eligible','unknown','excluded','conflict','noi_known','pre_reserve_known','cash_known','known_deficit',
           'reported_2','reported_3','reported_4','eligible_2','eligible_3','eligible_4')
    return {k:int(np.count_nonzero(out[k])) for k in masks} | {
        'stress_deficit':int(np.count_nonzero(out['cash_known'] & (out['stress_cash_cents']<0)))}
