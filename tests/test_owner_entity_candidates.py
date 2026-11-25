import pytest

from backend.core.owner_entity_candidates import reconcile


def test_shared_agent_cannot_merge_entities_or_fill_an_unresolved_owner():
    observations = [
        dict(document_id="L00000000001", entity_name="Example A LLC", agent_id="same-agent",
             source_ref="fixture/sunbiz/1", observed_date="2026-10-01"),
        dict(document_id="L00000000002", entity_name="Example B LLC", agent_id="same-agent",
             source_ref="fixture/sunbiz/2", observed_date="2026-10-01"),
    ]
    mortgage = dict(parcel_id="12095:fixture", instrument_id="mortgage-1", kind="MORTGAGE",
                    source_ref="fixture/records/1", observed_date="2026-10-01")
    candidate = reconcile("12095:fixture", "Example A LLC", observations, [mortgage], cutoff="2026-10-02")
    assert [row["document_id"] for row in candidate["candidates"]] == ["L00000000001"]
    assert candidate["accepted_owner_id"] is None
    assert candidate["mortgage_status"] == "UNKNOWN"
    assert candidate["instruments"][0]["review_status"] == "REVIEW_REQUIRED"
    unresolved = reconcile("12095:fixture", "Unknown Owner LLC", observations, [], cutoff="2026-10-02")
    assert unresolved["candidate_state"] == "UNRESOLVED"
    with pytest.raises(ValueError, match="cutoff"):
        reconcile("12095:fixture", "Unknown Owner LLC", observations, [], cutoff="2026-01-01")
