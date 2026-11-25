import json
from fastapi import Depends,HTTPException,Query
from pydantic import BaseModel,Field,ConfigDict,StrictInt
from .core import strategy_cases as s
from .core import strategy_batches as b
from .core import unit_evidence as u
from .core.acquisition_patterns import DecisionReceipts, digest, screen_rule
from .core import financing as f
from .core import portfolio as p
from .core import recycling as rc
from .core import investment_paths as ip
from .core import site_paths as sp

class Case(BaseModel):
    model_config=ConfigDict(extra='forbid')
    run_id:str=Field(min_length=1,max_length=64)
    parcel_key:str=Field(min_length=1,max_length=64)
    strategy_id:str=Field(pattern=r'^SMF-[0-9]{2}$')

class Finance(BaseModel):
    model_config=ConfigDict(extra='forbid')
    as_of:str=Field(min_length=10,max_length=10)
    operations:dict[str,StrictInt|None]=Field(default_factory=dict,max_length=5)
    capital:dict[str,StrictInt|None]=Field(default_factory=dict,max_length=2)

class Batch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    run_id:str=Field(min_length=1,max_length=64)
    offset:StrictInt=Field(ge=0)
    limit:StrictInt=Field(ge=1,le=1000)

class Purchase(BaseModel):
    model_config=ConfigDict(extra='forbid')
    finance_id:str=Field(min_length=64,max_length=64)
    inputs:dict[str,StrictInt|None]=Field(max_length=7)

class OwnerOccupancy(BaseModel):
    model_config=ConfigDict(extra="forbid")
    inputs:dict[str,StrictInt|None]=Field(max_length=7)

class FinancingGrid(BaseModel):
    model_config=ConfigDict(extra="forbid")
    inputs:dict[str,StrictInt|None]=Field(max_length=21)

class DatedOption(BaseModel):
    model_config=ConfigDict(extra='forbid')
    finance_id:str=Field(pattern=r'^[0-9a-f]{64}$')
    year:StrictInt=Field(ge=1,le=5)

class PortfolioAssumptions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    initial_cash_cents:StrictInt
    liquidity_floor_cents:StrictInt
    max_managed_units:StrictInt
    existing_managed_units:StrictInt
    horizon_years:StrictInt
    stress_revenue_bps:StrictInt
    stress_opex_bps:StrictInt
    stress_extra_capex_per_unit_cents:StrictInt

class Portfolio(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dated_options:list[DatedOption]=Field(min_length=1,max_length=12)
    assumptions:PortfolioAssumptions

class Recycling(BaseModel):
    model_config=ConfigDict(extra="forbid")
    finance_id:str=Field(pattern=r"^[0-9a-f]{64}$")
    assumptions:dict[str,StrictInt]=Field(max_length=24)

class PathMandate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    objective:str
    horizon_years:StrictInt
    unit_counts:list[StrictInt]=Field(min_length=1,max_length=3)
    capital_cents:StrictInt|None=None
    run_id:str|None=None
    parcel_key:str|None=None

class SiteFinding(BaseModel):
    model_config=ConfigDict(extra='forbid')
    finding_id:str=Field(min_length=1,max_length=100)
    topic:str=Field(min_length=1,max_length=80)
    state:str=Field(min_length=1,max_length=20)
    source_ref:str=Field(min_length=1,max_length=500)
    source_date:str=Field(min_length=10,max_length=10)
    summary:str=Field(min_length=1,max_length=2000)
    strategy_ids:list[str]=Field(default_factory=list,max_length=83)

class SiteDiscovery(BaseModel):
    model_config=ConfigDict(extra='forbid')
    site_id:str=Field(min_length=1,max_length=100)
    boundary_revision:str=Field(min_length=1,max_length=200)
    program_revision: str | None = Field(default=None, min_length=1, max_length=200)
    findings:list[SiteFinding]=Field(max_length=100)
    run_id:str|None=None
    parcel_key:str|None=None

class PathOption(BaseModel):
    model_config=ConfigDict(extra='forbid')
    finance_id:str=Field(pattern=r'^[0-9a-f]{64}$')
    year:StrictInt
    recycling_assumptions:dict[str,StrictInt]=Field(max_length=24)

class PathAssumptions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    initial_cash_cents:StrictInt
    liquidity_floor_cents:StrictInt
    max_managed_units:StrictInt
    horizon_years:StrictInt
    stress_revenue_bps:StrictInt
    stress_opex_bps:StrictInt

class PathSchedule(BaseModel):
    model_config=ConfigDict(extra='forbid')
    dated_options:list[PathOption]=Field(min_length=1,max_length=6)
    assumptions:PathAssumptions

class ParcelClaimSource(BaseModel):
    model_config=ConfigDict(extra='forbid')
    run_id:str=Field(min_length=1,max_length=64)
    parcel_key:str=Field(min_length=1,max_length=64)
    source_ref:str=Field(min_length=1,max_length=500)
    excerpt:str=Field(min_length=1,max_length=4000)
    source_date:str=Field(min_length=10,max_length=10)
    valid_from:str|None=Field(default=None,min_length=10,max_length=10)
    valid_until:str=Field(min_length=10,max_length=10)

class UnitClaim(ParcelClaimSource):
    units: StrictInt = Field(ge=1, le=100000)
    supersedes_claim_id: str | None = Field(default=None, min_length=64, max_length=64)


class ParcelMetricClaim(ParcelClaimSource):
    metric: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=32)


class UnitReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    decision:str
    source_ref:str=Field(min_length=1,max_length=500)
    excerpt:str=Field(min_length=1,max_length=4000)
    source_date:str=Field(min_length=10,max_length=10)
    expected_review_id:str|None=None

class UnitPattern(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule: dict = Field(max_length=15)
    as_of: str = Field(min_length=10, max_length=10)
    jurisdiction: str = Field(min_length=1, max_length=32)
    track: str = Field(min_length=1, max_length=32)
    retain: bool = False
    metric: str = Field(default=u.UNIT_METRIC, max_length=64)


def register(app,actor,permit,conn,event):
    with conn() as db:s.initialize(db);b.initialize(db);u.initialize(db);p.initialize(db);rc.initialize(db);ip.initialize(db)
    with conn() as db:
        DecisionReceipts.initialize(db)
    def allowed(who=Depends(actor)):
        permit(who,'COMMERCIAL');return who
    def writer(who=Depends(allowed)):
        permit(who,'COMMERCIAL',write=True);return who
    def failure(exc):
        return HTTPException(404 if isinstance(exc,LookupError) else 409,str(exc))
    @app.get('/api/strategy-library')
    def catalog(q:str=Query('',max_length=200),lane:str=Query('',max_length=80),who=Depends(allowed)):
        try:return s.catalog_view(q,lane)
        except ValueError as exc:raise failure(exc) from exc
    @app.post('/api/strategy-cases')
    def prepare(body:Case,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=s.prepare(db,**body.model_dump());r=out['receipt']
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_PREPARE',r['id'],{'run_id':r['run_id'],'parcel_key':r['parcel_key'],'strategy_id':r['strategy']['source']['ID'],'catalog_sha256':r['catalog_sha256']})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
    @app.get('/api/strategy-cases/{cid}')
    def read(cid:str,who=Depends(allowed)):
        with conn() as db:
            try:return s.read_case(db,cid)
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
    @app.post('/api/strategy-cases/{cid}/finance')
    def finance(cid:str,body:Finance,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=s.financial(db,cid,**body.model_dump());r=out['receipt']
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_FINANCIAL_SCENARIO',r['id'],{'case_id':cid,'input_sha256':r['input_sha256']})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/strategy-batches')
    def batch(body:Batch,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=b.screen(db,**body.model_dump());r=out['receipt']
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_BATCH',r['id'],{'run_id':r['run_id'],'offset':r['offset'],'end':r['end']})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
    @app.get('/api/strategy-batches/{rid}')
    def batch_read(rid:str,who=Depends(allowed)):
        with conn() as db:
            try:return b.read(db,rid)
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
    @app.post('/api/strategy-cases/{cid}/purchase')
    def purchase(cid:str,body:Purchase,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=b.purchase_limits(db,cid,**body.model_dump());r=out['receipt']
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_PURCHASE_SCENARIO',r['id'],{'case_id':cid,'finance_id':r['finance_id']})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/unit-evidence')
    def propose_unit(body:UnitClaim,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=u.propose(db,**body.model_dump())
                if not out['replay']:event(db,'COMMERCIAL',who,'UNIT_CLAIM',out['claim']['id'],{'parcel_key':body.parcel_key})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
    @app.post('/api/parcel-metric-evidence')
    def propose_parcel_metric(body: ParcelMetricClaim, who=Depends(writer)):
        with conn() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                output = u.propose_metric(db, **body.model_dump())
                if not output["replay"]:
                    event(db, "COMMERCIAL", who, "PARCEL_METRIC_CLAIM", output["claim"]["id"],
                          {"parcel_key": body.parcel_key, "metric": body.metric})
                return output
            except (LookupError, ValueError) as exc:
                raise failure(exc) from exc

    @app.post('/api/unit-evidence/{cid}/review')
    def review_unit(cid:str,body:UnitReview,who=Depends(allowed)):
        if who!='SW-13':raise HTTPException(403,'Independent SW-13 credential required')
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=u.adjudicate(db,cid,**body.model_dump())
                if not out['replay']:event(db,'COMMERCIAL',who,'UNIT_RESEARCH_REVIEW',out['review']['id'],{'claim_id':cid,'decision':body.decision})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
    @app.get('/api/unit-evidence/{run_id}/{parcel_key}')
    def inspect_units(run_id:str,parcel_key:str,as_of:str|None=None,valid_on:str|None=None,who=Depends(allowed)):
        with conn() as db:
            try:
                run=u.get(db,run_id);u.evidence(db,run['snapshot_id'],parcel_key)
                return u.state(db,run['snapshot_id'],parcel_key,as_of=as_of,valid_on=valid_on)
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/unit-evidence/{run_id}/{parcel_key}/screen-pattern')
    def screen_unit_pattern(run_id: str, parcel_key: str, body: UnitPattern, who=Depends(allowed)):
        if body.retain:
            permit(who, "COMMERCIAL", write=True)
        with conn() as db:
            db.execute("BEGIN IMMEDIATE" if body.retain else "BEGIN")
            try:
                snapshot = u.get(db, run_id)["snapshot_id"]
                projection, facts = u.pattern_projection(db, snapshot, parcel_key, u.day(body.as_of), metric=body.metric)
                result = screen_rule(body.rule, facts, jurisdiction=body.jurisdiction,
                                     track=body.track, as_of=body.as_of)
                packet = {"result": result, "evidence_state": projection["status"],
                          "evidence_sha256": projection["evidence_sha256"]}
                if body.retain:
                    payload = {**packet, "kind": "UNIT_EVIDENCE_SCREEN",
                               "snapshot_id": snapshot, "parcel_key": parcel_key}
                    if body.metric != u.UNIT_METRIC:
                        payload["metric"] = body.metric
                    operation_id = "unit-screen:" + digest(payload)
                    receipt = DecisionReceipts.append_locked(db, operation_id, payload)
                    packet["receipt"] = {"operation_id": operation_id, "sha256": receipt["receipt_hash"]}
                return packet
            except (LookupError, ValueError, TypeError, KeyError) as exc:
                raise failure(exc) from exc

    @app.get('/api/unit-pattern-receipts/{operation_id}')
    def read_unit_pattern(operation_id: str, who=Depends(allowed)):
        with conn() as db:
            db.execute("BEGIN")
            row = db.execute(
                "SELECT body, prior_hash, receipt_hash FROM acquisition_pattern_receipts WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(404, "Unit pattern receipt not found")
            payload = json.loads(row["body"])
            if payload.get("kind") != "UNIT_EVIDENCE_SCREEN":
                raise HTTPException(404, "Unit pattern receipt not found")
            if digest({"operation_id": operation_id, "body": row["body"],
                       "prior_hash": row["prior_hash"]}) != row["receipt_hash"]:
                raise HTTPException(409, "Unit pattern receipt digest mismatch")
            try:
                projection = u.state(db, payload["snapshot_id"], payload["parcel_key"],
                                     metric=payload.get("metric", u.UNIT_METRIC))
            except (LookupError, ValueError) as exc:
                raise failure(exc) from exc
            return {"receipt": payload, "sha256": row["receipt_hash"],
                    "evidence_current": projection["evidence_sha256"] == payload["evidence_sha256"]}

    @app.post('/api/strategy-cases/{cid}/owner-occupancy')
    def owner_occupancy(cid:str,body:OwnerOccupancy,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=s.owner_occupancy(db,cid,body.inputs)
                if not out['replay']:event(db,'COMMERCIAL',who,'OWNER_OCCUPANCY_SCENARIO',out['receipt']['id'],{'case_id':cid})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/strategy-cases/{cid}/financing-grid')
    def financing_grid(cid:str,body:FinancingGrid,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=f.run(db,cid,body.inputs)
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_FINANCING_GRID',out['receipt']['id'],{'case_id':cid})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/strategy-portfolio')
    def portfolio(body:Portfolio,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=p.run(db,**body.model_dump());r=out['receipt']
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_PORTFOLIO',r['id'],{'option_count':len(r['options'])})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/strategy-recycling')
    def recycling(body:Recycling,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=rc.run(db,**body.model_dump());r=out['receipt']
                if not out['replay']:event(db,'COMMERCIAL',who,'STRATEGY_RECYCLING',r['id'],{'finance_id':r['finance_id']})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/investment-paths/identify')
    def identify_paths(body:PathMandate,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=ip.identify(db,**body.model_dump())
                if not out['replay']:event(db,'COMMERCIAL',who,'INVESTMENT_PATH_IDENTIFICATION',out['receipt']['id'],{})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/investment-paths/from-site')
    def discover_site_paths(body:SiteDiscovery,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=sp.discover(db,**body.model_dump())
                if not out['replay']:event(db,'COMMERCIAL',who,'SITE_PATH_DISCOVERY',out['receipt']['id'],{})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc

    @app.post('/api/investment-paths/compound')
    def compound_paths(body:PathSchedule,who=Depends(writer)):
        with conn() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                out=ip.compound(db,**body.model_dump())
                if not out['replay']:event(db,'COMMERCIAL',who,'INVESTMENT_PATH_SCHEDULE',out['receipt']['id'],{})
                return out
            except (LookupError,ValueError) as exc:raise failure(exc) from exc
