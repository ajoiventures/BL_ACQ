"""Black River operational ontology, inspired by object/link/action patterns.
Independent, offline proof of status-function rules. Not a Palantir Foundry deployment.
"""
from __future__ import annotations
import sqlite3, json, uuid, hashlib
from datetime import datetime, timezone

OBJECT_TYPES={"Person","Organization","LegalEntity","Property","Parcel","Business","Account","Contract","Invoice","Payment","Opportunity","Deal","Job","Skill","Agent","Evidence","Model","Approval","Obligation","Permit","Asset","Customer","Project"}
DOMAINS={"COMMERCIAL","FAMILY_OFFICE","MAIN_STREET_INSTITUTIONAL"}
STATES={"UNVERIFIED","EVIDENCE_FOUND","VERIFIED","CONTRADICTED","EXPIRED","SUPERSEDED","DISPUTED"}
LINK_TYPES={"OWNED_BY","LOCATED_IN","SOURCED_FROM","EVIDENCED_BY","AUTHORIZES","OBLIGATES","ASSIGNED_TO","FUNDED_BY","BILLED_TO","PAID_BY","UNDERWRITTEN_BY","DEPENDS_ON","GOVERNED_BY","RELATES_TO"}
ACTIONS={"REGISTER_EVIDENCE","ASSERT_STATUS","VERIFY_STATUS","DISPUTE_STATUS","LINK_OBJECTS","AUTHORIZE_ACTION","EXECUTE_SIMULATION"}
class OntologyError(ValueError):pass

def stamp(): return datetime.now(timezone.utc).isoformat()
def pack(x): return json.dumps(x,sort_keys=True,separators=(',',':'))

