import pytest
from backend.core.swarm import Swarm,GateError

def begin():
 s=Swarm();j=s.create('Synthetic Main Street intelligence sale',evidence=['public-source:sample'])
 return s,j

def approved():
 s,j=begin()
 s.transition(j,'EVIDENCE_REVIEW','SW-02',['synthetic:market research'])
 s.transition(j,'UNDERWRITTEN','SW-05',['synthetic:cost model'])
 s.transition(j,'AUDIT_PASSED','SW-13',['synthetic:auditor checks'])
 s.transition(j,'APPROVAL_REQUIRED','SW-00')
 s.transition(j,'APPROVED','FOUNDER',approval_token='test-only-approval')
 return s,j

def test_full_simulated_cycle():
 s,j=approved()
 for state,actor in [('DELIVERED_SIMULATED','SW-07'),('INVOICED_SIMULATED','SW-10'),('SETTLED_SIMULATED','SW-10')]:s.transition(j,state,actor,['synthetic:'+state])
 s.journal(j,'BR Operations',[{'account':'Cash','debit':100,'credit':0},{'account':'Service revenue','debit':0,'credit':100}])
 s.transition(j,'RECONCILED_SIMULATED','SW-13',['synthetic:finance-reviewed'])
 assert s.report(j)['job']['state']=='RECONCILED_SIMULATED'
 assert s.verify_log()

def test_no_unauthorized_approval():
 s,j=begin()
 with pytest.raises(GateError):s.transition(j,'APPROVED','SW-07',approval_token='fake')

def test_no_missing_evidence():
 s,j=begin()
 with pytest.raises(GateError):s.transition(j,'EVIDENCE_REVIEW','SW-02')

def test_no_auditor_self_approval():
 s,j=begin();s.transition(j,'EVIDENCE_REVIEW','SW-02',['source']);s.transition(j,'UNDERWRITTEN','SW-05',['model'])
 with pytest.raises(GateError):s.transition(j,'AUDIT_PASSED','SW-05',['fake'])

def test_no_domain_confusion():
 s,j=begin()
 with pytest.raises(GateError):s.create('Private file leaked',domain='OPEN_ACCESS')

def test_no_unbalanced_journal():
 s,j=approved()
 for st,actor in [('DELIVERED_SIMULATED','SW-07'),('INVOICED_SIMULATED','SW-10'),('SETTLED_SIMULATED','SW-10')]:s.transition(j,st,actor,['synthetic'])
 with pytest.raises(GateError):s.journal(j,'BR Operations',[{'account':'Cash','debit':100,'credit':0},{'account':'Revenue','debit':0,'credit':90}])

def test_idempotent_transition():
 s,j=begin();first=s.transition(j,'EVIDENCE_REVIEW','SW-02',['source']);second=s.transition(j,'EVIDENCE_REVIEW','SW-02',['source']);assert first['hash']==second['hash']

def test_approval_missing_token():
 s,j=approved();s2,j2=begin()
 for st,act,ev in [('EVIDENCE_REVIEW','SW-02',['src']),('UNDERWRITTEN','SW-05',['model']),('AUDIT_PASSED','SW-13',['audit']),('APPROVAL_REQUIRED','SW-00',[])]:s2.transition(j2,st,act,ev)
 with pytest.raises(GateError):s2.transition(j2,'APPROVED','FOUNDER')

def test_hash_chain_detects_tamper():
 s,j=begin();assert s.verify_log();s.db.execute("UPDATE events SET actor='BAD' WHERE seq=1");assert not s.verify_log()

def test_no_settlement_without_delivery():
 s,j=approved()
 with pytest.raises(GateError):s.transition(j,'SETTLED_SIMULATED','SW-10',['synthetic'])

def test_no_real_world_functions():
 s,j=begin();assert s._job(j)['simulation']==1
 assert all('send' not in n and 'wire' not in n for n in dir(s))

def test_journal_rejects_other_entity_actor():
 s,j=approved()
 for st,act in [('DELIVERED_SIMULATED','SW-07'),('INVOICED_SIMULATED','SW-10'),('SETTLED_SIMULATED','SW-10')]:s.transition(j,st,act,['synthetic'])
 with pytest.raises(GateError):s.journal(j,'BR Operations',[{'account':'cash','debit':10,'credit':0},{'account':'revenue','debit':0,'credit':10}],actor='SW-02')
