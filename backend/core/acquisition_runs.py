"""Persistent, request-stepped research runs over immutable retained parcel snapshot.
No real title, zoning, unit or financial conclusion is inferred from use codes.
"""
import hashlib,json,os,uuid
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from .acquisition_batch import FIELDS,screen,summarize,BackendUnavailable
from tools.run_acquisition_batch import reconcile
from . import acquisition_leases as leases, acquisition_tasks as tasks, property_features as pf
from .orange_roll_context import bind_orange_context


def encode(x): return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(x): return hashlib.sha256(encode(x).encode()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS acq_snapshots(id TEXT PRIMARY KEY, manifest TEXT NOT NULL, total INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS acq_parcels(snapshot_id TEXT NOT NULL, ordinal INTEGER NOT NULL, parcel_key TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(snapshot_id,ordinal),UNIQUE(snapshot_id,parcel_key),FOREIGN KEY(snapshot_id) REFERENCES acq_snapshots(id))')
    db.execute('CREATE TABLE IF NOT EXISTS acq_runs(id TEXT PRIMARY KEY,request_id TEXT UNIQUE NOT NULL,snapshot_id TEXT NOT NULL,backend TEXT NOT NULL,batch_size INTEGER NOT NULL,state TEXT NOT NULL,cursor INTEGER NOT NULL,total INTEGER NOT NULL,version INTEGER NOT NULL,error TEXT,created TEXT NOT NULL, FOREIGN KEY(snapshot_id) REFERENCES acq_snapshots(id))')
    db.execute('CREATE TABLE IF NOT EXISTS acq_batches(run_id TEXT NOT NULL,start INTEGER NOT NULL,end INTEGER NOT NULL,receipt TEXT NOT NULL,PRIMARY KEY(run_id,start),FOREIGN KEY(run_id) REFERENCES acq_runs(id))')
    db.execute('CREATE TABLE IF NOT EXISTS acq_results(run_id TEXT NOT NULL,parcel_key TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(run_id,parcel_key),FOREIGN KEY(run_id) REFERENCES acq_runs(id))')
    db.execute('CREATE TABLE IF NOT EXISTS acq_run_contracts(run_id TEXT PRIMARY KEY,feature_version TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES acq_runs(id))')
    leases.initialize(db)
    tasks.initialize(db)
    for table in ('acq_snapshots','acq_parcels','acq_batches','acq_results','acq_run_contracts'):
        for op in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable acquisition evidence'); END")


def snapshot(db, source="retained"):
    if source == "retained":
        rows, manifest = reconcile()
    elif source == "orange_2026_final_roll":
        rows, manifest = orange_research_snapshot()
    else:
        raise ValueError("Unknown acquisition snapshot source")
    key = sha({"manifest": manifest, "records": rows})
    if not db.execute("SELECT 1 FROM acq_snapshots WHERE id=?", (key,)).fetchone():
        db.execute("INSERT INTO acq_snapshots VALUES(?,?,?)", (key, encode(manifest), len(rows)))
        db.executemany("INSERT INTO acq_parcels VALUES(?,?,?,?)",
                       ((key, i, row["parcel_key"], encode(row)) for i, row in enumerate(rows)))
    return key, len(rows), manifest


def orange_research_snapshot():
    from tools.screen_orange_final_roll import load_final_roll

    evidence = Path(__file__).resolve().parents[2] / "docs/acquisition/orange-final-roll"
    inventory_sha = "46930f23b1dd129cc95c36d89c301ecdc6f1ed1a3f3b06cd0034ec1b3c86926a"
    gate, records = load_final_roll(evidence / "official_final_roll_inventory.csv", inventory_sha, 6078)
    context, context_manifest = bind_orange_context(evidence.parent / "orange-sales-spatial", records)
    rows = [{
        "parcel_key": row["parcel_key"],
        "source_context": context[row["parcel_key"]],
        "reported_units": row["source_reported_units"],
        "reported_buildings": row["source_reported_buildings"],
        "source_observations": [{
            "feature_id": row["source_parcel_id"], "city": "", "zip": "",
            "situs": row["source_situs"], "use_code": row["source_use_code"],
        }],
    } for row in records]
    manifest = {
        "snapshot_source": "orange_2026_final_roll", "county_fips": "12095",
        "source_gate": gate, "inventory_sha256": inventory_sha,
        "source_context": context_manifest,
        "authority": "RESEARCH_ONLY", "legal_unit_basis": "UNKNOWN",
        "research_quarantine_required": True,
    }
    return rows, manifest


def orange_research_enabled():
    return os.getenv("BR_ENABLE_ORANGE_RESEARCH_SNAPSHOT") == "1"


def snapshot_available(db, snapshot_id):
    record = db.execute("SELECT manifest FROM acq_snapshots WHERE id=?", (snapshot_id,)).fetchone()
    if record is None:
        raise LookupError("Snapshot not found")
    manifest = json.loads(record[0])
    if (manifest.get("research_quarantine_required")
            and not orange_research_enabled()):
        raise LookupError("Research snapshot is unavailable")
    return manifest


def get(db,run_id):
    r=db.execute('SELECT * FROM acq_runs WHERE id=?',(run_id,)).fetchone()
    if r is None: raise LookupError('Run not found')
    snapshot_available(db, r['snapshot_id'])
    out=dict(r); out['batches']=[json.loads(x[0]) for x in db.execute('SELECT receipt FROM acq_batches WHERE run_id=? ORDER BY start',(run_id,))]
    out['actual_backend']=out['batches'][0]['backend'] if out['batches'] else None
    out['offer_ready']=0;out['authority']='RESEARCH_ONLY';return out


def start(db,request_id,backend,batch_size,cohort_id=None,snapshot_source="retained"):
    if snapshot_source != "retained" and cohort_id:
        raise ValueError("Select a snapshot source or an existing cohort")
    if snapshot_source == "orange_2026_final_roll" and not orange_research_enabled():
        raise ValueError("Orange research snapshot is disabled in this runtime")
    old=db.execute('SELECT * FROM acq_runs WHERE request_id=?',(request_id,)).fetchone()
    if old:
        manifest=json.loads(db.execute('SELECT manifest FROM acq_snapshots WHERE id=?',(old['snapshot_id'],)).fetchone()[0])
        if old['backend']!=backend or old['batch_size']!=batch_size or manifest.get('cohort_id')!=cohort_id or (
            not cohort_id and manifest.get('snapshot_source','retained') != snapshot_source
        ):raise ValueError('Request ID reused with different inputs')
        return get(db,old['id'])
    if cohort_id:
        from .acquisition_cohorts import run_snapshot
        key,total=run_snapshot(db,cohort_id)
    else:key,total,_=snapshot(db,snapshot_source)
    run_id=str(uuid.uuid4())
    db.execute('INSERT INTO acq_runs VALUES(?,?,?,?,?,?,?,?,?,?,?)',(run_id,request_id,key,backend,batch_size,'READY',0,total,1,None,now()))
    db.execute('INSERT INTO acq_run_contracts VALUES(?,?)',(run_id,pf.VERSION))
    return get(db,run_id)


def step(db,run_id,version,action,lease_id=None):
    r=get(db,run_id)
    if version!=r['version']:raise ValueError('Stale run version; reload')
    state=r['state'];cursor=r['cursor'];error=None
    if action=='advance' and state in ('READY','RUNNING'):
        tasks.require_task_advance(db, run_id, lease_id)
        leases.require_advance(db, run_id, lease_id)
        rows=db.execute('SELECT parcel_key,record FROM acq_parcels WHERE snapshot_id=? AND ordinal>=? ORDER BY ordinal LIMIT ?',(r['snapshot_id'],cursor,r['batch_size'])).fetchall()
        if not rows:raise ValueError('Missing batch records')
        try:
            records=[json.loads(row['record']) for row in rows]
            contract=db.execute('SELECT feature_version FROM acq_run_contracts WHERE run_id=?',(run_id,)).fetchone()
            if contract and contract[0]!=pf.VERSION:raise ValueError('Unsupported frozen feature contract')
            if contract:arrays,features=pf.project(records)
            else:arrays,features={k:np.full(len(rows),-1,dtype=np.int64) for k in FIELDS},None
            out,timing=screen(arrays,r['backend'])
        except BackendUnavailable as exc:
            state='FAILED';error=str(exc)
        else:
            results=[{'parcel_key':row['parcel_key'],'screen':'HOLD','legal_units':None,'annual_cash_cents':None,'reason':'No accepted legal unit count or financial evidence'} for row in rows]
            if features is not None:results=pf.result_rows(features,out)
            receipt={**timing,'feature_contract':contract[0] if contract else 'legacy-placeholder','numeric_input_sha256':sha({k:v.tolist() for k,v in arrays.items()}),'start':cursor,'end':cursor+len(rows),'snapshot_id':r['snapshot_id'],'input_sha256':sha([json.loads(row['record']) for row in rows]),'results_sha256':sha(results),'counts':summarize(out)}
            db.execute('INSERT INTO acq_batches VALUES(?,?,?,?)',(run_id,cursor,cursor+len(rows),encode(receipt)))
            db.executemany('INSERT INTO acq_results VALUES(?,?,?)',((run_id,x['parcel_key'],encode(x)) for x in results))
            cursor+=len(rows);state='COMPLETED' if cursor==r['total'] else 'RUNNING'
    elif action=='pause' and state in ('READY','RUNNING'):state='PAUSED'
    elif action=='resume' and state in ('PAUSED','FAILED'):state='READY'
    elif action=='cancel' and state in ('READY','RUNNING','PAUSED','FAILED'):state='CANCELLED'
    else:raise ValueError('Action not allowed in current state')
    db.execute('UPDATE acq_runs SET state=?,cursor=?,version=version+1,error=? WHERE id=?',(state,cursor,error,run_id))
    tasks.after_step(db, run_id, state, action, lease_id, cursor > r['cursor'])
    leases.after_step(db, run_id, state, action, lease_id)
    return get(db,run_id)


def properties(db,snapshot_id,q,limit,offset):
    r=db.execute('SELECT manifest,total FROM acq_snapshots WHERE id=?',(snapshot_id,)).fetchone()
    if r is None:raise LookupError('Snapshot not found')
    snapshot_available(db, snapshot_id)
    params=(snapshot_id,q)
    count=db.execute('SELECT count(*) FROM acq_parcels WHERE snapshot_id=? AND instr(parcel_key,?)>0',params).fetchone()[0]
    rows=db.execute('SELECT record FROM acq_parcels WHERE snapshot_id=? AND instr(parcel_key,?)>0 ORDER BY ordinal LIMIT ? OFFSET ?',(*params,limit,offset))
    return {'snapshot_id':snapshot_id,'manifest':json.loads(r['manifest']),'matches':count,'offset':offset,'items':[json.loads(x[0]) for x in rows]}


def verify_batch(db, run_id, start):
    """Recompute receipt digests from bounded, persisted inputs and outputs."""
    if not 0 <= start <= 2**63 - 1:
        raise LookupError("Batch not found")
    run = db.execute("SELECT snapshot_id, batch_size FROM acq_runs WHERE id=?", (run_id,)).fetchone()
    if run is None:
        raise LookupError("Run not found")
    snapshot_available(db, run["snapshot_id"])
    batch = db.execute(
        "SELECT end, receipt FROM acq_batches WHERE run_id=? AND start=?", (run_id, start)
    ).fetchone()
    if batch is None:
        raise LookupError("Batch not found")
    count = batch["end"] - start
    receipt = json.loads(batch["receipt"])
    if (not 0 < count <= min(run["batch_size"], 10_000)
            or receipt["start"] != start or receipt["end"] != batch["end"]
            or receipt["snapshot_id"] != run["snapshot_id"]):
        raise ValueError("Batch receipt scope mismatch")
    rows = db.execute("""
        SELECT p.record, r.result
        FROM acq_parcels p
        LEFT JOIN acq_results r ON r.run_id=? AND r.parcel_key=p.parcel_key
        WHERE p.snapshot_id=? AND p.ordinal>=? AND p.ordinal<?
        ORDER BY p.ordinal
    """, (run_id, run["snapshot_id"], start, batch["end"])).fetchall()
    if len(rows) != count or any(row["result"] is None for row in rows):
        raise ValueError("Persisted batch is incomplete")
    input_hash = sha([json.loads(row["record"]) for row in rows])
    result_hash = sha([json.loads(row["result"]) for row in rows])
    if input_hash != receipt["input_sha256"] or result_hash != receipt["results_sha256"]:
        raise ValueError("Persisted batch digest mismatch")
    return {"run_id": run_id, "snapshot_id": run["snapshot_id"], "start": start,
            "end": batch["end"], "records_verified": count,
            "input_sha256": input_hash, "results_sha256": result_hash,
            "authority": "RESEARCH_ONLY"}
