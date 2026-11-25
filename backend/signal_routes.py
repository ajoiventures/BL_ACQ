"""Authenticated source intake, isolated from founder instruction intake."""
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from filing.inbox import MAX_ATTACHMENT_BYTES, defender_scan, file_untrusted_document, read_capture
from pydantic import BaseModel, ConfigDict, Field

from .core import signal_flow as flow
from .core.tickets import TicketError

Topic = Literal["ECONOMIC_DEVELOPMENT","DATA_CENTER","MAIN_STREET","ACQUISITION","CAPITAL","INFORMATIONAL","TOWN_GROWTH","MACRO_FINANCIAL"]
Domain = Literal["COMMERCIAL","MAIN_STREET_INSTITUTIONAL"]

class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Claim(Strict):
    claim: str = Field(min_length=1,max_length=1000)
    quote: str = Field(min_length=1,max_length=2000)

class Capture(Strict):
    request_id: str = Field(min_length=1,max_length=120)
    source_key: str = Field(min_length=1,max_length=120)
    security_domain: Domain
    source_url: str = Field(min_length=8,max_length=2000)
    title: str = Field(min_length=1,max_length=300)
    content: str = Field(min_length=1,max_length=20000)
    capture_kind: Literal["EXCERPT_ONLY"] = "EXCERPT_ONLY"
    published_at: str|None = Field(default=None,max_length=40)
    event_at: str|None = Field(default=None,max_length=40)
    topic_tags: list[Topic] = Field(min_length=1,max_length=8)
    source_claims: list[Claim] = Field(default_factory=list,max_length=10)

class Plan(Strict):
    request_id: str = Field(min_length=1,max_length=120)
    revision: int = Field(ge=1,strict=True)
    disposition: Literal["LINK_EXISTING","INFORMATIONAL","PARKED"] = "LINK_EXISTING"

class Release(Strict):
    request_id: str = Field(min_length=1,max_length=120)
    plan_id: str = Field(min_length=1,max_length=80)
    plan_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


