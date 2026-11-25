"""Bounded LaGro-inspired synthesis of operator-supplied site findings.
Research hypotheses only; a source locator is not independently accepted evidence.
"""
from datetime import date
from site_academy.runner import load_skills
from . import investment_paths as ip
from .strategy_library import load_catalog
from .acquisition_runs import sha, get
from .acquisition_cohorts import evidence

VERSION='br-site-paths/5'
METHOD_IDS=('SA-4-3-1','SA-8-3-2','SA-8-3-3','SA-8-3-4','SA-8-4-1','SA-8-4-2')
# Explicit discovery rules, not legal rules or claims about particular sites.
RULES={
 'SMF-01':('existing_fourplex','Investigate repositioning an existing fourplex','HOLD_OR_IMPROVE'),
 'SMF-02':('owner_occupancy_layout','Investigate owner occupancy and remaining rental units','OWNER_OCCUPANCY'),
 'SMF-13':('bedroom_layout_opportunity','Test lawful bedroom configuration and rental demand','LAYOUT_FEASIBILITY'),
 'SMF-14':('underused_service_space','Investigate lawful reuse of garage or service area','SERVICE_SPACE_FEASIBILITY'),
 'SMF-05':('potential_accessory_space','Test accessory dwelling design and lawful use','ADU_FEASIBILITY'),
 'SMF-07':('deep_lot_opportunity','Test courtyard or tandem infill envelopes','INFILL_FEASIBILITY'),
 'SMF-08':('underused_upper_floor','Test upper-floor housing, access and life safety','ADAPTIVE_REUSE'),
 'SMF-09':('adjacent_lot_opportunity','Test parcel assembly and townhome layout','ASSEMBLAGE_FEASIBILITY'),
 'SMF-12':('shared_meter_opportunity','Investigate metering and operating-cost changes','OPERATING_IMPROVEMENT'),
 'SMF-20':('institutional_access','Test furnished rental demand and lawful lease terms','RENTAL_MARKET_RESEARCH'),
 'SMF-56':('frontage_opportunity','Test frontage and form alternatives against current code','FRONTAGE_FEASIBILITY'),
}
# Each factor is a research question, never a clearance or legal finding.
FACTORS=('legal_use','title','physical','access','utility','environmental','market','cost','capital','operations')
TOPICS={v[0] for v in RULES.values()}|{f'{factor}_{suffix}' for factor in FACTORS for suffix in ('constraint','support')}

def applies(f,sid):
    return not f.get('strategy_ids') or sid in f['strategy_ids']

def feasibility(findings,sid):
    result=[]
    for factor in FACTORS:
        selected=[f for f in findings if applies(f,sid) and f['topic'] in (factor+'_constraint',factor+'_support')]
        constraints=[f for f in selected if f['topic']==factor+'_constraint']
        # A positive support assertion is program-specific. Unscoped favorable statements cannot establish program fit.
        support=[f for f in selected if f['topic']==factor+'_support' and f.get('strategy_ids')]
        cs={f['state'] for f in constraints};ss={f['state'] for f in support}
        if {'OBSERVED','CONTRARY'}<=cs or {'OBSERVED','CONTRARY'}<=ss or ('OBSERVED' in cs and 'OBSERVED' in ss):state='CONFLICT_RESEARCH'
        elif 'OBSERVED' in cs or 'CONTRARY' in ss:state='CONSTRAINT_REPORTED'
        elif 'OBSERVED' in ss:state='SUPPORT_REPORTED_UNVERIFIED'
        else:state='UNKNOWN'
        result.append({'factor':factor,'state':state,'finding_ids':sorted(f['finding_id'] for f in selected),'scope':'PROGRAM_RESEARCH_NOT_CLEARANCE'})
    states={r['state'] for r in result}
    disposition=('HOLD_CONFLICT' if 'CONFLICT_RESEARCH' in states else 'HOLD_CONSTRAINT' if 'CONSTRAINT_REPORTED' in states else 'HOLD_MISSING_SUPPORT' if 'UNKNOWN' in states else 'REVIEW_REQUIRED')
    return {'disposition':disposition,'factors':result,'design_authorized':False,'transaction_authorized':False}

