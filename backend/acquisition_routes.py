import json
import time
from datetime import date
from fastapi import Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, StrictInt
from typing import Literal
from uuid import UUID
from .core import acquisition_leases as leases
from .core import acquisition_tasks as tasks
from .core import acquisition_runs as runs
from .core import unit_evidence
from .core import acquisition_learning, acquisition_daily_funnel, college_park_viewport, outreach_preview

class FunnelDecision(BaseModel):
    run_id: UUID
    decision: Literal["DEFER", "NO_SELECTION"]


class Start(BaseModel):
    request_id:str=Field(min_length=1,max_length=128)
    backend:Literal['cpu_reference','cuda']='cuda'
    batch_size:int=Field(default=1000,ge=1,le=10000)
    cohort_id:str|None=Field(default=None,min_length=1,max_length=64)
    snapshot_source:Literal['retained','orange_2026_final_roll']='retained'
class Step(BaseModel):
    version:int=Field(ge=1)
    action:Literal['advance','pause','resume','cancel']
    lease_id: UUID | None = None


class WorkerLease(BaseModel):
    lease_id: UUID
    task_id: UUID | None = None
    seconds: int = Field(default=30, ge=1, le=leases.MAX_LEASE_SECONDS)
    batches: int = Field(ge=1, le=leases.MAX_LEASE_BATCHES)

class WorkerTask(BaseModel):
    expected_version: int | None = Field(default=None, ge=1)
    context_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    parcel_key: str | None = Field(default=None, min_length=1, max_length=64)
    site_receipt_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    task_id: UUID
    batches: int = Field(ge=1, le=leases.MAX_LEASE_BATCHES)


class LearningOutcome(BaseModel):
    parcel_key: str = Field(min_length=1, max_length=64)
    outcome: Literal["PENDING", "FAILED", "CLOSED"]
    observed_on: str = Field(min_length=10, max_length=10)
    source_ref: str = Field(min_length=1, max_length=500)
    source_revision_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    excerpt: str = Field(min_length=1, max_length=4000)
    reported_cash_cents: StrictInt | None = Field(default=None, ge=-100_000_000_000, le=100_000_000_000)


class OutcomeReconciliation(BaseModel):
    model_config = {"extra": "forbid"}
    ledger_ref: str = Field(min_length=1, max_length=500)
    ledger_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ledger_cash_cents: StrictInt = Field(ge=-100_000_000_000, le=100_000_000_000)


class LearningPair(BaseModel):
    baseline_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class LearningRevision(BaseModel):
    kind: Literal["SKILL", "RULE", "WEIGHT"]
    component_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$")
    baseline_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class LearningProposal(BaseModel):
    pairs: list[LearningPair] = Field(min_length=2, max_length=20)
    rationale: str = Field(min_length=10, max_length=1000)
    expected_outcome: str = Field(min_length=10, max_length=1000)
    rollback: str = Field(min_length=10, max_length=1000)
    previous_proposal_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    revision: LearningRevision | None = None


class LearningReview(BaseModel):
    decision: Literal["VALIDATE_REHEARSAL", "REJECT"]
    rationale: str = Field(min_length=10, max_length=1000)


class OutreachPreview(BaseModel):
    request_id: str = Field(min_length=1, max_length=64)
    packet_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    recipient_ids: list[str] = Field(min_length=1, max_length=50)
    suppressed_ids: list[str] = Field(default_factory=list, max_length=50)


def worker_progress(run):
    return {key: run[key] for key in ("id", "state", "cursor", "total", "version",
                                     "backend", "actual_backend", "error", "offer_ready")}


