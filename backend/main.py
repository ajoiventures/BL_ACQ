"""Local command center. Credentials are server-held; all execution is simulated."""
import os,json,uuid,hashlib,sqlite3,re
import logging
from hmac import compare_digest
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime,timezone
from contextlib import closing,contextmanager
from fastapi import FastAPI,HTTPException,Header,Depends,Request,Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel,Field
from .core.ontology import Ontology,OntologyError,DOMAINS,stamp
from .core.swarm import Swarm,AGENTS,LEADERS
ROOT=Path(__file__).resolve().parents[1]
DB=os.getenv('BR_DB',str(ROOT/'data/command.db'))
Path(DB).parent.mkdir(parents=True,exist_ok=True)
app=FastAPI(title='Black River Founder Command Center',version='0.1.0')
MODULES={'home':'FAMILY_OFFICE','mail':'FAMILY_OFFICE','family':'FAMILY_OFFICE','garden':'FAMILY_OFFICE','property':'FAMILY_OFFICE','commercial':'COMMERCIAL'}
KINDS={'home':['Cleaning','Maintenance','Vendor','Procurement','Routine','Inventory'],'mail':['Physical mail','Document','Scan intake','Forwarding','Deadline'],'family':['Bill','Budget','Account','Tax','Insurance','Asset','Liability','Income','Expense'],'garden':['Plant','Watering','Pruning','Fertilization','Propagation','Harvest','Estate plan'],'property':['Facility','Asset','Construction','Grounds','Animal','Maintenance'],'commercial':['Opportunity','Client','Acquisition','Underwriting','Contract','Revenue']}

def actor(request: Request, authorization:str=Header(default='')):
 match = re.fullmatch(r"Bearer ([^\s]+)", authorization)
 if match is None:
  raise HTTPException(401, "Valid Bearer credential required")
 token = match.group(1)
 credentials = (
  (os.getenv("BR_FOUNDER_TOKEN", ""), "FOUNDER"),
  (os.getenv("BR_AUDIT_TOKEN", ""), "SW-13"),
  (os.getenv("BR_OPERATIONS_TOKEN", ""), "SW-09"),
 )
 token_bytes = token.encode("utf-8")
 matches = [role for secret, role in credentials
            if secret and compare_digest(token_bytes, secret.encode("utf-8"))]
 worker_token = os.getenv("BR_ACQ_WORKER_TOKEN", "")
 if worker_token and compare_digest(token_bytes, worker_token.encode("utf-8")):
  if matches:
   raise HTTPException(403, "Worker credential must be distinct from operator credentials")
  expiry = os.getenv("BR_ACQ_WORKER_EXPIRES_AT")
  if expiry is not None:
   try:
    expires_at = datetime.fromisoformat(expiry)
   except ValueError as exc:
    raise HTTPException(403, "Worker credential expiry is invalid") from exc
   if expires_at.utcoffset() is None:
    raise HTTPException(403, "Worker credential expiry is invalid")
   if expires_at <= datetime.now(timezone.utc):
    raise HTTPException(403, "Worker credential expired")
  run_id = os.getenv("BR_ACQ_WORKER_RUN_ID", "")
  if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", run_id):
   raise HTTPException(403, "Worker run is not assigned")
  base = "/api/acquisition-runs/" + run_id
  method, path = request.method, request.scope["path"]
  release_path = base + "/worker-lease/"
  if ((method == "GET" and path in {base, base + "/worker-task"})
      or (method == "POST" and path in {base + "/worker-lease", base + "/step"})
      or (method == "DELETE" and path.startswith(release_path)
          and "/" not in path[len(release_path):])):
   return "ACQ_WORKER"
  raise HTTPException(403, "Worker credential is scoped to its assigned acquisition run")
 if not matches:
  raise HTTPException(401, "Valid local credential required")
 if len(matches) != 1:
  raise HTTPException(403, "Operator credentials must be distinct")
 return matches[0]

def permit(a,domain,write=False):
 if domain not in DOMAINS: raise HTTPException(422,'Unknown domain')
 if a=='SW-09' and domain!='FAMILY_OFFICE': raise HTTPException(403,'Domain permission denied')
 if write and a=='SW-13': raise HTTPException(403,'Auditor cannot originate or authorize work')

@contextmanager
def conn():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=5000')
 try:
  with c:yield c
 finally:c.close()

def event(c,domain,actor,action,obj,payload):
 prev=c.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone();prev=prev[0] if prev else 'GENESIS'
 body=json.dumps([domain,actor,action,obj,payload],sort_keys=True);h=hashlib.sha256((prev+body).encode()).hexdigest()
 c.execute('INSERT INTO audit(domain,actor,action,object_id,body,prev_hash,hash,at) VALUES(?,?,?,?,?,?,?,?)',(domain,actor,action,obj,body,prev,h,stamp()))