class Ontology:
 def __init__(self,path=":memory:"):
  self.db=sqlite3.connect(str(path)); self.db.row_factory=sqlite3.Row
  self.db.executescript("""
  PRAGMA foreign_keys=ON;
  CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,type TEXT NOT NULL,domain TEXT NOT NULL,title TEXT NOT NULL,properties TEXT NOT NULL,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS links(id TEXT PRIMARY KEY,src TEXT NOT NULL,dst TEXT NOT NULL,type TEXT NOT NULL,domain TEXT NOT NULL,source_id TEXT,created_at TEXT NOT NULL,FOREIGN KEY(src) REFERENCES objects(id),FOREIGN KEY(dst) REFERENCES objects(id));
  CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,object_id TEXT NOT NULL,source_uri TEXT NOT NULL,kind TEXT NOT NULL,source_date TEXT NOT NULL,content_hash TEXT NOT NULL,domain TEXT NOT NULL,recorded_at TEXT NOT NULL,FOREIGN KEY(object_id) REFERENCES objects(id));
  CREATE TABLE IF NOT EXISTS statuses(id TEXT PRIMARY KEY,subject_id TEXT NOT NULL,predicate TEXT NOT NULL,value TEXT NOT NULL,context TEXT NOT NULL,authority TEXT NOT NULL,rights TEXT NOT NULL,obligations TEXT NOT NULL,prohibitions TEXT NOT NULL,effective_at TEXT NOT NULL,expires_at TEXT,verification TEXT NOT NULL,source_evidence TEXT NOT NULL,verified_by TEXT,created_at TEXT NOT NULL,FOREIGN KEY(subject_id) REFERENCES objects(id),FOREIGN KEY(source_evidence) REFERENCES evidence(id));
  CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,kind TEXT NOT NULL,object_id TEXT NOT NULL,actor TEXT NOT NULL,domain TEXT NOT NULL,parameters TEXT NOT NULL,approval_id TEXT,state TEXT NOT NULL,recorded_at TEXT NOT NULL,FOREIGN KEY(object_id) REFERENCES objects(id));
  CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY,object_id TEXT NOT NULL,action_kind TEXT NOT NULL,approved_by TEXT NOT NULL,scope TEXT NOT NULL,expires_at TEXT NOT NULL,recorded_at TEXT NOT NULL,FOREIGN KEY(object_id) REFERENCES objects(id));
  """)
  self.db.commit()
 def obj(self,obj_id):
  r=self.db.execute('SELECT * FROM objects WHERE id=?',(obj_id,)).fetchone()
  if not r:raise OntologyError('Unknown object')
  return dict(r)
 def register(self,typ,domain,title,properties=None,oid=None):
  if typ not in OBJECT_TYPES or domain not in DOMAINS:raise OntologyError('Invalid type or domain')
  oid=oid or str(uuid.uuid4())
  with self.db:self.db.execute('INSERT INTO objects VALUES (?,?,?,?,?,?)',(oid,typ,domain,title,pack(properties or {}),stamp()))
  return oid
 def _domain(self,oid,domain):
  if self.obj(oid)['domain']!=domain:raise OntologyError('Cross-domain access denied')
 def attach_evidence(self,oid,domain,source_uri,kind,source_date,content):
  self._domain(oid,domain)
  if not source_uri or not source_date or not content:raise OntologyError('Source, date and content required')
  eid=str(uuid.uuid4())
  with self.db:self.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?)',(eid,oid,source_uri,kind,source_date,hashlib.sha256(content.encode()).hexdigest(),domain,stamp()))
  return eid
 def status(self,oid,domain,predicate,value,context,authority,evidence_id,rights=None,obligations=None,prohibitions=None,effective_at=None,expires_at=None):
  self._domain(oid,domain)
  ev=self.db.execute('SELECT * FROM evidence WHERE id=?',(evidence_id,)).fetchone()
  if not ev or ev['object_id']!=oid or ev['domain']!=domain:raise OntologyError('Object-specific source evidence required')
  if not all([predicate,value,context,authority]):raise OntologyError('X counts as Y only in a named context with asserted authority')
  sid=str(uuid.uuid4())
  with self.db:self.db.execute('INSERT INTO statuses VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,oid,predicate,value,context,authority,pack(rights or []),pack(obligations or []),pack(prohibitions or []),effective_at or stamp(),expires_at,'EVIDENCE_FOUND',evidence_id,None,stamp()))
  return sid
 def verify(self,sid,domain,reviewer,decision,independent_evidence_id=None):
  if decision not in ("VERIFIED","CONTRADICTED","DISPUTED","EXPIRED","SUPERSEDED"):raise OntologyError('Bad review decision')
  row=self.db.execute('SELECT * FROM statuses WHERE id=?',(sid,)).fetchone()
  if not row:raise OntologyError('Unknown assertion')
  self._domain(row['subject_id'],domain)
  if reviewer not in ('SW-13','FOUNDER','QUALIFIED_PROFESSIONAL'):raise OntologyError('Independent or authorized reviewer required')
  if decision=='VERIFIED':
   if not independent_evidence_id:raise OntologyError('Independent evidence required')
   e=self.db.execute('SELECT * FROM evidence WHERE id=?',(independent_evidence_id,)).fetchone()
   if not e or e['object_id']!=row['subject_id'] or e['id']==row['source_evidence']:raise OntologyError('Independent supporting evidence must match subject')
   if e['domain']!=domain:raise OntologyError('Evidence access denied')
   if row['expires_at'] and row['expires_at']<=stamp():raise OntologyError('Assertion already expired')
  with self.db:self.db.execute('UPDATE statuses SET verification=?,verified_by=? WHERE id=?',(decision,reviewer,sid))
 def relate(self,source,dest,kind,domain,evidence_id=None):
  if kind not in LINK_TYPES:raise OntologyError('Unknown relationship')
  self._domain(source,domain);self._domain(dest,domain)
  if kind in ('OWNED_BY','AUTHORIZES','PAID_BY','FUNDED_BY'):
   if not evidence_id:raise OntologyError('Institutionally consequential link requires evidence')
   e=self.db.execute('SELECT * FROM evidence WHERE id=?',(evidence_id,)).fetchone()
   if not e or e['object_id']!=source:raise OntologyError('Relationship evidence mismatch')
  lid=str(uuid.uuid4())
  with self.db:self.db.execute('INSERT INTO links VALUES (?,?,?,?,?,?,?)',(lid,source,dest,kind,domain,evidence_id,stamp()))
  return lid
 def approve(self,oid,domain,action_kind,scope,expires_at,actor='FOUNDER'):
  self._domain(oid,domain)
  if actor!='FOUNDER' or not scope or action_kind not in ACTIONS:raise OntologyError('Only founder may approve scoped actions')
  aid=str(uuid.uuid4())
  with self.db:self.db.execute('INSERT INTO approvals VALUES (?,?,?,?,?,?,?)',(aid,oid,action_kind,actor,pack(scope),expires_at,stamp()))
  return aid
 def apply(self,oid,domain,kind,actor,parameters=None,approval_id=None):
  self._domain(oid,domain)
  if kind not in ACTIONS:raise OntologyError('Unknown action')
  if actor not in ('SW-00','SW-01','SW-02','SW-03','SW-04','SW-05','SW-07','SW-10','SW-13','FOUNDER'):raise OntologyError('Unknown agent')
  # Intentional: no real-world external connectors or irreversible effects.
  if kind in ('AUTHORIZE_ACTION','EXECUTE_SIMULATION'):
   a=self.db.execute('SELECT * FROM approvals WHERE id=?',(approval_id,)).fetchone() if approval_id else None
   if not a or a['object_id']!=oid or a['action_kind']!=kind or a['expires_at']<=stamp():raise OntologyError('Valid scoped founder approval required')
   if pack(parameters or {})!=a['scope']:raise OntologyError('Approved scope mismatch')
  if kind=='VERIFY_STATUS' and actor!='SW-13':raise OntologyError('Independent reviewer required')
  state='SIMULATED' if kind=='EXECUTE_SIMULATION' else 'RECORDED_ONLY'
  action_id=str(uuid.uuid4())
  with self.db:self.db.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?)',(action_id,kind,oid,actor,domain,pack(parameters or {}),approval_id,state,stamp()))
  return action_id
 def dashboard(self,domain):
  if domain not in DOMAINS:raise OntologyError('Unknown domain')
  return {'objects':self.db.execute('SELECT count(*) FROM objects WHERE domain=?',(domain,)).fetchone()[0], 'verified_statuses':self.db.execute("SELECT count(*) FROM statuses s JOIN objects o ON o.id=s.subject_id WHERE o.domain=? AND s.verification='VERIFIED'",(domain,)).fetchone()[0], 'open_assertions':self.db.execute("SELECT count(*) FROM statuses s JOIN objects o ON o.id=s.subject_id WHERE o.domain=? AND s.verification IN ('UNVERIFIED','EVIDENCE_FOUND','DISPUTED')",(domain,)).fetchone()[0]}
