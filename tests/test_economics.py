import math
import pytest
from site_academy import economics as e

@pytest.mark.parametrize('method,args,key,expected', [
    (e.median_location,([0,4,10],[1,1,2]),'optimal_interval_km',[4,10]),
    (e.labor_shift,(1000,10,2,3,1),'equilibrium_job_change',15),
    (e.residual_bid,(120000,80000,5000,1000),'annual_bid_usd_m2',35),
    (e.far_capacity,(1000,1.5,.7,75),'whole_units_upper_bound',14),
    (e.congestion,(500,.01,24),'marginal_external_usd_per_vehicle',2),
    (e.transit_cost,(2,8,30,20,18,18,12),'generalized_usd_trip',12.9),
    (e.foundation_gap,(10000,600000,.012),'grant_usd_pupil',2800),
    (e.prevention_benefit,(100,.1,1000,8000),'annual_net_benefit_usd',2000),
    (e.maintenance,(1000,5,0,4500),'incremental_npv_usd',500),
    (e.maintenance,(110,1,.1,100),'incremental_npv_usd',0),
    (e.price_ceiling,(100,2000,5,200,4),'shortage_units',900),
    (e.price_ceiling,(300,2000,5,200,4),'shortage_units',0),
    (e.public_good,([100,-20,60],120),'incremental_surplus_usd',20),
    (e.matching_grant,(10000,.5,3000),'local_usd',7000),
])
def test_methods(method,args,key,expected):
    assert method(*args)[key] == pytest.approx(expected)

@pytest.mark.parametrize('method,args', [
    (e.median_location,([1,2],[1])), (e.labor_shift,(100,2,1,0,0)),
    (e.foundation_gap,(1,1,True)), (e.far_capacity,(200,2,1.1,50)),
    (e.public_good,([],0)), (e.maintenance,(5,1.5,.1,9)),
    (e.congestion,(math.nan,1,1)), (e.price_ceiling,(500,5,1,10,1)),
])
def test_bad_inputs(method,args):
    with pytest.raises(ValueError):
        method(*args)

def test_dispatch_and_demo():
    with pytest.raises(ValueError):
        e.run({'model':'__import__','inputs':{}})
    with pytest.raises(ValueError):
        e.run({'model':'public_good','inputs':{}})
    assert e.demo()['time_benefit_usd_per_existing_trip'] == pytest.approx(2.25)
