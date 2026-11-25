from datetime import datetime,timedelta,timezone
import pytest
from backend.core.ontology import Ontology,OntologyError

def setup():
 o=Ontology();p=o.register('Property','COMMERCIAL','Synthetic Parcel');return o,p

def test_evidence_does_not_create_legal_ownership():
 o,p=setup();e=o.attach_evidence(p,'COMMERCIAL','synthetic:assessor','assessment','2026-11-18','owner name')
 s=o.status(p,'COMMERCIAL','owner','Test LLC','Florida property records','County Appraiser',e)
 assert o.dashboard('COMMERCIAL')['verified_statuses']==0
 assert o.dashboard('COMMERCIAL')['open_assertions']==1

def test_independent_verification():
 o,p=setup();e=o.attach_evidence(p,'COMMERCIAL','synthetic:deed','deed','2026-11-18','signed paper');s=o.status(p,'COMMERCIAL','title_holder','Test LLC','recording jurisdiction','county clerk',e)
 with pytest.raises(OntologyError):o.verify(s,'COMMERCIAL','SW-02','VERIFIED')
 with pytest.raises(OntologyError):o.verify(s,'COMMERCIAL','SW-13','VERIFIED',e)
 e2=o.attach_evidence(p,'COMMERCIAL','synthetic:clerk','indexed record','2026-11-18','recorded entry')
 o.verify(s,'COMMERCIAL','SW-13','VERIFIED',e2)
 assert o.dashboard('COMMERCIAL')['verified_statuses']==1

def test_cross_domain_block():
 o,p=setup()
 with pytest.raises(OntologyError):o.attach_evidence(p,'FAMILY_OFFICE','x','doc','2026-11-18','content')
 private=o.register('Account','FAMILY_OFFICE','Personal account')
 with pytest.raises(OntologyError):o.relate(p,private,'RELATES_TO','COMMERCIAL')

def test_owner_link_requires_evidence():
 o,p=setup();person=o.register('Person','COMMERCIAL','Counterparty')
 with pytest.raises(OntologyError):o.relate(p,person,'OWNED_BY','COMMERCIAL')
 e=o.attach_evidence(p,'COMMERCIAL','synthetic:county','index','2026-11-18','text')
 assert o.relate(p,person,'OWNED_BY','COMMERCIAL',e)
 assert o.dashboard('COMMERCIAL')['verified_statuses']==0

def test_simulated_action_needs_scoped_founder_authorization():
 o,p=setup();scope={'task':'prototype','max_cash':0}
 with pytest.raises(OntologyError):o.apply(p,'COMMERCIAL','EXECUTE_SIMULATION','SW-07',scope)
 a=o.approve(p,'COMMERCIAL','EXECUTE_SIMULATION',scope,(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())
 with pytest.raises(OntologyError):o.apply(p,'COMMERCIAL','EXECUTE_SIMULATION','SW-07',{'task':'other','max_cash':0},a)
 assert o.apply(p,'COMMERCIAL','EXECUTE_SIMULATION','SW-07',scope,a)

def test_no_real_cash_operations():
 o,p=setup()
 with pytest.raises(OntologyError):o.apply(p,'COMMERCIAL','WIRE_FUNDS','FOUNDER')
