"""Bounded transportation research engine. Supplied graph and lifecycle evidence only.
No inferred delivery, legal access, valuation premium or transaction permission.
"""
from heapq import heappop, heappush
from math import isfinite
from datetime import date

STATES = {'CONCEPT','UNFUNDED_PRIORITY','PROGRAMMED_PHASE','OBLIGATED_PHASE','CONSTRUCTION','OPEN','CANCELLED','UNKNOWN'}
MODES = {'walk','bike','drive','transit','freight'}

def assess_phase(*, phase_id, state, source_id, observed_date, cutoff, phase_scope, funding_scope=None):
    if not all(isinstance(v,str) and v.strip() for v in (phase_id,source_id,phase_scope)) or state not in STATES:
        raise ValueError('invalid phase evidence')
    observed=date.fromisoformat(observed_date); at=date.fromisoformat(cutoff)
    if observed>at: raise ValueError('evidence unavailable at cutoff')
    if state in {'PROGRAMMED_PHASE','OBLIGATED_PHASE'} and not funding_scope:
        raise ValueError('phase-specific funding evidence required')
    return dict(phase_id=phase_id, state=state, source_id=source_id, observed_date=observed_date, cutoff=cutoff,
        phase_scope=phase_scope, funding_scope=funding_scope, scenario_only=state!='OPEN',
        operational_claim='SOURCE_REPORTED_OPEN_REVIEW_REQUIRED' if state=='OPEN' else 'NOT_ESTABLISHED',
        rent_premium=None, legal_access='UNKNOWN', decision='RESEARCH_ONLY')

def accessibility(nodes, edges, origin, destinations, mode, *, network_complete=False):
    """Shortest travel time over an explicitly supplied directed network, not a route service.
    Edges must be observed open, hypothetical alternatives use separate graph inputs.
    Missing destinations never imply no access on an incomplete network.
    """
    if mode not in MODES or not isinstance(network_complete,bool):raise ValueError('invalid mode or coverage')
    if any(not isinstance(n,str) or not n for n in nodes) or len(set(nodes))!=len(nodes):raise ValueError('invalid nodes')
    if origin not in nodes or any(d not in nodes for d in destinations):raise ValueError('unknown endpoint')
    adj={n:[] for n in nodes}
    for e in edges:
        a,b,t,em,s=e['from'],e['to'],e['minutes'],e['mode'],e['state']
        if a not in adj or b not in adj or em not in MODES or s not in STATES or isinstance(t,bool) or not isinstance(t,(int,float)) or not isfinite(t) or t<=0:raise ValueError('invalid edge')
        if em==mode and s=='OPEN':adj[a].append((b,t))
    dist={origin:0.0}; heap=[(0.0,origin)]
    while heap:
        cost,a=heappop(heap)
        if cost!=dist[a]:continue
        for b,t in adj[a]:
            new=cost+t
            if new<dist.get(b,float('inf')):dist[b]=new;heappush(heap,(new,b))
    return {'mode':mode,'network_complete_supplied':network_complete,'classification':'SUPPLIED_NETWORK_RESEARCH_ONLY',
        'destinations':[{'id':d,'minutes':dist.get(d),'status':'ROUTE_IN_SUPPLIED_GRAPH' if d in dist else 'NO_ROUTE_IN_SUPPLIED_GRAPH' if network_complete else 'UNKNOWN_INCOMPLETE_NETWORK'} for d in destinations],
        'market_effect':None,'legal_access':'UNKNOWN','authorization':False}
