import copy
from contextlib import contextmanager
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
import sqlite3

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

from backend.core import city_planning as planning
from backend.planning_routes import register


@pytest.fixture
def setup(tmp_path,monkeypatch):
    path=tmp_path/'planning.db'
    monkeypatch.setattr(planning,'today',lambda:date(2026,11,23))
    monkeypatch.setattr(planning,'stamp',lambda:'2026-11-23T12:00:00+00:00')
    @contextmanager
    def conn():
        db=sqlite3.connect(path)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db: yield db
        finally:
            db.close()
    with conn() as db:
        db.execute('CREATE TABLE log(domain TEXT,actor TEXT,action TEXT,obj TEXT,payload TEXT)')
    def event(db,domain,who,action,obj,payload):
        db.execute('INSERT INTO log VALUES(?,?,?,?,?)',(domain,who,action,obj,json.dumps(payload)))
    def actor(auth:str=Header(default='')):
        if auth not in ('FOUNDER','SW-13','SW-09'):
            raise HTTPException(401,'Credential required')
        return auth
    def permit(who,domain,write=False):
        if domain not in planning.DOMAINS:
            raise HTTPException(422,'Unknown domain')
        if who=='SW-09' or (write and who=='SW-13'):
            raise HTTPException(403,'Domain permission denied')
    app=FastAPI()
    register(app,actor,permit,conn,event)
    return TestClient(app),conn


def payload():
    return {
        'request_id':'planning-1','security_domain':'COMMERCIAL',
        'baseline':{'place_id':'US-FL-HAINES-CITY','title':'Haines City population planning baseline',
                    'population':45973,'reference_date':'2025-07-01','vintage':'Vintage 2025',
                    'source_url':'https://www.census.gov/','evidence_status':'SOURCE_REPORTED'},
        'horizon_years':5,
        'scenarios':[{'name':'Illustrative slower','annual_growth_rate':'0.005'},
                     {'name':'Illustrative middle','annual_growth_rate':'0.02'},
                     {'name':'Illustrative faster','annual_growth_rate':'0.04'}],
    }


def post(client,body,role='FOUNDER'):
    return client.post('/api/cities-planning/project',headers={'auth':role},json=body)


