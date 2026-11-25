"""Conditional one-asset capital recycling. Integer USD cents, annual checkpoints.
No authority, appraisal, tax calculation or actual capital assumption.
"""
import json
from . import financing as f, strategy_cases as cases
from .portfolio import integer, exact
from .profit_review import MAX_CENTS
from .acquisition_runs import sha, encode, now
VERSION='br-capital-recycling/1'
FIELDS={'horizon_years':(2,30),'action_year':(1,29),'initial_liquid_cash_cents':(0,MAX_CENTS),'liquidity_floor_cents':(0,MAX_CENTS),'initial_market_value_cents':(1,MAX_CENTS),'annual_value_growth_bps':(-5000,5000),'annual_revenue_growth_bps':(-5000,5000),'annual_opex_growth_bps':(-5000,5000),'stress_revenue_bps':(0,10000),'stress_opex_bps':(0,10000),'sale_cost_bps':(0,10000),'sale_fixed_cost_cents':(0,MAX_CENTS),'sale_tax_provision_cents':(0,MAX_CENTS),'refi_ltv_bps':(0,10000),'refi_cap_cents':(0,MAX_CENTS),'refi_rate_bps':(0,3000),'refi_term_months':(12,480),'refi_cost_bps':(0,10000),'refi_fixed_cost_cents':(0,MAX_CENTS),'refi_min_dscr_bps':(0,100000),'renovation_cost_cents':(0,MAX_CENTS),'renovation_annual_revenue_delta_cents':(-MAX_CENTS,MAX_CENTS),'renovation_annual_opex_delta_cents':(-MAX_CENTS,MAX_CENTS),'renovation_value_delta_cents':(-MAX_CENTS,MAX_CENTS)}

def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS recycling_receipts(id TEXT PRIMARY KEY, receipt TEXT NOT NULL, created TEXT NOT NULL)')
    for op in ('UPDATE','DELETE'):
        db.execute(f"CREATE TRIGGER IF NOT EXISTS recycling_no_{op.lower()} BEFORE {op} ON recycling_receipts BEGIN SELECT RAISE(ABORT,'Immutable recycling receipt'); END")

def loan(principal,rate,term):
    payment=f.loan_year(principal,rate,term)['monthly_payment_cents']
    return [principal,rate,term,payment]

def advance(state):
    balance,rate,months,payment=state; paid=interest_total=0
    for _ in range(12):
        if not balance:break
        interest=(balance*rate+60000)//120000
        due=balance+interest if months<=1 else min(payment,balance+interest)
        balance=exact(balance+interest-due);paid+=due;interest_total+=interest;months-=1
    state[:]=[balance,rate,max(0,months),payment]
    return exact(paid),exact(interest_total)

