"""Replay the retained College Park crossing removal scenarios."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median

from pyproj import Geod

from backend.core.transportation import accessibility


def replay(snapshot, receipt):
    raw = snapshot.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt["source_sha256"]:
        raise ValueError("OpenStreetMap snapshot checksum does not match the receipt")
    edges = []
    geod = Geod(ellps="WGS84")
    for way in json.loads(raw)["elements"]:
        tags = way.get("tags", {})
        if way.get("type") != "way" or tags.get("highway") not in {"footway", "pedestrian"}:
            continue
        if (tags.get("foot", tags.get("access")) in {"no", "private", "restricted"}
                or tags.get("oneway:foot") not in (None, "no")):
            continue
        nodes, geometry = way["nodes"], way["geometry"]
        for a, b, start, end in zip(nodes, nodes[1:], geometry, geometry[1:]):
            meters = geod.inv(start["lon"], start["lat"], end["lon"], end["lat"])[2]
            if a != b and meters > 0:
                for first, last in ((a, b), (b, a)):
                    edges.append({"from": str(first), "to": str(last), "mode": "walk",
                                  "state": "OPEN", "minutes": meters / receipt["speed_m_per_minute"],
                                  "way": way["id"]})
    nodes = sorted({edge[key] for edge in edges for key in ("from", "to")})
    if (len(nodes), len(edges)) != (receipt["nodes"], receipt["directed_edges"]):
        raise ValueError("Reconstructed network counts differ from the receipt")
    detours = []
    for row in receipt["results"]:
        origin, destination = row["origin_osm_node"], row["destination_osm_node"]
        scenarios = (
            ("mapped_scenario", edges),
            ("crossing_removed_scenario", [edge for edge in edges if edge["way"] != row["way_id"]]),
        )
        for name, scenario in scenarios:
            result = accessibility(nodes, scenario, origin, [destination], "walk")["destinations"][0]
            if result != row[name]:
                raise ValueError(f"Crossing {row['way_id']} differs in {name}")
        before = row["mapped_scenario"]["minutes"]
        after = row["crossing_removed_scenario"]["minutes"]
        if before is not None and after is not None:
            detours.append(after - before)
    return {"scenario_pairs": len(receipt["results"]), "pairs_with_detours": sum(t > 0 for t in detours),
            "median_added_minutes": round(median(detours), 3) if detours else None,
            "maximum_added_minutes": round(max(detours), 3) if detours else None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.snapshot, json.loads(args.receipt.read_bytes())), indent=2))
