import sqlite3
import pytest
from backend.core import investment_paths as ip, site_paths, strategy_prediction as sp


def setup():
    db=sqlite3.connect(':memory:'); ip.initialize(db); return db


def prior(db,**kw):
    args=dict(site_id='SYNTHETIC-STUDY',boundary_revision='b1',model_version='illustration',as_of='2025-01-02T00:00:00+00:00',inputs=[{'source_ref':'synthetic://pre-site','available_at':'2025-01-01T00:00:00+00:00'}],probabilities={'SMF-07':.8,'SMF-08':.2,'SMF-02':.9})
    return sp.freeze(db,**{**args,**kw})['receipt']


def findings():
    return [dict(finding_id=str(i),topic=topic,state=state,source_ref='synthetic://finding/'+str(i),source_date='2025-01-03',summary='Synthetic fixture') for i,(topic,state) in enumerate([('deep_lot_opportunity','CONTRARY'),('underused_upper_floor','OBSERVED')])]


def post(db,**kw):
    return site_paths.discover(db,**{**dict(site_id='SYNTHETIC-STUDY',boundary_revision='b1',findings=findings()),**kw})['receipt']


def test_frozen_forecast_comparison():
    db=setup(); p=prior(db); s=post(db); out=sp.compare(db,p['id'],s['id'])['receipt']; assert len(p['rows'])==83
    assert out['paired_count']==2 and out['unpaired_count']==81 and out['diagnostic_brier']==pytest.approx(.64)
    assert out['mean_residual']==pytest.approx(0) and out['residual_variance']==pytest.approx(.64)
    assert not out['training_eligible'] and out['financial_authority_cents']==0
    assert sp.compare(db,p['id'],s['id'])['replay']
    assert next(r for r in out['rows'] if r['strategy_id']=='SMF-02')['diagnostic_label'] is None


def test_reject_leakage_scope_and_invalid_probabilities():
    db=setup(); s=post(db); p=prior(db)
    with pytest.raises(ValueError): sp.compare(db,p['id'],s['id'])
    with pytest.raises(ValueError): prior(db,probabilities={'SMF-07':float('nan')})
    with pytest.raises(ValueError): prior(db,inputs=[{'source_ref':'synthetic://future','available_at':'2025-02-01T00:00:00+00:00'}])
    with pytest.raises(ValueError): sp.compare(db,p['id'],post(db,boundary_revision='other')['id'])


def test_synthetic_calibration_holdout_and_leakage():
    def row(i,p,y,year):
        return dict(site_id=f'SYNTHETIC-{i}',strategy_id='SMF-07',p=p,y=y,forecast_at=f'{year}-01-01T00:00:00+00:00',label_at=f'{year}-02-01T00:00:00+00:00')
    train=[row(i,.8,int(i%4==0),2024) for i in range(8)]
    holdout=[row(i,.8,int(i%4==0),2025) for i in range(8,12)]
    out=sp.synthetic_calibration_experiment(train,holdout)
    assert out['candidate_brier']<out['baseline_brier'] and not out['production_promoted']
    with pytest.raises(ValueError):sp.synthetic_calibration_experiment(train,[{**holdout[0],'site_id':train[0]['site_id']}])
    with pytest.raises(ValueError):sp.synthetic_calibration_experiment(train,[{**holdout[0],'forecast_at':'2024-01-01T00:00:00+00:00'}])