def grow(v,bps):return exact(v*(10000+bps)//10000)

def simulate(inputs,best,a):
    if set(a)!=set(FIELDS):raise ValueError('Supply all recycling assumptions; explicit zero is required')
    for k,(lo,hi) in FIELDS.items():integer(a[k],lo,hi,k)
    if a['action_year']>=a['horizon_years']:raise ValueError('Action year must precede horizon end')
    if a['refi_ltv_bps']==0 or a['refi_cap_cents']==0:raise ValueError('Supply a positive hypothetical refinance limit')
    horizon=a['horizon_years']; action=a['action_year'];results=[]
    for strategy in ('HOLD','RENOVATE','REFINANCE','SELL'):
        cash=exact(a['initial_liquid_cash_cents']-best['initial_cash_required_cents']);reserve=inputs['initial_reserve_cents'];value=a['initial_market_value_cents'];revenue=inputs['annual_revenue_cents'];opex=inputs['annual_opex_cents'];owned=True
        debt=loan(best['loan_cents'],inputs['annual_rate_bps'],inputs['term_months']);rows=[];reasons=[]
        if cash<a['liquidity_floor_cents']:reasons.append('INITIAL_LIQUIDITY')
        for y in range(1,horizon+1):
            start_cash=cash;start_debt=debt[0];paid=interest=noi=operating=reserve_add=capex=0; transaction=0; details=None
            if owned:
                paid,interest=advance(debt)
                noi=exact(grow(revenue,-a['stress_revenue_bps'])-f.ceildiv(opex*(10000+a['stress_opex_bps']),10000))
                reserve_add=inputs['annual_reserves_cents'];capex=inputs['annual_capex_cents'];reserve=exact(reserve+reserve_add)
                operating=exact(noi-paid-reserve_add-capex);cash=exact(cash+operating)
                value=grow(value,a['annual_value_growth_bps'])
                revenue=grow(revenue,a['annual_revenue_growth_bps']);opex=grow(opex,a['annual_opex_growth_bps'])
            if cash<a['liquidity_floor_cents']:reasons.append(f'YEAR_{y}_PRE_ACTION_LIQUIDITY')
            if y==action and owned:
                if strategy=='RENOVATE':
                    nr=exact(revenue+a['renovation_annual_revenue_delta_cents']);no=exact(opex+a['renovation_annual_opex_delta_cents']);nv=exact(value+a['renovation_value_delta_cents'])
                    if min(nr,no,nv)<0:reasons.append('INVALID_RENOVATION_ASSUMPTIONS');details={'executed_in_scenario':False}
                    else:
                        transaction=-a['renovation_cost_cents'];revenue,opex,value=nr,no,nv;details={'renovation_cash_cents':-transaction,'assumed_value_delta_cents':a['renovation_value_delta_cents']}
                elif strategy=='REFINANCE':
                    principal=min(value*a['refi_ltv_bps']//10000,a['refi_cap_cents']);fee=exact(f.ceildiv(principal*a['refi_cost_bps'],10000)+a['refi_fixed_cost_cents']);new_debt=loan(principal,a['refi_rate_bps'],a['refi_term_months']);next_paid,_=advance(new_debt.copy());next_noi=exact(grow(revenue,-a['stress_revenue_bps'])-f.ceildiv(opex*(10000+a['stress_opex_bps']),10000));net=exact(principal-debt[0]-fee)
                    details={'new_loan_cents':principal,'old_payoff_cents':debt[0],'fees_cents':fee,'net_cash_cents':net,'next_stress_noi_cents':next_noi,'next_debt_service_cents':next_paid}
                    if not principal or net<=0 or (next_paid and next_noi*10000<next_paid*a['refi_min_dscr_bps']):reasons.append('REFINANCE_CASH_OUT_OR_DSCR');details['executed_in_scenario']=False
                    else:transaction=net;debt=new_debt;details['executed_in_scenario']=True
                elif strategy=='SELL':
                    fee=exact(f.ceildiv(value*a['sale_cost_bps'],10000)+a['sale_fixed_cost_cents']);pretax=exact(value-fee-debt[0]);transaction=exact(pretax-a['sale_tax_provision_cents']);details={'gross_sale_cents':value,'selling_cost_cents':fee,'debt_payoff_cents':debt[0],'pre_tax_proceeds_cents':pretax,'assumed_tax_provision_cents':a['sale_tax_provision_cents']};value=0;debt=[0,0,0,0];owned=False
                cash=exact(cash+transaction)
            if cash<a['liquidity_floor_cents']:reasons.append(f'YEAR_{y}_ENDING_LIQUIDITY')
            rows.append(dict(year=y,starting_liquid_cash_cents=start_cash,opening_debt_cents=start_debt,operating_noi_cents=noi,debt_service_cents=paid,interest_cents=interest,principal_paid_cents=paid-interest,reserve_contribution_cents=reserve_add,cash_capex_cents=capex,operating_cash_cents=operating,transaction_cash_cents=transaction,action_details=details,ending_liquid_cash_cents=cash,ending_debt_cents=debt[0],assumed_market_value_cents=value,segregated_reserves_cents=reserve,owned=owned))
        results.append(dict(strategy=strategy,status='CONDITIONAL_PASS' if not reasons else 'CONDITIONAL_FAIL',failure_reasons=reasons,years=rows,terminal_liquid_cash_cents=cash,terminal_unrealized_equity_cents=exact(value-debt[0]),terminal_segregated_reserves_cents=reserve,terminal_operating_cash_cents=rows[-1]['operating_cash_cents'],terminal_cash_plus_equity_excluding_reserves_cents=exact(cash+value-debt[0]),terminal_redeployment_ceiling_cents=max(0,cash-a['liquidity_floor_cents']) if not reasons else None))
    return results

def run(db,finance_id,assumptions):
    row=db.execute('SELECT receipt,case_id FROM strategy_financial_receipts WHERE id=?',(finance_id,)).fetchone()
    if row is None:raise LookupError('Financing receipt not found')
    r=json.loads(row['receipt']);case=cases.read_case(db,row['case_id']);cr=case['receipt']
    if r.get('version')!=f.VERSION or r.get('strategy_id')!='SMF-01' or not r.get('result',{}).get('best'):raise ValueError('Passing rental financing grid required')
    if r['id']!=finance_id or sha({k:v for k,v in r.items() if k!='id'})!=finance_id:raise ValueError('Financing receipt integrity mismatch')
    if not case['catalog_current'] or not case['unit_evidence_current'] or r['case_id']!=cr['id'] or r['catalog_sha256']!=cr['catalog_sha256'] or r['unit_evidence_sha256']!=cr['unit_evidence_sha256']:raise ValueError('Stale or mismatched financing context')
    body={'version':VERSION,'finance_id':finance_id,'case_id':cr['id'],'assumptions':assumptions,'alternatives':simulate(r['inputs'],r['result']['best'],assumptions),'authority':'HYPOTHETICAL_RESEARCH_ONLY','financial_authority_cents':0,'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'limitations':['Single asset; starting cash includes purchase and initial reserve funding. Annual checkpoints; no monthly solvency. One action at end of specified year; subsequent operations start following year.','Value growth, rent, expenses and renovation benefits are supplied assumptions, not forecasts or appraisals. Common stress applies to operations, not asset prices. No marketability, lender approval or actual capital verification.','Refinance proceeds and sale proceeds are transaction cash, not NOI or profit. Tax provision is supplied, not a tax calculation; no 1031, depreciation, operating income tax or reserve release modeled.','Segregated reserves accumulate separately, including after sale; no automatic reinvestment. Cash plus equity is not liquidation value or realized profit. Redeployment ceiling is cash above floor only, not transaction authority.']}
    rid=sha(body);old=db.execute('SELECT receipt FROM recycling_receipts WHERE id=?',(rid,)).fetchone()
    if old:return {'receipt':json.loads(old[0]),'replay':True}
    receipt={**body,'id':rid};db.execute('INSERT INTO recycling_receipts VALUES(?,?,?)',(rid,encode(receipt),now()));return {'receipt':receipt,'replay':False}