def record_digest(item):
 return hashlib.sha256(json.dumps(dict(item),sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def preparation_scope(item):
 return {'operation':'PREPARE_DRAFT','financial_authority':0,'contractual_authority':0,
         'external_execution':False,'record_version':item['version'],'record_sha256':record_digest(item)}

def decision_is_current(c,decision):
 current=c.execute('SELECT * FROM records WHERE id=?',(decision['record_id'],)).fetchone()
 scope=json.loads(decision['scope'])
 return bool(current and current['domain']==decision['domain']
             and scope.get('record_version')==current['version']
             and scope.get('record_sha256')==record_digest(current))

def initialize():
 o=Ontology(DB);o.db.close();s=Swarm(DB);s.db.close()
 with conn() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,module TEXT,domain TEXT,kind TEXT,title TEXT,notes TEXT,state TEXT,priority INTEGER,due TEXT,owner TEXT,simulation INTEGER DEFAULT 1,version INTEGER DEFAULT 1,created TEXT);
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,domain TEXT,actor TEXT,action TEXT,object_id TEXT,body TEXT,prev_hash TEXT,hash TEXT,at TEXT);
CREATE TABLE IF NOT EXISTS decisions(id TEXT PRIMARY KEY,record_id TEXT,domain TEXT,state TEXT,scope TEXT,expires_at TEXT,approved_by TEXT);
CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY,title TEXT,description TEXT,source TEXT,prerequisites TEXT,maturity TEXT,owner TEXT);
CREATE TABLE IF NOT EXISTS context(actor TEXT PRIMARY KEY,payload TEXT);
CREATE TABLE IF NOT EXISTS assessments(id TEXT PRIMARY KEY,skill_id TEXT,evidence TEXT,verdict TEXT,reviewer TEXT,at TEXT);
CREATE TABLE IF NOT EXISTS job_runs(id TEXT PRIMARY KEY,domain TEXT,leader TEXT,specialist TEXT,state TEXT,input TEXT,output TEXT,error TEXT,created TEXT);
CREATE TABLE IF NOT EXISTS contract_job_context(job_id TEXT PRIMARY KEY REFERENCES job_runs(id), digest TEXT NOT NULL, packet TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS contract_job_context_no_update BEFORE UPDATE ON contract_job_context BEGIN SELECT RAISE(ABORT,'Immutable context'); END;
CREATE TRIGGER IF NOT EXISTS contract_job_context_no_delete BEFORE DELETE ON contract_job_context BEGIN SELECT RAISE(ABORT,'Immutable context'); END;
CREATE TRIGGER IF NOT EXISTS no_audit_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Append-only audit'); END;
CREATE TRIGGER IF NOT EXISTS no_audit_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Append-only audit'); END;''')
  if not c.execute('SELECT 1 FROM records').fetchone():
   seeds=[('home','Maintenance','Review home maintenance scope','Record the issue, supporting photos and a proposed vendor scope. No vendor has been hired.',1),('home','Cleaning','Prepare weekly cleaning routine','Draft room-by-room checklist; no completed cleaning is asserted.',2),('home','Inventory','Create household inventory','List supplies and reorder thresholds before procurement.',3),('family','Insurance','Assemble insurance coverage review','Upload policy evidence before comparing coverage, limits and renewal dates.',1),('family','Bill','Review an unverified bill','SIMULATION: demonstration invoice; amount and payment status unknown.',1),('mail','Physical mail','Classify incoming physical mail','SIMULATION: scan intake awaiting classification and a documented deadline.',2),('garden','Plant','Gardenia · container record','SIMULATION: record moisture, light and observations before scheduling care.',2),('garden','Harvest','Basil · harvest plan','SIMULATION: proposed harvest record, not a completed harvest.',3),('property','Facility','Estate facilities register','SIMULATION: future estate planning; no ownership claimed.',3),('commercial','Opportunity','BR-PILOT-001 · intelligence brief','Simulation of source → model → audit → authorization → delivery. No client or revenue claimed.',1)]
   for i,(m,k,t,n,p) in enumerate(seeds):
    rid=f'BR-{i+1:03d}';d=MODULES[m]
    c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,m,d,k,t,n,'DRAFT',p,None,'SW-12' if m=='garden' else 'SW-09',1,1,stamp()))
    c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)',(rid,'Opportunity' if m=='commercial' else 'Asset',d,t,json.dumps({'simulation':True,'module':m}),stamp()))
    event(c,d,'SYSTEM','SEED_SIMULATION',rid,{})
   for rid in ['BR-001','BR-004','BR-010']:
    d=c.execute('SELECT domain FROM records WHERE id=?',(rid,)).fetchone()[0]
    scope=preparation_scope(c.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone())
    c.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?,?)',(str(uuid.uuid4()),rid,d,'PENDING',json.dumps(scope),'2099-01-01T00:00:00+00:00',None))
  # Import every explicit atomic identifier and expand source-defined ranges. No mastery inferred.
  source=ROOT/'sources/1__WnbVKG88waX1ACak_wBMeonKbRWAjWhsxK8yRSop0.txt'
  if source.exists():
   for line in source.read_text(encoding="utf-8").splitlines():
    match=re.match(r'^(?:Skill\s+)?([A-Z]{1,12}-?)(\d{2,3})(?:[––-](?:[A-Z]{1,12}-?)?(\d{2,3}))?\s*(?:[|:—–. ]+)\s*(.+)',line)
    if not match:continue
    prefix,start,end,desc=match.groups();end=int(end or start)
    if end<int(start) or end-int(start)>100:continue
    for num in range(int(start),end+1):
     sid=f'{prefix}{num:0{len(start)}d}'; title=desc.split('|')[0].split('. ')[0][:150]
     c.execute('INSERT OR IGNORE INTO skills VALUES(?,?,?,?,?,?,?)',(sid,title,line,'https://docs.google.com/document/d/1__WnbVKG88waX1ACak_wBMeonKbRWAjWhsxK8yRSop0/edit',json.dumps(['Evidence provenance','Domain permissions','Independent acceptance review']),'SPECIFIED','L1'))
  from site_academy import catalog, readable
  for item in catalog():
   locator = item.get('pages') or item.get('cells') or item.get('source', '')
   description = '\n\n'.join([item['reference'] + ' · ' + readable(locator),
                              readable(item['procedure']), 'Deliverable — ' + readable(item['output']),
                              'Acceptance — ' + readable(item['acceptance'])])
   for key in ('tool','equation','problem','answer'):
    if key in item:
     description += '\n\n' + key.capitalize() + ' — ' + readable(item[key])
   inputs = item['inputs'] if isinstance(item['inputs'], list) else [item['inputs']]
   c.execute("""INSERT INTO skills VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, description=excluded.description, source=excluded.source,
                prerequisites=excluded.prerequisites, owner=excluded.owner""",
             (item['id'], item['title'], description, 'urn:black-river:site-academy',
              json.dumps([readable(x) for x in inputs]), 'SPECIFIED', item['owner']))
initialize()

class RecordIn(BaseModel):
 module:str;kind:str;title:str=Field(min_length=3,max_length=180);notes:str=Field(default='',max_length=10000);priority:int=Field(default=2,ge=1,le=3);due:str|None=None
class Move(BaseModel):
 target:str;version:int; evidence:str=Field(default='',max_length=10000)
class EvidenceIn(BaseModel):
 source_uri:str=Field(min_length=3);content:str=Field(min_length=3);source_date:str;kind:str='SIMULATION'
