"""Evidence-bound research preparation; no strategy, property or transaction approval."""
from .strategy_library import load_catalog
from .acquisition_runs import get, encode, sha, now
from .acquisition_cohorts import evidence
from .profit_review import review, VERSION as PROFIT_VERSION, OPERATING_FIELDS, CAPITAL_FIELDS, MAX_CENTS
import json
from . import unit_evidence as u
VERSION='br-strategy-case/1'
FIN_VERSION='br-strategy-economics/1'
PILOTS={'SMF-01':(4,), 'SMF-02':(2,3,4)}


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS strategy_case_receipts(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, parcel_key TEXT NOT NULL, catalog_sha TEXT NOT NULL, receipt TEXT NOT NULL, created TEXT NOT NULL, FOREIGN KEY(run_id,parcel_key) REFERENCES acq_results(run_id,parcel_key))''')
    db.execute('''CREATE TABLE IF NOT EXISTS strategy_financial_receipts(id TEXT PRIMARY KEY, case_id TEXT NOT NULL, receipt TEXT NOT NULL, created TEXT NOT NULL, FOREIGN KEY(case_id) REFERENCES strategy_case_receipts(id))''')
    for table in ('strategy_case_receipts','strategy_financial_receipts'):
        for op in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable strategy receipt'); END")


def catalog_view(query='',lane=''):
    c=load_catalog();query=query.strip().casefold()
    rows=[r for r in c['records'] if (not lane or r['model_lane']==lane) and (not query or query in ' '.join(r['source'].values()).casefold())]
    return {'catalog_sha256':sha(c),'catalog_schema_version':c['schema_version'],
            'source_hashes':c['source_hashes'],'total':len(c['records']),'matches':len(rows),
            'records':rows,'lanes':sorted({r['model_lane'] for r in c['records']}),
            'flywheels':c['flywheels'],'authority':'RESEARCH_ONLY'}


def unit_fit(strategy_id,reported_units=None,legal_units=None,*,hypothetical=False):
    """Typed gate for pilot shape only; real retained records never get verified units here."""
    if not hypothetical and legal_units is not None:
        raise ValueError('No accepted legal-unit adapter has been connected')
    for v in (reported_units,legal_units):
        if v is not None and (type(v) is not int or not 1<=v<=100000):raise ValueError('Invalid unit count')
    if strategy_id not in PILOTS:return 'RESEARCH_DEFERRED'
    if legal_units is None:return 'NEEDS_LEGAL_UNIT_EVIDENCE'
    if reported_units is not None and reported_units!=legal_units:return 'CONFLICTING_UNIT_COUNTS'
    if legal_units not in PILOTS[strategy_id]:return 'OUTSIDE_PILOT_UNIT_RANGE'
    return 'HYPOTHETICAL_UNIT_GATE_MATCH_ONLY'


def prepare(db,run_id,parcel_key,strategy_id):
    c=load_catalog();digest=sha(c);run=get(db,run_id)
    result=db.execute('SELECT result FROM acq_results WHERE run_id=? AND parcel_key=?',(run_id,parcel_key)).fetchone()
    if result is None:raise LookupError('No processed parcel result in this run')
    record=next((r for r in c['records'] if r['source']['ID']==strategy_id),None)
    if record is None:raise LookupError('Strategy not found')
    ev=evidence(db,run['snapshot_id'],parcel_key);result=json.loads(result[0])
    # Source use code is never converted into a unit count. This adapter has no accepted-unit source.
    st=u.state(db,run['snapshot_id'],parcel_key)
    fit=u.fit(strategy_id,st,PILOTS)
    body={'version':VERSION,'catalog_sha256':digest,'source_hashes':c['source_hashes'], 'run_id':run_id,'snapshot_id':run['snapshot_id'],'parcel_key':parcel_key,'record_sha256':ev['record_sha256'],'screen_result_sha256':sha(result),'source_reported_values':ev['source_reported_values'],'conflicting_fields':ev['conflicting_fields'],'legal_units':None,'unit_evidence_sha256':st['evidence_sha256'],'reviewed_research_units':st['reviewed_units'],'strategy':record,'unit_gate':fit,'diligence_gate':record['required_gate'],'work_packages':[w for w in c['work_packages'] if w['strategy_id']==strategy_id], 'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'next_action':ev['next_action'] if strategy_id in PILOTS else 'Review strategy applicability, transaction rights and required evidence before activating this research lane.','status':'HOLD_RESEARCH_ONLY','financial_authority_cents':0,'external_authority':False,'dispatch_performed':False}
    cid=sha(body)
    existing=db.execute('SELECT receipt FROM strategy_case_receipts WHERE id=?',(cid,)).fetchone()
    if existing:return {'receipt':json.loads(existing[0]),'replay':True}
    receipt={**body,'id':cid}
    db.execute('INSERT INTO strategy_case_receipts VALUES(?,?,?,?,?,?)',(cid,run_id,parcel_key,digest,encode(receipt),now()))
    return {'receipt':receipt,'replay':False}


def read_case(db,cid):
    row=db.execute('SELECT receipt,catalog_sha FROM strategy_case_receipts WHERE id=?',(cid,)).fetchone()
    if row is None:raise LookupError('Strategy case receipt not found')
    r=json.loads(row['receipt']);st=u.state(db,r['snapshot_id'],r['parcel_key'])
    return {'receipt':r,'catalog_current':row['catalog_sha']==sha(load_catalog()),'unit_evidence_current':r.get('unit_evidence_sha256')==st['evidence_sha256']}


def financial(db,cid,as_of,operations,capital):
    case=read_case(db,cid)
    if not case['catalog_current'] or not case['unit_evidence_current']:raise ValueError('Strategy catalog or unit evidence changed; prepare a new case')
    r=case['receipt'];sid=r['strategy']['source']['ID']
    if sid!='SMF-01':raise ValueError('Financial adapter not implemented for this strategy; no generic model substitution')
    def amounts(values,allowed):
        if set(values)-set(allowed):raise ValueError('Unsupported financial fields')
        out={}
        for k in allowed:
            v=values.get(k)
            if v is not None and (type(v) is not int or not 0<=v<=MAX_CENTS):raise ValueError('Use nonnegative integer USD cents or null')
            out[k]={'value_cents':v,'evidence_status':'UNKNOWN' if v is None else 'HYPOTHETICAL'}
        return out
    ops=amounts(operations,OPERATING_FIELDS);cap=amounts(capital,CAPITAL_FIELDS)
    scenarios=[];revenue=ops['revenue_cents']['value_cents']
    if revenue is not None:
        scenarios=[{'id':'REVENUE_DOWN_10','label':'10% lower annual revenue (other inputs fixed)','operations':{'revenue_cents':{'value_cents':revenue*9//10,'evidence_status':'HYPOTHETICAL'}}}]
    inputs={'schema_version':PROFIT_VERSION,'review_id':cid,'domain':'COMMERCIAL','currency':'USD','period':'ANNUAL','mode':'ANALYST_REVIEW','as_of':as_of,'source':{'reference':'hypothetical strategy scenario for receipt '+cid,'source_date':None},'subject':{'label':r['parcel_key']},'operations':ops,'capital':cap,'scenarios':scenarios}
    report=review(inputs)
    body={'version':FIN_VERSION,'case_id':cid,'strategy_id':sid,'catalog_sha256':r['catalog_sha256'],'input_sha256':report['input_sha256'],'report':report,'decision_gates':r['decision_gates'],'scope':'HYPOTHETICAL_EXISTING_RENTAL_ANNUAL_ONLY','limitations':['No acquisition basis, purchase price, closing capital, conversion cost, tax, terminal value, or owner-occupied model.','Alternatives are mutually exclusive scenarios, not additive returns. No offer or financial authority.']}
    fid=sha(body)
    row=db.execute('SELECT receipt FROM strategy_financial_receipts WHERE id=?',(fid,)).fetchone()
    if row:return {'receipt':json.loads(row[0]),'replay':True}
    receipt={**body,'id':fid};db.execute('INSERT INTO strategy_financial_receipts VALUES(?,?,?,?)',(fid,cid,encode(receipt),now()))
    return {'receipt':receipt,'replay':False}


def owner_occupancy(db,cid,inputs):
    """Hypothetical one-unit owner occupancy; no imputed rent or lender eligibility."""
    case=read_case(db,cid);r=case['receipt']
    if not case['catalog_current'] or not case['unit_evidence_current']:raise ValueError('Strategy catalog or unit evidence changed')
    if r['strategy']['source']['ID']!='SMF-02':raise ValueError('Owner-occupancy adapter requires SMF-02')
    fields=('assumed_units','tenant_revenue_cents','operating_cost_cents','debt_service_cents','reserve_contribution_cents','cash_capex_cents','alternative_housing_cost_cents')
    if set(inputs)!=set(fields):raise ValueError('Provide every assumption, using null for unknown')
    n=inputs['assumed_units']
    if type(n)!=int or n not in (2,3,4):raise ValueError('Hypothetical 2–4 unit property required')
    if r['reviewed_research_units'] is not None and r['reviewed_research_units']!=n:raise ValueError('Assumed count conflicts with scoped reviewed count')
    for k in fields[1:]:
        v=inputs[k]
        if v is not None and (type(v)!=int or not 0<=v<=MAX_CENTS):raise ValueError('Use nonnegative integer USD cents or null')
    revenue,opex,debt,reserves,capex,alternative=(inputs[k] for k in fields[1:])
    costs=None if None in (opex,debt,reserves,capex) else opex+debt+reserves+capex
    def scenario(rent):
        outlay=None if costs is None or rent is None else costs-rent
        comparison=None if outlay is None or alternative is None else alternative-outlay
        noi=None if rent is None or opex is None else rent-opex
        for v in (outlay,comparison,noi,costs):
            if v is not None and abs(v)>MAX_CENTS:raise ValueError('Result exceeds exact JSON integer range')
        return {'tenant_revenue_cents':rent,'property_noi_excluding_imputed_rent_cents':noi,'net_owner_cash_outlay_cents':outlay,'difference_vs_alternative_housing_cents':comparison}
    body={'version':'br-owner-occupied/1','case_id':cid,'strategy_id':'SMF-02','catalog_sha256':r['catalog_sha256'],'inputs':inputs,'owner_occupied_units':1,'assumed_rental_units':n-1,'baseline':scenario(revenue),'revenue_down_10':scenario(None if revenue is None else revenue*9//10),'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'scope':'HYPOTHETICAL_OWNER_OCCUPANCY_ONLY','financial_authority_cents':0,'limitations':['One owner-occupied unit, no imputed rent. Tenant revenue is collected rent from other units only. Negative net outlay means a hypothetical cash surplus, not verified investment return.','Alternative housing cost must be comparable annual out-of-pocket cost; difference is not an investment return. Excludes purchase cash, taxes on income, amortization benefit and exit value. Debt service is supplied, not loan approval.']}
    fid=sha(body);old=db.execute('SELECT receipt FROM strategy_financial_receipts WHERE id=?',(fid,)).fetchone()
    if old:return {'receipt':json.loads(old[0]),'replay':True}
    receipt={**body,'id':fid};db.execute('INSERT INTO strategy_financial_receipts VALUES(?,?,?,?)',(fid,cid,encode(receipt),now()));return {'receipt':receipt,'replay':False}
