"""Independent integration checks against the application's registered routes.

These checks use an isolated database and synthetic packets. They do not grant
independent business acceptance or exercise external connectors or a browser.
"""
from copy import deepcopy
import hashlib
import json

from fastapi.testclient import TestClient
import pytest

from backend.core.economic_development import digest
from tools.apply_economic_development import fixtures


@pytest.fixture
def registered_api(tmp_path, monkeypatch):
    database = tmp_path / "independent-economic-review.sqlite3"
    monkeypatch.setenv("BR_DB", str(database))
    monkeypatch.setenv("BR_FOUNDER_TOKEN", "isolated-economic-review-founder")
    monkeypatch.setenv("BR_AUDIT_TOKEN", "isolated-economic-review-auditor")
    monkeypatch.setenv("BR_OPERATIONS_TOKEN", "isolated-economic-review-operations")
    from backend import main
    monkeypatch.setattr(main, "DB", str(database))
    main.initialize()
    with TestClient(main.app) as client:
        yield client, main


def headers(role="founder"):
    return {"Authorization": "Bearer isolated-economic-review-" + role}


def state_snapshot(main):
    with main.conn() as db:
        return {
            "records": [tuple(row) for row in db.execute("SELECT id,state,version FROM records ORDER BY id")],
            "decisions": [tuple(row) for row in db.execute("SELECT id,state,scope FROM decisions ORDER BY id")],
            "jobs": [tuple(row) for row in db.execute("SELECT id,state FROM job_runs ORDER BY id")],
        }


def audit_count(main):
    with main.conn() as db:
        return db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]


def test_registered_baseline_preserves_unknowns_and_binds_report_to_audit(registered_api):
    client, main = registered_api
    packet = fixtures()[0]
    before = state_snapshot(main)
    initial_audit_count = audit_count(main)
    # Header text cannot impersonate the auditor; the actual bearer selects actor.
    response = client.post("/api/economic-development/baseline", json=packet,
                           headers={**headers(), "X-Role": "SW-13"})
    assert response.status_code == 200, response.text
    envelope = response.json()
    report = envelope["report"]
    assert report["storefront_metrics"]["survey_coverage"]["value"] == "0.8"
    assert report["storefront_metrics"]["known_vacancy_rate"]["value"] == "0.125"
    assert report["storefront_metrics"]["vacancy_rate_lower_bound"]["value"] == "0.1"
    assert report["storefront_metrics"]["vacancy_rate_upper_bound"]["value"] == "0.3"
    assert report["input_snapshot"]["storefronts"]["unknown_count"] == 20
    assert report["input_sha256"] == digest(report["input_snapshot"])
    unsigned = deepcopy(report)
    report_hash = unsigned.pop("report_sha256")
    assert report_hash == digest(unsigned)
    with main.conn() as db:
        last = db.execute("SELECT * FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        assert last["actor"] == "FOUNDER"
        assert last["domain"] == packet["domain"]
        assert last["action"] == "ECONOMIC_BASELINE_SCREENING"
        assert json.loads(last["body"])[-1]["report"] == report
        assert last["hash"] == envelope["audit_hash"]
        assert hashlib.sha256((last["prev_hash"] + last["body"]).encode()).hexdigest() == last["hash"]
    assert audit_count(main) == initial_audit_count + 1
    assert state_snapshot(main) == before


def test_registered_dc_failure_preserves_unresolved_items_and_zero_authority(registered_api):
    client, main = registered_api
    before = state_snapshot(main)
    response = client.post("/api/economic-development/data-center", json=fixtures()[2], headers=headers("auditor"))
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["status"] == "FAIL"
    assert {"utility_capacity", "utility_delivery"} <= set(report["failed_gates"])
    assert "fiber_route_diversity" in report["unknown_gates"]
    assert report["planning_load"]["capacity_margin_mw"] == "-3"
    assert report["acquisition_readiness"] == "NOT_DETERMINED"
    assert report["accepted_evidence"] is False
    assert report["utility_capacity_promised"] is False
    assert report["stage_advanced"] is False
    assert all(report[key] == 0 for key in ("financial_authority_cents", "external_authority", "contractual_authority", "ticket_closure_authority"))
    assert state_snapshot(main) == before


@pytest.mark.parametrize("mutation", [
    "accepted_evidence", "actor", "financial_authority_cents", "forged_source", "forged_observation", "report_sha256",
])
def test_registered_routes_reject_claimed_authority_without_audit_side_effect(registered_api, mutation):
    client, main = registered_api
    packet = fixtures()[3]
    if mutation == "forged_source":
        packet["source"]["evidence_status"] = "ACCEPTED"
    elif mutation == "forged_observation":
        packet["utility"]["deliverable_mw"]["evidence_status"] = "VERIFIED"
    else:
        packet[mutation] = {"actor": "SW-13", "financial_authority_cents": 50000000,
                            "accepted_evidence": True, "report_sha256": "forged"}[mutation]
    before = state_snapshot(main)
    initial_audit_count = audit_count(main)
    response = client.post("/api/economic-development/data-center", json=packet, headers=headers())
    assert response.status_code == 422, response.text
    assert audit_count(main) == initial_audit_count
    assert state_snapshot(main) == before


def test_registered_auth_domains_and_contract_are_the_real_application_policy(registered_api):
    client, main = registered_api
    packet = fixtures()[1]
    initial_audit_count = audit_count(main)
    url = "/api/economic-development/data-center"
    assert client.post(url, json=packet).status_code == 401
    assert client.post(url, json=packet, headers={"X-Role": "FOUNDER"}).status_code == 401
    assert client.post(url, json=packet, headers=headers("operations")).status_code == 403
    packet["domain"] = "FAMILY_OFFICE"
    assert client.post(url, json=packet, headers=headers()).status_code == 422
    contract = client.get("/api/economic-development/contract", headers=headers("auditor"))
    assert contract.status_code == 200, contract.text
    assert set(contract.json()["it_load_bases"]) == {"ANNUAL_AVERAGE", "NAMEPLATE", "PEAK"}
    assert contract.json()["accepted_evidence"] is False
    assert audit_count(main) == initial_audit_count


def test_registered_proximity_and_unknown_capacity_never_become_powered_land(registered_api):
    client, main = registered_api
    response = client.post("/api/economic-development/data-center", json=fixtures()[1], headers=headers())
    assert response.status_code == 200, response.text
    report = response.json()["report"]
    assert report["input_snapshot"]["context"]["land_acres"]["value"] == "500"
    assert report["input_snapshot"]["context"]["nearby_substation"]["value"] is True
    assert report["status"] == "UNKNOWN"
    assert report["planning_load"]["supplied_deliverable_mw"] is None
    assert report["planning_load"]["capacity_margin_mw"] is None
    assert report["utility_capacity_promised"] is False
    assert report["acquisition_readiness"] == "NOT_DETERMINED"
