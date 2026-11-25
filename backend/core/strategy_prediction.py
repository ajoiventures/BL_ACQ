"""Pre-site forecast and post-site diagnostic comparison; no approval or live model training."""
import json
import math
from datetime import datetime
from . import investment_paths as ip
from .acquisition_runs import sha
from .strategy_library import load_catalog

VERSION = 'br-strategy-prediction/1'
EVENT = 'SITE_SYNTHESIS_SUPPORTS_FURTHER_FEASIBILITY'


def _time(s):
    t = datetime.fromisoformat(s)
    if t.tzinfo is None:
        raise ValueError('Timestamp must include timezone')
    return t


def _load(db, rid, kind):
    row = db.execute('SELECT receipt,created FROM investment_path_receipts WHERE id=?', (rid,)).fetchone()
    if not row:
        raise LookupError('Receipt not found')
    r = json.loads(row[0])
    if r['kind'] != kind or r['id'] != rid or sha({k:v for k,v in r.items() if k!='id'}) != rid:
        raise ValueError('Wrong or altered receipt')
    return r, _time(row[1])


def freeze(db, *, site_id, boundary_revision, model_version, as_of, inputs, probabilities):
    """Accept explicit model estimates; null means unscored. Not a calibrated model."""
    if not all(isinstance(x,str) and x.strip() for x in (site_id,boundary_revision,model_version)):
        raise ValueError('Study, boundary and model version required')
    cutoff = _time(as_of)
    if not inputs or any(not i['source_ref'].strip() or _time(i['available_at']) > cutoff for i in inputs):
        raise ValueError('Pre-site source available at cutoff required')
    catalog = load_catalog()
    ids = [r['source']['ID'] for r in catalog['records']]
    if set(probabilities)-set(ids):
        raise ValueError('Unknown strategy')
    for p in probabilities.values():
        if p is not None and (type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1):
            raise ValueError('Probability must be null or finite [0,1]')
    return ip.persist(db, {'version':VERSION,'kind':'PRE_SITE_STRATEGY_FORECAST','event':EVENT,'site_id':site_id,'boundary_revision':boundary_revision,'model_version':model_version,'as_of':as_of,'inputs':inputs,'catalog_sha256':sha(catalog),'probability_status':'SUPPLIED_UNCALIBRATED_ESTIMATES','rows':[{'strategy_id':s,'p':probabilities.get(s)} for s in ids],'financial_authority_cents':0})


def compare(db, forecast_id, site_receipt_id):
    """Compare against existing site synthesis. Research dispositions are not reviewed truth."""
    prior, t0 = _load(db,forecast_id,'PRE_SITE_STRATEGY_FORECAST')
    post, t1 = _load(db,site_receipt_id,'SITE_DERIVED_PATH_DISCOVERY')
    if t1 <= t0 or _time(prior['as_of']) > t0:
        raise ValueError('Forecast must be frozen before site receipt, with no future inputs')
    for key in ('site_id','boundary_revision','catalog_sha256'):
        if prior[key] != post[key]:
            raise ValueError('Mismatched study, boundary or catalog revision')
    states = {r['strategy_id']:r['status'] for r in post['catalog_dispositions']}
    rows = []
    for r in prior['rows']:
        status=states[r['strategy_id']]
        # Only explicit positive or contrary research findings count in diagnostic comparison.
        y={'SITE_HYPOTHESIS':1,'CONTRARY_FINDING':0}.get(status)
        p=r['p']; residual=None if y is None or p is None else y-p
        rows.append({**r,'site_status':status,'diagnostic_label':y,'residual':residual,'squared_error':None if residual is None else residual**2})
    e=[r['residual'] for r in rows if r['residual'] is not None]
    bias=sum(e)/len(e) if e else None
    return ip.persist(db,{'version':VERSION,'kind':'STRATEGY_FORECAST_DIAGNOSTIC','forecast_id':forecast_id,'site_receipt_id':site_receipt_id,'rows':rows,'paired_count':len(e),'unpaired_count':len(rows)-len(e),'mean_residual':bias,'residual_variance':sum((x-bias)**2 for x in e)/len(e) if e else None,'diagnostic_brier':sum(x*x for x in e)/len(e) if e else None,'training_eligible':False,'label_status':'UNREVIEWED_SITE_RESEARCH_NOT_GROUND_TRUTH','financial_authority_cents':0})


def synthetic_calibration_experiment(train, holdout, *, alpha=2):
    """Fixture-only experiment: strategy-specific probability-bin shrinkage.

    Not a production trainer. Actual labels require separately authenticated acceptance.
    """
    if type(alpha) is not int or alpha<1 or not train or not holdout:
        raise ValueError('Nonempty partitions and positive smoothing required')
    catalog_ids={r['source']['ID'] for r in load_catalog()['records']}
    for rows in (train,holdout):
        keys=[]
        for r in rows:
            if not r['site_id'].startswith('SYNTHETIC-') or r['strategy_id'] not in catalog_ids or type(r['y']) is not int or r['y'] not in (0,1) or type(r['p']) not in (int,float) or not 0<=r['p']<=1:
                raise ValueError('Synthetic binary fixtures only')
            if _time(r['label_at']) <= _time(r['forecast_at']):
                raise ValueError('Label must follow prediction')
            keys.append((r['site_id'],r['strategy_id']))
        if len(keys)!=len(set(keys)): raise ValueError('Duplicate case-strategy label')
    if {r['site_id'] for r in train}&{r['site_id'] for r in holdout} or max(_time(r['label_at']) for r in train)>=min(_time(r['forecast_at']) for r in holdout):
        raise ValueError('Group and temporal separation required')
    def key(r): return (r['strategy_id'],min(4,int(r['p']*5)))
    groups={}
    for r in train: groups.setdefault(key(r),[]).append(r['y'])
    results=[]
    for r in holdout:
        labels=groups.get(key(r),[])
        p=(sum(labels)+alpha*r['p'])/(len(labels)+alpha)
        results.append({**r,'training_bin_n':len(labels),'candidate_p':p})
    return {'kind':'SYNTHETIC_CALIBRATION_EXPERIMENT','training_n':len(train),'holdout_n':len(holdout),'baseline_brier':sum((r['p']-r['y'])**2 for r in results)/len(results),'candidate_brier':sum((r['candidate_p']-r['y'])**2 for r in results)/len(results),'rows':results,'production_promoted':False,'real_training_eligible':False}
