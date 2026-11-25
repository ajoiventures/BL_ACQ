"""REX-02.02: publish a small, source-bound multifamily GIS review dataset."""
from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from shapely.geometry import shape


def prepare(source, expected_sha256):
    raw = source.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Published selection checksum mismatch")
    selection = json.loads(raw)
    features = selection["features"]
    if not 1 <= len(features) <= 64:
        raise ValueError("Expected a bounded selection of 1 to 64 parcels")
    seen = set()
    prepared = []
    for feature in features:
        props = feature["properties"]
        identity = props["county_parcel_id"]
        if not isinstance(identity, str) or len(identity) != 15 or not identity.isascii() or not identity.isdigit():
            raise ValueError("Expected a 15-digit Orange County parcel key")
        if identity in seen:
            raise ValueError("Repeated parcel identity in the selection")
        seen.add(identity)
        geom = shape(feature["geometry"])
        if geom.is_empty or not geom.is_valid or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Expected valid polygon geometry")
        reported = props["reported_units"]
        if type(reported) is not int or reported not in (2, 3, 4):
            raise ValueError("Reported unit count falls outside this exercise cohort")
        lawful = props["lawful_units"]
        prepared.append({
            "type": "Feature", "geometry": feature["geometry"],
            "properties": {
                "parcel_id": f"12095:{identity}", "reported_units": reported,
                "lawful_units": lawful, "decision": "HOLD",
            },
        })
    return {"type": "FeatureCollection", "features": prepared,
            "black_river": {"project": "REX-02.02", "source_sha256": digest,
                            "coordinate_system": "OGC:CRS84", "scope": "Research cohort only"}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("expected_sha256")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.expected_sha256)
    with TemporaryDirectory(dir=args.output.parent) as directory:
        staged = Path(directory) / "review.geojson"
        staged.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        args.output.hardlink_to(staged)


if __name__ == "__main__":
    main()