def register(app,actor,permit,conn,event):
    with conn() as db:
        runs.initialize(db)
        acquisition_learning.initialize(db)
        outreach_preview.initialize(db)
        acquisition_daily_funnel.initialize(db)
    def allowed(who=Depends(actor)):
        permit(who,'COMMERCIAL');return who
    def writer(who=Depends(allowed)):
        permit(who,'COMMERCIAL',write=True);return who
    @app.put("/api/acquisition-funnel/{day}")
    def publish_funnel(day: date, body: FunnelDecision, who=Depends(writer)):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                key = day.isoformat()
                previous = acquisition_daily_funnel.read(db, key)
                report = acquisition_daily_funnel.publish(db, key, str(body.run_id), body.decision)
                if previous is None:
                    event(db, "COMMERCIAL", who, "ACQ_FUNNEL_PUBLISHED", key,
                          {"run_id": report["run_id"], "report_sha256": report["report_sha256"]})
                return report
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.get("/api/acquisition-funnel/{day}")
    def read_funnel(day: date, who=Depends(allowed)):
        with conn() as db:
            try:
                report = acquisition_daily_funnel.read(db, day.isoformat())
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        if report is None:
            raise HTTPException(404, "No recorded funnel for that day")
        return Response(runs.encode(report), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.post("/api/acquisition-outreach/previews")
    def save_outreach_preview(body: OutreachPreview, who=Depends(writer)):
        with conn() as db:
            try:
                result = outreach_preview.preview(db, **body.model_dump())
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            if not result["replay"]:
                event(db, "COMMERCIAL", who, "ACQ_OUTREACH_PREVIEW", body.request_id,
                      {"packet_sha256": body.packet_sha256, "recipient_count": len(body.recipient_ids),
                       "suppressed_count": len(result["suppressed_ids"]), "delivery_state": "DISABLED"})
            return result

    @app.get("/api/acquisition-outreach/previews/{request_id}")
    def recover_outreach_preview(request_id: str, response: Response, who=Depends(allowed)):
        with conn() as db:
            try:
                result = outreach_preview.read_preview(db, request_id)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
        response.headers["Cache-Control"] = "private, no-store"
        return result

    @app.get("/api/acquisition-map/college-park")
    def college_park_map(response: Response, west: float, south: float, east: float,
                         north: float, zoom: int = Query(ge=0, le=22),
                         revision: str | None = Query(default=None, max_length=64),
                         who=Depends(allowed)):
        try:
            result = college_park_viewport.viewport(west, south, east, north, zoom, revision)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(409, str(exc)) from exc
        except (OSError, ImportError) as exc:
            raise HTTPException(503, "College Park map evidence unavailable") from exc
        response.headers["Cache-Control"] = "private, no-store"
        return result

    @app.get('/api/acquisition-runs')
    def list_runs(who=Depends(allowed)):
        with conn() as db:
            listed = []
            for row in db.execute('SELECT * FROM acq_runs ORDER BY created DESC LIMIT 50'):
                try:
                    runs.snapshot_available(db, row['snapshot_id'])
                except LookupError:
                    continue
                listed.append(dict(row))
            return listed
    @app.post('/api/acquisition-runs')
    def start_run(body:Start,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                previous=db.execute('SELECT id FROM acq_runs WHERE request_id=?',(body.request_id,)).fetchone()
                result=runs.start(db,**body.model_dump())
                if not previous:event(db,'COMMERCIAL',who,'ACQ_RUN_START',result['id'],{'snapshot_id':result['snapshot_id'],'backend':result['backend'],'total':result['total']})
                return result
            except LookupError as e:raise HTTPException(404,str(e)) from e
            except ValueError as e:raise HTTPException(409,str(e)) from e
    @app.get('/api/acquisition-runs/sources')
    def available_sources(who=Depends(allowed)):
        sources = ["retained"]
        if runs.orange_research_enabled():
            sources.append("orange_2026_final_roll")
        return {"sources": sources}

    @app.get('/api/acquisition-runs/{run_id}')
    def read_run(run_id:str,who=Depends(allowed)):
        with conn() as db:
            try:
                run = runs.get(db, run_id)
                if who == "ACQ_WORKER":
                    return worker_progress(run)
                return run
            except LookupError as e:raise HTTPException(404,str(e)) from e
    @app.get("/api/acquisition-runs/{run_id}/batches/{start}/verification")
    def verify_run_batch(run_id: str, start: int, who=Depends(allowed)):
        with conn() as db:
            try:
                report = runs.verify_batch(db, run_id, start)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(409, "Persisted batch verification failed") from exc
        return Response(runs.encode(report), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.post('/api/acquisition-runs/{run_id}/batches/{batch_start}/learning-episode')
    def capture_learning_episode(run_id: str, batch_start: int, who=Depends(writer)):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                output = acquisition_learning.capture_batch(db, run_id, batch_start)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(409, "Batch episode verification failed") from exc
            if not output["replay"]:
                event(db, "COMMERCIAL", who, "ACQ_LEARNING_EPISODE_CAPTURED", output["id"],
                      {"run_id": run_id, "batch_start": batch_start})
            return Response(runs.encode(output), media_type="application/json",
                            headers={"Cache-Control": "private, no-store"})

    @app.post('/api/acquisition-learning-proposals')
    def propose_learning(body: LearningProposal, who=Depends(writer)):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                output = acquisition_learning.propose_comparison(db, **body.model_dump())
                if not output["replay"]:
                    event(db, "COMMERCIAL", who, "ACQ_LEARNING_PROPOSAL_CREATED", output["id"],
                          {"previous_proposal_id": body.previous_proposal_id})
                return output
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.get('/api/acquisition-learning-proposals/{proposal_id}')
    def read_learning_proposal(proposal_id: str, who=Depends(allowed)):
        with conn() as db:
            db.execute("BEGIN")
            try:
                output = acquisition_learning.read_proposal(db, proposal_id)
                output["memory_views"] = acquisition_learning.proposal_memory(output)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except (ValueError, TypeError) as exc:
                raise HTTPException(409, "Learning proposal verification failed") from exc
        return Response(runs.encode(output), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.post('/api/acquisition-learning-proposals/{proposal_id}/review')
    def review_learning(proposal_id: str, body: LearningReview, who=Depends(allowed)):
        if who != "SW-13":
            raise HTTPException(403, "Independent review required")
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                output = acquisition_learning.review_comparison(db, proposal_id, reviewer=who, **body.model_dump())
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            if not output["replay"]:
                event(db, "COMMERCIAL", who, "ACQ_LEARNING_PROPOSAL_REVIEWED", proposal_id, output["review"])
            return output

    @app.get('/api/acquisition-runs/{run_id}/learning-attempts')
    def read_learning_attempts(run_id: str, after: int = Query(0, ge=0, le=2**63 - 1),
                               limit: int = Query(25, ge=1, le=100), who=Depends(allowed)):
        with conn() as db:
            db.execute("BEGIN")
            try:
                output = acquisition_learning.attempt_history(db, run_id, after=after, limit=limit)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except (ValueError, KeyError, TypeError) as exc:
                raise HTTPException(409, "Run attempt audit verification failed") from exc
        return Response(runs.encode(output), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.post('/api/acquisition-learning-episodes/{episode_id}/outcomes')
    def report_learning_outcome(episode_id: str, body: LearningOutcome, who=Depends(writer)):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                output = acquisition_learning.report_outcome(db, episode_id, **body.model_dump())
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            if not output["replay"]:
                event(db, "COMMERCIAL", who, "ACQ_LEARNING_OUTCOME_REPORTED", output["id"],
                      {"episode_id": episode_id, "parcel_key": body.parcel_key})
        return Response(runs.encode(output), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.post('/api/acquisition-learning-episodes/{episode_id}/outcomes/{outcome_id}/review')
    def reconcile_learning_outcome(episode_id: str, outcome_id: str, body: OutcomeReconciliation, who=Depends(allowed)):
        if who != "SW-13":
            raise HTTPException(403, "Independent reviewer required")
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                output = acquisition_learning.reconcile_outcome(
                    db, episode_id, outcome_id, reviewer=who, **body.model_dump(),
                )
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            if not output["replay"]:
                event(db, "COMMERCIAL", who, "ACQ_LEARNING_OUTCOME_REVIEWED", outcome_id,
                      {"episode_id": episode_id, "disposition": output["review"]["disposition"]})
        return Response(runs.encode(output), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.get('/api/acquisition-learning-episodes/{episode_id}/outcomes')
    def read_learning_outcomes(episode_id: str, offset: int = Query(0, ge=0, le=2**63 - 1),
                               limit: int = Query(25, ge=1, le=100), who=Depends(allowed)):
        with conn() as db:
            db.execute("BEGIN")
            try:
                output = acquisition_learning.outcome_history(db, episode_id, offset=offset, limit=limit)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, "Learning outcome verification failed") from exc
        return Response(runs.encode(output), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    @app.get('/api/acquisition-learning-episodes/{episode_id}')
    def read_learning_episode(episode_id: str, who=Depends(allowed)):
        with conn() as db:
            try:
                output = acquisition_learning.read(db, episode_id)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, "Learning episode digest mismatch") from exc
        return Response(runs.encode(output), media_type="application/json",
                        headers={"Cache-Control": "private, no-store"})

    def preparation_packet(db, run, parcel_key=None, site_receipt_id=None):
        snapshot = runs.snapshot_available(db, run["snapshot_id"])
        feature = db.execute("SELECT feature_version FROM acq_run_contracts WHERE run_id=?",
                             (run["id"],)).fetchone()
        packet = {
            "contract": "br-acquisition-preparation/3",
            "run_id": run["id"], "expected_version": run["version"],
            "state": run["state"], "cursor": run["cursor"], "total": run["total"],
            "snapshot_id": run["snapshot_id"],
            "source": snapshot.get("snapshot_source", "retained"),
            "inventory_sha256": snapshot.get("inventory_sha256"),
            "source_manifest_sha256": runs.sha(snapshot),
            "feature_contract": feature[0] if feature else None,
            "source_evidence_scope": "SOURCE_REPORTED_RESEARCH",
            "worker_scope": {
                "mode": "INTERNAL_ACQUISITION_BATCH",
                "requested_backend": run["backend"],
                "allowed_operations": ["READ_ASSIGNED_RUN", "CLAIM_ASSIGNED_LEASE", "ADVANCE_BOUNDED_BATCH", "RELEASE_ASSIGNED_LEASE"],
                "output_contract": "PERSISTED_ACQUISITION_BATCH_RECEIPT",
                "external_authority": False,
            },
            "authority": "RESEARCH_ONLY",
        }

        if parcel_key is not None:
            snapshot_id = run["snapshot_id"]
            cutoff = unit_evidence.today()
            source = unit_evidence.evidence(db, snapshot_id, parcel_key)
            metrics = {}
            for metric in (unit_evidence.UNIT_METRIC, *unit_evidence.METRICS):
                projection = unit_evidence.state(db, snapshot_id, parcel_key, as_of=cutoff, metric=metric)
                key = "reviewed_units" if metric == unit_evidence.UNIT_METRIC else "reviewed_value"
                metrics[metric] = {
                    "state": projection["status"], "value": projection[key],
                    "evidence_sha256": projection["evidence_sha256"],
                    "review_ids": projection["active_review_ids"],
                    "pending_claim_ids": projection["pending_claim_ids"],
                }
            packet["parcel_evidence"] = {
                "parcel_key": parcel_key, "knowledge_cutoff": cutoff,
                "record_sha256": source["record_sha256"],
                "source_reported_values": source["source_reported_values"],
                "source_conflicts": source["conflicting_fields"], "reviewed_metrics": metrics,
                "legal_units": None,
            }
        if site_receipt_id:
            if parcel_key is None:
                raise ValueError("Site discovery requires a parcel-bound preparation packet")
            row = db.execute("SELECT receipt FROM investment_path_receipts WHERE id=?", (site_receipt_id,)).fetchone()
            if row is None:
                raise LookupError("Site discovery receipt not found")
            discovery = json.loads(row["receipt"])
            body = {key: value for key, value in discovery.items() if key != "id"}
            if (discovery.get("id") != site_receipt_id or runs.sha(body) != site_receipt_id
                    or discovery.get("kind") != "SITE_DERIVED_PATH_DISCOVERY"):
                raise ValueError("Invalid site discovery receipt")
            expected = {
                "run_id": run["id"], "snapshot_id": run["snapshot_id"], "parcel_key": parcel_key,
                "record_sha256": packet["parcel_evidence"]["record_sha256"],
            }
            if discovery.get("context") != expected:
                raise ValueError("Site discovery belongs to a different run or parcel revision")
            if any(finding["source_date"] > cutoff for finding in discovery["findings"]):
                raise ValueError("Site discovery includes findings after the knowledge cutoff")
            packet["site_discovery"] = {
                "receipt_id": site_receipt_id, "version": discovery["version"],
                "boundary_revision": discovery["boundary_revision"],
                "program_revision": discovery.get("program_revision"),
                "method_references": discovery.get("method_references"),
                "catalog_sha256": discovery["catalog_sha256"],
                "method_reference_ids": discovery["method_reference_ids"],
                "method_application_status": discovery["method_application_status"],
                "findings": [{key: finding[key] for key in ("finding_id", "source_ref", "source_date", "state")}
                             for finding in discovery["findings"]],
                "scope": "SOURCE_REPORTED_RESEARCH",
            }
        return packet

    @app.get('/api/acquisition-runs/{run_id}/preparation-context')
    def preparation_context(run_id: str, parcel_key: str | None = Query(None, min_length=1, max_length=64),
                            site_receipt_id: str | None = Query(None, pattern=r"^[0-9a-f]{64}$"),
                            who=Depends(allowed)):
        with conn() as db:
            db.execute("BEGIN")
            try:
                run = runs.get(db, run_id)
                packet = preparation_packet(db, run, parcel_key, site_receipt_id)
            except LookupError as exc:
                raise HTTPException(404, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            busy = tasks.active(db, run_id) is not None or leases.current(db, run_id) is not None
            return {**packet, "context_sha256": runs.sha(packet),
                    "queue_available": run["state"] in {"READY", "RUNNING"} and not busy}

    @app.get('/api/acquisition-worker-dispatch')
    def read_worker_dispatch(limit: int = Query(20, ge=1, le=100), who=Depends(allowed)):
        with conn() as db:
            ready = tasks.dispatchable(
                db, limit=limit, include_quarantined=runs.orange_research_enabled(), now=time.time(),
            )
        return Response(runs.encode({"tasks": ready, "scope": "INTERNAL_RESEARCH_ONLY"}),
                        media_type="application/json", headers={"Cache-Control": "private, no-store"})

    @app.get('/api/acquisition-runs/{run_id}/worker-task')
    def read_worker_task(run_id: str, who=Depends(allowed)):
        with conn() as db:
            try:
                runs.get(db, run_id)
                return {"task": tasks.latest(db, run_id)}
            except LookupError as e:
                raise HTTPException(404, str(e)) from e

    @app.post('/api/acquisition-runs/{run_id}/worker-task')
    def queue_worker_task(run_id: str, body: WorkerTask, who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                run = runs.get(db, run_id)
                if (body.parcel_key is not None or body.site_receipt_id is not None) and body.context_sha256 is None:
                    raise ValueError("Parcel preparation requires its reviewed context digest")
                packet = preparation_packet(db, run, body.parcel_key, body.site_receipt_id) if body.context_sha256 else None
                task = tasks.enqueue(
                    db, run, str(body.task_id), body.batches, expected_version=body.expected_version,
                    context_sha256=body.context_sha256, current_context_sha256=runs.sha(packet) if packet else None,
                )
                if not task["replay"]:
                    event(db, "COMMERCIAL", who, "ACQ_WORKER_TASK_QUEUED", run_id,
                          {"task_id": task["id"], "batches": body.batches, "cursor": run["cursor"],
                           "run_version": run["version"], "preparation_context": packet})
                return task
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except ValueError as e:
                raise HTTPException(409, str(e)) from e

    @app.post('/api/acquisition-runs/{run_id}/worker-lease')
    def claim_worker(run_id: str, body: WorkerLease, who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                run = runs.get(db, run_id)
                result = tasks.bind_lease(db, run, str(body.task_id) if body.task_id else None,
                                          str(body.lease_id), body.seconds, body.batches)
                if not result["replay"]:
                    event(db, 'COMMERCIAL', who, 'ACQ_WORKER_CLAIM', run_id,
                          {"budget": body.batches, "expires_at": result["expires_at"],
                           "task_id": str(body.task_id) if body.task_id else None})
                return result
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except ValueError as e:
                raise HTTPException(409, str(e)) from e

    @app.delete('/api/acquisition-runs/{run_id}/worker-lease/{lease_id}')
    def release_worker(run_id: str, lease_id: UUID, who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                runs.get(db, run_id)
                released = tasks.release(db, run_id, str(lease_id))
                if released:
                    event(db, 'COMMERCIAL', who, 'ACQ_WORKER_RELEASE', run_id, {})
                return {"released": released}
            except LookupError as e:
                raise HTTPException(404, str(e)) from e
            except ValueError as e:
                raise HTTPException(409, str(e)) from e

    @app.post('/api/acquisition-runs/{run_id}/step')
    def advance(run_id:str,body:Step,who=Depends(writer)):
        if who == "ACQ_WORKER" and (body.action != "advance" or body.lease_id is None):
            raise HTTPException(403,"Worker may only advance through its active lease")
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                result=runs.step(db,run_id,**body.model_dump(mode="json"))
                event(db,'COMMERCIAL',who,'ACQ_RUN_STEP',run_id,{'action':body.action,'state':result['state'],'version':result['version'],'cursor':result['cursor'],'error':result['error'],
                      'requested_backend':result['backend'],'snapshot_id':result['snapshot_id']})
                return worker_progress(result) if who == 'ACQ_WORKER' else result
            except LookupError as e:raise HTTPException(404,str(e)) from e
            except ValueError as e:raise HTTPException(409,str(e)) from e
    @app.get('/api/acquisition-runs/{run_id}/properties')
    def properties(run_id:str,q:str=Query(default='',max_length=64),limit:int=Query(default=25,ge=1,le=100),offset:int=Query(default=0,ge=0),who=Depends(allowed)):
        with conn() as db:
            try:
                run=runs.get(db,run_id);out=runs.properties(db,run['snapshot_id'],q,limit,offset)
                import json
                for item in out['items']:
                    row=db.execute('SELECT result FROM acq_results WHERE run_id=? AND parcel_key=?',(run_id,item['parcel_key'])).fetchone()
                    item['run_result']=json.loads(row[0]) if row else None
                return out
            except LookupError as e:raise HTTPException(404,str(e)) from e
    # Explicit filtered cohorts are research selections, not verified legal unit groups.
    from .core import acquisition_cohorts as cohorts

    with conn() as db:cohorts.initialize(db)
    class CohortRequest(BaseModel):
        run_id:str=Field(min_length=1,max_length=64)
        city:str=Field(default='',max_length=100)
        use_code:str=Field(default='',max_length=8)
        site_receipt_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
        path_id: str | None = Field(default=None, min_length=1, max_length=100)
    @app.post('/api/acquisition-cohorts')
    def freeze_cohort(body:CohortRequest,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                r = runs.get(db, body.run_id)
                shortlist = None
                if body.site_receipt_id or body.path_id:
                    if not body.site_receipt_id or not body.path_id or body.city or body.use_code:
                        raise ValueError("A site shortlist requires a receipt and path without inventory filters")
                    row = db.execute("SELECT receipt FROM investment_path_receipts WHERE id=?",
                                     (body.site_receipt_id,)).fetchone()
                    if row is None:
                        raise LookupError("Site discovery receipt not found")
                    discovery = json.loads(row[0])
                    context = discovery.get("context") or {}
                    packet = preparation_packet(db, r, context.get("parcel_key"), body.site_receipt_id)
                    site = packet["site_discovery"]
                    path = next((item for item in discovery["candidate_paths"] if item["path_id"] == body.path_id), None)
                    if path is None or not site["program_revision"]:
                        raise ValueError("Shortlist requires a retained candidate path and program revision")
                    shortlist = {"parcel_key": context["parcel_key"], "site_receipt_id": body.site_receipt_id,
                                 "path_id": body.path_id, "program_revision": site["program_revision"],
                                 "boundary_revision": site["boundary_revision"],
                                 "record_sha256": context["record_sha256"],
                                 "evidence_state": "SOURCE_REPORTED_RESEARCH"}
                c = cohorts.freeze(db, r["snapshot_id"], body.city, body.use_code, shortlist=shortlist)
                if not c['replay']:event(db,'COMMERCIAL',who,'ACQ_COHORT_FREEZE',c['id'],{'total':c['total'],'snapshot_id':r['snapshot_id'],'filters':c['manifest']['filters'],'shortlist':shortlist})
                return c
            except LookupError as e:raise HTTPException(404,str(e)) from e
            except ValueError as e:raise HTTPException(409,str(e)) from e
    @app.get('/api/acquisition-cohorts/{cid}')
    def cohort_page(cid:str,after:str=Query(default='',max_length=64),limit:int=Query(default=25,ge=1,le=100),who=Depends(allowed)):
        with conn() as db:
            try:return {**cohorts.get(db,cid),**cohorts.page(db,cid,after,limit)}
            except LookupError as e:raise HTTPException(404,str(e)) from e
    @app.get('/api/acquisition-cohorts/{cid}/qgis.csv')
    def qgis_export(cid:str,who=Depends(allowed)):
        with conn() as db:
            try:return Response(cohorts.export_csv(db,cid),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="black-river-{cid[:12]}.csv"','Cache-Control':'no-store'})
            except LookupError as e:raise HTTPException(404,str(e)) from e
            except ValueError as e:raise HTTPException(409,str(e)) from e
    @app.get('/api/acquisition-runs/{run_id}/evidence/{parcel_key}')
    def evidence(run_id:str,parcel_key:str,who=Depends(allowed)):
        with conn() as db:
            try:return cohorts.evidence(db,runs.get(db,run_id)['snapshot_id'],parcel_key)
            except LookupError as e:raise HTTPException(404,str(e)) from e
