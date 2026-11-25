"""Bounded FDOR 2026 submission-layout probe; NOT an accepted public-roll adapter.
Only explicitly allowlisted non-contact attributes leave the parser. Source counts
are observations, never a legal-use determination or a proof of title.
"""
from __future__ import annotations
import csv
import hashlib
import io
import re
from pathlib import Path

LAYOUT_URL = 'https://floridarevenue.com/property/Documents/2026NALSummaryTable.pdf'
LAYOUT_REVISION = '2026-01-20'
FIELDS = 92
MAX_PROBE_BYTES = 16 * 1024 * 1024


def probe_nal(path: Path, *, expected_sha256: str, encoding: str, county: str, year: int) -> dict:
    """Probe a bounded explicitly supplied artifact, not a production import.

    Input format must be a headerless 92-column CSV matching the reviewed
    submission summary. Public extracts may differ; mismatches are rejected.
    No raw rows, owner/contact identifiers or confidential values in results.
    """
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError('Expected artifact SHA256 required')
    if encoding not in {'utf-8', 'utf-8-sig', 'cp1252'}:
        raise ValueError('Explicit supported encoding required; not inferred')
    if not re.fullmatch(r'[0-9]{2}', county) or not 11 <= int(county) <= 77 or type(year) is not int or year != 2026:
        raise ValueError('Expected 2026 county scope required')
    with path.open('rb') as f:
        data = f.read(MAX_PROBE_BYTES + 1)
    if len(data) > MAX_PROBE_BYTES:
        raise ValueError('Probe input exceeds size limit; not a bulk loader')
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError('Artifact digest mismatch')
    try:
        decoded = data.decode(encoding, errors='strict')
    except UnicodeError:
        raise ValueError('Artifact encoding mismatch') from None
    rows, rejected = [], []
    try:
        reader = csv.reader(io.StringIO(decoded, newline=''), strict=True)
        for index, raw in enumerate(reader, 1):
            def reject(reason):
                rejected.append({'record': index, 'reason': reason})
            if len(raw) != FIELDS:
                reject('FIELD_COUNT'); continue
            def field(n): return raw[n-1].strip()
            # Confidential records and unexpected SSNs are never emitted.
            if field(70) or field(67) or field(69):
                reject('RESTRICTED_OR_UNEXPECTED_SENSITIVE_FIELD'); continue
            if field(1) != county or field(3) != 'R' or field(4) != str(year):
                reject('SCOPE_OR_FILE_TYPE'); continue
            pid = field(2)
            if not pid or len(pid) > 26 or any(ord(c) < 32 for c in pid):
                reject('PARCEL_ID'); continue
            def numeric(n, width):
                v = field(n)
                if not v: return None
                if not re.fullmatch(r'[0-9]{1,' + str(width) + '}', v): raise ValueError()
                return int(v)
            try:
                units = numeric(49, 4)
                buildings = numeric(48, 4)
                land_sqft = numeric(41, 12)
                living_area = numeric(47, 12)
                just_value = numeric(8, 12)
                use = field(5)
                if use and not re.fullmatch(r'[0-9]{1,3}', use): raise ValueError()
            except ValueError:
                reject('INVALID_SELECTED_FIELD'); continue
            rows.append({'record':index,'county':county,'parcel_id':pid,'assessment_year':year,
                         'reported_units':units,'reported_buildings':buildings,'land_sqft':land_sqft,
                         'living_area_sqft':living_area,'reported_just_value':just_value,
                         'dor_use_code_raw':use or None,'legal_units':None,
                         'evidence_state':'SOURCE_REPORTED_UNREVIEWED'})
    except csv.Error:
        raise ValueError('Malformed CSV; no partial probe returned') from None
    return {'mode':'BOUNDED_LAYOUT_PROBE_NOT_ACCEPTED_INGEST','layout_url':LAYOUT_URL,
            'layout_revision':LAYOUT_REVISION,'sha256':digest,'encoding':encoding,
            'county':county,'assessment_year':year,'rows':rows,'rejected':rejected,
            'records_seen':len(rows)+len(rejected),'production_accepted':False}
