"""Black River controlled multi-agent *simulation*, with SQLite persistence.
No live external tools, money movements, messages, or legal authority.
"""
from __future__ import annotations
import hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

DOMAINS={"COMMERCIAL", "FAMILY_OFFICE", "MAIN_STREET_INSTITUTIONAL"}
LEADERS={
 "L1": "Institutional Strategy & Skills", "L2": "AI Systems Engineering",
 "L3": "Investment CIO & CFO", "L4": "Commercial Operations"
}
AGENTS={
 "SW-00":"Orchestration","SW-01":"Spatial Intelligence","SW-02":"Sourcing",
 "SW-03":"Title & Entitlements","SW-04":"Decision Science","SW-05":"Underwriting",
 "SW-06":"Private Capital Eligibility","SW-07":"Transaction Desk","SW-08":"Construction",
 "SW-09":"Asset Operations","SW-10":"Portfolio CIO/CFO","SW-11":"Board Reporting",
 "SW-12":"Estate Stewardship","SW-13":"Independent Audit"
}
STATES=("DRAFT","EVIDENCE_REVIEW","UNDERWRITTEN","AUDIT_PASSED","APPROVAL_REQUIRED","APPROVED","DELIVERED_SIMULATED","INVOICED_SIMULATED","SETTLED_SIMULATED","RECONCILED_SIMULATED")
NEXT={"DRAFT":"EVIDENCE_REVIEW","EVIDENCE_REVIEW":"UNDERWRITTEN","UNDERWRITTEN":"AUDIT_PASSED","AUDIT_PASSED":"APPROVAL_REQUIRED","APPROVAL_REQUIRED":"APPROVED","APPROVED":"DELIVERED_SIMULATED","DELIVERED_SIMULATED":"INVOICED_SIMULATED","INVOICED_SIMULATED":"SETTLED_SIMULATED","SETTLED_SIMULATED":"RECONCILED_SIMULATED"}
class GateError(ValueError): pass

def now(): return datetime.now(timezone.utc).isoformat()
def canon(d): return json.dumps(d,sort_keys=True,separators=(',',':'))