def transition_graph(paths):
    nodes=[{'id':'SITE','kind':'SITE_FINDINGS'},{'id':'WAIT','kind':'NO_ACQUISITION'},{'id':'COMPARE','kind':'HUMAN_COMPARISON'}]
    edges=[{'from':'SITE','to':'WAIT','condition':'ALWAYS_AVAILABLE'}]
    for path in paths:
        prefix=path['path_id'];stages=('HYPOTHESIS','PRELIMINARY_FEASIBILITY','CONCEPT_ALTERNATIVES','DETAILED_FEASIBILITY','REVIEW')
        ids=[prefix+':'+stage for stage in stages]
        nodes.extend({'id':i,'kind':stage,'strategy_id':path['strategy_id']} for i,stage in zip(ids,stages))
        edges.append({'from':'SITE','to':ids[0],'condition':'SUPPORTING_SITE_FINDING'})
        edges.extend({'from':a,'to':b,'condition':c} for a,b,c in zip(ids,ids[1:],('COLLECT_PROGRAM_SPECIFIC_EVIDENCE','HUMAN_ACCEPTED_PRELIMINARY_FEASIBILITY','REVIEWED_DESIGN_QUANTITIES','DETAILED_REVIEW_REQUIRED')))
        edges.append({'from':ids[-1],'to':'COMPARE','condition':'INDEPENDENT_REVIEW_REQUIRED'})
        edges.append({'from':ids[1],'to':ids[0],'condition':'REVISE_PROGRAM_OR_RESOLVE_EVIDENCE'})
        edges.append({'from':ids[1],'to':'WAIT','condition':'HOLD_OR_REJECT'})
        edges.append({'from':ids[3],'to':ids[0],'condition':'REVISE_IF_INFEASIBLE'})
    return {'nodes':nodes,'edges':edges,'status':'RESEARCH_GRAPH_NOT_EXECUTION','automatically_traversable':False}

def method_references():
    cards = {card["id"]: card for card in load_skills("site")}
    return [{
        "card_id": card_id, "card_sha256": sha(cards[card_id]),
        "source": "James A. LaGro Jr., Site Analysis", "edition": 2, "publication_year": 2008,
        "source_locator": "chatgpt-library:libfile_418e9433f188819199db62a0283df1ff",
        "review_depth": "EDITION_VERIFIED_CARD_LOCATOR_RETAINED",
        "applicability": "SITE_STUDY_METHOD_AND_ASSESSMENT",
        "source_quality_flags": ["SECTION_LOCATOR_FROM_EXISTING_CARD", "NO_SITE_VERIFICATION"],
        "contradictions_reviewed": False,
        "section": cards[card_id]["source_section"], "printed_pages": cards[card_id]["pages"],
        "assessment": {key: cards[card_id][key] for key in ("inputs", "output", "acceptance")},
    } for card_id in METHOD_IDS]


