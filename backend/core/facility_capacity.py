"""Exact-scope public facility evidence for BR-T140."""
from datetime import date
from decimal import Decimal, InvalidOperation

SCOPE_FIELDS = ("facility_id", "service_area_revision", "metric", "unit")


def assess_capacity(scope, records, *, as_of):
    """Resolve matching dated evidence without treating demand as capacity."""
    if any(not scope.get(key) for key in SCOPE_FIELDS):
        raise ValueError("Capacity requires a facility, service area revision, metric and unit")
    effective = []
    excluded = []
    stale = False
    for record in records:
        if any(record.get(key) != scope[key] for key in SCOPE_FIELDS):
            continue
        source = record.get("source")
        observed = date.fromisoformat(record["observed_on"])
        valid_through = date.fromisoformat(record["valid_through"])
        if not source or valid_through < observed:
            raise ValueError("Capacity evidence needs a source and valid observation window")
        if observed > as_of:
            excluded.append(source)
            continue
        if valid_through < as_of:
            excluded.append(source)
            stale = True
            continue
        if record.get("value") is None:
            excluded.append(source)
            continue
        try:
            value = Decimal(str(record["value"]))
        except InvalidOperation as exc:
            raise ValueError("Capacity evidence must be numeric") from exc
        if not value.is_finite() or value < 0:
            raise ValueError("Capacity evidence must be finite and nonnegative")
        effective.append((source, value))
    values = {value for _, value in effective}
    if len(values) > 1:
        state = "CONFLICT"
    elif values:
        state = "SOURCE_REPORTED"
    else:
        state = "STALE" if stale else "MISSING"
    return {
        "status": state,
        "value": str(effective[0][1]) if state == "SOURCE_REPORTED" else None,
        "sources": sorted({source for source, _ in effective}),
        "excluded_sources": sorted(set(excluded)),
    }


def public_office_schedule(hours, *, on_date):
    """Resolve published office hours while leaving appointments and capacity unknown."""
    if not hours or date.fromisoformat(hours["observed_date"]) > on_date:
        return {"status": "UNKNOWN", "hours": None, "source": None}
    if on_date.isoformat() in hours.get("announced_closures", ()):
        return {"status": "ANNOUNCED_CLOSURE", "hours": None,
                "source": hours.get("closure_source", hours["source"])}
    if on_date.weekday() >= 5 and hours.get("weekend") == "closed":
        return {"status": "REGULARLY_CLOSED", "hours": None, "source": hours["source"]}
    window = hours.get("weekdays") if on_date.weekday() < 5 else None
    return {"status": "PUBLISHED_WEEKLY_HOURS" if window else "UNKNOWN",
            "hours": window, "source": hours["source"]}
