from datetime import datetime, timedelta, timezone
from test_strategy_cases import client,case_input
from test_api import F,A,O
from test_acquisition_runs import start,step
import pytest

@pytest.fixture(scope='module')
def cohort_run():
    r=start(size=1000).json()
    while r['state']!='COMPLETED':r=step(r).json()
    p=client.get('/api/acquisition-runs/'+r['id']+'/properties',headers=F).json()['items']
    return r,p[0]['parcel_key'],p[1]['parcel_key']

def test_reviewed_claim_routing_conflict_and_revocation(cohort_run):
    r,key,other=cohort_run
    d=datetime.now(timezone.utc).date().isoformat();end=(datetime.now(timezone.utc).date()+timedelta(days=7)).isoformat()
    b={'run_id':r['id'],'parcel_key':key,'units':4,'source_ref':'fixture://permit','excerpt':'Synthetic four-unit permit fixture','source_date':d,'valid_until':end}
    url='/api/unit-evidence';case={'run_id':r['id'],'parcel_key':key,'strategy_id':'SMF-01'}
    old=client.post('/api/strategy-cases',headers=F,json=case).json()['receipt']
    assert client.post(url,headers=A,json=b).status_code==403
    assert client.post(url,headers=O,json=b).status_code==403
    x=client.post(url,headers=F,json=b).json();cid=x['claim']['id'];assert client.post(url,headers=F,json=b).json()['replay']
    review={'decision':'ACCEPT_RESEARCH','source_ref':'fixture://independent','excerpt':'Synthetic independent four-unit record','source_date':d}
    path=url+'/'+cid+'/review'
    assert client.post(path,headers=F,json=review).status_code==403
    assert client.post(path,headers=A,json={**review,'source_ref':b['source_ref']}).status_code==409
    pattern_path = f'{url}/{r["id"]}/{key}/screen-pattern'
    screen = {
        "as_of": d, "jurisdiction": "US-FL", "track": "MS",
        "rule": {
            "schema_version": 1, "pattern_id": "UNIT-COUNT-TEST", "version": 1,
            "taxonomy_path": "ACQUISITION.PARCEL.REVIEW.UNITS",
            "kind": "REVIEW_CHECK", "lifecycle": "DRAFT", "jurisdictions": ["US-FL"],
            "tracks": ["MS"], "effective_from": d, "effective_to": None,
            "title": "Review a four-unit research count", "source_refs": ["fixture://rule"],
            "predicate": {"field": "reviewed_research_unit_count", "op": "eq",
                          "value": "4", "unit": "dwelling_unit"},
        },
    }
    assert client.post(pattern_path, headers=O, json=screen).status_code == 403
    assert client.post(pattern_path, headers=F, json={**screen, "facts": {}}).status_code == 422
    assert client.post(pattern_path, headers=F, json=screen).json()["result"]["status"] == "NEEDS_EVIDENCE"
    rid=client.post(path,headers=A,json=review).json()['review']['id']
    inspect_path = f'{url}/{r["id"]}/{key}'
    prior_day = (datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat()
    assert client.get(inspect_path, headers=A, params={"as_of":d, "valid_on":prior_day}).json()["status"]=="UNKNOWN"
    assert client.get(inspect_path, headers=A, params={"as_of":d, "valid_on":d}).json()["status"]=="REVIEWED_RESEARCH_COUNT"
    assert client.get(inspect_path, headers=A, params={"as_of":prior_day, "valid_on":d}).status_code==409
    evaluated = client.post(pattern_path, headers=A, json=screen).json()
    assert evaluated["result"]["status"] == "DRAFT_MATCH_REVIEW"
    assert not evaluated["result"]["legal_determination"]
    retained = {**screen, "retain": True}
    assert client.post(pattern_path, headers=A, json=retained).status_code == 403
    receipt = client.post(pattern_path, headers=F, json=retained).json()["receipt"]
    assert client.post(pattern_path, headers=F, json=retained).json()["receipt"] == receipt
    receipt_url = "/api/unit-pattern-receipts/" + receipt["operation_id"]
    assert client.get(receipt_url, headers=O).status_code == 403
    assert client.get(receipt_url, headers=A).json()["evidence_current"]

    assert client.post(path,headers=A,json=review).json()['replay']
    assert not client.get('/api/strategy-cases/'+old['id'],headers=A).json()['unit_evidence_current']
    new=client.post('/api/strategy-cases',headers=F,json=case).json()['receipt'];assert new['unit_gate']=='REVIEWED_RESEARCH_UNIT_MATCH_ONLY' and new['legal_units'] is None and new['reviewed_research_units']==4
    assert new['financial_authority_cents']==0 and set(new['decision_gates'].values())=={'UNKNOWN'}
    batch={'run_id':r['id'],'offset':0,'limit':2};v=client.post('/api/strategy-batches',headers=F,json=batch).json()['receipt'];assert v['gate_counts']=={'REVIEWED_RESEARCH_UNIT_MATCH_ONLY':2,'NEEDS_LEGAL_UNIT_EVIDENCE':2,'RESEARCH_DEFERRED':162}
    assert len(v['gate_templates'])==2 and v['offer_ready']==0
    # Competing unreviewed claim holds the parcel rather than selecting preferred count.
    c2=client.post(url,headers=F,json={**b,'units':3,'source_ref':'fixture://competing','excerpt':'Synthetic three-unit claim'}).json()['claim']['id']
    st=client.get(f'{url}/{r["id"]}/{key}',headers=A).json();assert st['status']=='CONFLICT' and st['reviewed_units'] is None
    assert not client.get('/api/strategy-batches/'+v['id'],headers=A).json()['unit_evidence_current']
    assert client.post('/api/strategy-cases/'+new['id']+'/finance',headers=F,json={'as_of':d}).status_code==409
    assert client.post(url+'/'+c2+'/review',headers=A,json={**review,'decision':'REJECT'}).status_code==200
    assert client.get(f'{url}/{r["id"]}/{key}',headers=A).json()['status']=='REVIEWED_RESEARCH_COUNT'
    before_correction = datetime.now(timezone.utc).isoformat()
    correction = client.post(url, headers=F, json={
        **b, "units": 3, "valid_from": d, "supersedes_claim_id": cid,
        "source_ref": "fixture://corrected-permit", "excerpt": "Corrected three-unit permit",
    }).json()["claim"]
    assert client.get(inspect_path, headers=A).json()["status"] == "CONFLICT"
    correction_path = url + "/" + correction["id"] + "/review"
    correction_review = client.post(correction_path, headers=A, json=review).json()["review"]["id"]
    assert client.get(inspect_path, headers=A).json()["reviewed_units"] == 3
    assert client.get(inspect_path, headers=A, params={"as_of": before_correction}).json()["reviewed_units"] == 4
    latest = client.post(url, headers=F, json={
        **b, "units": 2, "valid_from": d, "supersedes_claim_id": correction["id"],
        "source_ref": "fixture://second-corrected-permit", "excerpt": "Corrected two-unit permit",
    }).json()["claim"]
    latest_path = url + "/" + latest["id"] + "/review"
    latest_review = client.post(latest_path, headers=A, json=review).json()["review"]["id"]
    assert client.post(correction_path, headers=A, json={
        **review, "decision": "REVOKE", "expected_review_id": correction_review,
    }).status_code == 200
    assert client.get(inspect_path, headers=A).json()["reviewed_units"] == 2
    assert client.post(latest_path, headers=A, json={
        **review, "decision": "REVOKE", "expected_review_id": latest_review,
    }).status_code == 200
    assert client.get(inspect_path, headers=A).json()["reviewed_units"] == 4
    assert client.post(path,headers=A,json={**review,'decision':'REVOKE'}).status_code==409
    assert client.post(path,headers=A,json={**review,'decision':'REVOKE','expected_review_id':rid}).status_code==200
    assert client.get(f'{url}/{r["id"]}/{key}',headers=A).json()['status']=='UNKNOWN'
    assert client.post(pattern_path, headers=F, json=screen).json()['result']['status'] == 'NEEDS_EVIDENCE'
    historical = client.get(receipt_url, headers=A).json()
    assert not historical['evidence_current'] and historical['sha256'] == receipt['sha256']
    assert historical['receipt']['result']['status'] == 'DRAFT_MATCH_REVIEW'
    assert client.get(f'{url}/{r["id"]}/{other}',headers=A).json()['status']=='UNKNOWN'

def test_expired_and_bad_source(cohort_run):
    r,key,_=cohort_run;d=datetime.now(timezone.utc).date().isoformat();past=(datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat()
    b={'run_id':r['id'],'parcel_key':key,'units':2,'source_ref':'fixture://x','excerpt':'test','source_date':d,'valid_until':past}
    assert client.post('/api/unit-evidence',headers=F,json=b).status_code==409
    assert client.post('/api/unit-evidence',headers=F,json={**b,'valid_until':d,'source_ref':' '}).status_code==409
    assert client.post('/api/unit-evidence',headers=F,json={**b,'valid_until':d,'parcel_key':'wrong'}).status_code==404


def test_future_effective_claim_is_recorded_without_becoming_active(cohort_run):
    run, _, parcel = cohort_run
    today = datetime.now(timezone.utc).date()
    start_day = (today + timedelta(days=1)).isoformat()
    end_day = (today + timedelta(days=2)).isoformat()
    body = {
        "run_id": run["id"], "parcel_key": parcel, "units": 3,
        "source_ref": "fixture://future-effective-permit",
        "excerpt": "Synthetic future-effective three-unit permit",
        "source_date": today.isoformat(), "valid_from": start_day, "valid_until": end_day,
    }
    url = "/api/unit-evidence"
    assert client.post(url, headers=F, json={**body, "valid_from": "9999-01-01"}).status_code == 409
    response = client.post(url, headers=F, json=body)
    assert response.status_code == 200, response.text
    claim = response.json()["claim"]
    assert claim["valid_from"] == start_day
    assert client.post(url, headers=F, json=body).json()["replay"]
    projection = client.get(f'{url}/{run["id"]}/{parcel}', headers=A).json()
    assert claim["id"] in [entry["claim"]["id"] for entry in projection["entries"]]
    assert claim["id"] not in projection["pending_claim_ids"]


def test_owner_occupancy_separate_economics(case_input):
    cid=client.post('/api/strategy-cases',headers=F,json={**case_input,'strategy_id':'SMF-02'}).json()['receipt']['id']
    path='/api/strategy-cases/'+cid+'/owner-occupancy'
    inputs={'assumed_units':4,'tenant_revenue_cents':4500000,'operating_cost_cents':1800000,'debt_service_cents':2400000,'reserve_contribution_cents':400000,'cash_capex_cents':300000,'alternative_housing_cost_cents':1800000}
    body={'inputs':inputs}
    assert client.post(path,headers=A,json=body).status_code==403
    r=client.post(path,headers=F,json=body).json()['receipt']
    assert r['baseline']['net_owner_cash_outlay_cents']==400000 and r['baseline']['difference_vs_alternative_housing_cents']==1400000
    assert r['revenue_down_10']['net_owner_cash_outlay_cents']==850000 and r['assumed_rental_units']==3 and r['financial_authority_cents']==0
    assert client.post(path,headers=F,json=body).json()['replay']
    assert client.post(path,headers=F,json={'inputs':{**inputs,'tenant_revenue_cents':None}}).json()['receipt']['baseline']['net_owner_cash_outlay_cents'] is None
    assert client.post(path,headers=F,json={'inputs':{**inputs,'assumed_units':5}}).status_code==409
    assert client.post('/api/strategy-cases/'+cid+'/purchase',headers=F,json={'finance_id':r['id'],'inputs':{}}).status_code==409


def test_competing_pending_counts_are_visible_without_promoting_either(cohort_run):
    run, _, key = cohort_run
    today = datetime.now(timezone.utc).date()
    url = "/api/unit-evidence"
    proposal = {"run_id": run["id"], "parcel_key": key, "source_date": today.isoformat(),
                "valid_until": (today + timedelta(days=7)).isoformat()}
    batch_request = {"run_id": run["id"], "offset": 0, "limit": 2}
    endpoint = "/api/strategy-batches"
    prior = client.post(endpoint, headers=F, json=batch_request).json()["receipt"]
    assert client.get(f"{endpoint}/{prior['id']}", headers=A).json()["unit_evidence_current"]
    for units in (2, 3):
        response = client.post(url, headers=F, json={
            **proposal, "units": units, "source_ref": f"fixture://pending/{units}",
            "excerpt": f"Synthetic pending count {units}",
        })
        assert response.status_code == 200
    state = client.get(f"{url}/{run['id']}/{key}", headers=A).json()
    assert state["status"] == "CONFLICT"
    assert len(state["pending_claim_ids"]) == 2
    assert state["active_review_ids"] == []
    assert state["reviewed_units"] is None and state["legal_units"] is None
    case = client.post("/api/strategy-cases", headers=F, json={
        "run_id": run["id"], "parcel_key": key, "strategy_id": "SMF-01",
    }).json()["receipt"]
    assert case["unit_gate"] == "CONFLICTING_UNIT_COUNTS"
    old = client.get(f"{endpoint}/{prior['id']}", headers=A).json()
    assert old["receipt"] == prior
    assert old["unit_evidence_current"] is False
    batch = client.post(endpoint, headers=F, json=batch_request).json()["receipt"]
    assert batch["id"] != prior["id"] and batch["offer_ready"] == 0
    row = next(record for record in batch["records"] if record["parcel_key"] == key)
    assert row["reviewed_research_units"] is None and row["legal_units"] is None
    assert batch["gate_templates"][row["gate_template_id"]]["SMF-01"] == case["unit_gate"]


@pytest.mark.parametrize("metric,unit,value", [
    ("lot_coverage_ratio", "ratio", "0.45"),
    ("contiguous_upland_acres", "acre", "4.25"),
])
def test_reviewed_parcel_metric_flows_to_pattern_receipt(cohort_run, metric, unit, value):
    run, parcel, _ = cohort_run
    today = datetime.now(timezone.utc).date().isoformat()
    proposal = {
        "run_id": run["id"], "parcel_key": parcel, "metric": metric, "value": value,
        "source_ref": f"fixture://{metric}/measurement", "excerpt": "Synthetic parcel measurement",
        "source_date": today, "valid_until": (datetime.now(timezone.utc).date() + timedelta(days=5)).isoformat(),
    }
    url = "/api/parcel-metric-evidence"
    assert client.post(url, headers=O, json=proposal).status_code == 403
    assert client.post(url, headers=F, json={**proposal, "value": "NaN"}).status_code == 409
    claim = client.post(url, headers=F, json=proposal).json()["claim"]
    assert claim["unit"] == unit
    assert client.post(url, headers=F, json={**proposal, "value": value + "0"}).json()["replay"]
    base = f'/api/unit-evidence/{run["id"]}/{parcel}'
    path = base + "/screen-pattern"
    body = {
        "as_of": today, "jurisdiction": "US-FL", "track": "MS", "metric": metric, "retain": True,
        "rule": {
            "schema_version": 1, "pattern_id": metric, "version": 1,
            "taxonomy_path": "ACQUISITION.PARCEL.REVIEW.METRIC", "kind": "REVIEW_CHECK",
            "lifecycle": "DRAFT", "jurisdictions": ["US-FL"], "tracks": ["MS"],
            "effective_from": today, "effective_to": None, "title": "Check parcel metric",
            "source_refs": ["fixture://rule"], "predicate": {"field": metric, "op": "eq", "value": value, "unit": unit},
        },
    }
    assert client.post(path, headers=F, json=body).json()["result"]["status"] == "NEEDS_EVIDENCE"
    review = {"decision": "ACCEPT_RESEARCH", "source_ref": f"fixture://{metric}/review",
              "excerpt": "Distinct synthetic measurement verification", "source_date": today}
    review_url = f'/api/unit-evidence/{claim["id"]}/review'
    assert client.post(review_url, headers=F, json=review).status_code == 403
    assert client.post(review_url, headers=A, json=review).status_code == 200
    result = client.post(path, headers=F, json=body).json()
    assert result["result"]["status"] == "DRAFT_MATCH_REVIEW"
    assert result["result"]["input_snapshot"]["facts"][metric]["value"] == value
    receipt = client.get("/api/unit-pattern-receipts/" + result["receipt"]["operation_id"], headers=A).json()
    assert receipt["evidence_current"] and receipt["receipt"]["metric"] == metric
    assert not any(row["claim"]["id"] == claim["id"] for row in client.get(base, headers=F).json()["entries"])
