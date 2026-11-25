from datetime import date

from backend.core.facility_capacity import assess_capacity


def test_facility_capacity_preserves_missingness_staleness_and_conflict():
    scope = dict(facility_id="clinic", service_area_revision="area-1", metric="seats", unit="people")
    current = {**scope, "value": 0, "source": "a", "observed_on": "2026-01-01",
               "valid_through": "2026-12-31"}
    as_of = date(2026, 6, 1)

    def assess(*records):
        return assess_capacity(scope, records, as_of=as_of)

    assert assess({**current, "metric": "visits"})["status"] == "MISSING"
    assert assess({**current, "service_area_revision": "area-2"})["status"] == "MISSING"
    assert assess({**current, "value": None})["status"] == "MISSING"
    assert assess({**current, "observed_on": "2026-06-02"})["status"] == "MISSING"
    assert assess({**current, "valid_through": "2026-05-31"})["status"] == "STALE"
    assert assess(current)["value"] == "0"
    conflict = assess(current, {**current, "source": "b", "value": 2})
    assert conflict == {"status": "CONFLICT", "value": None, "sources": ["a", "b"],
                        "excluded_sources": []}


def test_announced_closure_takes_precedence_over_published_weekday_hours():
    from backend.core.facility_capacity import public_office_schedule

    hours = {"observed_date": "2026-11-24", "weekdays": ["08:00", "17:00"],
             "weekend": "closed", "source": "schedule", "closure_source": "notice",
             "announced_closures": ["2026-11-25"]}
    closed = public_office_schedule(hours, on_date=date(2026, 11, 25))
    assert closed == {"status": "ANNOUNCED_CLOSURE", "hours": None, "source": "notice"}
    assert public_office_schedule(hours, on_date=date(2026, 11, 23))["status"] == "UNKNOWN"
    assert public_office_schedule(hours, on_date=date(2026, 11, 28))["status"] == "REGULARLY_CLOSED"
    assert public_office_schedule(hours, on_date=date(2026, 11, 30))["hours"] == hours["weekdays"]
