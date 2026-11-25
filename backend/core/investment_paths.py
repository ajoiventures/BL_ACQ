"""Legacy mandate research templates and bounded capital schedules.
Site-derived discovery is owned by site_paths; these templates are not site findings.
No market or transaction authority; a path is an explicit hypothesis, not a recommendation.
"""
import json
from itertools import product
from collections import Counter
from . import strategy_cases as cases, financing, recycling, unit_evidence as u
from .strategy_library import load_catalog
from .acquisition_runs import sha, encode, now, get
from .acquisition_cohorts import evidence
from .portfolio import integer, exact
from .profit_review import MAX_CENTS
VERSION='br-investment-paths/1'
GOALS={'RECURRING_INCOME','CAPITAL_VELOCITY','OWNER_HOUSING','LONG_TERM_WEALTH','CAPITAL_PRESERVATION'}
ACTIONS=('HOLD','RENOVATE','REFINANCE','SELL')
FOCUS={'RECURRING_INCOME':('Stressed recurring cash after reserves','HOLD','RENOVATE','REFINANCE','SELL'),'CAPITAL_VELOCITY':('Dated cash recovered net of costs and payoff','SELL','REFINANCE','RENOVATE','HOLD'),'OWNER_HOUSING':('Stressed net personal housing outlay','HOLD'),'LONG_TERM_WEALTH':('Cash plus separately reported unrealized equity','RENOVATE','HOLD','REFINANCE','SELL'),'CAPITAL_PRESERVATION':('Minimum liquidity and downside losses','HOLD','SELL','RENOVATE','REFINANCE')}

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS investment_path_receipts(id TEXT PRIMARY KEY, receipt TEXT NOT NULL, created TEXT NOT NULL)')
    for op in ('UPDATE','DELETE'):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS investment_paths_no_{op.lower()} BEFORE {op} ON investment_path_receipts BEGIN SELECT RAISE(ABORT,'Immutable path receipt'); END")

def persist(db,body):
    rid=sha(body);old=db.execute('SELECT receipt FROM investment_path_receipts WHERE id=?',(rid,)).fetchone()
    if old:return {'receipt':json.loads(old[0]),'replay':True}
    receipt={**body,'id':rid};db.execute('INSERT INTO investment_path_receipts VALUES(?,?,?)',(rid,encode(receipt),now()));return {'receipt':receipt,'replay':False}