class AssertionIn(BaseModel):
 evidence_id:str;value:str;context:str;authority:str;expires_at:str|None=None
 obligation_clause: str | None = Field(default=None, min_length=1, max_length=200)
class ReviewIn(BaseModel):
 decision:str;independent_evidence_id:str|None=None
class LinkIn(BaseModel):
 destination:str;kind:str='RELATES_TO';evidence_id:str|None=None
class Decide(BaseModel):
 decision:str
class JobIn(BaseModel):
 domain:str;leader:str;specialist:str;question:str=Field(min_length=5,max_length=3000)
 request_id: uuid.UUID | None = None
 contract_record_id: uuid.UUID | None = None
 context_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

@app.get('/api/health')
def health():return {'status':'ok','mode':'IMPLEMENTED_SIMULATION','external_connectors':False}

@app.get("/api/ready")
def readiness():
    """Check persistence without creating a database or touching application data."""
    uri = Path(DB).resolve().as_uri() + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=1)) as db:
            db.execute("SELECT id FROM records LIMIT 1").fetchone()
            db.execute("SELECT seq FROM audit LIMIT 1").fetchone()
    except sqlite3.Error:
        logging.getLogger(__name__).warning("Readiness check failed for application database")
        return JSONResponse({"status": "unavailable"}, status_code=503,
                            headers={"Cache-Control": "no-store"})
    return JSONResponse({"status": "ready"}, headers={"Cache-Control": "no-store"})


def overdue_records(records, today):
 """Calendar deadlines are due through the end of the founder's local day."""
 return sorted(
  (row for row in records if row['due'] and row['state'] != 'COMPLETED_SIMULATION'
   and datetime.fromisoformat(row['due']).date() < today),
  key=lambda row: (row['due'][:10], row['priority'], row['id'])
 )


@app.get('/api/bootstrap')
def bootstrap(a=Depends(actor)):
 with conn() as c:
  domains=[d for d in DOMAINS if a!='SW-09' or d=='FAMILY_OFFICE']
  records=[dict(r) for r in c.execute('SELECT * FROM records ORDER BY priority,created') if r['domain'] in domains]
  decisions=[dict(r) for r in c.execute('SELECT d.*,r.title FROM decisions d JOIN records r ON r.id=d.record_id') if r['domain'] in domains]
  for decision in decisions:
   decision['recorded_state']=decision['state']
   if decision['state'] in ('PENDING','APPROVED') and not decision_is_current(c,decision):
    decision['state']='STALE'
   elif decision['state'] in ('PENDING','APPROVED') and decision['expires_at']<=stamp():
    decision['state']='EXPIRED'
  ctx=c.execute('SELECT payload FROM context WHERE actor=?',(a,)).fetchone()
  return dict(actor=a,overdue=overdue_records(records, datetime.now(ZoneInfo("America/New_York")).date()),records=records,decisions=decisions,kinds=KINDS,leaders=LEADERS,agents=AGENTS,skill_count=c.execute('SELECT count(*) FROM skills').fetchone()[0],context=json.loads(ctx[0]) if ctx else {},financials={'cash':None,'net_worth':None,'income':None,'expenses':None,'authority':0,'reason':'No verified ledger or settlement imported'},integrations=[{'name':n,'state':'NOT_CONNECTED'} for n in ['Gmail','Google Drive live sync','Bank / settlements','OCR','Maps / parcel service']])

@app.post('/api/records')
def create(b:RecordIn,a=Depends(actor)):
 if b.module not in MODULES or b.kind not in KINDS[b.module]:raise HTTPException(422,'Invalid module or kind')
 d=MODULES[b.module];permit(a,d,True);rid=str(uuid.uuid4())
 if b.due:
  try:datetime.fromisoformat(b.due)
  except ValueError:raise HTTPException(422,'Invalid deadline')
 with conn() as c:
  c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(rid,b.module,d,b.kind,b.title,b.notes,'DRAFT',b.priority,b.due,a,1,1,stamp()))
  c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?)',(rid,'Asset',d,b.title,json.dumps({'simulation':True,'module':b.module}),stamp()))
  event(c,d,a,'CREATE_DRAFT',rid,b.model_dump())
 return {'id':rid}

def record(c,rid,a,write=False):
 r=c.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
 if not r:raise HTTPException(404,'Record not found')
 permit(a,r['domain'],write);return dict(r)

@app.post('/api/records/{rid}/transition')
def transition(rid:str,b:Move,a=Depends(actor)):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');r=record(c,rid,a)
  if b.version!=r['version']:raise HTTPException(409,'Record changed; refresh before continuing')
  allowed={'DRAFT':'IN_PROGRESS','IN_PROGRESS':'REVIEW_REQUIRED','REVIEW_REQUIRED':'COMPLETED_SIMULATION'}
  if allowed.get(r['state'])!=b.target:raise HTTPException(409,'Illegal state transition')
  if b.target=='COMPLETED_SIMULATION':
   if a!='SW-13':raise HTTPException(403,'Independent SW-13 credential required')
  elif a=='SW-13':raise HTTPException(403,'Auditor cannot perform originating work')
  if b.target!='IN_PROGRESS' and not b.evidence.strip():raise HTTPException(422,'Evidence narrative required')
  c.execute('UPDATE records SET state=?,version=version+1 WHERE id=?',(b.target,rid));event(c,r['domain'],a,'TRANSITION',rid,b.model_dump())
 return {'state':b.target}

@app.get('/api/ontology')
def ontology(domain:str='FAMILY_OFFICE',a=Depends(actor)):
 permit(a,domain)
 with conn() as c:
  objects=[dict(r) for r in c.execute('SELECT * FROM objects WHERE domain=?',(domain,))]
  statuses=[dict(r) for r in c.execute('SELECT s.* FROM statuses s JOIN objects o ON o.id=s.subject_id WHERE o.domain=?',(domain,))]
  for s in statuses:
   s['effective_verification']='EXPIRED' if s['expires_at'] and s['expires_at']<=stamp() else ('NOT_YET_EFFECTIVE' if s['effective_at']>stamp() else s['verification'])
  return {'objects':objects,'links':[dict(r) for r in c.execute('SELECT * FROM links WHERE domain=?',(domain,))],'evidence':[dict(r) for r in c.execute('SELECT * FROM evidence WHERE domain=?',(domain,))],'statuses':statuses}

