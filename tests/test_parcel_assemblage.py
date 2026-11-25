import pytest
from shapely.geometry import box, Point

from backend.core.parcel_assemblage import adjacency_pairs


def test_assemblage_requires_edge_and_nonoverlapping_interiors():
    base = box(0, 0, 2, 2)
    for other, expected in (
        (box(2, 0, 4, 2), (2, 0, True)),
        (box(2, 2, 4, 4), (0, 0, False)),
        (box(1, 0, 3, 2), (2, 2, False)),
        (box(3, 0, 5, 2), (0, 0, False)),
    ):
        result, = adjacency_pairs({"A": base, "B": other})
        assert (result["shared_boundary_m"], result["interior_overlap_m2"],
                result["geometry_candidate"]) == expected
        assert all(result[key] is None for key in ("ownership", "legal_access", "utilities"))


def test_assemblage_rejects_bad_geometry_and_unbounded_input():
    with pytest.raises(ValueError, match="polygon"):
        adjacency_pairs({"A": Point(0, 0)})
    with pytest.raises(ValueError, match="64"):
        adjacency_pairs({str(i): box(i, 0, i + 1, 1) for i in range(65)})


def test_slope_on_rectangular_grid_with_missing_and_excluded_neighbors():
    import numpy as np
    from backend.core.parcel_assemblage import terrain_slopes_percent

    y, x = np.indices((5, 5))
    elevation = 0.12 * x + 0.08 * y
    mask = np.ones_like(elevation, dtype=bool)
    mask[2, 0] = False
    elevation[2, 4] = np.nan
    slopes = terrain_slopes_percent(elevation, mask, x_spacing_m=3, y_spacing_m=2)
    assert len(slopes) == 7
    assert slopes == pytest.approx([100 * np.hypot(.04, .04)] * 7)
    with pytest.raises(ValueError, match="spacing"):
        terrain_slopes_percent(elevation, mask, x_spacing_m=0, y_spacing_m=2)


def test_conceptual_massing_applies_each_limit():
    from backend.core.parcel_assemblage import conceptual_massing

    parcel = box(0, 0, 10, 10)
    assumptions = dict(setback_m=1, height_limit_m=7, story_height_m=3, floor_area_ratio=1)
    result = conceptual_massing(parcel, **assumptions)
    assert result["setback_footprint_m2"] == 64
    assert result["story_limit"] == 2
    assert result["conceptual_gross_floor_area_upper_bound_m2"] == 100
    assert result["zoning_compliance"] is None
    assert conceptual_massing(parcel, **{**assumptions, "floor_area_ratio": 2})[
        "conceptual_gross_floor_area_upper_bound_m2"] == 128
    assert conceptual_massing(parcel, **{**assumptions, "setback_m": 5})[
        "conceptual_gross_floor_area_upper_bound_m2"] == 0
    with pytest.raises(ValueError, match="story height"):
        conceptual_massing(parcel, **{**assumptions, "story_height_m": 0})


def test_terrain_profile_visibility_keeps_missing_data_unknown():
    from backend.core.parcel_assemblage import terrain_profile_visibility

    kwargs = {"observer_height_m": 1.5, "target_height_m": 1.5}
    assert terrain_profile_visibility([10, 11, 10], **kwargs) == "CLEAR_IN_TERRAIN_MODEL"
    assert terrain_profile_visibility([10, 11.5, 10], **kwargs) == "BLOCKED"
    assert terrain_profile_visibility([10, None, 10], **kwargs) == "UNKNOWN"
    with pytest.raises(ValueError, match="samples"):
        terrain_profile_visibility([10], **kwargs)


def test_viewshed_limits_radius_and_preserves_unknown_and_obstruction():
    from backend.core.parcel_assemblage import terrain_viewshed

    grid = [[0, 0, 0, 0], [0, 0, 5, 0], [0, float("nan"), 0, 0], [0, 0, 0, 0]]
    result = terrain_viewshed(grid, observer_cell=(1, 1), observer_height_m=1,
                              target_height_m=1, radius_cells=2)
    assert result[1, 3] == "BLOCKED"
    assert result[3, 1] == "UNKNOWN"
    assert result[0, 1] == "CLEAR_IN_TERRAIN_MODEL"
    assert (3, 3) not in result
    assert (1, 1) not in result


def test_assemblage_scope_is_screened_without_inferring_buyability():
    from backend.core.parcel_assemblage import screen_assemblage

    selected = {"A": box(0, 0, 1, 1), "B": box(1, 0, 2, 1), "C": box(2, 0, 3, 1)}
    limits = dict(max_parcels=3, max_site_area_m2=3)
    result = screen_assemblage(selected, **limits)
    assert result == {"geometry_status": "CONTIGUOUS", "site_area_m2": 3,
                      "ownership": None, "legal_access": None, "utilities": None}
    assert screen_assemblage(selected, **{**limits, "max_parcels": 2})[
        "geometry_status"] == "OUTSIDE_PARCEL_LIMIT"
    assert screen_assemblage(selected, **{**limits, "max_site_area_m2": 2})[
        "geometry_status"] == "OUTSIDE_AREA_LIMIT"
    assert screen_assemblage({"A": selected["A"], "C": selected["C"]}, **limits)[
        "geometry_status"] == "DISCONNECTED"
    assert screen_assemblage({**selected, "C": box(.5, 0, 1.5, 1)}, **limits)[
        "geometry_status"] == "OVERLAPPING_PARCELS"
