import pytest
from backend.core.transportation import assess_phase, accessibility

def test_phase_funding_not_open_and_cutoff():
    args=dict(phase_id='P1',state='PROGRAMMED_PHASE',source_id='TIP',observed_date='2026-11-18',cutoff='2026-11-23',phase_scope='design')
    with pytest.raises(ValueError):assess_phase(**args)
    r=assess_phase(**args,funding_scope='design only')
    assert r['scenario_only'] and r['operational_claim']=='NOT_ESTABLISHED' and r['rent_premium'] is None
    with pytest.raises(ValueError):assess_phase(**{**args,'cutoff':'2026-11-17'},funding_scope='design only')

def test_network_separates_planned_and_open_modes():
    e=[{'from':'A','to':'B','minutes':5,'mode':'walk','state':'OPEN'},{'from':'B','to':'C','minutes':3,'mode':'walk','state':'PROGRAMMED_PHASE'},{'from':'A','to':'C','minutes':2,'mode':'drive','state':'OPEN'}]
    r=accessibility(['A','B','C'],e,'A',['B','C'],'walk')
    assert r['destinations'][0]['minutes']==5 and r['destinations'][1]['status']=='UNKNOWN_INCOMPLETE_NETWORK'
    assert r['market_effect'] is None and not r['authorization']
    assert accessibility(['A','B','C'],e,'A',['C'],'drive')['destinations'][0]['minutes']==2
    with pytest.raises(ValueError):accessibility(['A','B','C'],[{**e[0],'minutes':float('nan')}],'A',['B'],'walk')
