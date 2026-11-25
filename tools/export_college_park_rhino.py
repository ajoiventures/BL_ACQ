"""Export and verify a pinned College Park selection in Rhino's 3DM format."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

from pyproj import Transformer
import rhino3dm as rhino
from shapely.geometry import MultiPolygon, Polygon
from shapely.ops import transform

from tools.prepare_spatial_evidence import polygon
from tools.replay_college_park_published_selection import read_verified

SURVEY_FOOT_METRES = 1200 / 3937
ORIGIN = (530000.0, 1540000.0)
CONTRACT = "college-park-rhino-selection/1"


def export(selection_path, qgis_receipt, model_path):
    receipt = json.loads(qgis_receipt.read_bytes())
    digest = receipt["source_sha256"]
    selection = json.loads(read_verified(selection_path, digest))
    if selection["black_river"]["contract"] != "college-park-published-selection/1":
        raise ValueError("Unexpected selection contract")
    features = selection["features"]
    expected = {item["parcel_id"]: item for item in receipt["features"]}
    if len(features) != len(expected) or set(expected) != {f["id"] for f in features}:
        raise ValueError("Parcel IDs disagree with the QGIS readback")
    if model_path.exists():
        raise FileExistsError(model_path)

    model = rhino.File3dm()
    model.Settings.ModelUnitSystem = rhino.UnitSystem.Meters
    model.Strings["contract"] = CONTRACT
    model.Strings["source_sha256"] = digest
    model.Strings["grid_crs"] = "EPSG:2236"
    model.Strings["grid_origin_us_survey_feet"] = json.dumps(ORIGIN)
    model.Strings["metres_per_us_survey_foot"] = "1200/3937"
    project = Transformer.from_crs(4326, 2236, always_xy=True).transform
    for feature in features:
        pid = feature["id"]
        geometry = transform(project, polygon(feature))
        parts = geometry.geoms if isinstance(geometry, MultiPolygon) else (geometry,)
        for part_number, part in enumerate(parts):
            for ring_number, ring in enumerate((part.exterior, *part.interiors)):
                points = [
                    rhino.Point3d((x - ORIGIN[0]) * SURVEY_FOOT_METRES,
                                  (y - ORIGIN[1]) * SURVEY_FOOT_METRES, 0)
                    for x, y in ring.coords
                ]
                attrs = rhino.ObjectAttributes()
                attrs.Name = f"{pid}/{part_number}/{ring_number}"
                attrs.SetUserString("county_parcel_id", pid)
                attrs.SetUserString("county_object_ids", feature["properties"]["county_object_ids"])
                attrs.SetUserString("part", str(part_number))
                attrs.SetUserString("ring", str(ring_number))
                model.Objects.AddCurve(rhino.PolylineCurve(points), attrs)
    if not model.Write(str(model_path), 8):
        raise ValueError("Rhino archive write failed")

    readback = rhino.File3dm.Read(str(model_path))
    if (readback is None or readback.Settings.ModelUnitSystem != rhino.UnitSystem.Meters
            or readback.Strings["source_sha256"] != digest
            or readback.Strings["grid_crs"] != "EPSG:2236"
            or json.loads(readback.Strings["grid_origin_us_survey_feet"]) != list(ORIGIN)
            or readback.Strings["metres_per_us_survey_foot"] != "1200/3937"):
        raise ValueError("Rhino units or source metadata changed")
    rings = defaultdict(dict)
    for obj in readback.Objects:
        attrs = obj.Attributes
        pid = attrs.GetUserString("county_parcel_id")
        if attrs.GetUserString("county_object_ids") != expected[pid]["county_object_ids"]:
            raise ValueError("Rhino county feature IDs changed")
        part = int(attrs.GetUserString("part"))
        ring = int(attrs.GetUserString("ring"))
        curve = obj.Geometry
        if not curve.IsClosed or ring in rings[pid, part]:
            raise ValueError("Rhino ring is open or duplicated")
        points = [curve.Point(i) for i in range(curve.PointCount)]
        rings[pid, part][ring] = [(p.X, p.Y) for p in points]
    areas = defaultdict(float)
    for (pid, _), part in rings.items():
        geometry = Polygon(part[0], [coords for i, coords in sorted(part.items()) if i])
        if not geometry.is_valid:
            raise ValueError("Rhino ring readback is invalid")
        areas[pid] += geometry.area / SURVEY_FOOT_METRES ** 2
    if set(areas) != set(expected) or any(
        not math.isclose(area, expected[pid]["projected_area_us_survey_sqft"],
                         rel_tol=1e-10, abs_tol=0.01)
        for pid, area in areas.items()
    ):
        raise ValueError("Rhino areas do not reconcile with QGIS")
    return {"contract": CONTRACT, "rhino3dm_version": rhino.__version__,
            "source_sha256": digest, "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
            "model_units": "metres", "grid_crs": "EPSG:2236", "grid_origin_us_survey_feet": ORIGIN,
            "metres_per_us_survey_foot": "1200/3937", "object_count": len(readback.Objects),
            "area_us_survey_sqft_by_parcel": dict(sorted(areas.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("selection", "qgis_receipt", "model", "receipt"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = export(args.selection, args.qgis_receipt, args.model)
    with args.receipt.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
