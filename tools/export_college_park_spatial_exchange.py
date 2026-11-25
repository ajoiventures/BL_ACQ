"""Publish and independently read back the pinned College Park survey in GDAL."""
import argparse
import ctypes
from ctypes import wintypes
from hashlib import sha256
import json
from math import isclose
from pathlib import Path

from osgeo import gdal, ogr, osr

FIELDS = (
    ("county_parcel_id", ogr.OFTString),
    ("county_object_ids", ogr.OFTString),
    ("parcel_area_us_survey_sqft", ogr.OFTReal),
    ("overlap_us_survey_sqft", ogr.OFTReal),
    ("overlap_fraction", ogr.OFTReal),
)


def verified(path, digest):
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != digest:
        raise ValueError(f"Changed source: {path.name}")
    return json.loads(raw)


def peak_working_set():
    if not hasattr(ctypes, "windll"):
        return None
    class Counters(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("page_faults", wintypes.DWORD),
                    *[(key, ctypes.c_size_t) for key in ("peak", "working", "peak_paged",
                      "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]]
    counters = Counters()
    counters.size = ctypes.sizeof(counters)
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    read = ctypes.windll.psapi.GetProcessMemoryInfo
    read.argtypes = (wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD)
    if not read(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.size):
        raise ctypes.WinError()
    return counters.peak


def reference(code):
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(code)
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return srs


def publish(evidence, output):
    gdal.UseExceptions()
    comparison = json.loads((evidence / "published-city-geometry-comparison.json").read_bytes())
    pins = dict(comparison["parcel_input_sha256"])
    receipt_name = comparison["layers"]["program"]["geometry_receipt"]
    receipt = json.loads((evidence / receipt_name).read_bytes())
    boundary_file = receipt_name.replace(".receipt.json", ".json")
    pins[boundary_file] = receipt["sha256"]
    projected = reference(2236)
    projection = osr.CoordinateTransformation(reference(4326), projected)
    boundary = verified(evidence / boundary_file, pins[boundary_file])
    if boundary["spatialReference"]["latestWkid"] != 2236:
        raise ValueError("Unexpected City CRS")
    city, = boundary["features"]
    district = ogr.CreateGeometryFromJson(json.dumps({
        "type": "Polygon", "coordinates": city["geometry"]["rings"]}))
    district.AssignSpatialReference(projected)

    parcels = verified(evidence / "unique-parcel-input.geojson", pins["unique-parcel-input.geojson"])
    component = verified(evidence / "parcel-component-disposition.geojson",
                         pins["parcel-component-disposition.geojson"])
    features = [*parcels["features"], component]
    if len(features) > 1000:
        raise ValueError("Pilot feature limit exceeded")
    rows = {}
    paths = {"GPKG": output / "college-park-v1.gpkg"}
    if paths["GPKG"].exists():
        raise FileExistsError("Choose an unused export directory")
    datasets = [ogr.GetDriverByName("GPKG").CreateDataSource(str(paths["GPKG"]))]
    layers = [datasets[0].CreateLayer("college_park", projected, ogr.wkbMultiPolygon)]
    for layer in layers:
        for name, datatype in FIELDS:
            layer.CreateField(ogr.FieldDefn(name, datatype))
    for f in features:
        props = f["properties"]
        pid = props.get("PARCEL", props.get("county_parcel_id"))
        if not pid or pid in rows:
            raise ValueError("Missing or duplicate county ID")
        ids = [props["OBJECTID"]] if "OBJECTID" in props else [c["OBJECTID"] for c in props["components"]]
        geom = ogr.CreateGeometryFromJson(json.dumps(f["geometry"]))
        geom.FlattenTo2D()
        geom.Transform(projection)
        geom = ogr.ForceToMultiPolygon(geom)
        if not geom.IsValid() or geom.GetArea() <= 0:
            raise ValueError("Invalid projected parcel")
        area = geom.GetArea()
        overlap = geom.Intersection(district).GetArea() if geom.Intersects(district) else 0.0
        values = (pid, ",".join(map(str, ids)), area, overlap, overlap / area)
        rows[pid] = (values, geom)
        for layer in layers:
            record = ogr.Feature(layer.GetLayerDefn())
            for (name, _), value in zip(FIELDS, values, strict=True):
                record.SetField(name, value)
            record.SetGeometry(geom)
            layer.CreateFeature(record)
    for ds in datasets:
        ds.Close()

    summary = {}
    for driver, path in paths.items():
        ds = ogr.Open(str(path))
        layer = ds.GetLayer()
        srs = layer.GetSpatialRef()
        assert srs.GetAuthorityCode(None) == "2236" and srs.GetLinearUnits() == projected.GetLinearUnits()
        checked = set()
        for f in layer:
            pid = f["county_parcel_id"]
            expected, geom = rows[pid]
            assert pid not in checked and f["county_object_ids"] == expected[1]
            assert all(isclose(f[name], value, abs_tol=1e-8)
                       for (name, _), value in zip(FIELDS[2:], expected[2:], strict=True))
            assert f.GetGeometryRef().Equals(geom)
            checked.add(pid)
        assert checked == rows.keys()
        summary[driver] = {"file": path.name, "sha256": sha256(path.read_bytes()).hexdigest(),
                           "rows": len(checked)}
        ds.Close()
    positive = sum(values[3] > 0 for values, _ in rows.values())
    assert positive == comparison["coverage"]["positive_overlap"]
    return {"contract": "college-park-survey-exchange/1", "gdal": gdal.VersionInfo("RELEASE_NAME"),
            "epsg": 2236, "area_units": "US survey square feet", "source_sha256": pins,
            "outputs": summary, "positive_overlap": positive, "peak_working_set_bytes": peak_working_set(),
            "basis": "City map and retained county survey envelope", "legal_or_survey_acceptance": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = publish(args.evidence, args.output)
    with (args.output / "college-park-survey-exchange.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result))
