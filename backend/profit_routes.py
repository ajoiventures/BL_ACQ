"""Authenticated review-only adapter for the bounded profit cash reviewer."""
from typing import Any

from fastapi import Body, Depends, HTTPException

from .core.profit_review import ProfitReviewError, coach_acquisition, review


def register(app, actor, permit, conn, event):
    def review_role(who=Depends(actor)):
        if who not in ("FOUNDER", "SW-13"):
            raise HTTPException(403, "Profit review requires founder or auditor access")
        return who

    def run_review(body, who, calculate, action, identifier):
        domain = body.get("domain")
        if type(domain) is not str:
            raise HTTPException(422, "domain requires a string")
        # A review request creates neither an operational record nor authority.
        permit(who, domain)
        try:
            report = calculate(body)
        except ProfitReviewError as exc:
            raise HTTPException(422, str(exc)) from exc
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            event(db, domain, who, action, report[identifier], {"report": report})
            audit_hash = db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()[0]
        return {"report": report, "audit_hash": audit_hash}

    @app.post("/api/profit-review")
    def profit_review(body: dict[str, Any] = Body(...), who=Depends(review_role)):
        return run_review(body, who, review, "PROFIT_REVIEW", "review_id")

    @app.post("/api/acquisition-coach")
    def acquisition_coach(body: dict[str, Any] = Body(...), who=Depends(review_role)):
        return run_review(body, who, coach_acquisition, "ACQUISITION_COACH", "plan_id")
