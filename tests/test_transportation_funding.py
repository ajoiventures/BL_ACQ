import copy
import json
from pathlib import Path
import pytest
from backend.core.transportation_funding import reconcile_funding, money
from tools.prepare_transportation_funding import build

P=Path('docs/acquisition/run/138T/observations.json')

def test_actual_source_display_packet():
    r=build(P); items=r['funding']['observations']
    assert len(items)==5
    assert items[0]['components_sum_usd']=='5175441.22'
    assert items[0]['arithmetic_status']==items[2]['arithmetic_status']=='BALANCED'
    assert items[1]['arithmetic_status']=='NOT_TESTABLE_NO_COMPONENTS'
    assert r['funding']['cross_scope_total_usd'] is None
    assert all(i['funds_disbursed_usd'] is None for i in items)
    assert all(p['scenario_only'] for p in r['phases'])
    assert not r['network_promotion'] and r['parcel_entitlement']=='UNKNOWN'

def test_funding_does_not_mix_scopes_or_duplicate():
    rows=json.loads(P.read_text())['funding']; x=copy.deepcopy(rows[0]); x['components'][0]['scope_id']='OTHER'
    with pytest.raises(ValueError): reconcile_funding([x])
    with pytest.raises(ValueError): reconcile_funding([rows[0],rows[0]])
    x=copy.deepcopy(rows[0]); x['components'].append(x['components'][0])
    with pytest.raises(ValueError): reconcile_funding([x])

def test_decimal_variance_is_not_financial_authority():
    x=copy.deepcopy(json.loads(P.read_text())['funding'][0]); x['total_usd']='5175441.23'
    r=reconcile_funding([x]); assert r['observations'][0]['arithmetic_difference_usd']=='0.01'
    assert not r['authorization'] and r['market_effect'] is None
    for v in ['NaN','Infinity','-1','0.001',1.0]:
        with pytest.raises(ValueError): money(v)