def identify(db,objective,horizon_years,unit_counts,capital_cents=None,run_id=None,parcel_key=None):
    if objective not in GOALS:raise ValueError('Unknown mandate objective')
    integer(horizon_years,1,30,'horizon')
    if not unit_counts or len(set(unit_counts))!=len(unit_counts) or any(type(v) is not int or v not in (2,3,4) for v in unit_counts):raise ValueError('Select distinct 2–4 unit targets')
    if capital_cents is not None:integer(capital_cents,0,MAX_CENTS,'hypothetical capital')
    if (run_id is None)!=(parcel_key is None) or run_id=='' or parcel_key=='':raise ValueError('Provide both run and parcel or neither')
    cat=load_catalog();context=None;state=None
    if run_id:
        run=get(db,run_id);r=db.execute('SELECT result FROM acq_results WHERE run_id=? AND parcel_key=?',(run_id,parcel_key)).fetchone()
        if not r:raise LookupError('Processed parcel required')
        ev=evidence(db,run['snapshot_id'],parcel_key);state=u.state(db,run['snapshot_id'],parcel_key)
        context={'run_id':run_id,'parcel_key':parcel_key,'snapshot_id':run['snapshot_id'],'record_sha256':ev['record_sha256'],'unit_evidence_sha256':state['evidence_sha256'],'screen_result_sha256':sha(json.loads(r[0]))}
    units=sorted(unit_counts);catalog_rows=[];paths=[]
    for rec in cat['records']:
        sid=rec['source']['ID'];pilot=sid in cases.PILOTS
        mandate_match=pilot and bool(set(units)&set(cases.PILOTS[sid])) and ((objective=='OWNER_HOUSING')==(sid=='SMF-02'))
        gate=u.fit(sid,state,cases.PILOTS) if state is not None else ('PROPERTY_NOT_SELECTED' if pilot else 'RESEARCH_DEFERRED')
        # Actual research-unit gate remains distinct from legal acceptance.
        fits=state is None or (state['reviewed_units'] is None or state['reviewed_units'] in units)
        priority='PILOT_RESEARCH' if mandate_match and fits and gate not in ('OUTSIDE_PILOT_UNIT_RANGE','CONFLICTING_UNIT_COUNTS') else 'SPECIALIST_RESEARCH'
        catalog_rows.append({'strategy_id':sid,'name':rec['source']['Strategy'],'model_lane':rec['model_lane'],'route_status':priority,'unit_gate':gate,'required_gate':rec['required_gate'],'ticket_ids':rec['ticket_ids']})
        if priority!='PILOT_RESEARCH':continue
        for action in (FOCUS[objective][1:] if sid=='SMF-01' and horizon_years>=2 else ('HOLD',)):
            steps=['SOURCE_CANDIDATE','VERIFY_TITLE_AND_LEGAL_UNITS','UNDERWRITE_AND_VERIFY_CAPITAL','HUMAN_AUTHORIZED_ACQUISITION','STABILIZE_OPERATIONS']
            if action!='HOLD':steps+=['VERIFY_'+action+'_FEASIBILITY',action]
            else:steps+=['HOLD_AND_MONITOR']
            steps+=['RECONCILE_ACTUAL_AVAILABLE_CASH','REASSESS_NEXT_ACQUISITION']
            paths.append({'path_id':sid+'-'+action,'strategy_id':sid,'action':action,'steps':steps,'status':'RESEARCH_ONLY','unit_gate':gate,'required_gate':rec['required_gate'],'next_action':'Define candidate cohort and request legal-unit, rent, cost and capital evidence' if context is None else 'Reconcile property legal-use and operating evidence before financial selection','swarm_work_package_ids':[w['work_package_id'] for w in cat['work_packages'] if w['strategy_id']==sid]})
    paths.append({'path_id':'NO_ACQUISITION','strategy_id':None,'action':'WAIT','steps':['PRESERVE_LIQUIDITY','RESOLVE_EVIDENCE_AND_CAPITAL','REASSESS_MANDATE'],'status':'RESEARCH_ONLY','unit_gate':'NOT_APPLICABLE','required_gate':'No acquisition is required','next_action':'Resolve capital and evidence gaps','swarm_work_package_ids':[]})
    return persist(db,{'version':VERSION,'kind':'EARLY_PATH_IDENTIFICATION','catalog_sha256':sha(cat),'objective':objective,'evaluation_focus':FOCUS[objective][0],'horizon_years':horizon_years,'target_units':units,'hypothetical_capital_cents':capital_cents,'context':context,'catalog_dispositions':catalog_rows,'candidate_paths':paths,'flywheels':cat['flywheels'],'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'financial_authority_cents':0,'limitations':['Legacy mandate templates only; not site-derived discovery and not a property shortlist. Use /api/investment-paths/from-site for site-specific hypotheses.','Research routing only; no property, verified funds or economic ranking required to begin.','Only SMF-01 existing fourplex and SMF-02 owner-occupied 2–4 are bounded pilot templates; other strategies retain their specialist gates.','Order is an editorial research sequence, not a computed economic ranking. Duplex/triplex rental models beyond the bounded pilot require specialist validation.','No automatic work dispatch or external action.']})


def schedule(options,*,initial_cash_cents,liquidity_floor_cents,max_managed_units,horizon_years,stress_revenue_bps,stress_opex_bps):
    """Exact finite search: zero or one lifecycle option per asset; common annual cash ledger."""
    integer(initial_cash_cents,0,MAX_CENTS,'cash');integer(liquidity_floor_cents,0,MAX_CENTS,'liquidity');integer(max_managed_units,0,100000,'capacity');integer(horizon_years,2,30,'horizon');integer(stress_revenue_bps,0,10000,'stress revenue');integer(stress_opex_bps,0,10000,'stress opex')
    if not 1<=len(options)<=6:raise ValueError('Supply 1–6 distinct dated property options')
    if len({o['parcel_key'] for o in options})!=len(options):raise ValueError('One dated option per distinct parcel')
    groups=[]
    for o in sorted(options,key=lambda x:x['parcel_key']):
        y=integer(o['year'],1,horizon_years-1,'acquisition year');a={**o['assumptions'],'horizon_years':horizon_years-y+1,'initial_liquid_cash_cents':o['best']['initial_cash_required_cents'],'liquidity_floor_cents':0,'stress_revenue_bps':stress_revenue_bps,'stress_opex_bps':stress_opex_bps}
        alts=recycling.simulate(o['inputs'],o['best'],a)
        # Single-asset cash starts at zero: portfolio liquidity must be tested against shared cash, not isolated cash.
        groups.append([None]+[{**o,'alternative':r} for r in alts if not any('LIQUIDITY' not in x for x in r['failure_reasons'])])
    best=None;rank=None;failures=Counter();evaluated=0;feasible=0;frontier=[]
    for combo in product(*groups):
        evaluated+=1;selected=[o for o in combo if o];cash=initial_cash_cents;rows=[];reason=None
        if cash<liquidity_floor_cents:reason='INITIAL_LIQUIDITY'
        for y in range(1,horizon_years+1):
            if reason:break
            new=[o for o in selected if o['year']==y];active=[o for o in selected if o['year']<=y];spend=exact(sum(o['best']['initial_cash_required_cents'] for o in new));cash=exact(cash-spend)
            start_units=sum(o['inputs']['assumed_units'] for o in active if o['year']==y or o['alternative']['years'][y-o['year']-1]['owned'])
            if start_units>max_managed_units:reason='CAPACITY';break
            if cash<liquidity_floor_cents:reason='PURCHASE_LIQUIDITY';break
            flows=[o['alternative']['years'][y-o['year']] for o in active];oper=exact(sum(r['operating_cash_cents'] for r in flows));cash=exact(cash+oper)
            if cash<liquidity_floor_cents:reason='PRE_ACTION_LIQUIDITY';break
            # Same-year costs funded before any same-year proceeds, avoiding assumed intraday financing.
            tx_out=exact(sum(min(0,r['transaction_cash_cents']) for r in flows));tx_in=exact(sum(max(0,r['transaction_cash_cents']) for r in flows));cash=exact(cash+tx_out)
            if cash<liquidity_floor_cents:reason='ACTION_LIQUIDITY';break
            cash=exact(cash+tx_in);equity=exact(sum(r['assumed_market_value_cents']-r['ending_debt_cents'] for r in flows));reserves=exact(sum(r['segregated_reserves_cents'] for r in flows));units=sum(o['inputs']['assumed_units'] for o,r in zip(active,flows) if r['owned'])
            rows.append({'year':y,'acquisition_cash_cents':spend,'operating_cash_cents':oper,'transaction_out_cents':tx_out,'transaction_in_cents':tx_in,'ending_cash_cents':cash,'unrealized_equity_cents':equity,'segregated_reserves_cents':reserves,'owned_units':units})
        if reason:failures[reason]+=1;continue
        feasible+=1;last=rows[-1];metric=(last['operating_cash_cents'],cash,exact(cash+last['unrealized_equity_cents']))
        result={'selected':[{'parcel_key':o['parcel_key'],'finance_id':o['finance_id'],'year':o['year'],'action':o['alternative']['strategy']} for o in selected],'years':rows,'terminal_metrics':list(metric)}
        if rank is None or metric>rank:rank=metric;best=result
        if not any(all(a>=b for a,b in zip(x['terminal_metrics'],metric)) for x in frontier):
            frontier=[x for x in frontier if not all(a>=b for a,b in zip(metric,x['terminal_metrics']))];frontier.append({'selected':result['selected'],'terminal_metrics':list(metric)})
    return {'evaluated':evaluated,'feasible':feasible,'failure_counts':dict(failures),'best':best,'pareto_frontier':frontier,'metric_order':['terminal_operating_cash_cents','terminal_liquid_cash_cents','terminal_cash_plus_unrealized_equity_cents']}


def compound(db,dated_options,assumptions):
    opts=[]
    for item in dated_options:
        fid=item['finance_id'];row=db.execute('SELECT receipt,case_id FROM strategy_financial_receipts WHERE id=?',(fid,)).fetchone()
        if not row:raise LookupError('Financing receipt not found')
        r=json.loads(row['receipt']);case=cases.read_case(db,row['case_id']);cr=case['receipt']
        if r.get('version')!=financing.VERSION or r.get('strategy_id')!='SMF-01' or not r.get('result',{}).get('best'):raise ValueError('Passing rental financing receipt required')
        if r['id']!=fid or sha({k:v for k,v in r.items() if k!='id'})!=fid:raise ValueError('Financing receipt integrity mismatch')
        if not case['catalog_current'] or not case['unit_evidence_current'] or r['case_id']!=cr['id'] or r['catalog_sha256']!=cr['catalog_sha256'] or r['unit_evidence_sha256']!=cr['unit_evidence_sha256']:raise ValueError('Stale financing context')
        opts.append({'finance_id':fid,'parcel_key':cr['parcel_key'],'year':item['year'],'inputs':r['inputs'],'best':r['result']['best'],'assumptions':item['recycling_assumptions']})
    opts.sort(key=lambda o:o['parcel_key']);result=schedule(opts,**assumptions)
    return persist(db,{'version':VERSION,'kind':'CONDITIONAL_CAPITAL_SCHEDULE','options':opts,'assumptions':assumptions,'result':result,'financial_authority_cents':0,'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'limitations':['Hypothetical annual checkpoints, one action per asset, fixed acquisition dates and supplied financial inputs; no monthly solvency, actual taxes, 1031 or lender approval.','Common deterministic stress, not probabilities. No acquisition before proceeds received in a previous year. No reserve release or double counting of standalone liquidity.','No global optimum beyond the supplied bounded options.']})
