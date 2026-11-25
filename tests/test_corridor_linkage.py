import pytest
from backend.core.corridor_linkage import corridor_routes, conditional_impact

def sample():
    def e(i,a,b,s,m,state='OPEN',mode='walk'):
        return dict(id=i,**{'from':a,'to':b},seconds=s,meters=m,state=state,mode=mode)
    return dict(nodes=['p','a','b','c'],edges=[e('1','p','a',100,80),e('2','p','b',200,70),e('3','p','c',20,10,'PROGRAMMED_PHASE'),e('4','p','c',10,10,mode='drive')],corridors={'A':['a'],'B':['b'],'C':['c']},entrance={'node':'p','source_id':'synthetic','seconds':30,'meters':15},graph_revision='synthetic-1')

def test_corridor_specific_cost_distance_and_access():
    r=corridor_routes(**sample());a,b,c=r['routes']
    assert (a['seconds'],a['meters'])==(130,95)
    assert (b['seconds'],b['meters'])==(230,85)
    assert c['status']=='UNKNOWN_INCOMPLETE_NETWORK' and c['meters'] is None
    assert r['score'] is None and not r['authorization']

def test_missing_entrance_and_reverse_direction():
    x=sample();x['entrance']=None
    assert all(r['status']=='UNKNOWN_ENTRANCE' for r in corridor_routes(**x)['routes'])
    x=sample();x['entrance']['node']='a';x['corridors']={'P':['p']};x['network_complete']=True
    assert corridor_routes(**x)['routes'][0]['status']=='NO_ROUTE_IN_SUPPLIED_GRAPH'

def test_duplicate_and_nonfinite_rejected():
    x=sample();x['edges'].append(x['edges'][0]);
    with pytest.raises(ValueError):corridor_routes(**x)
    x=sample();x['edges'][0]['seconds']=float('nan')
    with pytest.raises(ValueError):corridor_routes(**x)

def test_spillover_explicit_and_displacement():
    x=dict(added_units=4,displaced_units=2,occupancy=.9,household_size=2,household_income=50000,spending_share=.2,local_capture=.5,walk_trips_per_household_day=2)
    r=conditional_impact(**x)
    assert r['annual_local_spending_scenario']==9000 and r['daily_walk_trips_scenario']==3.6 and r['parking_adequacy'] is None
    with pytest.raises(ValueError):conditional_impact(**{**x,'occupancy':1.2})
