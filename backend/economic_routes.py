"""Authenticated, audit-only adapters for economic-development analyst screens."""
from typing import Any

from fastapi import Body, Depends, HTTPException, Query

from .core.economic_development import EconomicDevelopmentError, baseline, contract, data_center


def register(app, actor, permit, conn, event):
    def review_role(who=Depends(actor)):
        if who not in ("FOUNDER", "SW-13"):
            raise HTTPException(403, "Economic development screening requires founder or auditor access")
        return who

    def run_review(body, who, calculate, action):
        domain = body.get("domain")
        if type(domain) is not str:
            raise HTTPException(422, "domain requires a string")
        permit(who, domain)
        try:
            report = calculate(body)
        except EconomicDevelopmentError as exc:
            raise HTTPException(422, str(exc)) from exc
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            event(db, domain, who, action, report["review_id"], {"report": report})
            audit_hash = db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()[0]
        return {"report": report, "audit_hash": audit_hash}

    @app.post("/api/economic-development/baseline")
    def economic_baseline(body: dict[str, Any] = Body(...), who=Depends(review_role)):
        return run_review(body, who, baseline, "ECONOMIC_BASELINE_SCREENING")

    @app.post("/api/economic-development/data-center")
    def data_center_screening(body: dict[str, Any] = Body(...), who=Depends(review_role)):
        return run_review(body, who, data_center, "DATA_CENTER_SCREENING")

    @app.get("/api/economic-development/contract")
    def economic_contract(domain: str = Query(default="MAIN_STREET_INSTITUTIONAL"), who=Depends(review_role)):
        permit(who, domain)
        definitions = contract()
        if domain not in definitions["allowed_domains"]:
            raise HTTPException(422, "Economic development requires COMMERCIAL or MAIN_STREET_INSTITUTIONAL domain")
        return definitions
