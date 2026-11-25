import json,copy
from pathlib import Path
import pytest
from tools.prepare_urban_pillars import prepare
R=Path(__file__).resolve().parents[1]
def load(p):return json.loads((R/p).read_text())
def inputs():return [load('docs/national-atlas/batch-138c/queue.json'),load('docs/cities-planning/urban-pillars.json'),load('docs/session-tickets.json')]
def test_catalog_and_routing():
 q,c,t=inputs(); l=load('docs/cities-planning/layer-contract.json');assert set(p['engine_id'] for p in c['pillars'])<=set(e['id'] for e in l['engines']);r=prepare(q,c,t);assert r['program_count']==120 and r['pillar_report_count']==115*18 and r['accepted_pillar_reports']==0;assert not r['dispatch_performed'];assert all(not x['investment_authorized'] for x in r['records']);assert all(not x['pillar_reports'] for x in r['records'] if x['designation']=='Partner');assert r==prepare(q,c,t)
def test_invalid_routing_and_duplicate():
 q,c,t=inputs();c['pillars'][0]['primary_ticket']='BR-T999';with_error=lambda:prepare(q,c,t)
 with pytest.raises(ValueError):with_error()
 q,c,t=inputs();q['records'].append(copy.deepcopy(q['records'][0]));
 with pytest.raises(ValueError):prepare(q,c,t)