def discover(db, *, site_id, boundary_revision, findings, run_id=None, parcel_key=None, program_revision=None):
    if not site_id.strip() or not boundary_revision.strip():raise ValueError('Study identity and boundary revision required')
    if program_revision is not None and not program_revision.strip():
        raise ValueError("Program revision cannot be blank")
    if (run_id is None)!=(parcel_key is None):raise ValueError('Supply both processed run and parcel or neither')
    context=None
    if run_id is not None:
        run=get(db,run_id)
        if not db.execute('SELECT 1 FROM acq_results WHERE run_id=? AND parcel_key=?',(run_id,parcel_key)).fetchone():raise LookupError('Processed parcel required')
        ev=evidence(db,run['snapshot_id'],parcel_key)
        context={'run_id':run_id,'parcel_key':parcel_key,'snapshot_id':run['snapshot_id'],'record_sha256':ev['record_sha256']}
        if site_id!=parcel_key:raise ValueError('Parcel study identity must match processed parcel')
    cat=load_catalog();valid_strategies={r['source']['ID'] for r in cat['records']}
    by_topic={}; seen=set(); normalized=[]
    for f in findings:
        if f['topic'] not in TOPICS or f['state'] not in ('OBSERVED','CONTRARY','UNKNOWN'):raise ValueError('Unknown finding topic or state')
        if not all(f[k].strip() for k in ('finding_id','source_ref','summary')):raise ValueError('Finding ID, source locator and summary required')
        if f['finding_id'] in seen:raise ValueError('Duplicate finding identity')
        seen.add(f['finding_id'])
        try:date.fromisoformat(f['source_date'])
        except ValueError:raise ValueError('Invalid source date')
        scopes=f.get('strategy_ids') or []
        if len(scopes)!=len(set(scopes)) or not set(scopes)<=valid_strategies:raise ValueError('Unknown or repeated strategy scope')
        item={**f,'strategy_ids':sorted(scopes)}
        normalized.append(item);by_topic.setdefault(item['topic'],[]).append(item)
    normalized.sort(key=lambda f:f['finding_id'])
    paths=[];dispositions=[]
    # Constraints inform specialist diligence; absence of a claim is never clearance.
    for rec in cat['records']:
        sid=rec['source']['ID'];rule=RULES.get(sid);items=[f for f in by_topic.get(rule[0],[]) if applies(f,sid)] if rule else []
        states={f['state'] for f in items}
        status=('SPECIALIST_MAPPING_PENDING' if not rule else 'CONFLICT_RESEARCH' if {'OBSERVED','CONTRARY'}<=states else 'SITE_HYPOTHESIS' if 'OBSERVED' in states else 'CONTRARY_FINDING' if 'CONTRARY' in states else 'NEEDS_SITE_FINDING')
        row={'strategy_id':sid,'name':rec['source']['Strategy'],'status':status,'finding_ids':sorted(f['finding_id'] for f in items),'required_gate':rec['required_gate']}
        dispositions.append(row)
        if status!='SITE_HYPOTHESIS':continue
        constraints=[f['finding_id'] for f in normalized if applies(f,sid) and f['topic'].endswith('_constraint') and f['state']!='CONTRARY']
        paths.append({**row,'path_id':sid+'-'+rule[2],'steps':['VERIFY_SITE_FINDINGS',rule[1],'PRELIMINARY_FEASIBILITY_BEFORE_DETAILED_DESIGN','DEVELOP_AND_COMPARE_CONCEPT_ALTERNATIVES','VERIFY_LEGAL_PHYSICAL_MARKET_AND_CAPITAL_GATES','COMPARE_ECONOMICS_AND_EXIT','HUMAN_REVIEW'],'constraint_finding_ids':constraints,'preliminary_feasibility':feasibility(normalized,sid),'work_package_ids':[w['work_package_id'] for w in cat['work_packages'] if w['strategy_id']==sid],'decision_gates':dict.fromkeys(('buyable','fundable','sellable'),'UNKNOWN'),'status':'RESEARCH_ONLY'})
    return ip.persist(db,{'version':VERSION,'kind':'SITE_DERIVED_PATH_DISCOVERY','site_id':site_id,'boundary_revision':boundary_revision,'context':context,'catalog_sha256':sha(cat),'method_reference_ids':list(METHOD_IDS),'method_references':method_references(),'program_revision':program_revision,'method_application_status':'REFERENCE_ONLY_NOT_ASSESSED','findings':normalized,'catalog_dispositions':dispositions,'candidate_paths':paths,'transition_graph':transition_graph(paths),'no_acquisition_alternative':True,'financial_authority_cents':0,'limitations':['Operator-supplied findings are unverified assertions; no geometry, lawful use, capacity, demand or available capital inferred.','Eleven explicit research mappings; all other strategies remain specialist mapping work. Preliminary factors reflect unverified supplied findings and never authorize design or transactions.','No acquisition alternative always retained. Historical receipts must be regenerated when inputs change.']})
