import pytest

from backend.core.spatial_constraints import screen_estate_acreage


def test_estate_criterion_does_not_apply_to_main_street():
    infill = screen_estate_acreage("MAIN_STREET_INFILL", 22_189)
    assert infill["status"] == "NOT_APPLICABLE"
    assert infill["estate_minimum_acres"] is None
    assert screen_estate_acreage("ESTATE", 22_189)["status"] == "BELOW_MINIMUM_EVEN_BEFORE_CONSTRAINTS"


@pytest.mark.parametrize("area", [None, 35 * 43_560, 40 * 43_560])
def test_total_area_never_establishes_upland_eligibility(area):
    result = screen_estate_acreage("ESTATE", area)
    assert result["status"] == "UNKNOWN_CONTIGUOUS_UPLANDS"
    assert result["contiguous_upland_acres"] is None


@pytest.mark.parametrize("area", [False, float("inf"), 0, -1])
def test_invalid_measurement_rejected(area):
    with pytest.raises(ValueError, match="parcel area"):
        screen_estate_acreage("ESTATE", area)


def test_dated_network_excludes_planned_and_unverified_phase_edges():
    from backend.core.spatial_constraints import screen_network_access

    first = dict(phase_id="design", state="PROGRAMMED_PHASE", source_id="tip/2026",
                 observed_date="2026-01-10", phase_scope="design", funding_scope="design only")
    second = dict(phase_id="open", state="OPEN", source_id="city/2026",
                  observed_date="2026-01-20", phase_scope="built crossing")
    settings = dict(nodes=["parcel", "crossing", "shop", "park"], origin="parcel",
                    destinations=["shop", "park"], mode="walk", network_revision="city-network/1",
                    authority_source="city/inventory/2026", observed_date="2026-01-24",
                    cutoff="2026-02-01", phases=[first, second], network_complete=True)
    edges = [
        dict(**{"from": "parcel", "to": "crossing"}, mode="walk", minutes=3, state="OPEN", phase_id="open"),
        dict(**{"from": "crossing", "to": "shop"}, mode="walk", minutes=2, state="OPEN"),
        dict(**{"from": "parcel", "to": "shop"}, mode="walk", minutes=1, state="OPEN", phase_id="design"),
        dict(**{"from": "parcel", "to": "park"}, mode="walk", minutes=1, state="OPEN", phase_id="missing"),
    ]
    report = screen_network_access(edges=edges, **settings)
    assert report["destinations"] == [
        {"id": "shop", "minutes": 5, "status": "ROUTE_IN_SUPPLIED_GRAPH"},
        {"id": "park", "minutes": None, "status": "UNKNOWN_INCOMPLETE_NETWORK"},
    ]
    assert report["legal_access"] == "UNKNOWN"
    assert report["travel_time_unit"] == "minutes"
    assert report["withheld_phase_edges"] == 2
    with pytest.raises(ValueError, match="cutoff"):
        screen_network_access(edges=edges, **{**settings, "cutoff": "2026-01-01"})


def test_walkable_main_street_separates_route_from_parcel_eligibility():
    import json
    from pathlib import Path

    from backend.core.spatial_constraints import screen_walkable_main_street

    path = Path(__file__).resolve().parents[1] / "docs/acquisition/college-park-coverage/candidate-screen.json"
    candidates = json.loads(path.read_bytes())["matches"]
    common = {
        "nodes": ["gate", "grocery", "park"],
        "edges": [
            {"id": "sidewalk", "from": "gate", "to": "grocery", "seconds": 120,
             "meters": 160, "mode": "walk", "state": "OPEN"},
            {"id": "proposed-crossing", "from": "grocery", "to": "park", "seconds": 30,
             "meters": 15, "mode": "walk", "state": "CONCEPT"},
        ],
        "destinations": {"grocery": ["grocery"], "park": ["park"]},
        "graph_revision": "development-graph",
    }
    connector = {"node": "gate", "seconds": 15, "meters": 20, "source_id": "development-entrance"}
    for parcel in candidates:
        held = screen_walkable_main_street(
            parcel_id=parcel["county_parcel_id"], district_membership=parcel["accepted_district_membership"],
            lawful_units=parcel["lawful_units"], entrance=None, **common,
        )
        assert held["decision"] == "HOLD"
        assert all(route["status"] == "UNKNOWN_ENTRANCE" for route in held["access"]["routes"])
    result = screen_walkable_main_street(
        parcel_id="development-parcel", district_membership=True, lawful_units=3,
        entrance=connector, network_complete=True, **common,
    )
    assert result["decision"] == "WALKABILITY_REVIEW_CANDIDATE"
    grocery, park = result["access"]["routes"]
    assert grocery["seconds"] == 135 and grocery["path_edge_ids"] == ["sidewalk"]
    assert park["status"] == "NO_ROUTE_IN_SUPPLIED_GRAPH"
    assert result["authorization"] is False
    draft = screen_walkable_main_street(
        parcel_id="development-parcel", district_membership=True, lawful_units=3,
        entrance=connector, network_complete=True, network_draft=True, **common,
    )
    assert draft["decision"] == "HOLD"
    assert draft["reasons"] == ["PEDESTRIAN_NETWORK_DRAFT"]
    assert draft["access"]["routes"][0]["seconds"] == 135
