import hashlib,json
from collections import Counter
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode
from urllib.request import urlopen
from datetime import datetime,timezone
from tools.prepare_corridor_coverage import sha
from tools.prepare_spatial_evidence import polygon,prepare

def main():
    root=Path("docs/acquisition")
    out=root/"college-park-coverage"
    historic=json.loads((root/"run/138H/candidate-ids.json").read_bytes())
    boundary=root/"run/137L/college-park-boundary.geojson"

    def get(name,url):
        with urlopen(url,timeout=40) as response:
            raw=response.read(4_000_001)
        if len(raw)>4_000_000:
            raise ValueError("response cap")
        p=out/"raw"/f"{name}.json"
        p.write_bytes(raw)
        (out/"raw"/f"{name}.receipt.json").write_text(json.dumps({
            "url":url,"utc":datetime.now(timezone.utc).isoformat(),
            "sha256":hashlib.sha256(raw).hexdigest(),"bytes":len(raw)
        },indent=2))
        return p,json.loads(raw)

    _,ids=get("ids",historic["ids_url"])
    _,count=get("count",historic["count_url"])
    ids=sorted(ids["objectIds"])
    assert len(ids)==len(set(ids))==count["count"]<=1000
    candidate=out/"candidate.json"
    candidate.write_text(json.dumps({**historic,"count":len(ids),"objectIds":ids,
                                    "observed_utc":datetime.now(timezone.utc).isoformat()},indent=2))

    def pull(offset):
        requested=ids[offset:offset+50]
        url=historic["source"]+"?"+urlencode({
            "objectIds":",".join(map(str,requested)),"f":"geojson","outSR":4326,
            "returnGeometry":"true","outFields":"OBJECTID,PARCEL,DOR_CODE,ACREAGE,LIVING_AREA,TOTAL_MKT",
        })
        path,page=get(f"geometry_{offset:04}",url)
        if sorted(f["properties"]["OBJECTID"] for f in page["features"]) != requested:
            raise ValueError("county geometry ID coverage mismatch")
        manifest=out/"raw"/f"geometry_{offset:04}.manifest.json"
        manifest.write_text(json.dumps({"source":url,"requested_ids":requested,"sha256":sha(path)},indent=2))
        return path,manifest,sha(manifest)

    with ThreadPoolExecutor(max_workers=4) as pool:
        batches=list(pool.map(pull,range(0,len(ids),50)))
    _,after=get("ids_after",historic["ids_url"])
    if ids!=sorted(after["objectIds"]):
        raise ValueError("source envelope changed during capture")
    features=[f for path,_,_ in batches for f in json.loads(path.read_bytes())["features"]]
    parcel_counts=Counter(f["properties"]["PARCEL"] for f in features)
    duplicates={key:value for key,value in parcel_counts.items() if value>1}
    unique=out/"unique-parcel-input.geojson"
    unique.write_text(json.dumps({"type":"FeatureCollection","features":[
        f for f in features if f["properties"]["PARCEL"] not in duplicates
    ]}))
    geo=prepare(unique,boundary,parcel_sha=sha(unique),boundary_sha=sha(boundary))
    report={"candidate_count":len(ids),"captured_count":len(features),"remaining_count":len(ids)-len(features),
            "distinct_parcel_ids":len(parcel_counts),"quarantined_multiple_feature_ids":duplicates,
            "polygon_intersections_computed":len(geo["features"]),
            "provisional_relations":dict(Counter(
                f["properties"]["provisional_boundary_relation"] for f in geo["features"])),
            "accepted_membership_count":None,"provisional_boundary_sha256":sha(boundary),
            "source_snapshot_atomic":False}
    source=json.loads((out/"orlando-main-streets.geojson").read_bytes())
    target=polygon(json.loads(boundary.read_bytes())["features"][0])
    city_polygons = [polygon(f) for f in source["features"] if f.get("geometry")]
    exact = sum(geometry.equals(target) for geometry in city_polygons)
    ratio = max((g.intersection(target).area / g.union(target).area for g in city_polygons), default=None)
    report.update(original_city_export_best_overlap_fraction=ratio,historical_ids_removed=len(set(historic["objectIds"])-set(ids)),
                  historical_ids_added=len(set(ids)-set(historic["objectIds"])),
                  original_city_export_sha256=sha(out/"orlando-main-streets.geojson"),
                  original_city_export_exact_polygon_matches=exact,
                  original_city_export_feature_count=len(source["features"]),
                  original_city_export_usable_geometry_count=len(city_polygons))
    (out/"coverage.json").write_text(json.dumps(report,indent=2))
    (out/"spatial-coverage.geojson").write_text(json.dumps(geo))
    print({k:report[k] for k in ("candidate_count","captured_count","remaining_count","provisional_relations","historical_ids_removed","historical_ids_added","original_city_export_exact_polygon_matches")})


if __name__ == "__main__":
    main()