@app.post('/api/objects/{rid}/evidence')
def evidence(rid:str,b:EvidenceIn,a=Depends(actor)):
 with conn() as c:r=record(c,rid,a,True)
 try:datetime.fromisoformat(b.source_date)
 except ValueError:raise HTTPException(422,'ISO source date required')
 o=Ontology(DB)
 try:eid=o.attach_evidence(rid,r['domain'],b.source_uri,'SIMULATION',b.source_date,b.content)
 finally:o.db.close()
 with conn() as c:event(c,r['domain'],a,'ATTACH_EVIDENCE',rid,{'evidence_id':eid})
 return {'id':eid}

@app.post('/api/objects/{rid}/assertions')
def assertion(rid:str,b:AssertionIn,a=Depends(actor)):
 with conn() as c:r=record(c,rid,a,True)
 if b.expires_at:
  try:
   dt=datetime.fromisoformat(b.expires_at)
   if not dt.tzinfo:raise ValueError()
   b.expires_at=dt.astimezone(timezone.utc).isoformat()
  except ValueError:raise HTTPException(422,'Timezone-aware expiry required')
 o=Ontology(DB)
 predicate, context = 'counts_as', b.context
 if b.obligation_clause is not None:
  try:
   if r['module'] != 'commercial' or r['kind'] != 'Contract' or not b.obligation_clause.strip():
    raise ValueError()
   if datetime.strptime(b.value, "%Y-%m-%d").date().isoformat() != b.value:
    raise ValueError()
  except ValueError:
   o.db.close()
   raise HTTPException(422, 'Contract obligation requires a clause locator and ISO date')
  predicate = 'contract_obligation_date'
  context = json.dumps({"clause_locator": b.obligation_clause.strip(), "description": b.context})
 try:sid=o.status(rid,r['domain'],predicate,b.value,context,b.authority,b.evidence_id,prohibitions=['No real-world authority; simulation only'],expires_at=b.expires_at)
 except OntologyError as e:raise HTTPException(422,str(e))
 finally:o.db.close()
 with conn() as c:event(c,r['domain'],a,'ASSERT_STATUS',rid,{'id':sid})
 return {'id':sid,'verification':'EVIDENCE_FOUND'}

def contract_preparation_packet(c, rid, actor):
 item = record(c, rid, actor)
 if item["module"] != "commercial" or item["kind"] != "Contract":
  raise HTTPException(404, "Contract record required")
 rows = c.execute("""
  SELECT s.id,s.value,s.context,s.effective_at,s.expires_at,s.verification,s.verified_by,
         e.id AS evidence_id,e.source_uri,e.source_date,e.content_hash
  FROM statuses s JOIN evidence e ON e.id=s.source_evidence AND e.object_id=s.subject_id
  WHERE s.subject_id=? AND e.domain=? AND s.predicate='contract_obligation_date'
  ORDER BY s.id LIMIT 101
 """, (rid, item["domain"])).fetchall()
 if len(rows) > 100:
  raise HTTPException(409, "Contract has more than 100 obligation assertions")
 cutoff = stamp()
 obligations = []
 for row in rows:
  entry = dict(row)
  context = json.loads(entry.pop("context"))
  current = row["effective_at"] <= cutoff and (not row["expires_at"] or cutoff < row["expires_at"])
  reviewed = current and row["verification"] == "VERIFIED" and row["verified_by"] == "SW-13"
  if reviewed:
   state = "REVIEWED_SIMULATION"
  elif current and row["verification"] == "EVIDENCE_FOUND":
   state = "SOURCE_REPORTED"
  else:
   state = "WITHHELD"
  obligations.append({**entry, **context, "evidence_state": state,
                      "reviewed_due_date": row["value"] if reviewed else None})
 reported_dates = {}
 for item_obligation in obligations:
  if item_obligation["evidence_state"] != "WITHHELD":
   reported_dates.setdefault(item_obligation["clause_locator"], set()).add(item_obligation["value"])
 for item_obligation in obligations:
  if (item_obligation["evidence_state"] != "WITHHELD"
      and len(reported_dates[item_obligation["clause_locator"]]) > 1):
   item_obligation.update(evidence_state="CONFLICT", reviewed_due_date=None)
 packet = {"schema_version": 1, "contract_record_id": rid, "record_revision_sha256": record_digest(item),
           "obligations": obligations, "authority": "LOCAL_PREPARATION_ONLY"}
 return packet, cutoff


@app.get('/api/records/{rid}/obligation-preparation')
def obligation_preparation(rid: str, a=Depends(actor)):
 with conn() as c:
  c.execute("BEGIN")
  packet, cutoff = contract_preparation_packet(c, rid, a)
  return JSONResponse({**packet, "context_sha256": record_digest(packet), "observed_at": cutoff},
                      headers={"Cache-Control": "private, no-store"})


@app.post('/api/assertions/{sid}/review')
def review(sid:str,b:ReviewIn,a=Depends(actor)):
 if a!='SW-13':raise HTTPException(403,'Independent audit required')
 o=Ontology(DB)
 try:
  s=o.db.execute('SELECT * FROM statuses WHERE id=?',(sid,)).fetchone()
  if not s:raise HTTPException(404,'Assertion not found')
  d=o.obj(s['subject_id'])['domain']
  if b.decision=='VERIFIED':
   ev=o.db.execute('SELECT * FROM evidence WHERE id=?',(b.independent_evidence_id,)).fetchone();original=o.db.execute('SELECT * FROM evidence WHERE id=?',(s['source_evidence'],)).fetchone()
   if not ev or ev['content_hash']==original['content_hash'] or ev['source_uri']==original['source_uri']:raise HTTPException(422,'Distinct independent source and content required')
  o.verify(sid,d,a,b.decision,b.independent_evidence_id)
 except OntologyError as e:raise HTTPException(422,str(e))
 finally:o.db.close()
 with conn() as c:event(c,d,a,'REVIEW_ASSERTION',sid,b.model_dump())
 return {'state':b.decision,'simulation':True}

