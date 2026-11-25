"""Bounded parcel geometry reference for BR-T086."""
from itertools import combinations


def adjacency_pairs(parcels):
    """Compare parcel polygons in the same projected CRS with meter units."""
    if len(parcels) > 64:
        raise ValueError("Parcel comparison is limited to 64 polygons")
    for geometry in parcels.values():
        if (geometry.geom_type not in {"Polygon", "MultiPolygon"} or not geometry.is_valid
                or geometry.is_empty or geometry.area <= 0):
            raise ValueError("Expected a valid nonempty parcel polygon")
    pairs = []
    for left_id, right_id in combinations(sorted(parcels), 2):
        left, right = parcels[left_id], parcels[right_id]
        shared = left.boundary.intersection(right.boundary).length
        overlap = left.intersection(right).area
        pairs.append({"parcel_ids": [left_id, right_id], "shared_boundary_m": shared,
                      "interior_overlap_m2": overlap, "separation_m": left.distance(right),
                      "geometry_candidate": shared > 0 and overlap == 0,
                      "ownership": None, "legal_access": None, "utilities": None})
    return pairs


def terrain_slopes_percent(elevation, interior_mask, *, x_spacing_m, y_spacing_m):
    """Return centered grades only where the center and four neighbors are valid."""
    import numpy as np

    if not all(np.isfinite(spacing) and spacing > 0 for spacing in (x_spacing_m, y_spacing_m)):
        raise ValueError("Grid spacing must be finite and positive")
    grid = np.ma.asarray(elevation, dtype=float).filled(np.nan)
    mask = np.asarray(interior_mask, dtype=bool)
    if grid.ndim != 2 or mask.shape != grid.shape:
        raise ValueError("Elevation and interior mask must be matching two-dimensional grids")
    valid = mask & np.isfinite(grid)
    stencil = (valid[1:-1, 1:-1] & valid[:-2, 1:-1] & valid[2:, 1:-1]
               & valid[1:-1, :-2] & valid[1:-1, 2:])
    dx = (grid[1:-1, 2:][stencil] - grid[1:-1, :-2][stencil]) / x_spacing_m
    dy = (grid[2:, 1:-1][stencil] - grid[:-2, 1:-1][stencil]) / y_spacing_m
    return 50 * np.hypot(dx, dy)


def conceptual_massing(parcel, *, setback_m, height_limit_m, story_height_m, floor_area_ratio):
    """Screen gross floor area on a projected polygon under supplied scenario limits."""
    from math import floor, isfinite

    if (parcel.geom_type not in {"Polygon", "MultiPolygon"} or parcel.is_empty
            or not parcel.is_valid or not isfinite(parcel.area) or parcel.area <= 0):
        raise ValueError("Expected a valid nonempty parcel polygon")
    limits = (setback_m, height_limit_m, story_height_m, floor_area_ratio)
    if any(isinstance(v, bool) or not isfinite(v) or v < 0 for v in limits) or story_height_m == 0:
        raise ValueError("Massing limits must be finite and nonnegative, with positive story height")
    footprint_area = parcel.buffer(-setback_m).area if setback_m else parcel.area
    stories = floor(height_limit_m / story_height_m)
    area_by_height = stories * footprint_area
    area_by_ratio = floor_area_ratio * parcel.area
    if not all(isfinite(v) for v in (area_by_height, area_by_ratio)):
        raise ValueError("Massing area exceeds numeric limits")
    return {
        "setback_footprint_m2": footprint_area,
        "story_limit": stories,
        "area_by_height_m2": area_by_height,
        "area_by_ratio_m2": area_by_ratio,
        "conceptual_gross_floor_area_upper_bound_m2": min(area_by_height, area_by_ratio),
        "zoning_compliance": None,
    }


def terrain_profile_visibility(elevations_m, *, observer_height_m, target_height_m):
    """Classify visibility along an evenly spaced, straight terrain profile."""
    from math import isfinite

    if not 2 <= len(elevations_m) <= 4096:
        raise ValueError("A terrain profile needs 2 to 4096 samples")
    if any(not isfinite(h) or h < 0 for h in (observer_height_m, target_height_m)):
        raise ValueError("Endpoint heights must be finite and nonnegative")
    if any(z is None or not isfinite(z) for z in elevations_m):
        return "UNKNOWN"
    start = elevations_m[0] + observer_height_m
    end = elevations_m[-1] + target_height_m
    for i, surface in enumerate(elevations_m[1:-1], 1):
        ratio = i / (len(elevations_m) - 1)
        if surface >= (1 - ratio) * start + ratio * end:
            return "BLOCKED"
    return "CLEAR_IN_TERRAIN_MODEL"


def terrain_viewshed(elevation, *, observer_cell, observer_height_m, target_height_m, radius_cells):
    """Trace evenly spaced nearest-cell profiles on a square bare-earth grid."""
    import numpy as np

    grid = np.ma.asarray(elevation, dtype=float).filled(np.nan)
    if grid.ndim != 2 or type(radius_cells) is not int or not 1 <= radius_cells <= 64:
        raise ValueError("Expected a two-dimensional grid and a radius of 1 to 64 cells")
    row, column = observer_cell
    if any(type(i) is not int or not 0 <= i < size for i, size in zip(observer_cell, grid.shape)):
        raise ValueError("Observer must be inside the grid")
    results = {}
    for y in range(max(0, row-radius_cells), min(grid.shape[0], row+radius_cells+1)):
        for x in range(max(0, column-radius_cells), min(grid.shape[1], column+radius_cells+1)):
            dy, dx = y-row, x-column
            if not 0 < dy*dy + dx*dx <= radius_cells*radius_cells:
                continue
            steps = max(abs(dx), abs(dy))
            profile = [grid[round(row + dy*i/steps), round(column + dx*i/steps)]
                       for i in range(steps+1)]
            results[y, x] = terrain_profile_visibility(
                profile, observer_height_m=observer_height_m, target_height_m=target_height_m)
    return results


def screen_assemblage(parcels, *, max_parcels, max_site_area_m2):
    """Screen one explicitly selected scope against size and contiguity limits."""
    from math import isfinite

    if (type(max_parcels) is not int or not 2 <= max_parcels <= 64
            or not isfinite(max_site_area_m2) or max_site_area_m2 <= 0):
        raise ValueError("Expected a parcel limit of 2 to 64 and a positive finite area limit")
    if not 2 <= len(parcels) <= max_parcels:
        return {"geometry_status": "OUTSIDE_PARCEL_LIMIT", "site_area_m2": None,
                "ownership": None, "legal_access": None, "utilities": None}
    pairs = adjacency_pairs(parcels)
    area = sum(parcel.area for parcel in parcels.values())
    neighbors = {key: set() for key in parcels}
    for pair in pairs:
        left, right = pair["parcel_ids"]
        if pair["geometry_candidate"]:
            neighbors[left].add(right)
            neighbors[right].add(left)
    pending = [next(iter(parcels))]
    visited = set(pending)
    while pending:
        adjacent = neighbors[pending.pop()] - visited
        visited.update(adjacent)
        pending.extend(adjacent)
    if any(pair["interior_overlap_m2"] > 0 for pair in pairs):
        status = "OVERLAPPING_PARCELS"
    elif area > max_site_area_m2:
        status = "OUTSIDE_AREA_LIMIT"
    elif len(visited) != len(parcels):
        status = "DISCONNECTED"
    else:
        status = "CONTIGUOUS"
    return {"geometry_status": status, "site_area_m2": area,
            "ownership": None, "legal_access": None, "utilities": None}
