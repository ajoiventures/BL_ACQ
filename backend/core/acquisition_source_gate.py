"""Bounded source routing reference; no license, title or outreach authorization.
Only source metadata is routed here. All real artifact imports require separate
rights, schema, provenance and domain review in the normal evidence workflow.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from enum import Enum

class Purpose(str, Enum):
    ACADEMIC_RESEARCH = 'ACADEMIC_RESEARCH'
    COMMERCIAL_RESEARCH = 'COMMERCIAL_RESEARCH'
    COMMERCIAL_TRAINING = 'COMMERCIAL_TRAINING'
    OUTREACH = 'OUTREACH'

@dataclass(frozen=True)
class Source:
    key: str
    policy: str
    url: str | None
    scope: str

# Source page findings, not an import whitelist or proof of license rights.
SOURCES = (
    Source('FDOR','PUBLIC_REVIEW','https://floridarevenue.com/property/Pages/DataPortal_RequestAssessmentRollGISData.aspx','Assessment rolls and parcel source discovery'),
    Source('COUNTY_GIS','PUBLIC_REVIEW','https://vgispublic.ocpafl.org/server/rest/services/DynamicForJs/PARCEL/MapServer/4','County parcel geometry and non-contact attributes'),
    Source('FGDL_PARCELS','RETIRED_ROUTE','https://www.geoplan.ufl.edu/parcel-layers-removed-from-fgdl-per-state-request/','Removed standardized parcel layers; use official state replacement'),
    Source('SHIMBERG_RENT','PUBLIC_REVIEW','https://flhousingdata.shimberg.ufl.edu/market-rent-trackers/results','Aggregate market rent indicators; underlying provider terms apply'),
    Source('SHIMBERG_COURTS','PUBLIC_REVIEW','https://flhousingdata.shimberg.ufl.edu/eviction-foreclosure/results','Aggregate filing statistics, not parcel-level dockets'),
    Source('SUNBIZ','PUBLIC_REVIEW','https://dos.fl.gov/sunbiz/other-services/data-downloads/','Entity registration metadata; no officer-to-owner inference'),
    Source('FL_TAX_DEED','PUBLIC_REVIEW','https://www.flsenate.gov/Laws/Statutes/2026/197.502','Statutory due diligence and public auction research'),
    Source('DEWEY_ACADEMIC','ACADEMIC_ONLY','https://docs.deweydata.io/article/subscription-terms','Academic datasets including provider-specific terms; no commercial transfer'),
    Source('UF_LIBRARY_LICENSED','ACADEMIC_ONLY','https://uflib.ufl.edu/about/user-policies/terms-of-use/','Licensed databases, bulk and AI restrictions; separate clearance needed'),
    Source('COMMERCIAL_VENDOR','UNVERIFIED_LICENSE',None,'Placeholder category only; obtain distinct commercial contract'),
    Source('UTILITY_CUSTOMER','EXCLUDED','https://www.flsenate.gov/Laws/Statutes/2025/119.0713','Customer-level usage and shutoff information excluded from acquisition scoring'),
    Source('PERSONAL_HARDSHIP','EXCLUDED',None,'No age, bereavement, private contact or hardship targeting'),
)

def route(source_key: str, purpose: Purpose | str) -> dict:
    """Return only a metadata preparation disposition. Never release data."""
    purpose = Purpose(purpose)
    source = next((s for s in SOURCES if s.key == source_key), None)
    if purpose is Purpose.OUTREACH:
        state, reason = 'DENY', 'Separate authorized outreach process; no source grants contact authority'
    elif source is None:
        state, reason = 'HOLD', 'Unknown source; rights and provenance unresolved'
    elif source.policy == 'EXCLUDED':
        state, reason = 'DENY', 'Excluded from this acquisition preparation workflow'
    elif source.policy == 'RETIRED_ROUTE':
        state, reason = 'HOLD', 'Retired route; discover authoritative replacement'
    elif source.policy == 'ACADEMIC_ONLY':
        state, reason = ('HOLD','Academic environment only; verify institution and dataset terms before access') if purpose is Purpose.ACADEMIC_RESEARCH else ('DENY','Academic access does not authorize commercial use or model training')
    else:
        state, reason = 'HOLD', 'Verify artifact-level license, source schema, coverage, vintage and permitted use before ingestion'
    return {'source_key':source_key,'purpose':purpose.value,'disposition':state,'reason':reason,'source_url':source.url if source else None,'data_release_authorized':False,'outreach_authorized':False,'training_authorized':False}


def audit_routes() -> dict:
    rows = [route(s.key,p) for s in SOURCES for p in Purpose]
    return {'contract':'br-acquisition-source-routing/1','mode':'METADATA_ONLY','rows':rows,'counts':dict(Counter(r['disposition'] for r in rows)),'sources':len(SOURCES),'data_releases':0}