@app.post('/api/objects/{rid}/links')
def link(rid:str,b:LinkIn,a=Depends(actor)):
 with conn() as c:r=record(c,rid,a,True)
 o=Ontology(DB)
 try:lid=o.relate(rid,b.destination,b.kind,r['domain'],b.evidence_id)
 except OntologyError as e:raise HTTPException(403,str(e))
 finally:o.db.close()
 with conn() as c:event(c,r['domain'],a,'LINK_OBJECTS',rid,b.model_dump())
 return {'id':lid}

@app.post('/api/decisions/{did}')
def decide(did:str,b:Decide,a=Depends(actor)):
 if a!='FOUNDER':raise HTTPException(403,'Founder authorization required')
 if b.decision not in ['APPROVED','REJECTED']:raise HTTPException(422,'Invalid decision')
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM decisions WHERE id=?',(did,)).fetchone()
  if not r:raise HTTPException(404,'Decision not found')
  if r['state']!='PENDING' or r['expires_at']<=stamp():raise HTTPException(409,'Decision unavailable or expired')
  if b.decision=='APPROVED' and not decision_is_current(c,r):raise HTTPException(409,'Record changed or approval lacks a version binding; request a new decision')
  c.execute('UPDATE decisions SET state=?,approved_by=? WHERE id=?',(b.decision,a,did));event(c,r['domain'],a,b.decision,r['record_id'],json.loads(r['scope']))
 return {'state':b.decision,'external_authority':0}

@app.post('/api/external-actions')
def external(a=Depends(actor)):raise HTTPException(403,'External execution disabled. Financial and contractual authority remain zero.')

@app.get('/api/audit')
def audit(domain:str='FAMILY_OFFICE',a=Depends(actor)):
 permit(a,domain)
 with conn() as c:
  prev='GENESIS';valid=True
  for r in c.execute('SELECT * FROM audit ORDER BY seq'):
   valid &= r['prev_hash']==prev and hashlib.sha256((prev+r['body']).encode()).hexdigest()==r['hash'];prev=r['hash']
  return {'integrity':bool(valid),'events':[dict(r) for r in c.execute('SELECT * FROM audit WHERE domain=? ORDER BY seq DESC LIMIT 100',(domain,))]}

@app.get('/api/skills')
def skills(q:str='',a=Depends(actor)):
 with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM skills WHERE id LIKE ? OR description LIKE ? ORDER BY id',('%'+q+'%','%'+q+'%'))]

@app.post('/api/jobs')
def job(b:JobIn,a=Depends(actor)):
 permit(a,b.domain,True)
 if b.leader not in LEADERS or b.specialist not in AGENTS or b.specialist=='SW-13':raise HTTPException(422,'Valid originating leader/specialist required')
 bound = b.contract_record_id is not None or b.context_sha256 is not None
 if bound and (not b.contract_record_id or not b.context_sha256 or not b.request_id
               or (b.domain,b.leader,b.specialist) != ("COMMERCIAL","L4","SW-07")):
  raise HTTPException(422,"Contract preparation requires a reviewed context, request ID and the Commercial Transaction Desk")
 if b.request_id and not bound:
  raise HTTPException(422,"Request ID requires a contract preparation context")
 jid=str(b.request_id or uuid.uuid4())
 with conn() as c:
  c.execute("BEGIN IMMEDIATE")
  if bound:
   existing = c.execute("SELECT j.input,x.digest,x.packet FROM job_runs j LEFT JOIN contract_job_context x ON x.job_id=j.id WHERE j.id=?", (jid,)).fetchone()
   if existing:
    if (existing["digest"] != b.context_sha256 or existing["input"] != b.question
        or json.loads(existing["packet"])["contract_record_id"] != str(b.contract_record_id)):
     raise HTTPException(409,"Request ID already belongs to different work")
    return {"id":jid,"replay":True}
   packet, _ = contract_preparation_packet(c,str(b.contract_record_id),a)
   if record_digest(packet) != b.context_sha256:
    raise HTTPException(409,"Contract context changed; review the latest preparation")
  c.execute('INSERT INTO job_runs VALUES(?,?,?,?,?,?,?,?,?)',(jid,b.domain,b.leader,b.specialist,'QUEUED',b.question,'','',stamp()))
  if bound:
   c.execute("INSERT INTO contract_job_context VALUES(?,?,?)",(jid,b.context_sha256,json.dumps(packet)))
  event(c,b.domain,a,'QUEUE_SIMULATION',jid,b.model_dump(mode="json", exclude_none=True))
 return {'id':jid}



@app.post('/api/jobs/{jid}/run')
def run(jid:str,a=Depends(actor)):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');j=c.execute('SELECT * FROM job_runs WHERE id=?',(jid,)).fetchone()
  if not j:raise HTTPException(404,'Job not found')
  permit(a,j['domain'],True)
  if j['state']!='QUEUED':raise HTTPException(409,'Job already processed')
  output={'mode':'DETERMINISTIC_SIMULATION','handoff':'SW-13','next_action':'Attach source evidence and request independent review','claims':[],'financial_authority':0,'leader':j['leader'],'specialist':j['specialist']}
  bound = c.execute("SELECT digest,packet FROM contract_job_context WHERE job_id=?",(jid,)).fetchone()
  if bound:
   packet = json.loads(bound["packet"])
   current, _ = contract_preparation_packet(c,packet["contract_record_id"],a)
   if record_digest(current) != bound["digest"]:
    raise HTTPException(409,"Contract context changed; review and queue a replacement")
   output["contract_preparation"] = {"context_sha256": bound["digest"], "packet": packet,
                                     "tool_scope": "READ_RETAINED_CONTRACT_CONTEXT",
                                     "output_contract": "SIMULATION_HANDOFF_ONLY"}
  c.execute('UPDATE job_runs SET state=?,output=? WHERE id=?',('NEEDS_EVIDENCE',json.dumps(output),jid));event(c,j['domain'],j['specialist'],'SIMULATED_HANDOFF',jid,output)
 return output

