"""Model bounded centerline travel from parcel-near street nodes."""
import argparse
import hashlib
import json
from math import dist
from pathlib import Path

from backend.core.spatial_constraints import screen_network_access


def run(directory):
    measurement = json.loads((directory / "street-centerline-research-receipt.json").read_bytes())
    path = directory / "dated-street-network-source.json"
    raw = path.read_bytes()
    source = json.loads(raw)
    revision = hashlib.sha256(raw).hexdigest()
    metadata = json.loads((directory / "dated-street-network-provenance.json").read_bytes())
    if revision != metadata["sha256"] or source["spatialReference"].get("latestWkid", source["spatialReference"]["wkid"]) != 2236:
        raise ValueError("Unexpected network revision or coordinate system")
    nodes, edges, endpoints = set(), [], {}
    for segment in source["features"]:
        a = segment["attributes"]
        if a["Status"] != "CURRENT" or a["OneWayDir"] != "B" or not a["Speed"] or len(segment["geometry"]["paths"]) != 1:
            raise ValueError("Unsupported segment status, speed, direction or geometry")
        points = segment["geometry"]["paths"][0]
        start = f"{tuple(points[0])}/{a['FromElev']}"
        end = f"{tuple(points[-1])}/{a['ToElev']}"
        endpoints[a["OBJECTID"]] = (start, end)
        nodes.update((start, end))
        minutes = sum(dist(x, y) for x, y in zip(points, points[1:])) / (a["Speed"] * 5280 / 60)
        for left, right in ((start, end), (end, start)):
            edges.append({"from":left,"to":right,"minutes":minutes,"mode":"drive","state":"OPEN"})

    results = []
    for parcel in measurement["parcels"]:
        nearest = parcel["nearby_segments"][0]
        origin, opposite = endpoints[nearest["OBJECTID"]]
        other = next(s for s in parcel["nearby_segments"] if s["FullStreetName"] != nearest["FullStreetName"])
        targets = list(dict.fromkeys([opposite, *endpoints[other["OBJECTID"]]]))
        targets = [target for target in targets if target != origin]
        access = screen_network_access(
            nodes=sorted(nodes),edges=edges,origin=origin,destinations=targets,
            mode="drive",network_revision=revision,authority_source=measurement["source_layer"],
            observed_date=metadata["observed_utc"][:10],cutoff=metadata["observed_utc"][:10],
            phases=[],network_complete=False,
        )
        results.append(dict(parcel_id=parcel["parcel_id"],origin_segment=nearest["OBJECTID"],
                            origin=origin,comparison_segment=other["OBJECTID"],access=access))
    return dict(source_segments=len(endpoints), directed_edges=len(edges),results=results,
                scope="Endpoint-connected centerline proxy assuming the inventory Speed field is mph. Current inventory is treated as OPEN only in this supplied graph. No parcel-to-road connection, turns, travel conditions or legal access verified.")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    report=run(args.directory)
    with args.output.open("x",encoding="utf-8") as output:
        json.dump(report,output,indent=2)
        output.write("\n")
    print(report["source_segments"],report["directed_edges"],len(report["results"]))