def test_decimal_compounding_and_unassessed_scenario_contract(setup):
    client,conn=setup
    body=payload()
    response=post(client,body)
    assert response.status_code==200,response.text
    report=response.json()
    assert report['classification']=='HYPOTHETICAL_SCENARIOS'
    assert report['accuracy_status']=='UNASSESSED'
    assert report['baseline_verification_status']=='UNVERIFIED'
    assert report['confidence'] is None
    assert report['target_date']=='2030-07-01'
    assert report['time_classification']=='PROSPECTIVE_CONDITIONAL_SCENARIO'
    assert report['baseline']==body['baseline']
    assert report['input_snapshot']=={k:v for k,v in body.items() if k!='request_id'}
    assert report['input_sha256']==planning.sha(report['input_snapshot'])
    assert report['output_sha256']==planning.sha({k:v for k,v in report.items() if k!='output_sha256'})
    for actual,scenario in zip(report['scenarios'],body['scenarios']):
        expected=Decimal(45973)*(1+Decimal(scenario['annual_growth_rate']))**5
        assert actual['projected_population']==int(expected.quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        assert actual['net_population_change']==actual['projected_population']-45973
        assert actual['rate_kind']=='OPERATOR_ASSUMPTION'
        assert actual['classification']=='HYPOTHETICAL_SCENARIO'
    assert report['authority']==planning.AUTHORITY
    with conn() as db:
        assert db.execute('SELECT COUNT(*) FROM city_planning_forecasts').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM log').fetchone()[0]==1


def test_rounding_is_final_not_compounded_from_display_integer(setup):
    client,_=setup
    body=payload()
    body['baseline']['population']=10
    body['horizon_years']=1
    body['scenarios']=[{'name':'Growth','annual_growth_rate':'0.15'},{'name':'Decline','annual_growth_rate':'-0.05'}]
    first=post(client,body).json()
    assert [x['projected_population'] for x in first['scenarios']]==[12,10]
    body['request_id']='two-years'
    body['horizon_years']=2
    second=post(client,body).json()
    assert [x['projected_population'] for x in second['scenarios']]==[13,9]


def test_zero_and_negative_growth_and_zero_population(setup):
    client,_=setup
    body=payload()
    body['horizon_years']=2
    body['baseline']['population']=100
    body['scenarios']=[{'name':'No change','annual_growth_rate':'0'},{'name':'Decline','annual_growth_rate':'-0.10'}]
    result=post(client,body).json()
    assert [x['projected_population'] for x in result['scenarios']]==[100,81]
    assert result['scenarios'][1]['net_population_change']==-19
    assert result['scenarios'][1]['total_change_pct']=='-19.0000'
    body['request_id']='zero-baseline'
    body['baseline']['population']=0
    result=post(client,body).json()
    assert all(x['projected_population']==0 and x['total_change_pct'] is None for x in result['scenarios'])


def test_exact_retry_and_changed_request_conflict(setup):
    client,conn=setup
    body=payload()
    original=post(client,body).json()
    assert post(client,body).json()==original
    changed=copy.deepcopy(body)
    changed['horizon_years']=6
    assert post(client,changed).status_code==409
    body['request_id']='same-input-new-request'
    assert post(client,body).json()==original
    with conn() as db:
        assert db.execute('SELECT COUNT(*) FROM city_planning_forecasts').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM city_planning_requests').fetchone()[0]==2


def test_immutable_version_history_survives_changed_input_and_return_to_old_input(setup):
    client,conn=setup
    body=payload()
    first=post(client,body).json()
    changed=copy.deepcopy(body)
    changed.update(request_id='second',horizon_years=10)
    second=post(client,changed).json()
    body['request_id']='return-to-original-input'
    third=post(client,body).json()
    assert [first['forecast_revision'],second['forecast_revision'],third['forecast_revision']]==[1,2,3]
    assert first['input_sha256']==third['input_sha256']
    assert first['forecast_id']!=third['forecast_id']
    stored=client.get('/api/cities-planning/'+first['forecast_id'],headers={'auth':'FOUNDER'}).json()
    assert stored==first
    listed=client.get('/api/cities-planning',headers={'auth':'FOUNDER'}).json()
    assert [x['forecast_revision'] for x in listed]==[3,2,1]
    with pytest.raises(sqlite3.IntegrityError,match='Append-only'):
        with conn() as db:
            db.execute('DELETE FROM city_planning_forecasts')
    with pytest.raises(sqlite3.IntegrityError,match='Append-only'):
        with conn() as db:
            db.execute('UPDATE city_planning_requests SET forecast_id=?',(first['forecast_id'],))


def test_same_place_id_isolated_between_security_domains(setup):
    client,_=setup
    body=payload()
    commercial=post(client,body).json()
    body.update(request_id='institutional',security_domain='MAIN_STREET_INSTITUTIONAL')
    institutional=post(client,body).json()
    assert commercial['forecast_id']!=institutional['forecast_id']
    assert commercial['forecast_revision']==institutional['forecast_revision']==1


def test_leap_anniversary_and_calendar_overflow(setup):
    client,_=setup
    body=payload()
    body['baseline']['reference_date']='2024-02-29'
    body['horizon_years']=1
    first=post(client,body).json()
    assert first['target_date']=='2025-02-28'
    assert first['time_classification']=='HISTORICAL_CONDITIONAL_SCENARIO_NOT_PROSPECTIVE'
    body.update(request_id='leap-four',horizon_years=4)
    assert post(client,body).json()['target_date']=='2028-02-29'
    body['request_id']='calendar-overflow'
    body['baseline'].update(reference_date='9999-01-01',evidence_status='HYPOTHETICAL')
    assert post(client,body).status_code==422


def test_future_baseline_requires_explicit_hypothetical_label(setup):
    client,_=setup
    body=payload()
    body['baseline']['reference_date']='2028-01-01'
    assert post(client,body).status_code==422
    body['baseline']['evidence_status']='HYPOTHETICAL'
    response=post(client,body)
    assert response.status_code==200
    assert response.json()['baseline_verification_status']=='UNVERIFIED'


@pytest.mark.parametrize('path,value',[
    ('horizon_years',0),('horizon_years',21),('horizon_years',True),('horizon_years',1.5),
    ('population',-1),('population',2000000001),('population',True),('population',10.5),
    ('annual_growth_rate','NaN'),('annual_growth_rate','Infinity'),('annual_growth_rate','1e-2'),
    ('annual_growth_rate','0.15000001'),('annual_growth_rate','-0.10000001'),
    ('annual_growth_rate','0.010000001'),('annual_growth_rate',0.02),
    ('reference_date','2025-02-29'),('reference_date','2025-1-1'),
    ('source_url','https://['),('source_url','https://x.invalid:bad'),
    ('source_url','https://user:token@example.invalid'),('source_url','file:///etc/passwd'),
    ('source_url','https://bad host.invalid'),('source_url','https://:80'),
    ('evidence_status','VERIFIED'),('vintage',' '),('place_id',' '),
])
def test_invalid_inputs_fail_without_saving(setup,path,value):
    client,conn=setup
    body=payload()
    if path=='horizon_years':
        body[path]=value
    elif path=='annual_growth_rate':
        body['scenarios'][0][path]=value
    else:
        body['baseline'][path]=value
    assert post(client,body).status_code==422
    with conn() as db:
        assert db.execute('SELECT COUNT(*) FROM city_planning_forecasts').fetchone()[0]==0


@pytest.mark.parametrize('where,field,value',[
    ('root','confidence',0.99),('root','accuracy_status','VALIDATED'),
    ('baseline','accepted',True),('scenario','probability',0.8),
])
def test_caller_cannot_label_accuracy_or_acceptance(setup,where,field,value):
    client,_=setup
    body=payload()
    target=body if where=='root' else body['baseline'] if where=='baseline' else body['scenarios'][0]
    target[field]=value
    assert post(client,body).status_code==422


def test_duplicate_empty_or_excess_scenarios_rejected(setup):
    client,_=setup
    body=payload()
    body['scenarios'][1]['name']=' illustrative SLOWER '
    assert post(client,body).status_code==422
    body['scenarios']=[]
    assert post(client,body).status_code==422
    body['scenarios']=[{'name':str(i),'annual_growth_rate':'0.01'} for i in range(6)]
    assert post(client,body).status_code==422


def test_permissions_and_read_contract(setup):
    client,_=setup
    assert post(client,payload(),role='SW-13').status_code==403
    assert post(client,payload(),role='SW-09').status_code==403
    assert post(client,payload(),role='').status_code==401
    report=post(client,payload()).json()
    assert client.get('/api/cities-planning/'+report['forecast_id'],headers={'auth':'SW-13'}).status_code==200
    assert client.get('/api/cities-planning',headers={'auth':'SW-09'}).status_code==403
    assert client.get('/api/cities-planning/no-such-id',headers={'auth':'FOUNDER'}).status_code==404
    contract=client.get('/api/cities-planning/contract',headers={'auth':'FOUNDER'}).json()
    assert contract['list_limit']==100 and contract['accuracy_status']=='UNASSESSED'


def test_saved_research_forecast_is_authenticated_and_unscored(setup):
    client, _ = setup
    path = '/api/cities-planning/research/orlando-hpi'
    assert client.get(path).status_code == 401
    assert client.get(path, headers={'auth': 'SW-09'}).status_code == 403
    founder = client.get(path, headers={'auth': 'FOUNDER'})
    assert founder.status_code == 200
    assert client.get(path, headers={'auth': 'SW-13'}).json() == founder.json()
    forecast = founder.json()['payload']
    assert forecast['target']['quarter'] == '2027-Q3'
    assert forecast['target']['place_id'] == '36740'
    assert forecast['observation'] is None
    assert forecast['financial_authority'] == 0
    readback = founder.json()
    context = readback['planning_context']
    assert context['issue_sha256'] == readback['sha256']
    assert context['place_id'] == forecast['target']['place_id']
    assert len(readback['planning_context_sha256']) == 64
    assert [row['fips'] for row in context['boundary_reference']['members']] == [
        '12069', '12095', '12097', '12117']
    assert [pillar['id'] for pillar in context['pillars']] == ['UP-10', 'UP-18']
    assert not context['boundary_reference']['full_geometry_verified']


def test_orlando_forecast_withholds_changed_planning_context(setup, monkeypatch):
    from pathlib import Path

    client, _ = setup
    read_bytes = Path.read_bytes

    def changed_source(path):
        raw = read_bytes(path)
        if path.name == "orlando-hpi-as-published-interval-replay.json":
            return raw + b" "
        return raw

    monkeypatch.setattr(Path, "read_bytes", changed_source)
    response = client.get("/api/cities-planning/research/orlando-hpi", headers={"auth": "FOUNDER"})
    assert response.status_code == 503


def test_college_park_baseline_shared_revision_and_domain_permission(setup):
    client, _ = setup
    endpoint = "/api/cities-planning/research/college-park-baseline"
    headers = {"auth": "FOUNDER"}
    main_street = {"domain": "MAIN_STREET_INSTITUTIONAL"}
    assert client.get(endpoint, params=main_street).status_code == 401
    assert client.get(endpoint, params=main_street, headers={"auth": "SW-09"}).status_code == 403
    response = client.get(endpoint, params=main_street, headers=headers)
    assert response.status_code == 200, response.text
    projection = response.json()
    revision = projection["revision_sha256"]
    assert projection["baseline"]["place_id"] == "US-FL-ORLANDO:COLLEGE-PARK"
    assert projection["baseline"]["scope_gaps"]["legal_access"] is None
    assert projection["authority"] == planning.AUTHORITY
    citywide = projection["citywide_comparators"]
    assert citywide["employment"]["measures"]["wac"]["jobs"] == 416204
    assert citywide["employment"]["measures"]["rac"]["jobs"] == 154806
    assert citywide["assessor_housing"]["reported_unit_sum"] == 155502
    assert citywide["assessor_housing"]["parcels_without_numeric_values"] == 18571
    permits = projection["district_residential_permits"]
    assert permits["residential_review_issued_building_permits"] == 3
    assert permits["worktypes"]["New"] == {"issued": 1, "final_date": 1, "coo_date": 0, "coc_date": 1}
    assert projection["baseline"]["scope_gaps"]["completed_housing"] is None
    funding = projection["edgewater_funding"]
    roundabout, corridor = funding["records"]
    assert roundabout["published_project_cost"] == "5175441.22"
    assert roundabout["actual_expenditure"] is None and corridor["commitment"] is None
    assert funding["regional_tip_comparison"]["difference_from_city_reported_lap"] == "10000"
    operations = projection["district_operations"]
    assert operations["period_end"] == "2024-12-31"
    assert operations["reported_amounts"]["CYRevenuesLessExpensesAmt"] == -52385
    assert operations["current_budget"] is None and operations["vacancy"] is None
    commercial = {"domain": "COMMERCIAL", "revision_sha256": revision}
    assert client.get(endpoint, params=commercial, headers=headers).json() == projection
    commercial["revision_sha256"] = "0" * 64
    assert client.get(endpoint, params=commercial, headers=headers).status_code == 409


def test_college_park_baseline_unavailable_without_verified_receipts(setup, monkeypatch):
    client, _ = setup
    def stale(_):
        raise ValueError("Stale baseline source")
    monkeypatch.setattr("backend.planning_routes.load_verified_baseline", stale)
    response = client.get("/api/cities-planning/research/college-park-baseline",
                          params={"domain": "COMMERCIAL"}, headers={"auth": "FOUNDER"})
    assert response.status_code == 503
