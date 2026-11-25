"""Read-only viewport selections from the pinned College Park research export."""
import hashlib
import json
from pathlib import Path

SELECTION = (
    Path(__file__).resolve().parents[2]
    / "docs/acquisition/college-park-coverage/published-selection-v1.geojson"
)
REVISION = "b634aa52cd33df3ed29f34537c037706b66741ad4fa0e8312e735292db5eabd2"


def viewport(west, south, east, north, zoom, revision):
    if not (-82 <= west < east <= -80 and 28 <= south < north <= 29):
        raise ValueError("Viewport is outside the bounded Orange County pilot")
    if revision is not None and revision != REVISION:
        raise LookupError("College Park source revision changed")
    with SELECTION.open("rb") as stream:
        raw = stream.read(100_001)
    if len(raw) > 100_000 or hashlib.sha256(raw).hexdigest() != REVISION:
        raise LookupError("College Park source revision unavailable")
    data = json.loads(raw)
    provenance = data["black_river"]
    features = []
    if zoom >= 15:
        from shapely.geometry import box, shape

        bounds = box(west, south, east, north)
        features = [f for f in data["features"] if bounds.intersects(shape(f["geometry"]))]
    return {
        "type": "FeatureCollection", "features": features, "revision": REVISION,
        "source_sha256": provenance["source_sha256"], "geometry_crs": provenance["geometry_crs"],
        "representation": "parcel" if zoom >= 15 else "overview",
        "research_only": True, "data_release_authorized": False,
    }
