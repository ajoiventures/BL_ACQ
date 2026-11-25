"""Verify the extraction benchmark's acceptance checks independently of providers."""

from scripts.local_model import CASES, grade


def test_grader_rejects_document_instruction_and_stale_deadline():
    injected, kind, due, amount = CASES[-2]
    valid = {"kind": kind, "due": due, "amount": amount, "quote": "Payment due 2027-02-12."}
    assert grade(injected, (kind, due, amount), valid)
    assert not grade(injected, (kind, due, amount), {**valid, "amount": "999"})
    assert not grade(injected, (kind, due, amount), {**valid, "approve": True})
    revised, kind, due, amount = CASES[-1]
    valid = {"kind": kind, "due": due, "amount": amount, "quote": "Pay by 2027-03-19."}
    assert grade(revised, (kind, due, amount), valid)
    assert not grade(revised, (kind, due, amount), {**valid, "quote": "The old due date 2027-03-05"})
    assert not grade(revised, (kind, due, amount), {**valid, "quote": due})
    assert not grade(revised, (kind, due, amount), {**valid, "quote": revised})
    assert grade(revised, (kind, due, amount), {**valid, "quote": "Pay by 2027-03-19"})
    assert not grade(revised, (kind, due, amount), [valid])


def test_comparator_records_field_failures_and_keeps_running_after_provider_error():
    from scripts.local_model import benchmark

    def adapter(document):
        if document == CASES[0][0]:
            raise ConnectionError("disposable provider outage")
        return {"kind": "invoice", "due": None, "amount": "999", "quote": None}

    report = benchmark(adapter, CASES[:2])
    assert report["total"] == 2 and report["passed"] == 0
    assert report["cases"][0]["provider_error"] == "ConnectionError"
    assert report["cases"][1]["field_mismatches"] == ["kind", "amount"]
    assert all(row["seconds"] >= 0 for row in report["cases"])


def test_local_proposal_falls_back_without_promoting_model_output(monkeypatch):
    from scripts import local_model

    document = "Invoice. Pay by 2027-03-19."
    assert local_model.propose_or_review(document, None)["reason"] == "MODEL_NOT_CONFIGURED"

    def offline(*args):
        raise ConnectionError("provider unavailable")

    monkeypatch.setattr(local_model, "extract", offline)
    assert local_model.propose_or_review(document, "local")["status"] == "MANUAL_REVIEW"
    draft = {"kind": "invoice", "due": "2027-03-19", "amount": None, "quote": "Pay by 2027-03-19"}
    monkeypatch.setattr(local_model, "extract", lambda *args: draft)
    assert local_model.propose_or_review(document, "local")["status"] == "UNVERIFIED"
    draft["quote"] = draft["due"]
    assert local_model.propose_or_review(document, "local")["proposal"] is None


def test_local_proposal_rejects_invalid_calendar_date_and_amount(monkeypatch):
    from scripts import local_model

    document = "Invoice. Pay by 2027-02-30."
    draft = {"kind": "invoice", "due": "2027-02-30", "amount": None, "quote": "Pay by 2027-02-30"}
    monkeypatch.setattr(local_model, "extract", lambda *args: draft)
    assert local_model.propose_or_review(document, "local")["reason"] == "INVALID_PROPOSAL"
    draft.update(due=None, quote=None, amount="null")
    assert local_model.propose_or_review(document, "local")["reason"] == "INVALID_PROPOSAL"
