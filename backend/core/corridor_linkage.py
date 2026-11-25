"""Bounded CPU corridor linkage reference; no geographic, legal or economic approval.
Reuses the transportation lifecycle and mode vocabularies. Supplied directed graph only.
"""
from heapq import heappop, heappush
from math import isfinite
from backend.core.transportation import MODES, STATES


def _number(v, *, positive=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v) or v < 0 or (positive and v == 0):
        raise ValueError('invalid nonnegative finite measurement')
    return float(v)


def corridor_routes(*, nodes, edges, corridors, entrance, graph_revision, mode='walk', network_complete=False):
    """Return fastest path and length of that same path for each corridor separately.
    Entrance is an explicit supplied connector, never a centroid-to-road assumption.
    Unobserved/closed paths are excluded. All outputs remain research-only.
    """
    if mode not in MODES or not isinstance(network_complete, bool) or not isinstance(graph_revision,str) or not graph_revision.strip():
        raise ValueError('invalid graph contract')
    if any(not isinstance(n,str) or not n for n in nodes) or len(set(nodes)) != len(nodes):
        raise ValueError('invalid nodes')
    if not isinstance(corridors,dict) or not corridors or any(not isinstance(k,str) or not k or not v or not set(v)<=set(nodes) for k,v in corridors.items()):
        raise ValueError('invalid corridor destinations')
    adj={n:[] for n in nodes}; seen=set()
    for e in edges:
        a,b=e['from'],e['to']; eid=e['id']
        if not isinstance(eid,str) or not eid or eid in seen or a not in adj or b not in adj or e['mode'] not in MODES or e['state'] not in STATES:
            raise ValueError('invalid edge identity or topology')
        seen.add(eid); seconds=_number(e['seconds'],positive=True); meters=_number(e['meters'],positive=True)
        if e['mode']==mode and e['state']=='OPEN': adj[a].append((b,seconds,meters,eid))
    out={'graph_revision':graph_revision,'mode':mode,'network_complete_supplied':network_complete,'authorization':False,'legal_access':'UNKNOWN','score':None,'routes':[]}
    if entrance is None:
        out['routes']=[{'corridor_id':k,'status':'UNKNOWN_ENTRANCE','seconds':None,'meters':None,'path_edge_ids':[]} for k in sorted(corridors)]
        return out
    origin=entrance['node']; source=entrance['source_id']
    if origin not in adj or not isinstance(source,str) or not source.strip(): raise ValueError('invalid entrance evidence')
    start=(_number(entrance['seconds']),_number(entrance['meters']),())
    best={origin:start}; heap=[(*start,origin)]
    while heap:
        sec,met,path,a=heappop(heap)
        if (sec,met,path)!=best[a]:continue
        for b,s,m,eid in adj[a]:
            candidate=(sec+s,met+m,path+(eid,))
            if candidate<best.get(b,(float('inf'),float('inf'),())):
                best[b]=candidate;heappush(heap,(*candidate,b))
    for k,dests in sorted(corridors.items()):
        choices=[(*best[d],d) for d in dests if d in best]
        if not choices:
            out['routes'].append({'corridor_id':k,'status':'NO_ROUTE_IN_SUPPLIED_GRAPH' if network_complete else 'UNKNOWN_INCOMPLETE_NETWORK','seconds':None,'meters':None,'path_edge_ids':[]});continue
        sec,met,path,d=min(choices)
        out['routes'].append({'corridor_id':k,'status':'ROUTE_IN_SUPPLIED_GRAPH','seconds':sec,'meters':met,'path_edge_ids':list(path),'destination':d,'entrance_source_id':source,'within_5_minutes':sec<=300,'within_10_minutes':sec<=600})
    return out


def conditional_impact(*, added_units, displaced_units, occupancy, household_size, household_income, spending_share, local_capture, walk_trips_per_household_day):
    """Explicit scenario only: no defaults, no claim of causal net local impact."""
    for v in (added_units,displaced_units):
        if type(v) is not int or v<0: raise ValueError('unit counts must be nonnegative integers')
    for v in (occupancy,spending_share,local_capture):
        if _number(v)>1:raise ValueError('share exceeds one')
    for v in (household_size,household_income,walk_trips_per_household_day):_number(v)
    net=(added_units-displaced_units)*occupancy
    return {'classification':'CONDITIONAL_SCENARIO_NOT_FORECAST','net_occupied_households_assumed':net,'net_residents_assumed':net*household_size,'annual_local_spending_scenario':net*household_income*spending_share*local_capture,'daily_walk_trips_scenario':net*walk_trips_per_household_day,'retail_viability':None,'parking_adequacy':None,'authorization':False}
