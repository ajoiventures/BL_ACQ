"""Deterministic site-screening workers. Run from the organization root with -m."""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SIDE_METRES = 1200


def number(value, label):
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    return result


def grade(rise, run):
    """Signed longitudinal grade; both dimensions use the same length unit."""
    rise, run = number(rise, "rise"), number(run, "run")
    if run <= 0:
        raise ValueError("Horizontal run must be positive")
    scaled_rise = 100 * rise
    result = scaled_rise / run if math.isfinite(scaled_rise) else (rise / run) * 100
    return number(result, "grade")


def storm_volume_m3(area_m2, rain_mm, fraction):
    """Event runoff estimate with a user-specified volumetric runoff fraction."""
    area, depth, coefficient = (number(area_m2, "area"), number(rain_mm, "rain"),
                                number(fraction, "runoff fraction"))
    if area < 0 or depth < 0 or not 0 <= coefficient <= 1:
        raise ValueError("Use nonnegative area and depth and a fraction from zero to one")
    area_depth = area * depth
    if math.isfinite(area_depth):
        return area_depth / 1000 * coefficient
    return number((area / 1000) * (depth * coefficient), "runoff volume")


def capacity(cells):
    """Area accounting for disjoint polygons; overlapping constraints within a cell count once."""
    totals = {"excluded_m2": 0.0, "unresolved_m2": 0.0, "screenable_m2": 0.0}
    seen = set()
    constraint_keys = None
    for cell in cells:
        key = cell["id"]
        if not key or key in seen:
            raise ValueError("Each disjoint polygon needs a unique ID")
        seen.add(key)
        area = number(cell["area_m2"], "area")
        if area <= 0:
            raise ValueError("Cell area must be positive")
        constraints = cell["constraints"]
        if not isinstance(constraints, dict) or not constraints:
            raise ValueError("Declare each constraint and its observed state")
        if constraint_keys is None:
            constraint_keys = set(constraints)
        if set(constraints) != constraint_keys:
            raise ValueError("Use the same constraint keys in each cell, with null for unknowns")
        states = tuple(constraints.values())
        if any(v is not None and type(v) is not bool for v in states):
            raise ValueError("Constraint state must be true, false or null")
        if True in states:
            category = "excluded_m2"
        elif None in states:
            category = "unresolved_m2"
        else:
            category = "screenable_m2"
        totals[category] = number(totals[category] + area, category)
    if not seen:
        raise ValueError("Provide a disjoint cell partition")
    return totals


def alternatives(weights, concepts):
    """Compare normalized benefit criteria. Hard exclusions cannot be outweighed."""
    clean = {k: number(v, k) for k, v in weights.items()}
    if not clean or min(clean.values()) < 0 or not math.isclose(sum(clean.values()), 1):
        raise ValueError("Nonnegative weights must sum to one")
    if not concepts:
        raise ValueError("Provide at least one concept")
    result = []
    seen = set()
    for c in concepts:
        name, gate, scores = c["name"], c["clearance"], c["scores"]
        if not name or name in seen:
            raise ValueError("Provide distinct concept names")
        seen.add(name)
        if gate not in ("cleared", "excluded", "unknown") or set(scores) - set(clean):
            raise ValueError("Unknown clearance or criterion")
        values = {k: number(v, k) for k, v in scores.items() if v is not None}
        if any(v < 0 or v > 1 for v in values.values()):
            raise ValueError("Use a zero-to-one benefit scale")
        status = gate
        score = None
        if gate == "cleared":
            status = "incomplete"
            if set(values) == set(clean):
                status = "screened"
                score = round(sum(clean[k] * values[k] for k in clean), 6)
        result.append({"name": name, "status": status, "score": score})
    return sorted(result, key=lambda row: (row["score"] is None, -(row["score"] or 0), row["name"]))


def atlas_row(row):
    km = number(row["Centerline km"], "centerline km")
    count = int(row["Clipped line count"])
    if km < 0 or count < 0 or (not count and km):
        raise ValueError("Invalid road summary")
    return {
        "district": row["District"], "jurisdiction": row["Planning jurisdiction"],
        "center_lat": row["Center latitude"], "center_lon": row["Center longitude"],
        "sketch_area_km2": (SIDE_METRES / 1000) ** 2,
        "clipped_features": count, "sum_feature_km": km,
        "feature_km_per_sketch_km2": round(km / (SIDE_METRES / 1000) ** 2, 3),
        "mean_clipped_feature_m": round(1000 * km / count, 1) if count else "",
        "evidence": row["County GIS source"], "scope": "analyst-centered road sketch",
        "district_boundary": "unverified", "walkability": "requires pedestrian evidence"
    }


def run_atlas(source, destination):
    with Path(source).open(encoding="utf-8-sig", newline="") as f:
        rows = [atlas_row(r) for r in csv.DictReader(f)]
    if not rows or len({r["district"] for r in rows}) != len(rows):
        raise ValueError("Expected nonempty, distinct district records")
    with Path(destination).open("w", newline="", encoding="utf8") as f:
        writer = csv.DictWriter(f, rows[0])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="job", required=True)
    atlas = sub.add_parser("atlas")
    atlas.add_argument("--input", type=Path, default=ROOT / "atlas-seed.csv")
    atlas.add_argument("--output", type=Path, required=True)
    site = sub.add_parser("site")
    site.add_argument("file", type=Path, help="JSON with optional transects, runoff, cells or alternatives")
    args = parser.parse_args()
    if args.job == "atlas":
        print(f"Screened {run_atlas(args.input, args.output)} district contexts")
        return
    data = json.loads(args.file.read_text())
    if not isinstance(data, dict) or not data or set(data) - {"transects", "runoff", "cells", "alternatives"}:
        parser.error("Supply one or more supported measurement groups")
    results = {}
    if "transects" in data:
        results["grade_pct"] = [grade(**v) for v in data["transects"]]
    if "runoff" in data:
        results["runoff_m3"] = [storm_volume_m3(**v) for v in data["runoff"]]
    if "cells" in data:
        results["capacity"] = capacity(data["cells"])
    if "alternatives" in data:
        results["alternatives"] = alternatives(**data["alternatives"])
    print(json.dumps(results, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
