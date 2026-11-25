"""Read the College Park baseline and verify its retained source receipts."""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from xml.etree import ElementTree


DIRECTORY = "docs/economic-development/"


def load_verified_baseline(root):
    path = root / (DIRECTORY + "college-park-integrated-baseline.json")
    raw = path.read_bytes()
    baseline = json.loads(raw)
    sources = {}
    for relative, expected in baseline["source_sha256"].items():
        source = root / relative
        data = source.read_bytes()
        if sha256(data).hexdigest() != expected:
            raise ValueError(f"Stale baseline source: {relative}")
        sources[source.name] = json.loads(data)

    metrics = {(r["name"], r.get("method")): r for r in baseline["metrics"]}
    housing = sources["college-park-reported-unit-baseline.json"]
    group = housing["groups"]["published_program_intersection"]
    row = metrics["reported_housing_units", None]
    if (row["value"], row["denominator"], row["missing_parcels"], row["period"]) != (
        group["reported_unit_sum"], group["numeric_unit_parcels"],
        group["unknown_unit_value"], housing["assessment_year"],
    ):
        raise ValueError("Housing baseline differs from assessor receipt")
    receipts = sources["college-park-business-receipt-baseline.json"]
    open_cases, = [r for r in receipts["results"] if r["license_status"] == "Open"]
    row = metrics["open_business_receipt_cases", None]
    if (row["value"], row["period"], row["denominator"]) != (
        int(open_cases["distinct_case_numbers"]), receipts["observed_date"], None,
    ):
        raise ValueError("Business baseline differs from receipt case counts")
    employment = sources["college-park-lodes-employment.json"]
    if employment["boundary_sha256"] != baseline["municipal_boundary_sha256"] or (
        receipts["boundary_sha256"] != baseline["municipal_boundary_sha256"]
    ):
        raise ValueError("Employment or business boundary revision differs")
    for metric, measure in (("workplace_jobs", "wac"), ("residence_based_jobs", "rac")):
        for method, selection in employment["sets"].items():
            source = employment["measures"][measure]["slices"][method]
            row = metrics[metric, method]
            if (row["value"], row["denominator"], row["blocks_without_source_rows"], row["period"]) != (
                source["jobs"], len(selection), source["blocks_without_rows"], employment["year"],
            ):
                raise ValueError(f"Employment baseline differs for {metric}/{method}")
    citywide = baseline["citywide_comparison"]
    city_employment = sources[Path(citywide["employment_comparator"]).name]
    city_housing = sources[Path(citywide["assessor_housing_comparator"]).name]
    if city_employment["place_id"] != citywide["place_id"] or city_housing["place_id"] != citywide["place_id"]:
        raise ValueError("Citywide source place differs from the comparator")
    if city_employment["employment_year"] != employment["year"] or city_employment["job_type"] != employment["job_type"]:
        raise ValueError("Citywide and district employment releases differ")
    for name, city_measure in city_employment["measures"].items():
        if city_measure["source_sha256"] != employment["measures"][name]["source_sha256"]:
            raise ValueError("Citywide and district employment releases differ")
        if city_measure["blocks_with_source_rows"] + city_measure["blocks_without_source_rows"] != city_employment["blocks"]:
            raise ValueError("Citywide employment block denominator differs")
    if (city_housing["roll_archive_sha256"] != housing["roll_archive_sha256"]
            or city_housing["assessment_year"] != housing["assessment_year"]
            or city_housing["parcels_with_numeric_values"] + city_housing["parcels_without_numeric_values"]
            != city_housing["parcel_denominator"]):
        raise ValueError("Citywide assessor source or denominator differs")

    permits = sources[Path(baseline["residential_worktype_context"]).name]
    worktypes = permits["worktypes"]
    if (sum(row["issued"] for row in worktypes.values()) != permits["residential_review_issued_building_permits"]
            or any(not 0 <= row[key] <= row["issued"] for row in worktypes.values()
                   for key in ("final_date", "coo_date", "coc_date"))):
        raise ValueError("Residential permit milestones do not reconcile")

    funding = sources[Path(baseline["transportation"]["funding_evidence"]).name]
    council, = [row for row in funding["records"] if row["funding_state"] == "CITY_REPORTS_COUNCIL_LAP_APPROVAL"]
    tip = funding["regional_tip_comparison"]
    city = funding["city_capital_plan_corroboration"]
    components = {key: Decimal(value) for key, value in council["published_funding_components"].items()}
    if (funding["place_id"] != baseline["place_id"] or funding["currency"] != "USD"
            or council["fdot_project"] != tip["project"] or tip["project"] != city["project"]
            or sum(components.values()) != Decimal(council["published_project_cost"])
            or components["FDOT_LAP"] != Decimal(city["published_amount"])
            or Decimal(tip["fy2026_programmed"]) - components["FDOT_LAP"]
            != Decimal(tip["difference_from_city_reported_lap"])):
        raise ValueError("Edgewater funding phases do not reconcile")

    operations_source = baseline.get("district_operations_context")
    operations = None
    if operations_source:
        evidence = sources[Path(operations_source["receipt"]).name]
        original = (root / operations_source["filing"]).read_bytes()
        if sha256(original).hexdigest() != evidence["original_sha256"]:
            raise ValueError("Operating return digest mismatch")
        filing = ElementTree.fromstring(original)
        form = filing.find(".//{*}IRS990")
        amounts = evidence["reported_amounts"]
        if (filing.findtext(".//{*}EIN") != operations_source["ein"]
                or filing.findtext(".//{*}TaxPeriodEndDt") != evidence["period_end"]
                or form is None or any(form.findtext("{*}" + key) != str(value) for key, value in amounts.items())):
            raise ValueError("Operating return differs from reported amounts")
        operations = {key: evidence[key] for key in (
            "entity", "period_end", "units", "original_sha256", "reported_amounts",
            "current_budget", "vacancy", "turnover",
        )}

    return baseline, {
        "ticket": "BR-T097",
        "baseline_sha256": sha256(raw).hexdigest(),
        "baseline_revision": baseline["revision"],
        "place_id": baseline["place_id"],
        "source_receipts_checked": len(sources),
        "metrics_reconciled": len(metrics),
        "district_residential_permits": permits,
        "edgewater_funding": funding,
        "district_operations": operations,
        "citywide_comparators": {
            "employment": city_employment,
            "assessor_housing": {key: value for key, value in city_housing.items() if key != "districts"},
        },
        "unknown_fields": sorted(key for key, value in baseline["scope_gaps"].items() if value is None),
    }