@app.get('/api/jobs')
def jobs(domain:str='FAMILY_OFFICE',a=Depends(actor)):
 permit(a,domain)
 with conn() as c:return [dict(r) for r in c.execute('SELECT * FROM job_runs WHERE domain=? ORDER BY created DESC',(domain,))]

@app.put('/api/context')
def context(b:dict,a=Depends(actor)):
 payload=json.dumps(b)
 if len(payload)>10000:raise HTTPException(422,'Context too large')
 with conn() as c:c.execute('INSERT OR REPLACE INTO context VALUES(?,?)',(a,payload))
 return {'saved':True}

# Separate, empty-by-default simulation ledger. Values are integer cents.
with conn() as c:
 c.execute('CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY,domain TEXT,entity TEXT,debit_account TEXT,credit_account TEXT,cents INTEGER,evidence TEXT,created TEXT)')
ACCOUNT_TYPES={'Cash':'ASSET','Property':'ASSET','Payable':'LIABILITY','Owner equity':'EQUITY','Service revenue':'INCOME','Household expense':'EXPENSE','Maintenance expense':'EXPENSE'}
class JournalIn(BaseModel):
 domain:str='FAMILY_OFFICE';entity:str=Field(min_length=3,max_length=120);debit_account:str;credit_account:str;cents:int=Field(gt=0,le=100000000000);evidence:str=Field(min_length=10,max_length=3000)
@app.post('/api/ledger')
def journal(b:JournalIn,a=Depends(actor)):
 permit(a,b.domain,True)
 if a!='FOUNDER':raise HTTPException(403,'Founder owns simulation ledger input')
 if b.debit_account not in ACCOUNT_TYPES or b.credit_account not in ACCOUNT_TYPES or b.debit_account==b.credit_account:raise HTTPException(422,'Distinct supported accounts required')
 jid=str(uuid.uuid4())
 with conn() as c:
  c.execute('INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)',(jid,b.domain,b.entity,b.debit_account,b.credit_account,b.cents,b.evidence,stamp()))
  event(c,b.domain,a,'SIMULATION_JOURNAL',jid,b.model_dump())
 return {'id':jid,'simulation':True,'real_cash_impact':0}
@app.get('/api/ledger')
def ledger(domain:str='FAMILY_OFFICE',a=Depends(actor)):
 permit(a,domain)
 with conn() as c:rows=[dict(r) for r in c.execute('SELECT * FROM ledger WHERE domain=? ORDER BY created',(domain,))]
 balances={k:0 for k in ACCOUNT_TYPES}
 for r in rows:balances[r['debit_account']]+=r['cents'];balances[r['credit_account']]-=r['cents']
 assets=sum(v for k,v in balances.items() if ACCOUNT_TYPES[k]=='ASSET');liabilities=-sum(v for k,v in balances.items() if ACCOUNT_TYPES[k]=='LIABILITY');income=-sum(v for k,v in balances.items() if ACCOUNT_TYPES[k]=='INCOME');expense=sum(v for k,v in balances.items() if ACCOUNT_TYPES[k]=='EXPENSE')
 return {'simulation':True,'entity_scope':'Combined simulation entities; no consolidation eliminations','accounts':ACCOUNT_TYPES,'entries':rows,'balances_cents':balances,'summary_cents':{'assets':assets,'liabilities':liabilities,'net_worth':assets-liabilities,'income':income,'expenses':expense,'net_income':income-expense,'cash_movement':balances['Cash']} if rows else None,'balanced':sum(balances.values())==0}

class AssessmentIn(BaseModel):
 evidence:str=Field(min_length=20);verdict:str
@app.post('/api/skills/{sid}/assess')
def assess(sid:str,b:AssessmentIn,a=Depends(actor)):
 if a!='SW-13':raise HTTPException(403,'Independent competency reviewer required')
 if b.verdict not in ['PASS_SIMULATION','FAIL']:raise HTTPException(422,'Invalid assessment verdict')
 with conn() as c:
  if not c.execute('SELECT 1 FROM skills WHERE id=?',(sid,)).fetchone():raise HTTPException(404,'Skill not found')
  assessment_id=str(uuid.uuid4())
  c.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?)',(assessment_id,sid,b.evidence,b.verdict,a,stamp()))
  c.execute('UPDATE skills SET maturity=? WHERE id=?',('TESTED_SIMULATION' if b.verdict=='PASS_SIMULATION' else 'SPECIFIED',sid))
  event(c,'COMMERCIAL',a,'SKILL_ASSESSMENT',sid,b.model_dump())
 return {'id':assessment_id,'verdict':b.verdict,'live_authority':0}

class RecordEdit(BaseModel):
 title:str=Field(min_length=3,max_length=180);notes:str=Field(max_length=10000);due:str|None=None;version:int
@app.put('/api/records/{rid}')
def edit_record(rid:str,b:RecordEdit,a=Depends(actor)):
 if b.due:
  try:datetime.fromisoformat(b.due)
  except ValueError:raise HTTPException(422,'Invalid deadline')
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');r=record(c,rid,a,True)
  if r['version']!=b.version:raise HTTPException(409,'Record changed; refresh before editing')
  if r['state'] in ['REVIEW_REQUIRED','COMPLETED_SIMULATION']:raise HTTPException(409,'Submitted records are locked; create a new revision draft')
  c.execute('UPDATE records SET title=?,notes=?,due=?,version=version+1 WHERE id=?',(b.title,b.notes,b.due,rid))
  c.execute('UPDATE objects SET title=? WHERE id=?',(b.title,rid))
  event(c,r['domain'],a,'EDIT_DRAFT',rid,b.model_dump())
 return {'saved':True}
class MailForwardPreparation(BaseModel):
 recipient: str | None = Field(default=None,max_length=254,pattern=r"^[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+$")
 mail_capture_id: str | None = Field(default=None,pattern=r"^[0-9a-f]{64}$")