def register(app, actor, permit, conn, event):
    archive_root = Path(os.getenv("BR_SIGNAL_EVIDENCE_ROOT", str(Path(__file__).resolve().parents[1]/"data/signal_evidence")))
    defender_path = os.getenv('BR_ATTACHMENT_DEFENDER_PATH')
    with conn() as db:
        flow.initialize(db)
        db.execute("""CREATE TABLE IF NOT EXISTS retired_signal_attachments (
            source_id TEXT NOT NULL, revision INTEGER NOT NULL, capture_id TEXT NOT NULL,
            PRIMARY KEY(source_id, revision, capture_id)
        )""")

    def reader(who=Depends(actor)):
        if who not in ("FOUNDER","SW-13"):
            raise HTTPException(403,"Source intelligence requires founder or auditor access")
        return who

    def writer(who=Depends(actor)):
        if who != "FOUNDER":
            raise HTTPException(403,"Founder credential required to originate preparation work")
        return who

    def failure(exc):
        raise HTTPException(exc.code,str(exc)) from exc

    @app.get("/api/intelligence-flow/contract")
    def signal_contract(who=Depends(reader)):
        return flow.contract()

    @app.get("/api/intelligence-flow")
    def signal_listing(who=Depends(reader)):
        with conn() as db:
            rows=flow.listing(db)
            for row in rows:
                permit(who,row["security_domain"])
            return rows

    @app.post("/api/intelligence-flow/capture")
    def signal_capture(body:Capture,who=Depends(writer)):
        permit(who,body.security_domain,write=True)
        try:
            with conn() as db:
                db.execute("BEGIN IMMEDIATE")
                return flow.capture(db,event,who,body.model_dump(),archive_root)
        except (flow.SignalError,TicketError) as exc:
            failure(exc)

    @app.get("/api/intelligence-flow/{source_id}")
    def signal_detail(source_id:str,as_of:str|None=Query(default=None,max_length=40),who=Depends(reader)):
        try:
            with conn() as db:
                permit(who,flow.source_domain(db,source_id))
                return flow.detail(db,source_id,as_of)
        except (flow.SignalError,TicketError) as exc:
            failure(exc)
        except ValueError as exc:
            raise HTTPException(422,"as_of requires a valid timezone-aware ISO timestamp") from exc

    @app.get("/api/intelligence-flow/{source_id}/revisions/{revision}/excerpt")
    def signal_excerpt(source_id: str, revision: int, who=Depends(reader)):
        try:
            with conn() as db:
                domain = flow.source_domain(db, source_id)
                permit(who, domain)
                content = flow.read_source_excerpt(db, source_id, revision, domain, archive_root)
        except flow.SignalError as exc:
            failure(exc)
        return Response(content, media_type="text/plain",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @app.post("/api/intelligence-flow/{source_id}/revisions/{revision}/attachments")
    async def signal_upload_attachment(
        source_id: str, revision: int, request: Request,
        filename: str = Query(pattern=r"^[A-Za-z0-9][A-Za-z0-9_. -]{0,119}$"),
        who=Depends(writer),
    ):
        try:
            with conn() as db:
                domain = flow.source_domain(db, source_id)
                permit(who, domain, write=True)
                snapshot_hash = flow.source_revision_hash(db, source_id, revision)
        except flow.SignalError as exc:
            failure(exc)
        if request.headers.get("content-type") != "application/octet-stream":
            raise HTTPException(415, "Send the attachment as application/octet-stream")
        archive = archive_root / domain / "attachments" / source_id
        archive.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=archive) as directory:
            staged = Path(directory) / ("upload-" + filename)
            size = 0
            try:
                with staged.open("xb") as stream:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > MAX_ATTACHMENT_BYTES:
                            raise HTTPException(413, "Attachment exceeds the filing size limit")
                        stream.write(chunk)
            except ClientDisconnect as exc:
                raise HTTPException(400, "Attachment upload interrupted") from exc
            if not size:
                raise HTTPException(422, "Attachment is empty")

            def configured_scan(path):
                return defender_scan(Path(defender_path), path)

            receipt = await run_in_threadpool(
                file_untrusted_document, staged, archive,
                scanner=configured_scan if defender_path else None,
                source_revision=snapshot_hash, source_locator=filename,
            )
        with conn() as db:
            if attachment_is_retired(db, source_id, revision, receipt["capture_id"]):
                raise HTTPException(409, "Attachment capture has been retired")
        return {key: receipt[key] for key in ("capture_id", "capture_kind", "sha256", "reason")}

    def attachment_is_retired(db, source_id, revision, capture_id):
        return db.execute(
            "SELECT 1 FROM retired_signal_attachments WHERE source_id=? AND revision=? AND capture_id=?",
            (source_id, revision, capture_id),
        ).fetchone() is not None

    def verified_attachment(source_id, snapshot_hash, domain, capture_id):
        if len(capture_id) != 64 or any(char not in "0123456789abcdef" for char in capture_id):
            raise HTTPException(404, "Attachment not found")
        archive = archive_root / domain / "attachments" / source_id
        try:
            capture = read_capture(archive, capture_id)
        except FileNotFoundError as exc:
            raise HTTPException(404, "Attachment not found") from exc
        except (ValueError, OSError, sqlite3.Error) as exc:
            raise HTTPException(409, "Attachment could not be verified") from exc
        if capture["source_revision"] != snapshot_hash:
            raise HTTPException(404, "Attachment not found")
        return capture

    @app.get("/api/intelligence-flow/{source_id}/revisions/{revision}/attachments/{capture_id}")
    def signal_download_attachment(source_id: str, revision: int, capture_id: str, who=Depends(reader)):
        try:
            with conn() as db:
                domain = flow.source_domain(db, source_id)
                permit(who, domain)
                snapshot_hash = flow.source_revision_hash(db, source_id, revision)
                if attachment_is_retired(db, source_id, revision, capture_id):
                    raise HTTPException(404, "Attachment not found")
        except flow.SignalError as exc:
            failure(exc)
        capture = verified_attachment(source_id, snapshot_hash, domain, capture_id)
        return Response(
            capture["content"], media_type="application/octet-stream",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
                     "Content-Disposition": "attachment"},
        )

    @app.delete("/api/intelligence-flow/{source_id}/revisions/{revision}/attachments/{capture_id}")
    def signal_retire_attachment(source_id: str, revision: int, capture_id: str, who=Depends(writer)):
        try:
            with conn() as db:
                db.execute("BEGIN IMMEDIATE")
                domain = flow.source_domain(db, source_id)
                permit(who, domain, write=True)
                snapshot_hash = flow.source_revision_hash(db, source_id, revision)
                if not attachment_is_retired(db, source_id, revision, capture_id):
                    verified_attachment(source_id, snapshot_hash, domain, capture_id)
                    db.execute("INSERT INTO retired_signal_attachments VALUES(?,?,?)",
                               (source_id, revision, capture_id))
                    event(db, domain, who, "SIGNAL_ATTACHMENT_RETIRED", source_id,
                          {"revision": revision, "capture_id": capture_id, "bytes_retained": True})
        except flow.SignalError as exc:
            failure(exc)
        return Response(status_code=204)

    @app.post("/api/intelligence-flow/{source_id}/plan")
    def signal_plan(source_id:str,body:Plan,who=Depends(writer)):
        try:
            with conn() as db:
                db.execute("BEGIN IMMEDIATE")
                permit(who,flow.source_domain(db,source_id),write=True)
                return flow.make_plan(db,event,who,source_id,body.model_dump())
        except (flow.SignalError,TicketError) as exc:
            failure(exc)

    @app.post("/api/intelligence-flow/{source_id}/release")
    def signal_release(source_id:str,body:Release,who=Depends(writer)):
        try:
            with conn() as db:
                db.execute("BEGIN IMMEDIATE")
                permit(who,flow.source_domain(db,source_id),write=True)
                return flow.release(db,event,who,source_id,body.model_dump(),archive_root)
        except (flow.SignalError,TicketError) as exc:
            failure(exc)
