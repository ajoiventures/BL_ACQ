"""Authenticated preparation-only adapters for Cities & Planning scenarios."""
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .core import city_planning as planning
from .core.college_park_baseline import load_verified_baseline


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')


class Baseline(Strict):
    place_id:str=Field(min_length=1,max_length=120)
    title:str=Field(min_length=1,max_length=180)
    population:int=Field(ge=0,le=2000000000,strict=True)
    reference_date:str=Field(min_length=10,max_length=10)
    vintage:str=Field(min_length=1,max_length=120)
    source_url:str=Field(min_length=8,max_length=2000)
    evidence_status:Literal['SOURCE_REPORTED','HYPOTHETICAL']


class Scenario(Strict):
    name:str=Field(min_length=1,max_length=80)
    annual_growth_rate:str=Field(min_length=1,max_length=30)


class Projection(Strict):
    request_id:str=Field(min_length=1,max_length=120)
    security_domain:Literal['COMMERCIAL','MAIN_STREET_INSTITUTIONAL']
    baseline:Baseline
    horizon_years:int=Field(ge=1,le=20,strict=True)
    scenarios:list[Scenario]=Field(min_length=1,max_length=5)


def register(app,actor,permit,conn,event):
    with conn() as db:
        planning.initialize(db)

    def reader(who=Depends(actor)):
        if who not in ('FOUNDER','SW-13'):
            raise HTTPException(403,'Planning scenarios require founder or auditor access')
        return who

    def writer(who=Depends(actor)):
        if who!='FOUNDER':
            raise HTTPException(403,'Founder credential required to originate a planning scenario')
        return who

    @app.get('/api/cities-planning/contract')
    def planning_contract(who=Depends(reader)):
        return planning.contract()

    @app.get('/api/cities-planning')
    def planning_list(who=Depends(reader)):
        with conn() as db:
            reports=planning.listing(db)
            for report in reports:
                permit(who,report['security_domain'])
            return reports

    @app.post('/api/cities-planning/project')
    def planning_project(body:Projection,who=Depends(writer)):
        permit(who,body.security_domain,write=True)
        try:
            with conn() as db:
                db.execute('BEGIN IMMEDIATE')
                return planning.project(db,event,who,body.model_dump())
        except planning.PlanningError as exc:
            raise HTTPException(exc.code,str(exc)) from exc

    @app.get('/api/cities-planning/research/college-park-baseline')
    def college_park_baseline(
        domain: Literal['COMMERCIAL', 'MAIN_STREET_INSTITUTIONAL'],
        revision_sha256: str | None = None,
        who=Depends(reader),
    ):
        permit(who, domain)
        try:
            baseline, verification = load_verified_baseline(Path(__file__).resolve().parents[1])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(503, 'College Park baseline verification unavailable') from exc
        if revision_sha256 is not None and revision_sha256 != verification["baseline_sha256"]:
            raise HTTPException(409, 'College Park baseline revision changed')
        return {
            "baseline": baseline,
            "revision_sha256": verification["baseline_sha256"],
            "citywide_comparators": verification["citywide_comparators"],
            "district_residential_permits": verification["district_residential_permits"],
            "edgewater_funding": verification["edgewater_funding"],
            "district_operations": verification["district_operations"],
            "authority": planning.AUTHORITY,
        }

    @app.get('/api/cities-planning/research/orlando-hpi')
    def orlando_hpi_forecast(who=Depends(reader)):
        permit(who, 'MAIN_STREET_INSTITUTIONAL')
        root = Path(__file__).resolve().parents[1]
        reports = root / 'docs' / 'acquisition'
        artifact = reports / 'orlando-hpi-2027q3-forecast-issue.json'
        try:
            with artifact.open('rb') as stream:
                raw = stream.read(16385)
            if len(raw) > 16384:
                raise ValueError('Forecast issue exceeds the readback limit')
            issue = json.loads(raw)
            payload = issue['payload']
            encoded = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
            if (sha256(encoded).hexdigest() != issue['sha256']
                    or payload['schema'] != 'hpi-forecast-issue/1'
                    or payload['state'] != 'ISSUED_RESEARCH_ONLY'):
                raise ValueError('Invalid research forecast issue')
            context_raw = (reports / 'orlando-hpi-planning-context.json').read_bytes()
            context = json.loads(context_raw)
            if (context['issue_sha256'] != issue['sha256']
                    or context['place_id'] != payload['target']['place_id']):
                raise ValueError('Planning context belongs to another forecast')
            for source in context['sources'].values():
                path = (root / source['path']).resolve()
                if not path.is_relative_to(root / 'docs'):
                    raise ValueError('Forecast source is outside the evidence directory')
                if sha256(path.read_bytes()).hexdigest() != source['sha256']:
                    raise ValueError('Forecast planning evidence changed')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise HTTPException(503, 'Saved research forecast is unavailable') from exc
        return {
            **issue, 'planning_context': context,
            'planning_context_sha256': sha256(context_raw).hexdigest(),
        }

    @app.get('/api/cities-planning/{forecast_id}')
    def planning_record(forecast_id:str,who=Depends(reader)):
        try:
            with conn() as db:
                report=planning.get(db,forecast_id)
                permit(who,report['security_domain'])
                return report
        except planning.PlanningError as exc:
            raise HTTPException(exc.code,str(exc)) from exc