@app.post('/api/records/{rid}/request-approval')
def request_approval(rid:str, forwarding:MailForwardPreparation | None = None,a=Depends(actor)):
 with conn() as c:
  c.execute('BEGIN IMMEDIATE');r=record(c,rid,a,True)
  scope=preparation_scope(r)
  if forwarding is not None and forwarding.model_fields_set:
   if not forwarding.recipient or not forwarding.mail_capture_id:
    raise HTTPException(422,'Forwarding preparation requires a recipient and filed email capture')
   if r['module']!='mail' or r['kind']!='Forwarding':
    raise HTTPException(422,'Forwarding preparation requires a mail Forwarding record')
   from filing.inbox import read_capture
   archive=os.getenv('BR_FAMILY_MAIL_ARCHIVE')
   if not archive:
    raise HTTPException(409,'Family Office mail archive is unavailable')
   try:
    capture=read_capture(Path(archive),forwarding.mail_capture_id)
   except (OSError,ValueError) as exc:
    raise HTTPException(409,'Filed mail evidence could not be verified') from exc
   if not capture['source_name'].lower().endswith('.eml'):
    raise HTTPException(422,'Forwarding preparation requires a filed email')
   scope.update(operation='PREPARE_MAIL_FORWARD',recipient=forwarding.recipient,
                mail_capture_id=capture['capture_id'],mail_sha256=capture['sha256'])
  pending=c.execute("SELECT * FROM decisions WHERE record_id=? AND state='PENDING'",(rid,)).fetchall()
  if any(decision_is_current(c,d) and d['expires_at']>stamp() for d in pending):raise HTTPException(409,'A decision is already pending')
  if r['state']!='DRAFT':raise HTTPException(409,'Only draft preparation can be requested')
  for old in pending:
   c.execute("UPDATE decisions SET state='SUPERSEDED' WHERE id=?",(old['id'],))
   event(c,r['domain'],a,'SUPERSEDE_STALE_DECISION',rid,{'decision_id':old['id'],'original_scope':json.loads(old['scope'])})
  did=str(uuid.uuid4())
  from datetime import timedelta
  expires=(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()
  c.execute('INSERT INTO decisions VALUES(?,?,?,?,?,?,?)',(did,rid,r['domain'],'PENDING',json.dumps(scope),expires,None));event(c,r['domain'],a,'REQUEST_DRAFT_APPROVAL',rid,scope)
 return {'id':did,'scope':scope}


class RenewalIntake(BaseModel):
    version: int
    reference: str = Field(min_length=3,max_length=500)
    document: str = Field(min_length=10,max_length=12000)
    issued: str
    deadline: str | None = None
    quotation: str = Field(default='',max_length=1000)
    mail_capture_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

@app.post('/api/records/{rid}/renewal')
def classify_renewal(rid:str, body:RenewalIntake, a=Depends(actor)):
    """User-reviewed classification. Dates use an exact ISO quotation in this release."""
    from datetime import date
    try:
        date.fromisoformat(body.issued)
        if body.deadline:
            date.fromisoformat(body.deadline)
    except ValueError:
        raise HTTPException(422,'Enter a valid calendar date')
    if body.deadline and (not body.quotation.strip() or body.quotation not in body.document or body.deadline not in body.quotation):
        raise HTTPException(422,'Quote the deadline exactly, including its YYYY-MM-DD date')
    with conn() as c:
        item=record(c,rid,a,True)
        if item['module']!='mail' or item['state']!='DRAFT' or item['version']!=body.version:
            raise HTTPException(409,'Select the current version of a draft mail record')
        reference = body.reference
        if body.mail_capture_id is not None:
            from filing.inbox import extract_filed_mail, read_capture
            archive = os.getenv("BR_FAMILY_MAIL_ARCHIVE")
            if not archive:
                raise HTTPException(409, "Family Office mail archive is unavailable")
            try:
                capture = read_capture(Path(archive), body.mail_capture_id)
                filed_text = extract_filed_mail(capture)
            except (OSError, ValueError) as exc:
                raise HTTPException(409, "Filed mail evidence could not be verified") from exc
            if filed_text.strip() != body.document.strip():
                raise HTTPException(422, "Document does not match the filed mail text")
            reference = "mail-capture:" + capture["capture_id"]
        c.execute('BEGIN IMMEDIATE')
        item=record(c,rid,a,True)
        if item['module']!='mail' or item['state']!='DRAFT' or item['version']!=body.version:
            raise HTTPException(409,'Select the current version of a draft mail record')
        eid=str(uuid.uuid4())
        digest=hashlib.sha256(body.document.encode()).hexdigest()
        c.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?)',(eid,rid,reference,'SIMULATION',body.issued,digest,item['domain'],stamp()))
        note='Insurance renewal notice (simulation). '+('Deadline source: '+body.quotation if body.deadline else 'Deadline unknown.')
        c.execute('UPDATE records SET notes=?,due=?,version=version+1 WHERE id=?',(item['notes']+'\n'+note,body.deadline,rid))
        event(c,item['domain'],a,'CLASSIFY_RENEWAL',rid,{'classification':'Insurance renewal','evidence_id':eid,'quote':body.quotation,'deadline':body.deadline})
    return {'classification':'Insurance renewal','evidence_id':eid,'deadline':body.deadline}

class SiteStudyIn(BaseModel):
 curriculum:str=Field(default="site",pattern="^(site|urban|planning|acquisition)$")
 name:str=Field(min_length=2,max_length=160)

@app.post('/api/site-studies')
def open_site_study(b:SiteStudyIn, authorization:str=Header(default=''), a=Depends(actor)):
 from contextlib import closing
 from site_academy import runner
 permit(a, 'MAIN_STREET_INSTITUTIONAL', write=True)
 registry=runner.load_skills(b.curriculum)
 path=Path(DB).with_suffix('.site.sqlite3')
 with closing(runner.connect(path)) as db:
  try:
   study=runner.start(db,b.name,registry,curriculum=b.curriculum,caller_token=authorization.removeprefix('Bearer '))
  except PermissionError as exc:
   raise HTTPException(403,str(exc)) from exc
  except ValueError as exc:
   raise HTTPException(422,str(exc)) from exc
  return runner.status(db,study,caller_token=authorization.removeprefix('Bearer '))

@app.get('/api/site-studies')
def site_studies(a=Depends(actor)):
 from contextlib import closing
 from site_academy import runner
 permit(a, 'MAIN_STREET_INSTITUTIONAL')
 with closing(runner.connect(Path(DB).with_suffix('.site.sqlite3'))) as db:
  return [dict(r) for r in db.execute('SELECT id,name,curriculum FROM studies ORDER BY id DESC')]

