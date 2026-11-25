import csv
import pytest
from site_academy.spatial import ROOT, alternatives, capacity, grade, run_atlas, storm_volume_m3


def test_district_replay(tmp_path):
    output = tmp_path / "atlas.csv"
    assert run_atlas(ROOT / "atlas-seed.csv", output) == 66
    assert output.read_bytes() == (ROOT / "atlas-results.csv").read_bytes()
    with output.open() as f:
        first = next(csv.DictReader(f))
    assert float(first["feature_km_per_sketch_km2"]) == pytest.approx(28 / 1.44, abs=.001)


def test_dimensions():
    assert grade(-2, 40) == -5
    assert storm_volume_m3(100, 20, .5) == 1
    with pytest.raises(ValueError):
        grade(1, 0)
    with pytest.raises(ValueError):
        storm_volume_m3(100, 20, 1.3)


def test_overlap_and_missingness():
    states = [(True, True), (None, False), (False, False)]
    cells = [dict(id=str(i), area_m2=100, constraints=dict(flood=a, habitat=b))
             for i, (a, b) in enumerate(states)]
    assert capacity(cells) == dict(excluded_m2=100, unresolved_m2=100, screenable_m2=100)
    with pytest.raises(ValueError):
        capacity(cells + [cells[0]])


def test_non_compensatory_gates():
    scores = dict(shade=1, access=1)
    concepts = [dict(name="A", clearance="excluded", scores=scores),
                dict(name="B", clearance="cleared", scores=dict(access=.5, shade=.7)),
                dict(name="C", clearance="cleared", scores=dict(access=.8))]
    rows = alternatives(dict(shade=.5, access=.5), concepts)
    assert rows[0]["name"] == "B"
    assert rows[0]["score"] == .6
    assert [r["status"] for r in rows[1:]] == ["excluded", "incomplete"]


def test_extreme_inputs_cannot_produce_nonfinite_outputs():
    assert grade(1e308, 1e308) == 100
    assert storm_volume_m3(1e308, 1e308, 0) == 0
    with pytest.raises(ValueError, match="grade must be a finite number"):
        grade(1e308, 1)
    with pytest.raises(ValueError, match="runoff volume must be a finite number"):
        storm_volume_m3(1e308, 1e308, 1)
    with pytest.raises(ValueError, match="screenable_m2 must be a finite number"):
        capacity([
            {"id": str(i), "area_m2": 1e308, "constraints": {"flood": False}}
            for i in range(2)
        ])
