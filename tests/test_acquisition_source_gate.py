import pytest
from backend.core.acquisition_source_gate import route, audit_routes, Purpose

@pytest.mark.parametrize('source',['DEWEY_ACADEMIC','UF_LIBRARY_LICENSED'])
def test_academic_data_cannot_transfer(source):
    for p in (Purpose.COMMERCIAL_RESEARCH,Purpose.COMMERCIAL_TRAINING,Purpose.OUTREACH):
        assert route(source,p)['disposition']=='DENY'
    assert route(source,Purpose.ACADEMIC_RESEARCH)['disposition']=='HOLD'


def test_public_and_missing_are_not_grants():
    for source in ['FDOR','COUNTY_GIS','SUNBIZ','FGDL_PARCELS','COMMERCIAL_VENDOR','NOT_REGISTERED']:
        r=route(source,Purpose.COMMERCIAL_RESEARCH)
        assert r['disposition']=='HOLD' and not r['data_release_authorized']
    with pytest.raises(ValueError): route('FDOR','AUTO_APPROVE')


def test_all_routes_fail_closed_and_sensitive_channels_excluded():
    result=audit_routes()
    assert len(result['rows'])==result['sources']*4
    assert all(not r['data_release_authorized'] and not r['outreach_authorized'] and not r['training_authorized'] for r in result['rows'])
    for source in ['UTILITY_CUSTOMER','PERSONAL_HARDSHIP']:
        assert route(source,Purpose.COMMERCIAL_RESEARCH)['disposition']=='DENY'
