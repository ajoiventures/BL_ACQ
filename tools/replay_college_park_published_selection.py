"""Replay the pinned College Park city boundary and export the matched selection."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Polygon, mapping
from shapely.ops import transform

from tools.prepare_spatial_evidence import polygon


def read_verified(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Source revision changed: {path.name}")
    return raw


def replay(root):
    baseline = json.loads((root / "published-city-geometry-comparison.json").read_bytes())
    pins = dict(baseline["parcel_input_sha256"])
    boundaries = []
    for layer in baseline["layers"].values():
        receipt_name = layer["geometry_receipt"]
        receipt = json.loads((root / receipt_name).read_bytes())
        name = receipt_name.replace(".receipt.json", ".json")
        pins[name] = receipt["sha256"]
        data = json.loads(read_verified(root / name, pins[name]))
        if data["spatialReference"]["latestWkid"] != 2236 or len(data["features"]) != 1:
            raise ValueError("Unexpected city layer shape or CRS")
        feature, = data["features"]
        ring, = feature["geometry"]["rings"]
        area = Polygon(ring)
        if not area.is_valid or area.is_empty or feature["attributes"] != layer["city_feature"]:
            raise ValueError("Unexpected city district geometry or identity")
        boundaries.append(area)
    district, incentive = boundaries
    if not district.equals(incentive):
        raise ValueError("Program and incentive geometries disagree")

    singleton = "unique-parcel-input.geojson"
    component = "parcel-component-disposition.geojson"
    city_parcels = json.loads(read_verified(root / singleton, pins[singleton]))["features"]
    combined = json.loads(read_verified(root / component, pins[component]))
    city_parcels.append(combined)
    roll_file = root.parent / "orange-final-roll/official_final_roll_inventory.csv"
    roll_pin = json.loads((root.parent / "orange-sales-spatial/spatial-input-digests.json").read_bytes())[
        roll_file.name
    ]
    inventory = list(csv.DictReader(read_verified(roll_file, roll_pin).decode("utf-8").splitlines()))
    targets = {row["ALT_KEY"]: row for row in inventory}
    if len(targets) != len(inventory):
        raise ValueError("Ambiguous county identity in final-roll inventory")

    project = Transformer.from_crs(4326, 2236, always_xy=True).transform
    seen = set()
    selection = []
    positive = 0
    for feature in city_parcels:
        props = feature["properties"]
        pid = props.get("PARCEL", props.get("county_parcel_id"))
        if not pid or pid in seen:
            raise ValueError("Missing or repeated county parcel")
        seen.add(pid)
        geographic = polygon(feature)
        projected = transform(project, geographic)
        overlap = district.intersection(projected).area
        if overlap <= 0:
            continue
        positive += 1
        roll = targets.get(pid)
        if roll:
            ids = [props["OBJECTID"]] if feature is not combined else [
                c["OBJECTID"] for c in props["components"]
            ]
            selection.append({
                "type": "Feature", "id": pid, "geometry": mapping(geographic),
                "properties": {
                    "county_parcel_id": pid, "county_object_ids": ",".join(map(str, ids)),
                    "roll_parcel_id": roll["PARCEL_ID"], "address": roll["PHY_ADDR1"],
                    "reported_units": int(roll["NO_RES_UNTS"]), "lawful_units": None,
                    "parcel_area_us_survey_sqft": projected.area,
                    "overlap_us_survey_sqft": overlap,
                    "overlap_fraction": overlap / projected.area, "decision": "HOLD",
                },
            })
    counts = {"parcel_count": len(seen), "positive_overlap": positive, "zero_overlap": len(seen) - positive}
    if counts != baseline["coverage"] or {f["id"] for f in selection} != {
        row["county_id"] for row in baseline["exact_roll_2_to_4_unit_matches"]
    }:
        raise ValueError("Replay disagrees with the published comparison")
    return {
        "type": "FeatureCollection", "features": sorted(selection, key=lambda f: f["id"]),
        "black_river": {"contract": "college-park-published-selection/1",
                        "geometry_crs": "OGC:CRS84", "measurement_crs": "EPSG:2236",
                        "coverage": counts, "source_sha256": {**pins, roll_file.name: roll_pin}},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = replay(args.evidence)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