@app.get('/api/site-studies/{study}')
def read_site_study(study:int,authorization:str=Header(default=''),a=Depends(actor)):
 from contextlib import closing
 from site_academy import runner
 permit(a, 'MAIN_STREET_INSTITUTIONAL')
 with closing(runner.connect(Path(DB).with_suffix('.site.sqlite3'))) as db:
  if not db.execute('SELECT 1 FROM studies WHERE id=?',(study,)).fetchone():
   raise HTTPException(404,'Study not found')
  return runner.status(db,study,caller_token=authorization.removeprefix('Bearer '))

class SiteEvidence(BaseModel):
 action:str
 text:str=Field(min_length=1,max_length=150000)
 source:str=Field(min_length=1,max_length=500)
 reason:str=Field(min_length=1,max_length=1500)

@app.post('/api/site-studies/{study}/tasks/{skill}')
def site_evidence(study:int,skill:str,b:SiteEvidence,authorization:str=Header(default=''),a=Depends(actor)):
 from contextlib import closing
 from site_academy import runner
 permit(a,'MAIN_STREET_INSTITUTIONAL')
 with closing(runner.connect(Path(DB).with_suffix('.site.sqlite3'))) as db:
  try:
   state=runner.act(db,study,skill,b.action,b.text.encode(),b.source,b.reason,
                    caller_token=authorization.removeprefix('Bearer '))
  except PermissionError as exc:
   raise HTTPException(403,str(exc)) from exc
  except ValueError as exc:
   raise HTTPException(422,str(exc)) from exc
  return {'study':study,'skill':skill,'state':state}

from .ticket_routes import register as register_project_tickets
register_project_tickets(app,actor,permit,conn,event)
from .intake_routes import register as register_founder_intake
register_founder_intake(app,actor,conn,event)

from .profit_routes import register as register_profit_review
register_profit_review(app, actor, permit, conn, event)

from .economic_routes import register as register_economic_development
register_economic_development(app, actor, permit, conn, event)

from .signal_routes import register as register_intelligence_flow
register_intelligence_flow(app, actor, permit, conn, event)

from .planning_routes import register as register_cities_planning
register_cities_planning(app, actor, permit, conn, event)

from .acquisition_routes import register as register_acquisition_runs
register_acquisition_runs(app,actor,permit,conn,event)

from .strategy_routes import register as register_strategy_cases
register_strategy_cases(app,actor,permit,conn,event)


def load_college_park_dossier(parcel_id, as_of):
 from .core.dossier_readback import AS_OF, ParcelOutsideSample, read_dossier

 if not re.fullmatch(r"[0-9]{15}", parcel_id):
  raise HTTPException(422, "Expected a 15-digit county parcel ID")
 if as_of != AS_OF:
  raise HTTPException(422, "No retained dossier snapshot for that date")
 try:
  result = read_dossier(parcel_id, as_of, context_path=os.getenv("BR_DOSSIER_CONTEXT_PATH"))
 except ParcelOutsideSample:
  raise HTTPException(404, "Parcel is outside the retained dossier sample") from None
 except (ValueError, RuntimeError, OSError, KeyError, TypeError):
  raise HTTPException(503, "Retained dossier evidence could not be verified") from None
 return result

@app.get("/api/acquisition-dossiers/college-park/{parcel_id}")
def college_park_dossier(parcel_id: str, as_of: str, a=Depends(actor)):
 permit(a, "COMMERCIAL")
 return JSONResponse(load_college_park_dossier(parcel_id, as_of),
                     headers={"Cache-Control": "private, no-store"})


@app.post("/api/acquisition-dossiers/college-park/{parcel_id}/revisions")
def capture_college_park_dossier(parcel_id: str, as_of: str, a=Depends(actor)):
 from .core.dossier_readback import initialize_history, retain_revision

 permit(a, "COMMERCIAL", write=True)
 result = load_college_park_dossier(parcel_id, as_of)
 with conn() as db:
  db.execute("BEGIN IMMEDIATE")
  initialize_history(db)
  if retain_revision(db, result):
   event(db, "COMMERCIAL", a, "DOSSIER_REVISION_CAPTURED", parcel_id,
         {"revision_sha256": result["revision_sha256"], "as_of": as_of})
 return JSONResponse(result, headers={"Cache-Control": "private, no-store"})


@app.get("/api/acquisition-dossiers/college-park/{parcel_id}/revisions")
def list_college_park_revisions(parcel_id: str, limit: int = Query(20, ge=1, le=100),
                                offset: int = Query(0, ge=0, le=10_000), a=Depends(actor)):
 from .core.dossier_readback import list_revisions

 permit(a, "COMMERCIAL")
 if not re.fullmatch(r"[0-9]{15}", parcel_id):
  raise HTTPException(422, "Expected a 15-digit county parcel ID")
 with conn() as db:
  items = list_revisions(db, parcel_id, limit=limit, offset=offset)
 return JSONResponse({"parcel_id": parcel_id, "items": items, "offset": offset},
                     headers={"Cache-Control": "private, no-store"})


@app.get("/api/acquisition-dossiers/college-park/{parcel_id}/revisions/{revision}")
def read_college_park_revision(parcel_id: str, revision: str, a=Depends(actor)):
 from .core.dossier_readback import retained_revision

 permit(a, "COMMERCIAL")
 if not re.fullmatch(r"[0-9]{15}", parcel_id) or not re.fullmatch(r"[0-9a-f]{64}", revision):
  raise HTTPException(422, "Invalid dossier revision identity")
 with conn() as db:
  if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='acquisition_dossier_revisions'").fetchone():
   raise HTTPException(404, "Dossier revision not found")
  try:
   result = retained_revision(db, parcel_id, revision)
  except (ValueError, RuntimeError, KeyError, TypeError):
   raise HTTPException(503, "Retained dossier revision could not be verified") from None
 if result is None:
  raise HTTPException(404, "Dossier revision not found")
 return JSONResponse(result, headers={"Cache-Control": "private, no-store"})
