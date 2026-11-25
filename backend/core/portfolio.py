"""Bounded portfolio scheduling over hypothetical rental financing receipts.
No market, capital or transaction authority. All money is integer USD cents.
"""
from collections import Counter
import json
from . import strategy_cases as cases, financing
from .acquisition_runs import sha,encode,now
from .profit_review import MAX_CENTS
VERSION='br-portfolio-schedule/1'

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS portfolio_receipts(id TEXT PRIMARY KEY, receipt TEXT NOT NULL, created TEXT NOT NULL)')
    for op in ('UPDATE','DELETE'):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS portfolio_no_{op.lower()} BEFORE {op} ON portfolio_receipts BEGIN SELECT RAISE(ABORT,'Immutable portfolio receipt'); END")

def integer(x,lo,hi,label):
    if type(x) is not int or not lo<=x<=hi:raise ValueError('Invalid '+label)
    return x

def exact(x):return integer(x,-MAX_CENTS,MAX_CENTS,'computed cents outside safe range')

def debt_schedule(principal,payment,rate,years):
    balance=principal;result=[]
    for _ in range(years):
        total=0
        for _ in range(12):
            interest=(balance*rate+60000)//120000
            due=min(payment,balance+interest);balance+=interest-due;total+=due
        result.append(exact(total))
    return result

def optimize(options,*,initial_cash_cents,liquidity_floor_cents,max_managed_units,existing_managed_units,horizon_years,stress_revenue_bps,stress_opex_bps,stress_extra_capex_per_unit_cents):
    for k,v,lo,hi in [('initial cash',initial_cash_cents,0,MAX_CENTS),('liquidity floor',liquidity_floor_cents,0,MAX_CENTS),('managed capacity',max_managed_units,0,100000),('existing units',existing_managed_units,0,100000),('horizon',horizon_years,1,5),('revenue stress',stress_revenue_bps,0,10000),('expense stress',stress_opex_bps,0,10000),('extra capex',stress_extra_capex_per_unit_cents,0,MAX_CENTS)]:integer(v,lo,hi,k)
    if not 1<=len(options)<=12:raise ValueError('Supply 1–12 dated financing options')
    if len({(o['finance_id'],o['year']) for o in options})!=len(options):raise ValueError('Duplicate financing option and year')
    opts=[]
    for o in sorted(options,key=lambda o:(o['year'],o['finance_id'])):
        a,b=o['inputs'],o['best']; year=integer(o['year'],1,horizon_years,'acquisition year')
        debt=debt_schedule(b['loan_cents'],b['monthly_payment_cents'],a['annual_rate_bps'],horizon_years-year+1)
        if debt[0]!=b['year_one_debt_service_cents']:raise ValueError('Financing receipt debt mismatch')
        recurring=a['annual_reserves_cents']+a['annual_capex_cents'];n=a['assumed_units']
        base=a['annual_revenue_cents']-a['annual_opex_cents']-recurring
        # Common scenario affects every owned asset together; floor revenue, ceil expenses.
        down=a['annual_revenue_cents']*(10000-stress_revenue_bps)//10000-financing.ceildiv(a['annual_opex_cents']*(10000+stress_opex_bps),10000)-recurring-n*stress_extra_capex_per_unit_cents
        opts.append({**o,'units':n,'initial':b['initial_cash_required_cents'],'annual_base':[exact(base-d) for d in debt],'annual_stress':[exact(down-d) for d in debt]})
    failures=Counter();best=None;score=None;feasible=0
    # Exhaustive subsets of dated options. One acquisition per parcel, including alternatives in different years.
    for mask in range(1<<len(opts)):
        selected=[o for i,o in enumerate(opts) if mask>>i&1]
        if len({o['parcel_key'] for o in selected})!=len(selected):failures['DUPLICATE_PROPERTY']+=1;continue
        cash=[initial_cash_cents]*2; units=existing_managed_units; rows=[];reason=None
        if min(cash)<liquidity_floor_cents:reason='INITIAL_LIQUIDITY'
        elif units>max_managed_units:reason='MANAGEMENT_CAPACITY'
        for y in range(1,horizon_years+1):
            if reason:break
            new=[o for o in selected if o['year']==y];spend=exact(sum(o['initial'] for o in new));units+=sum(o['units'] for o in new)
            if units>max_managed_units:reason='MANAGEMENT_CAPACITY';break
            cash=[exact(c-spend) for c in cash];after=cash.copy()
            if min(cash)<liquidity_floor_cents:reason='ACQUISITION_LIQUIDITY';break
            owned=[o for o in selected if o['year']<=y];flows=[exact(sum(o[k][y-o['year']] for o in owned)) for k in ('annual_base','annual_stress')]
            cash=[exact(c+f) for c,f in zip(cash,flows)]
            if min(cash)<liquidity_floor_cents:reason='YEAR_END_LIQUIDITY';break
            rows.append({'year':y,'acquisitions':[o['finance_id'] for o in new],'initial_cash_spent_cents':spend,'managed_units':units,'baseline_post_purchase_cash_cents':after[0],'stress_post_purchase_cash_cents':after[1],'baseline_operating_cash_cents':flows[0],'stress_operating_cash_cents':flows[1],'baseline_ending_cash_cents':cash[0],'stress_ending_cash_cents':cash[1]})
        if reason:failures[reason]+=1;continue
        feasible+=1
        # Maximize sustainable terminal-year stressed cash, then stressed liquid cash, then baseline cash.
        rank=(rows[-1]['stress_operating_cash_cents'],cash[1],cash[0],-len(selected))
        if score is None or rank>score:
            score=rank;best={'selected':[{'finance_id':o['finance_id'],'parcel_key':o['parcel_key'],'year':o['year'],'units':o['units']} for o in selected],'years':rows,'terminal_stress_operating_cash_cents':rank[0],'terminal_stress_liquid_cash_cents':cash[1]}
    return {'status':'CONDITIONAL_SCHEDULE' if best is not None else 'NO_FEASIBLE_SCHEDULE','evaluated_subsets':1<<len(opts),'feasible_subsets':feasible,'first_failure_counts':dict(failures),'best':best,'objective':'MAX_TERMINAL_STRESS_OPERATING_CASH_THEN_STRESS_LIQUIDITY_THEN_BASELINE_LIQUIDITY_THEN_FEWER_ACQUISITIONS'}

