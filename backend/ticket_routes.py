from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from .core import release_sync, tickets


class TicketTransition(BaseModel):
    target: str
    version: int = Field(ge=1)
    evidence: str = Field(min_length=1, max_length=12000)
    source: str = Field(min_length=1, max_length=2000)


def register(app, actor, permit, conn, event):
    with conn() as db:
        tickets.import_manifest(db,event)

    def project_role(who=Depends(actor)):
        if who not in ("FOUNDER","SW-13"):
            raise HTTPException(403,"Integrated project tickets require founder or auditor access")
        return who

    def access(who, record):
        if record["domain"] != "PROJECT_INTERNAL":
            permit(who,record["domain"])

    @app.get("/api/tickets")
    def list_tickets(area:str="",status:str="",owner:str="",q:str="",who=Depends(project_role)):
        with conn() as db:
            rows = tickets.listing(db,area,owner=owner,q=q)
            for row in rows:
                access(who,row)
        planning, approvals = tickets.canonical_register()
        for row in rows:
            canonical_closed = tickets.is_canonically_closed(planning, row["id"])
            row["effective_status"] = "closed" if canonical_closed else row["status"]
            if row["status"] == "closed":
                continue
            metadata = planning.get(row["id"], {})
            if canonical_closed and row["id"] in approvals:
                row["canonical_approval"] = approvals[row["id"]]
            if canonical_closed:
                continue
            row["next_action"] = metadata.get("next_action") or ""
            row["blocker"] = metadata.get("blocker") or ""
        return [row for row in rows if not status or row["effective_status"] == status]

    @app.get("/api/tickets/{ticket_id}/history")
    def ticket_history(ticket_id:str,who=Depends(project_role)):
        with conn() as db:
            try:
                access(who,tickets.get(db,ticket_id))
                return tickets.history(db,ticket_id)
            except tickets.TicketError as exc:
                raise HTTPException(exc.code,str(exc)) from exc

    @app.get("/api/tickets/{ticket_id}/release-evidence")
    def ticket_release_evidence(ticket_id: str, who=Depends(project_role)):
        with conn() as db:
            try:
                access(who, tickets.get(db, ticket_id))
                return {"release_evidence": release_sync.latest_ticket_evidence(db, ticket_id)}
            except tickets.TicketError as exc:
                raise HTTPException(exc.code, str(exc)) from exc

    @app.post("/api/tickets/{ticket_id}/transition")
    def change_ticket(ticket_id:str,body:TicketTransition,who=Depends(project_role)):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                record = tickets.get(db,ticket_id)
                access(who,record)
                planning, _ = tickets.canonical_register()
                if tickets.is_canonically_closed(planning, ticket_id):
                    raise HTTPException(409, "Ticket is already complete in the canonical register")
                return tickets.transition(db,event,who,record,**body.model_dump())
            except tickets.TicketError as exc:
                raise HTTPException(exc.code,str(exc)) from exc
