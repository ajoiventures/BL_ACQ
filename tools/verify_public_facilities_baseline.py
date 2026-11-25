"""Validate BR-T140's bounded facilities evidence before using it in a comparison."""
import json
from pathlib import Path


def compare_observations(left, right):
    """Compare numeric observations only when their definitions and periods match."""
    if left is None or right is None:
        return "UNKNOWN"
    if left["period"] != right["period"]:
        return "PERIOD_MISMATCH"
    if left["metric"] != right["metric"]:
        return "METRIC_MISMATCH"
    if left["authority"] == right["authority"] and left["value"] != right["value"]:
        return "CONFLICT"
    return "COMPARABLE"


def verify_baseline(root):
    facilities = json.loads((root / "public-facilities-baseline.json").read_bytes())["facilities"]
    schools = {row["facility"]: row for row in facilities if "enrollment" in row}
    edgewater = schools["Edgewater High School"]["capacity"]
    seminole = schools["Seminole High School"]
    assert edgewater["utilization_percent"] == round(
        100 * edgewater["same_report_enrollment"] / edgewater["district_reported_capacity"], 1
    )
    assert seminole["historical_capacity"]["status"] == "historical_only"
    assert seminole["capacity"] is None

    records = json.loads((root / "public-facilities-fire-performance.json").read_bytes())["records"]
    timings = [dict(row, value=row["actual_percent"]) for row in records if "actual_percent" in row]
    assert len(timings) == 2
    sample = timings[0]
    probes = {
        "published_fire_metrics": compare_observations(*timings),
        "missing_measure": compare_observations(sample, None),
        "earlier_vintage": compare_observations(sample, dict(sample, period="FY2021-22")),
        "same_authority_conflict": compare_observations(sample, dict(sample, value=41)),
        "identical_replay": compare_observations(sample, sample),
    }
    assert probes == {
        "published_fire_metrics": "METRIC_MISMATCH",
        "missing_measure": "UNKNOWN",
        "earlier_vintage": "PERIOD_MISMATCH",
        "same_authority_conflict": "CONFLICT",
        "identical_replay": "COMPARABLE",
    }
    return {"facility_count": len(facilities), "checks": probes}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1] / "docs" / "acquisition"
    print(json.dumps(verify_baseline(root), indent=2))