class Swarm:
 def __init__(self, path: str|Path=":memory:"):
  self.db=sqlite3.connect(str(path)); self.db.row_factory=sqlite3.Row
  self.db.executescript("""
   PRAGMA foreign_keys=ON;
   CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, domain TEXT NOT NULL, title TEXT NOT NULL, state TEXT NOT NULL, leader TEXT NOT NULL, agent TEXT NOT NULL, evidence TEXT NOT NULL, approval TEXT, approved_by TEXT, audit_by TEXT, simulation INTEGER NOT NULL DEFAULT 1, created TEXT NOT NULL);
   CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, action TEXT NOT NULL, actor TEXT NOT NULL, key TEXT NOT NULL UNIQUE, payload TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL, at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES jobs(id));
   CREATE TABLE IF NOT EXISTS journals(id TEXT PRIMARY KEY, job_id TEXT NOT NULL, entity TEXT NOT NULL, entries TEXT NOT NULL, created TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES jobs(id));
  """);self.db.commit()
 def _job(self,jid):
  r=self.db.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
  if not r: raise GateError('Unknown job')
  return dict(r)
 def _event(self,jid,action,actor,key,payload):
  existing=self.db.execute('SELECT * FROM events WHERE key=?',(key,)).fetchone()
  if existing:
   if (existing['job_id'], existing['action'], existing['actor'], existing['payload']) != (jid,action,actor,canon(payload)):
    raise GateError('Idempotency key reused with different operation')
   return dict(existing)
  previous=self.db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
  ph=previous['hash'] if previous else 'GENESIS'
  data=dict(job_id=jid,action=action,actor=actor,key=key,payload=payload,prev_hash=ph)
  digest=hashlib.sha256(canon(data).encode()).hexdigest()
  self.db.execute('INSERT INTO events(job_id,action,actor,key,payload,prev_hash,hash,at) VALUES (?,?,?,?,?,?,?,?)',(jid,action,actor,key,canon(payload),ph,digest,now()))
  return dict(data,hash=digest)
 def create(self,title,domain="COMMERCIAL",leader="L4",agent="SW-02",evidence=None,jid=None):
  if domain not in DOMAINS or leader not in LEADERS or agent not in AGENTS: raise GateError('Unrecognized domain/assignment')
  jid=jid or str(uuid.uuid4())
  with self.db:
   self.db.execute('INSERT INTO jobs(id,domain,title,state,leader,agent,evidence,created) VALUES (?,?,?,?,?,?,?,?)',(jid,domain,title,'DRAFT',leader,agent,canon(evidence or []),now()))
   self._event(jid,'CREATE','SW-00',jid+':create',{'domain':domain,'title':title,'leader':leader,'agent':agent})
  return jid
 def transition(self,jid,target,actor,evidence=None,reviewer=None,approval_token=None,key=None):
  j=self._job(jid);key=key or jid+':'+target
  prior=self.db.execute('SELECT * FROM events WHERE key=?',(key,)).fetchone()
  if prior: return self._event(jid,prior['action'],prior['actor'],key,json.loads(prior['payload']))
  if NEXT.get(j['state'])!=target: raise GateError(f"Illegal transition {j['state']} -> {target}")
  if actor not in AGENTS and actor!='FOUNDER':raise GateError('Unknown actor')
  ev=evidence or []
  if target in ('EVIDENCE_REVIEW','UNDERWRITTEN') and not ev:raise GateError('Required source/model evidence')
  if target=='AUDIT_PASSED':
   if actor!='SW-13' or reviewer not in (None,'SW-13') or not ev:raise GateError('Independent SW-13 audit evidence required')
  elif target=='APPROVAL_REQUIRED' and actor!='SW-00':raise GateError('Only orchestrator can queue founder approval')
  elif target=='APPROVED':
   if actor!='FOUNDER' or not approval_token:raise GateError('Founder approval token required')
  elif target in ('DELIVERED_SIMULATED','INVOICED_SIMULATED','SETTLED_SIMULATED','RECONCILED_SIMULATED'):
   if not ev:raise GateError('Simulation evidence required')
   if target=='SETTLED_SIMULATED' and actor!='SW-10':raise GateError('Only finance may record simulated settlement')
   if target=='RECONCILED_SIMULATED' and actor!='SW-13':raise GateError('Independent audit must reconcile')
  payload={'from':j['state'],'to':target,'evidence':ev,'simulation':True}
  if target=='APPROVED':payload['approval_token_hash']=hashlib.sha256(approval_token.encode()).hexdigest()
  with self.db:
   self.db.execute('UPDATE jobs SET state=?, audit_by=COALESCE(?,audit_by), approved_by=COALESCE(?,approved_by) WHERE id=?',(target,'SW-13' if target=='AUDIT_PASSED' else None,'FOUNDER' if target=='APPROVED' else None,jid))
   out=self._event(jid,'TRANSITION',actor,key,payload)
  return out
 def journal(self,jid,entity,entries,actor='SW-10',key=None):
  j=self._job(jid)
  if j['state'] not in ('SETTLED_SIMULATED','RECONCILED_SIMULATED'):raise GateError('No simulated settlement evidence')
  if actor!='SW-10':raise GateError('Controller owns simulated journal posting')
  if entity in ('',None) or not entries:raise GateError('Entity and entries required')
  if any(set(e)!={'account','debit','credit'} or e['debit']<0 or e['credit']<0 for e in entries):raise GateError('Invalid journal line')
  deb=round(sum(e['debit'] for e in entries),2);cred=round(sum(e['credit'] for e in entries),2)
  if deb!=cred:raise GateError('Unbalanced journal')
  key=key or jid+':journal:'+entity
  with self.db:
   prior=self.db.execute('SELECT * FROM journals WHERE id=?',(key,)).fetchone()
   if prior:
    if prior['entries']!=canon(entries) or prior['entity']!=entity:raise GateError('Journal key collision')
    return key
   self.db.execute('INSERT INTO journals(id,job_id,entity,entries,created) VALUES (?,?,?,?,?)',(key,jid,entity,canon(entries),now()))
   self._event(jid,'BALANCED_JOURNAL','SW-10',key+':event',{'entity':entity,'debits':deb,'credits':cred,'simulation':True})
  return key
 def report(self,jid):
  j=self._job(jid)
  return {'job':j,'events':[dict(r) for r in self.db.execute('SELECT * FROM events WHERE job_id=? ORDER BY seq',(jid,))],'journals':[dict(r) for r in self.db.execute('SELECT * FROM journals WHERE job_id=?',(jid,))]}
 def verify_log(self):
  prev='GENESIS'
  for e in self.db.execute('SELECT * FROM events ORDER BY seq'):
   d=dict(job_id=e['job_id'],action=e['action'],actor=e['actor'],key=e['key'],payload=json.loads(e['payload']),prev_hash=e['prev_hash'])
   if e['prev_hash']!=prev or hashlib.sha256(canon(d).encode()).hexdigest()!=e['hash']:return False
   prev=e['hash']
  return True
