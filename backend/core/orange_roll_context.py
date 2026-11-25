"""Bind selected historical sales and county points to pinned Orange roll IDs."""
from collections import defaultdict
import csv
import hashlib
import io
from pathlib import Path
import re

from .acquisition_source_gate import Purpose, route
from .state_parcel_research import orange_id_candidate

SALES_SHA256 = "63d81cdcdf8d6c7bc88e643d1639538e2bfce6522804f78a749931f7230edf12"
POINTS_SHA256 = "04dae2b6a65537a9fcd675c9dc258643ae4db939e1bb45a66856c98c9e25abe4"
SALES_FIELDS = ("PARCEL_ID", "SALE_YR", "SALE_MO", "SALE_PRC", "QUAL_CD", "VI_CD",
                "MULTI_PAR_SAL", "SAL_CHG_CD", "CLERK_NO", "OR_BOOK", "OR_PAGE",
                "spatial_economic_cohort")
POINTS_FIELDS = ("OBJECTID", "PARCEL", "SITUS", "LATITUDE", "LONGITUDE", "NC_FLAG")


def pinned_rows(path, sha256, fields, max_rows):
    with path.open("rb") as stream:
        raw = stream.read(500_001)
    if len(raw) > 500_000 or hashlib.sha256(raw).hexdigest() != sha256:
        raise ValueError(f"Orange source digest or size mismatch: {path.name}")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != fields:
        raise ValueError("unexpected Orange source fields")
    rows = list(reader)
    if not 0 < len(rows) <= max_rows or any(None in row or None in row.values() for row in rows):
        raise ValueError("unexpected Orange source row structure")
    return rows


def bind_orange_context(directory, records):
    """Return typed research observations and accompanying source revision metadata."""
    directory = Path(directory)
    by_state = {}
    county_keys = set()
    for record in records:
        source_id = record["source_parcel_id"]
        key = record["parcel_key"]
        if key != "12095:" + orange_id_candidate(source_id):
            raise ValueError("Orange source and county identifiers disagree")
        if source_id in by_state or key in county_keys:
            raise ValueError("Duplicate Orange parcel identity")
        by_state[source_id] = key
        county_keys.add(key)
    sales = defaultdict(list)
    points = {}
    for row in pinned_rows(directory / "parcel-sales.csv", SALES_SHA256, SALES_FIELDS, 1200):
        key = by_state.get(row["PARCEL_ID"])
        if (key is None or row["SALE_YR"] not in {"2025", "2026"}
                or not re.fullmatch(r"0[1-9]|1[0-2]", row["SALE_MO"])):
            raise ValueError("sale outside the pinned roll scope")
        amount = row["SALE_PRC"]
        if amount and not re.fullmatch(r"[0-9]{1,12}", amount):
            raise ValueError("invalid reported sale amount")
        sales[key].append({
            "source_parcel_id": row["PARCEL_ID"], "clerk_reference": row["CLERK_NO"] or None,
            "record_book": row["OR_BOOK"] or None, "record_page": row["OR_PAGE"] or None,
            "sale_month": f"{row['SALE_YR']}-{row['SALE_MO']}",
            "reported_consideration_dollars": int(amount) if amount else None,
            "qualification_code": row["QUAL_CD"], "improvement_code": row["VI_CD"],
            "multiple_parcel_flag": row["MULTI_PAR_SAL"] or None,
            "parcel_change_code": row["SAL_CHG_CD"] or None,
        })
    for row in pinned_rows(directory / "county-centroids.csv", POINTS_SHA256, POINTS_FIELDS, 400):
        key = "12095:" + row["PARCEL"]
        if key not in county_keys or key in points:
            raise ValueError("unexpected or ambiguous county point identity")
        lat, lon = float(row["LATITUDE"]), float(row["LONGITUDE"])
        if not (28 < lat < 29 and -82 < lon < -80):
            raise ValueError("county point out of scope")
        points[key] = {"county_feature_id": int(row["OBJECTID"]), "latitude": lat,
                       "longitude": lon, "crs": "EPSG:4326", "kind": "ASSESSOR_INTERNAL_POINT"}
    meta = {
        "contract": "br-orange-roll-context/2",
        "sales": {"source": "FDOR_ORANGE_FINAL_SDF_2026", "projection_sha256": SALES_SHA256,
                  "role": "recorded_transfer_observations", "effective_precision": "month",
                  "source_gate": route("FDOR", Purpose.COMMERCIAL_RESEARCH)},
        "point": {"source": "OCPA_PARCEL_LAYER_4", "projection_sha256": POINTS_SHA256,
                  "role": "assessor_internal_point_observations", "capture_local_date": "2026-11-24",
                  "source_gate": route("COUNTY_GIS", Purpose.COMMERCIAL_RESEARCH)},
        "sale_observations": sum(map(len, sales.values())), "parcels_with_sale_observations": len(sales),
        "parcels_with_county_points": len(points),
    }
    return {
        key: {"recorded_sales": sorted(sales.get(key, []),
                                       key=lambda r: (r["sale_month"], r["clerk_reference"] or "")),
              "county_internal_point": points.get(key)}
        for key in county_keys
    }, meta
