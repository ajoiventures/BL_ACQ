"""Bounded, hypothetical financing price-grid search. No lending or offer authority."""
from decimal import Decimal, localcontext, ROUND_CEILING
import json
from collections import Counter
from . import strategy_cases as cases
from .acquisition_runs import sha, encode, now
from .profit_review import MAX_CENTS

VERSION='br-financing-grid/1'
FIELDS=('price_min_cents','price_max_cents','price_step_cents','cash_budget_cents','ltv_bps','loan_cap_cents','annual_rate_bps','term_months','closing_bps','fixed_closing_cents','initial_repair_cents','initial_reserve_cents','annual_revenue_cents','annual_opex_cents','annual_reserves_cents','annual_capex_cents','revenue_stress_bps','min_dscr_bps','min_yield_bps','max_owner_outlay_cents','assumed_units')
LIMITS={'ltv_bps':10000,'annual_rate_bps':3000,'term_months':480,'closing_bps':10000,'revenue_stress_bps':10000,'min_dscr_bps':100000,'min_yield_bps':100000,'assumed_units':4}

def ceildiv(a,b):return -(-a//b)

def payment_factor(rate_bps,months):
    with localcontext() as ctx:
        ctx.prec=60
        r=Decimal(rate_bps)/120000
        return Decimal(1)/months if not r else r/(1-(1+r)**(-months))

def loan_year(principal,rate_bps,months,factor=None):
    """Estimated cents schedule: upward payment rounding, monthly interest half-up."""
    if not principal:return dict(monthly_payment_cents=0,year_one_debt_service_cents=0,year_one_interest_cents=0,year_one_principal_cents=0,year_end_balance_cents=0)
    with localcontext() as ctx:
        ctx.prec=60
        factor=payment_factor(rate_bps,months) if factor is None else factor
        payment=ceildiv(principal,months) if rate_bps==0 else int((principal*factor).to_integral_value(rounding=ROUND_CEILING))
    balance=principal; interest_total=paid=0
    for _ in range(12):
        interest=(balance*rate_bps+60000)//120000
        due=min(payment,balance+interest);balance+=interest-due;interest_total+=interest;paid+=due
    return dict(monthly_payment_cents=payment,year_one_debt_service_cents=paid,year_one_interest_cents=interest_total,year_one_principal_cents=principal-balance,year_end_balance_cents=balance)

def evaluate(inputs,sid,reviewed_units=None):
    if sid not in ('SMF-01','SMF-02'):raise ValueError('No financing model for this strategy')
    if set(inputs)!=set(FIELDS):raise ValueError('Provide all financing assumptions; use null for unknown or inapplicable')
    for k,v in inputs.items():
        if v is not None and (type(v) is not int or not 0<=v<=LIMITS.get(k,MAX_CENTS)):raise ValueError('Invalid assumption '+k)
    owner=sid=='SMF-02'; n=inputs['assumed_units']
    if n is not None and n not in cases.PILOTS[sid]:raise ValueError('Unit assumption outside this strategy pilot range')
    if n is not None and reviewed_units is not None and n!=reviewed_units:raise ValueError('Unit assumption conflicts with reviewed research count')
    unused={'min_yield_bps','min_dscr_bps'} if owner else {'max_owner_outlay_cents'}
    if any(inputs[k] is not None for k in unused):raise ValueError('Inapplicable constraints must be null; owner housing cost is not investment yield')
    missing=[k for k in FIELDS if k not in unused and inputs[k] is None]
    if missing:return {'status':'MISSING_ASSUMPTIONS','missing':missing,'evaluated_prices':0,'best':None,'failure_counts':{}}
    a=inputs; low,high,step=(a[k] for k in FIELDS[:3])
    if low<1 or high<low or step<1 or a['term_months']<12:raise ValueError('Invalid price grid or term (12–480 months)')
    count=(high-low)//step+1
    if count>10001:raise ValueError('At most 10001 price candidates; increase grid step')
    factor=payment_factor(a['annual_rate_bps'],a['term_months']); fails=Counter();best=None;feasible=0
    revenue=a['annual_revenue_cents']; stressed=revenue*(10000-a['revenue_stress_bps'])//10000
    opex=a['annual_opex_cents']; recurring=a['annual_reserves_cents']+a['annual_capex_cents']
    for p in range(low,high+1,step):
        principal=min(p*a['ltv_bps']//10000,a['loan_cap_cents']);loan=loan_year(principal,a['annual_rate_bps'],a['term_months'],factor)
        closing=ceildiv(p*a['closing_bps'],10000)+a['fixed_closing_cents'];cash=p-principal+closing+a['initial_repair_cents']+a['initial_reserve_cents']; debt=loan['year_one_debt_service_cents'];noi=revenue-opex; downside_noi=stressed-opex
        base=noi-debt-recurring;down=downside_noi-debt-recurring
        if any(abs(v)>MAX_CENTS for v in (closing,cash,base,down,noi,downside_noi,*loan.values())):raise ValueError('Result exceeds exact JSON integer range')
        reasons=[]
        if cash>a['cash_budget_cents']:reasons.append('CASH_BUDGET')
        if owner:
            if -base>a['max_owner_outlay_cents'] or -down>a['max_owner_outlay_cents']:reasons.append('OWNER_OUTLAY')
        else:
            if debt and downside_noi*10000<debt*a['min_dscr_bps']:reasons.append('STRESS_DSCR')
            if cash<=0 or down*10000<cash*a['min_yield_bps']:reasons.append('STRESS_CASH_YIELD')
        if reasons:fails.update(reasons);continue
        feasible+=1
        best={'price_cents':p,'loan_cents':principal,'closing_cents':closing,'initial_cash_required_cents':cash,**loan,'baseline_noi_cents':noi,'stress_noi_cents':downside_noi,'baseline_annual_cash_cents':base,'stress_annual_cash_cents':down,'baseline_owner_outlay_cents':-base if owner else None,'stress_owner_outlay_cents':-down if owner else None,'stress_dscr_bps':None if not debt or owner else downside_noi*10000//debt,'stress_cash_yield_bps':None if owner or not cash else down*10000//cash}
        if any(v is not None and abs(v)>MAX_CENTS for v in best.values()):raise ValueError('Result exceeds exact JSON integer range')
    return {'status':'CONDITIONAL_GRID_MATCH' if best else 'NO_GRID_MATCH','missing':[],'evaluated_prices':count,'feasible_prices':feasible,'best':best,'failure_counts':dict(fails),'last_grid_price_cents':low+(count-1)*step,'price_cap_is_grid_only':True}

def run(db,cid,inputs):
    case=cases.read_case(db,cid);r=case['receipt']
    if not case['catalog_current'] or not case['unit_evidence_current']:raise ValueError('Strategy catalog or unit evidence changed; prepare a new case')
    sid=r['strategy']['source']['ID'];result=evaluate(inputs,sid,r['reviewed_research_units'])
    body={'version':VERSION,'case_id':cid,'strategy_id':sid,'catalog_sha256':r['catalog_sha256'],'unit_evidence_sha256':r['unit_evidence_sha256'],'inputs':inputs,'result':result,'scope':'HYPOTHETICAL_FIXED_RATE_FIRST_YEAR_PRICE_GRID','decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'financial_authority_cents':0,'limitations':['No verified lender offer, market value, capital availability, lawful units or actual operating evidence.','Fixed-rate fully amortizing estimate; no balloon, points, mortgage insurance or taxes unless included in explicit cost inputs; no escrow or closing adjustments.','Checks baseline and stressed owner outlay or stressed rental yield and DSCR; zero debt means DSCR is not applicable. Initial and recurring costs must not be double counted.','Highest passing grid point only, not continuous optimum or offer; price bounds and all inputs are hypothetical.']}
    fid=sha(body);old=db.execute('SELECT receipt FROM strategy_financial_receipts WHERE id=?',(fid,)).fetchone()
    if old:return {'receipt':json.loads(old[0]),'replay':True}
    receipt={**body,'id':fid};db.execute('INSERT INTO strategy_financial_receipts VALUES(?,?,?,?)',(fid,cid,encode(receipt),now()));return {'receipt':receipt,'replay':False}
