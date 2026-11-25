"""Immutable, bounded research cohorts and GIS attribute handoff.
Source-reported locality/use is not jurisdiction, legal unit count or ownership.
No geometry is synthesized. No evidence is accepted by this module.
"""
import csv, io, json
from .acquisition_runs import encode, sha, snapshot_available

LIMIT_EXPORT=10000

def initialize(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS acq_observation_index(
        snapshot_id TEXT NOT NULL, parcel_key TEXT NOT NULL, feature_id TEXT NOT NULL,
        city TEXT NOT NULL, use_code TEXT NOT NULL, PRIMARY KEY(snapshot_id,parcel_key,feature_id));
    CREATE INDEX IF NOT EXISTS acq_obs_city ON acq_observation_index(snapshot_id,city,parcel_key);
    CREATE INDEX IF NOT EXISTS acq_obs_code ON acq_observation_index(snapshot_id,use_code,parcel_key);
    CREATE TABLE IF NOT EXISTS acq_indexed_snapshots(snapshot_id TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS acq_cohorts(id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL, manifest TEXT NOT NULL, total INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS acq_cohort_members(cohort_id TEXT NOT NULL, parcel_key TEXT NOT NULL, PRIMARY KEY(cohort_id,parcel_key), FOREIGN KEY(cohort_id) REFERENCES acq_cohorts(id));''')
    for table in ('acq_observation_index','acq_indexed_snapshots','acq_cohorts','acq_cohort_members'):
        for op in ('UPDATE','DELETE'):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable cohort evidence'); END")

def index_snapshot(db,key):
    if db.execute('SELECT 1 FROM acq_indexed_snapshots WHERE snapshot_id=?',(key,)).fetchone():return
    for row in db.execute('SELECT parcel_key,record FROM acq_parcels WHERE snapshot_id=?',(key,)):
        r=json.loads(row['record'])
        db.executemany('INSERT INTO acq_observation_index VALUES(?,?,?,?,?)',[(key,row['parcel_key'],o['feature_id'],o['city'].strip().casefold(),o['use_code']) for o in r.get('source_observations',[])])
    db.execute('INSERT INTO acq_indexed_snapshots VALUES(?)',(key,))

def filters(city='',use_code=''):
    city=city.strip().casefold();use_code=use_code.strip()
    if len(city)>100 or len(use_code)>8 or (use_code and not use_code.isascii()) or (use_code and not use_code.isdigit()):raise ValueError('Invalid cohort filter')
    return {'source_city':city,'source_use_code':use_code}

def select_keys(db,key,f):
    # Both conditions must match the SAME source observation. No cross-row false matches.
    if not f['source_city'] and not f['source_use_code']:
        return db.execute('SELECT parcel_key FROM acq_parcels WHERE snapshot_id=? ORDER BY parcel_key',(key,))
    clauses=['snapshot_id=?'];params=[key]
    for col,val in [('city',f['source_city']),('use_code',f['source_use_code'])]:
        if val:clauses.append(col+'=?');params.append(val)
    return db.execute('SELECT DISTINCT parcel_key FROM acq_observation_index WHERE '+' AND '.join(clauses)+' ORDER BY parcel_key',params)

def freeze(db,key,city='',use_code='', *, shortlist=None):
    s=db.execute('SELECT manifest,total FROM acq_snapshots WHERE id=?',(key,)).fetchone()
    if not s:raise LookupError('Snapshot not found')
    snapshot_available(db,key)
    f=filters(city,use_code);index_snapshot(db,key)
    if any(f.values()) and not db.execute('SELECT 1 FROM acq_observation_index WHERE snapshot_id=? LIMIT 1',(key,)).fetchone():
        raise ValueError('Snapshot lacks source observation index; create a fresh run')
    manifest={'version':1,'snapshot_id':key,'filters':f,'source_manifest':json.loads(s['manifest']), 'authority':'RESEARCH_ONLY','legal_unit_basis':'UNKNOWN','geometry':'NOT_SUPPLIED'}
    if shortlist:
        manifest["shortlist"] = shortlist
    cid=sha(manifest)
    old=db.execute('SELECT total FROM acq_cohorts WHERE id=?',(cid,)).fetchone()
    if old:return {'id':cid,'total':old[0],'manifest':manifest,'replay':True}
    # Count first, then write immutable manifest and membership within caller transaction.
    members = select_keys(db, key, f) if shortlist is None else db.execute(
        "SELECT parcel_key FROM acq_parcels WHERE snapshot_id=? AND parcel_key=?",
        (key, shortlist["parcel_key"]),
    )
    total = sum(1 for _ in members)
    if shortlist and total != 1:
        raise LookupError("Shortlist parcel is outside the source snapshot")
    db.execute('INSERT INTO acq_cohorts VALUES(?,?,?,?)',(cid,key,encode(manifest),total))
    db.executemany('INSERT INTO acq_cohort_members VALUES(?,?)',((cid,r[0]) for r in select_keys(db,key,f)) if shortlist is None else [(cid, shortlist['parcel_key'])])
    return {'id':cid,'total':total,'manifest':manifest,'replay':False}

def get(db,cid):
    r=db.execute('SELECT * FROM acq_cohorts WHERE id=?',(cid,)).fetchone()
    if r is None:raise LookupError('Cohort not found')
    snapshot_available(db,r['snapshot_id'])
    return {**dict(r),'manifest':json.loads(r['manifest'])}

def page(db,cid,after='',limit=25):
    c=get(db,cid)
    rows=db.execute('SELECT p.record FROM acq_cohort_members m JOIN acq_parcels p ON p.snapshot_id=? AND p.parcel_key=m.parcel_key WHERE m.cohort_id=? AND m.parcel_key>? ORDER BY m.parcel_key LIMIT ?',(c['snapshot_id'],cid,after,limit+1)).fetchall()
    items=[json.loads(r[0]) for r in rows[:limit]]
    return {'cohort_id':cid,'total':c['total'],'items':items,'next_cursor':items[-1]['parcel_key'] if len(rows)>limit else None}

def evidence(db,key,parcel):
    manifest=snapshot_available(db,key)
    r=db.execute('SELECT record FROM acq_parcels WHERE snapshot_id=? AND parcel_key=?',(key,parcel)).fetchone()
    if r is None:raise LookupError('Parcel not found in snapshot')
    raw=json.loads(r[0]);obs=raw.get('source_observations',[])
    fields={k:sorted({o[k] for o in obs if o.get(k)}) for k in ('situs','city','zip','use_code')}
    for name in ("reported_units", "reported_buildings"):
        if name in raw:
            fields[name] = [] if raw[name] is None else [str(raw[name])]
    return {'snapshot_id':key,'parcel_key':parcel,'source_manifest':manifest,'record_sha256':sha(raw),'observations':obs,'source_reported_values':fields,'conflicting_fields':[k for k,v in fields.items() if len(v)>1], 'verification':'SOURCE_REPORTED_NOT_ACCEPTED','legal_units':None,'financial_inputs':None,'geometry':None,**({'source_context':raw['source_context']} if 'source_context' in raw else {}),'next_action':'Obtain current jurisdiction, legal unit and financial evidence; reconcile conflicting source observations.'}

def export_csv(db,cid):
    c=get(db,cid)
    if c["manifest"]["source_manifest"].get("research_quarantine_required"):
        raise ValueError("Source review is required before bulk export")
    if c['total']>LIMIT_EXPORT:raise ValueError('Cohort exceeds bounded GIS attribute export limit')
    out=io.StringIO(newline='');w=csv.writer(out);w.writerow(['parcel_key','county_fips','county_parcel_id','snapshot_id','cohort_id','source_use_codes','source_city_candidates','corridor_spine_match','legal_units','verification','geometry_status'])
    cursor=''
    while True:
        p=page(db,cid,cursor,500)
        for r in p['items']:
            county,pin=r['parcel_key'].split(':',1)
            # Only controlled numeric IDs and normalized source strings; protect spreadsheets from formula injection.
            def safe(v):return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r')) else v
            cities=sorted({o['city'] for o in r.get('source_observations',[]) if o['city']})
            w.writerow([r['parcel_key'],county,pin,c['snapshot_id'],cid,safe('|'.join(r['source_use_codes'])),safe('|'.join(cities)),int(r['college_park_spine_match']),'','SOURCE_REPORTED_NOT_ACCEPTED','NO_GEOMETRY'])
        cursor=p['next_cursor']
        if not cursor:break
    return out.getvalue()


def run_snapshot(db,cid):
    """Materialize a bounded immutable selection for the existing batch worker."""
    c=get(db,cid)
    if not c['total']:raise ValueError('Empty cohort cannot start a run')
    manifest={**c['manifest']['source_manifest'],'cohort_id':cid,'parent_snapshot_id':c['snapshot_id'],'cohort_filters':c['manifest']['filters'],'cohort_count':c['total']}
    if 'shortlist' in c['manifest']:
        manifest['cohort_filters'] = {**manifest['cohort_filters'], 'shortlist': c['manifest']['shortlist']}
    key=sha({'cohort_manifest':manifest})
    if not db.execute('SELECT 1 FROM acq_snapshots WHERE id=?',(key,)).fetchone():
        db.execute('INSERT INTO acq_snapshots VALUES(?,?,?)',(key,encode(manifest),c['total']))
        db.execute('''INSERT INTO acq_parcels(snapshot_id,ordinal,parcel_key,record)
        SELECT ?,row_number() OVER(ORDER BY m.parcel_key)-1,p.parcel_key,p.record FROM acq_cohort_members m
        JOIN acq_parcels p ON p.snapshot_id=? AND p.parcel_key=m.parcel_key WHERE m.cohort_id=?''',(key,c['snapshot_id'],cid))
        if db.execute('SELECT count(*) FROM acq_parcels WHERE snapshot_id=?',(key,)).fetchone()[0]!=c['total']:raise ValueError('Cohort membership mismatch')
    return key,c['total']
