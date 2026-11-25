import pytest

from backend.core.acquisition_unit_band import route_unit_band


@pytest.mark.parametrize("count,band,path", [
    (2,"PRIMARY","RESIDENTIAL"), (3,"PRIMARY","RESIDENTIAL"), (4,"PRIMARY","RESIDENTIAL"),
    (5,"PRIMARY","COMMERCIAL"), (6,"SECONDARY","COMMERCIAL"), (10,"SECONDARY","COMMERCIAL"),
    (11,"SELECTIVE","COMMERCIAL"), (20,"SELECTIVE","COMMERCIAL"), (21,"OUT_OF_SCOPE",None),
])
def test_unit_boundaries(count, band, path):
    assert route_unit_band(count, evidence_state="VERIFIED") == {
        "band": band, "financing_research_path": f"{path}_PROGRAM_RESEARCH" if path else None,
    }


@pytest.mark.parametrize("count,state", [(None,"VERIFIED"), (4,"UNKNOWN"), (5,"CONFLICT")])
def test_unverified_units_hold(count, state):
    assert route_unit_band(count, evidence_state=state) == {"band": "HOLD", "financing_research_path": None}
