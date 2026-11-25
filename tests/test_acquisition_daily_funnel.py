import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.core import acquisition_daily_funnel, acquisition_runs, unit_evidence


def test_daily_funnel_persists_real_orange_research_and_zero_selection(tmp_path, monkeypatch):
    from backend import main

    monkeypatch.setattr(main, "DB", str(tmp_path / "funnel.sqlite"))
    monkeypatch.setenv("BR_FOUNDER_TOKEN", "funnel-founder")
    monkeypatch.setenv("BR_AUDIT_TOKEN", "funnel-auditor")
    monkeypatch.setenv("BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT", "1")
    main.initialize()
    with main.conn() as db:
        acquisition_runs.initialize(db)
        acquisition_daily_funnel.initialize(db)
        unit_evidence.initialize(db)
    client = TestClient(main.app)
    founder = {"Authorization": "Bearer funnel-founder"}
    reviewer = {"Authorization": "Bearer funnel-auditor"}
    response = client.post("/api/acquisition-runs", headers=founder, json={
        "request_id": "daily-orange-test", "backend": "cpu_reference", "batch_size": 10_000,
        "snapshot_source": "orange_2026_final_roll",
    })
    assert response.status_code == 200, response.text
    run = response.json()
    day = "/api/acquisition-funnel/2026-11-24"
    decision = {"run_id": run["id"], "decision": "NO_SELECTION"}
    assert client.put(day, headers=reviewer, json=decision).status_code == 403
    assert client.put(day, headers=founder, json=decision).status_code == 409
    completed = client.post(f"/api/acquisition-runs/{run['id']}/step", headers=founder,
                            json={"version": run["version"], "action": "advance"})
    assert completed.status_code == 200, completed.text
    response = client.put(day, headers=founder, json=decision)
    assert response.status_code == 200, response.text
    with main.conn() as db:
        with pytest.raises(sqlite3.IntegrityError, match='Immutable daily funnel'):
            db.execute("UPDATE acquisition_daily_funnel SET report='{}' WHERE day='2026-11-24'")
    first = response.json()
    assert first["run_total"] == 6078
    assert [len(rows) for rows in first["stages"].values()] == [100, 25, 0, 0, 0]
    assert first["founder_decision"] == "NO_SELECTION"
    assert first["selected_parcel"] is None
    assert client.put(day, headers=founder, json=decision).json() == first
    assert client.put(day, headers=founder, json={**decision, "decision": "DEFER"}).status_code == 409
    with TestClient(main.app) as reopened:
        assert reopened.get(day, headers=reviewer).json() == first
    parcel_key = first["stages"]["reported_units_25"][0]
    monkeypatch.setattr(unit_evidence, "today", lambda: "2026-11-25")
    monkeypatch.setattr(unit_evidence, "now", lambda: "2026-11-25T12:00:00.000000+00:00")
    with main.conn() as db:
        claim = unit_evidence.propose(
            db, run["id"], parcel_key, 2, "Development claim", "Artificial unit-count excerpt",
            "2026-11-25", "2026-12-01"
        )["claim"]
        review = unit_evidence.adjudicate(
            db, claim["id"], "ACCEPT_RESEARCH", "Development review", "Independent fixture excerpt",
            "2026-11-25", None
        )["review"]
    assert client.get(day, headers=reviewer).json()["reviewed_unit_research"] == []
    second = client.put("/api/acquisition-funnel/2026-11-25", headers=founder, json=decision).json()
    assert second["prior_day"] == "2026-11-24"
    assert second["changes"] == {"added": [], "removed": [], "reason_changed": [parcel_key]}
    assert [row["review_ids"] for row in second["reviewed_unit_research"]] == [[review["id"]]]
    assert second["stages"]["lawful_units_10"] == []
    assert second["stages"]["underwritten_3"] == []
    assert second["selected_parcel"] is None
    retained = client.post("/api/acquisition-runs", headers=founder, json={
        "request_id": "daily-retained-test", "backend": "cpu_reference", "batch_size": 10_000,
    }).json()
    completed = client.post(f"/api/acquisition-runs/{retained['id']}/step", headers=founder,
                            json={"version": retained["version"], "action": "advance"})
    assert completed.status_code == 200, completed.text
    retained_decision = {**decision, "run_id": retained["id"]}
    third_day = "/api/acquisition-funnel/2026-11-26"
    monkeypatch.delenv("BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT")
    assert client.put(day, headers=founder, json=decision).status_code == 404
    assert client.put(third_day, headers=founder, json=retained_decision).status_code == 404
    monkeypatch.setenv("BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT", "1")
    third = client.put(third_day, headers=founder, json=retained_decision)
    assert third.status_code == 200, third.text
    assert third.json()["prior_day"] == "2026-11-25"
    monkeypatch.delenv("BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT")
    assert client.get(third_day, headers=reviewer).status_code == 404
    assert client.put(third_day, headers=founder, json=retained_decision).status_code == 404
    monkeypatch.setenv("BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT", "1")
    with main.conn() as db:
        db.execute("DROP TRIGGER acquisition_daily_funnel_no_update")
        db.execute("UPDATE acquisition_daily_funnel SET report='[]' WHERE day='2026-11-25'")
    assert client.get("/api/acquisition-funnel/2026-11-25", headers=reviewer).status_code == 409
    assert client.get(third_day, headers=reviewer).status_code == 409
    assert client.put(third_day, headers=founder, json=retained_decision).status_code == 409



def test_later_stages_accept_only_eligible_development_selection():
    import pytest

    parcels = [f"fixture-{index:02d}" for index in range(25)]
    counts = dict.fromkeys(parcels, 2)
    counts[parcels[0]] = 1
    cash = {key: index * 100 for index, key in enumerate(parcels)}
    cash[parcels[11]] = 999_000
    cash[parcels[10]] = 0
    expected_lawful = parcels[1:11]
    expected_underwritten = parcels[9:6:-1]
    stages = acquisition_daily_funnel.later_stages(
        parcels, counts, cash, "SELECT", expected_underwritten[0]
    )
    assert stages == {
        "lawful_units_10": expected_lawful,
        "underwritten_3": expected_underwritten,
        "founder_selection_1": [expected_underwritten[0]],
    }
    for parcel in (parcels[0], parcels[10], parcels[11], None):
        with pytest.raises(ValueError, match="cleared both"):
            acquisition_daily_funnel.later_stages(parcels, counts, cash, "SELECT", parcel)
    with pytest.raises(ValueError, match="only permitted"):
        acquisition_daily_funnel.later_stages(parcels, counts, cash, "DEFER", expected_underwritten[0])