def run(db,dated_options,assumptions):
    options=[]
    for item in dated_options:
        fid=item['finance_id'];row=db.execute('SELECT receipt,case_id FROM strategy_financial_receipts WHERE id=?',(fid,)).fetchone()
        if row is None:raise LookupError('Financing receipt not found')
        r=json.loads(row['receipt']);case=cases.read_case(db,row['case_id']);cr=case['receipt']
        if not case['catalog_current'] or not case['unit_evidence_current']:raise ValueError('Stale financing case; prepare a new scenario')
        if r.get('version')!=financing.VERSION or r.get('strategy_id')!='SMF-01' or not r.get('result',{}).get('best'):raise ValueError('Only passing SMF-01 rental financing grid receipts supported')
        if r['id']!=fid or sha({k:v for k,v in r.items() if k!='id'})!=fid:raise ValueError('Financing receipt integrity mismatch')
        if r['case_id']!=cr['id'] or r['catalog_sha256']!=cr['catalog_sha256'] or r['unit_evidence_sha256']!=cr['unit_evidence_sha256']:raise ValueError('Financing receipt context mismatch')
        options.append({'finance_id':fid,'year':item['year'],'parcel_key':cr['parcel_key'],'inputs':r['inputs'],'best':r['result']['best']})
    options.sort(key=lambda o:(o['year'],o['finance_id']))
    result=optimize(options,**assumptions)
    body={'version':VERSION,'options':options,'assumptions':assumptions,'result':result,'authority':'HYPOTHETICAL_RESEARCH_ONLY','financial_authority_cents':0,'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'limitations':['Only SMF-01 rental grid winners; assumed units and financing are not verified. No owner-occupancy returns, additional borrowing, sales, refinancing, appreciation, tax or external cash contributions.','Options are dated at start of year; end-year distributions can finance later acquisitions. Initial and recurring reserves are segregated, not redeployed; cash capex assumed incremental to reserves.','Common stress is a deterministic scenario, not a probability. Constant annual revenue and costs; actual fixed-payment debt schedule. No monthly liquidity, timing risk, concentration by market, or actual operating-capacity assessment. Existing units consume capacity; existing-asset cash and debt are excluded.','Exact search of supplied dated subsets only, including doing nothing; no continuous price or time optimization.']}
    rid=sha(body);old=db.execute('SELECT receipt FROM portfolio_receipts WHERE id=?',(rid,)).fetchone()
    if old:return {'receipt':json.loads(old[0]),'replay':True}
    receipt={**body,'id':rid};db.execute('INSERT INTO portfolio_receipts VALUES(?,?,?)',(rid,encode(receipt),now()));return {'receipt':receipt,'replay':False}
