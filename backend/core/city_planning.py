"""Conditional city population scenarios and an immutable local scenario registry.

This is an arithmetic planning screen, not an estimated demographic model.
Rates are operator assumptions. Accuracy remains unassessed until a separate,
properly matched observed-outcome evaluation is implemented.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import hashlib
import json
import re
from urllib.parse import urlparse

VERSION = 'city-planning-1.0'
DOMAINS = {'COMMERCIAL','MAIN_STREET_INSTITUTIONAL'}
AUTHORITY = {'financial_authority':0,'contractual_authority':0,'external_execution':False,'accepted_evidence':False}
RATE_PATTERN = re.compile(r'^[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?$')


class PlanningError(Exception):
    def __init__(self,code,detail):
        super().__init__(detail)
        self.code=code


def stamp():
    return datetime.now(timezone.utc).isoformat()


def today():
    return datetime.now(timezone.utc).date()


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS city_planning_forecasts(
        forecast_id TEXT PRIMARY KEY,security_domain TEXT NOT NULL,place_id TEXT NOT NULL,
        forecast_revision INTEGER NOT NULL,input_sha256 TEXT NOT NULL,output_sha256 TEXT NOT NULL,
        created_at TEXT NOT NULL,payload TEXT NOT NULL,
        UNIQUE(security_domain,place_id,forecast_revision))''')
    db.execute('''CREATE TABLE IF NOT EXISTS city_planning_requests(
        request_id TEXT PRIMARY KEY,request_sha256 TEXT NOT NULL,forecast_id TEXT NOT NULL,
        FOREIGN KEY(forecast_id) REFERENCES city_planning_forecasts(forecast_id))''')
    for table in ('city_planning_forecasts','city_planning_requests'):
        for verb in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS no_{table}_{verb.lower()} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT,'Append-only planning history'); END")


def validate(body):
    baseline=body['baseline']
    if body['security_domain'] not in DOMAINS:
        raise PlanningError(422,'Unsupported planning security domain')
    for field in ('place_id','title','vintage'):
        if not baseline[field].strip():
            raise PlanningError(422,f'baseline.{field} cannot be blank')
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',baseline['reference_date']):
            raise ValueError()
        reference=date.fromisoformat(baseline['reference_date'])
    except ValueError:
        raise PlanningError(422,'reference_date requires a valid YYYY-MM-DD date')
    if baseline['evidence_status']=='SOURCE_REPORTED' and reference>today():
        raise PlanningError(422,'A source-reported population baseline cannot have a future reference date; label a future assumption HYPOTHETICAL')
    if reference.year + body['horizon_years'] > 9999:
        raise PlanningError(422,'Projection target is outside the supported calendar')
    try:
        source=urlparse(baseline['source_url'])
        _=source.port
    except ValueError:
        raise PlanningError(422,'source_url requires a valid HTTP(S) locator')
    if source.scheme not in ('http','https') or not source.hostname or source.username or source.password or any(c.isspace() for c in baseline['source_url']):
        raise PlanningError(422,'source_url requires an HTTP(S) locator without credentials')
    seen=set()
    for scenario in body['scenarios']:
        name=scenario['name'].strip().casefold()
        if not name or name in seen:
            raise PlanningError(422,'Scenario names must be nonempty and distinct')
        seen.add(name)
        value=scenario['annual_growth_rate']
        if not RATE_PATTERN.fullmatch(value):
            raise PlanningError(422,'annual_growth_rate requires a plain decimal string with at most eight decimal places')
        try:
            rate=Decimal(value)
        except InvalidOperation:
            raise PlanningError(422,'Invalid growth rate')
        if not Decimal('-0.10')<=rate<=Decimal('0.15'):
            raise PlanningError(422,'annual_growth_rate must be between -0.10 and 0.15 for this bounded planning screen')
    return reference


def target_date(reference,horizon):
    try:
        return reference.replace(year=reference.year+horizon)
    except ValueError:
        # The sole remaining replacement failure for a validated bounded year
        # is February 29 in a non-leap target year.
        return reference.replace(year=reference.year+horizon,day=28)


def calculate(body):
    reference=validate(body)
    baseline=body['baseline']
    target=target_date(reference,body['horizon_years'])
    rows=[]
    # Inputs have <=8 fractional digits, <=10 integer population digits and a
    # <=20-year integer exponent. 256 digits exceed the exact product size.
    with localcontext() as context:
        context.prec=256
        population=Decimal(baseline['population'])
        for scenario in body['scenarios']:
            rate=Decimal(scenario['annual_growth_rate'])
            unrounded=population*((Decimal(1)+rate)**body['horizon_years'])
            projected=int(unrounded.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
            pct=None if population==0 else format(((unrounded-population)/population*100).quantize(Decimal('0.0001'),rounding=ROUND_HALF_UP),'f')
            rows.append({'name':scenario['name'],'annual_growth_rate':scenario['annual_growth_rate'],
                         'projected_population':projected,'net_population_change':projected-baseline['population'],
                         'total_change_pct':pct,'rate_kind':'OPERATOR_ASSUMPTION',
                         'classification':'HYPOTHETICAL_SCENARIO'})
    return {
        'security_domain':body['security_domain'],'baseline':baseline,
        'horizon_years':body['horizon_years'],'target_date':target.isoformat(),'scenarios':rows,
        'classification':'HYPOTHETICAL_SCENARIOS','accuracy_status':'UNASSESSED',
        'baseline_verification_status':'UNVERIFIED','confidence':None,'engine_version':VERSION,
        'method':'P(t) = P(0) × (1 + annual_growth_rate)^horizon_years',
        'rounding':{'population':'ROUND_HALF_UP_TO_WHOLE_PERSON',
                    'net_change':'ROUNDED_PROJECTED_POPULATION_MINUS_BASELINE',
                    'total_change_pct':'UNROUNDED_POPULATION_CHANGE_PERCENT_ROUNDED_HALF_UP_TO_4_DECIMALS',
                    'anniversary':'FEBRUARY_29_MAPS_TO_FEBRUARY_28_IN_NON_LEAP_TARGET_YEAR'},
        'time_classification':'PROSPECTIVE_CONDITIONAL_SCENARIO' if target>today() else 'HISTORICAL_CONDITIONAL_SCENARIO_NOT_PROSPECTIVE',
        'evaluation_status':'NOT_IMPLEMENTED_NO_ACCURACY_CLAIM',
        'limits':[
            'Annual growth rates are supplied assumptions; no rate is estimated from historical data or immigration stock.',
            'These calculations are conditional scenarios, not validated forecasts or probability-weighted outcomes.',
            'The source locator is retained but not fetched or independently accepted.',
            'Population growth does not establish jobs, housing demand, utility capacity, acquisition value or profitability.',
            'Observed-outcome scoring requires compatible geography, dates, population definitions and source vintages; it is not implemented here.',
        ],
        'authority':AUTHORITY,
    }


def get(db,forecast_id):
    row=db.execute('SELECT payload FROM city_planning_forecasts WHERE forecast_id=?',(forecast_id,)).fetchone()
    if row is None:
        raise PlanningError(404,'Planning scenario record not found')
    return json.loads(row['payload'])


def project(db,event,actor,body):
    request_hash=sha(body)
    previous=db.execute('SELECT * FROM city_planning_requests WHERE request_id=?',(body['request_id'],)).fetchone()
    if previous:
        if previous['request_sha256']!=request_hash:
            raise PlanningError(409,'Request ID was already used with different content')
        return get(db,previous['forecast_id'])
    result=calculate(body)
    inputs={key:value for key,value in body.items() if key!='request_id'}
    input_hash=sha(inputs)
    baseline=body['baseline']
    latest=db.execute('''SELECT * FROM city_planning_forecasts WHERE security_domain=? AND place_id=?
                         ORDER BY forecast_revision DESC LIMIT 1''',(body['security_domain'],baseline['place_id'])).fetchone()
    if latest and latest['input_sha256']==input_hash:
        result=json.loads(latest['payload'])
    else:
        revision=latest['forecast_revision']+1 if latest else 1
        identity={'security_domain':body['security_domain'],'place_id':baseline['place_id'],
                  'revision':revision,'input_sha256':input_hash}
        result.update(forecast_id='BR-FC-'+sha(identity)[:20],forecast_revision=revision,
                      input_sha256=input_hash,created_at=stamp(),input_snapshot=inputs)
        result['output_sha256']=sha(result)
        db.execute('INSERT INTO city_planning_forecasts VALUES(?,?,?,?,?,?,?,?)',
                   (result['forecast_id'],body['security_domain'],baseline['place_id'],revision,input_hash,
                    result['output_sha256'],result['created_at'],canonical(result)))
        event(db,body['security_domain'],actor,'CITY_PLANNING_SCENARIOS_CREATED',result['forecast_id'],
              {'place_id':baseline['place_id'],'forecast_revision':revision,'input_sha256':input_hash,
               'output_sha256':result['output_sha256'],'classification':'HYPOTHETICAL_SCENARIOS'})
    db.execute('INSERT INTO city_planning_requests VALUES(?,?,?)',(body['request_id'],request_hash,result['forecast_id']))
    return result


def listing(db):
    return [json.loads(row['payload']) for row in db.execute('SELECT payload FROM city_planning_forecasts ORDER BY rowid DESC LIMIT 100')]


def contract():
    return {'version':VERSION,'security_domains':sorted(DOMAINS),
            'baseline_evidence_states':['SOURCE_REPORTED','HYPOTHETICAL'],
            'population_bounds':[0,2000000000],'horizon_year_bounds':[1,20],
            'annual_growth_rate_bounds':['-0.10','0.15'],'scenario_count_bounds':[1,5],
            'rate_representation':'Plain decimal string; up to eight fractional digits',
            'calculation':'Decimal compounding, 256-digit context, whole-person ROUND_HALF_UP',
            'classification':'HYPOTHETICAL_SCENARIOS','accuracy_status':'UNASSESSED',
            'registry':'Immutable revisions keyed by security domain and place_id',
            'list_limit':100,'list_order':'Newest saved revision first; historical IDs remain directly readable',
            'evaluation':'Deferred: no observed-outcome accuracy is asserted',
            'ai_provider':'NOT_USED','authority':AUTHORITY}
