"""Bounded research screening over completed immutable acquisition runs.
This is a CPU gate matrix, not legal verification or GPU acceleration.
"""
import json
from collections import Counter
from . import strategy_cases as cases
from . import unit_evidence as u
from .acquisition_runs import sha, encode, now, get
from .profit_review import MAX_CENTS
VERSION='br-strategy-batch/2'

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS strategy_batch_receipts(id TEXT PRIMARY KEY, receipt TEXT NOT NULL, created TEXT NOT NULL)')
    for op in ('UPDATE','DELETE'):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS strategy_batch_no_{op.lower()} BEFORE {op} ON strategy_batch_receipts BEGIN SELECT RAISE(ABORT,'Immutable strategy batch'); END")

def screen(db,run_id,offset,limit):
    run=get(db,run_id)
    if run['state']!='COMPLETED':raise ValueError('Complete acquisition run before batch strategy screening')
    if type(offset)!=int or type(limit)!=int or offset<0 or not 1<=limit<=1000 or offset>=run['total']:raise ValueError('Invalid batch bounds')
    cat=cases.load_catalog(); digest=sha(cat)
    gates={r['source']['ID']:cases.unit_fit(r['source']['ID']) for r in cat['records']}
    rows=db.execute('SELECT p.parcel_key,p.record,r.result FROM acq_parcels p JOIN acq_results r ON r.run_id=? AND r.parcel_key=p.parcel_key WHERE p.snapshot_id=? AND p.ordinal>=? ORDER BY p.ordinal LIMIT ?',(run_id,run['snapshot_id'],offset,limit)).fetchall()
    if len(rows)!=min(limit,run['total']-offset):raise ValueError('Missing processed result')
    # The current pipeline cannot supply accepted legal counts, even if a reported count exists.
    # Fail closed if a future adapter starts emitting accepted units; do not silently ignore it.
    records=[]; counts=Counter(); templates={}
    for row in rows:
        result=json.loads(row['result'])
        if result.get('legal_units') is not None:raise ValueError('Accepted legal-unit adapter requires new strategy gate contract')
        st=u.state(db,run['snapshot_id'],row['parcel_key']);template={sid:u.fit(sid,st,cases.PILOTS) for sid in gates};tid=sha(template);templates[tid]=template;counts.update(template.values())
        records.append({'parcel_key':row['parcel_key'],'record_sha256':sha(json.loads(row['record'])),'screen_sha256':sha(result),'legal_units':None,'unit_evidence_sha256':st['evidence_sha256'],'reviewed_research_units':st['reviewed_units'],'gate_template_id':tid})
    n=len(records)
    body={'version':VERSION,'catalog_sha256':digest,'run_id':run_id,'snapshot_id':run['snapshot_id'],'offset':offset,'end':offset+n,'total_parcels':run['total'],'records':records,'strategy_gate_template':gates if len(templates)==1 and next(iter(templates.values()))==gates else None,'gate_templates':templates,'evaluated_pairs':n*len(gates),'gate_counts':dict(counts),'next_offset':offset+n if offset+n<run['total'] else None,'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'executor':'CPU_RULE_REFERENCE','offer_ready':0,'dispatch_performed':False,'financial_authority_cents':0,'scope':'COMPRESSED_REVIEWED_RESEARCH_GATE_MATRIX_ONLY'}
    rid=sha(body);prior=db.execute('SELECT receipt FROM strategy_batch_receipts WHERE id=?',(rid,)).fetchone()
    if prior:return {'receipt':json.loads(prior[0]),'replay':True}
    receipt={**body,'id':rid};db.execute('INSERT INTO strategy_batch_receipts VALUES(?,?,?)',(rid,encode(receipt),now()));return {'receipt':receipt,'replay':False}

def read(db,rid):
    row=db.execute('SELECT receipt FROM strategy_batch_receipts WHERE id=?',(rid,)).fetchone()
    if row is None:raise LookupError('Strategy batch not found')
    receipt=json.loads(row[0]);current=all(r.get('unit_evidence_sha256')==u.state(db,receipt['snapshot_id'],r['parcel_key'])['evidence_sha256'] for r in receipt.get('records',[])) if 'snapshot_id' in receipt else None
    return {'receipt':receipt,'catalog_current':receipt.get('catalog_sha256')==sha(cases.load_catalog()),'unit_evidence_current':current}


def purchase_limits(db,cid,finance_id,inputs):
    """Hypothetical fixed-loan acquisition budget and yield screen. No appraisal or offer."""
    case=cases.read_case(db,cid)
    if not case['catalog_current'] or not case['unit_evidence_current']:raise ValueError('Strategy catalog or unit evidence changed')
    row=db.execute('SELECT receipt FROM strategy_financial_receipts WHERE id=? AND case_id=?',(finance_id,cid)).fetchone()
    if row is None:raise LookupError('Matching financial receipt not found')
    fin=json.loads(row[0])
    if fin.get('scope')!='HYPOTHETICAL_EXISTING_RENTAL_ANNUAL_ONLY':raise ValueError('Incompatible financial receipt for rental purchase model')
    cash=fin['report']['operating_review']['distributable_cash_cents']
    downside=next((s['result']['distributable_cash_cents'] for s in fin['report']['scenarios'] if s['id']=='REVENUE_DOWN_10'),None)
    keys={'price_cents','loan_cents','closing_cents','initial_repair_cents','initial_reserve_cents','cash_budget_cents','min_yield_bps'}
    if set(inputs)!=keys:raise ValueError('All purchase assumptions must be explicitly present; use null for unknown')
    for k,v in inputs.items():
        if v is not None and (type(v)!=int or not 0<=v<= (100000 if k=='min_yield_bps' else MAX_CENTS)):raise ValueError('Invalid assumption '+k)
    p,l,c,r,s,b,y=(inputs[k] for k in ('price_cents','loan_cents','closing_cents','initial_repair_cents','initial_reserve_cents','cash_budget_cents','min_yield_bps'))
    if p is not None and l is not None and l>p:raise ValueError('Fixed loan cannot exceed purchase price')
    other=None if None in (c,r,s) else c+r+s
    equity=None if None in (p,l,other) else p-l+other
    cap_budget=None if None in (b,l,other) else b+l-other
    cap_yield=None if None in (cash,l,other,y) or y==0 else cash*10000//y+l-other
    max_price=None if cap_budget is None or (y!=0 and cap_yield is None) else min(cap_budget,cap_yield) if cap_yield is not None else cap_budget
    feasible=None if max_price is None or l is None else max_price>=l and (y!=0 or (cash is not None and cash>=0))
    for v in (other,equity,cap_budget,cap_yield,max_price):
        if v is not None and abs(v)>MAX_CENTS:raise ValueError('Result exceeds exact JSON integer range')
    body={'version':'br-fixed-loan-purchase/1','case_id':cid,'finance_id':finance_id,'catalog_sha256':fin['catalog_sha256'],'inputs':inputs,'annual_cash_cents':cash,'downside_annual_cash_cents':downside,'initial_cash_required_cents':equity,'budget_price_cap_cents':cap_budget,'yield_price_cap_cents':cap_yield,'conditional_price_ceiling_cents':max_price if feasible else None,'status':'HYPOTHETICAL_ONLY','decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'financial_authority_cents':0,'limitations':['Fixed loan amount and annual debt service supplied independently; lender terms, consistency, appraisal and availability not verified.','Initial repairs/reserves are separate from annual costs; avoid double counting. No taxes, exit valuation, financing approval or offer.','Price ceiling is a budget/yield arithmetic bound only, not market value.']}
    rid=sha(body);prior=db.execute('SELECT receipt FROM strategy_batch_receipts WHERE id=?',(rid,)).fetchone()
    if prior:return {'receipt':json.loads(prior[0]),'replay':True}
    receipt={**body,'id':rid};db.execute('INSERT INTO strategy_batch_receipts VALUES(?,?,?)',(rid,encode(receipt),now()));return {'receipt':receipt,'replay':False}
