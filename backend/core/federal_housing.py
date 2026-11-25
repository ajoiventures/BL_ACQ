"""Bounded FHFA state purchase-only research adapter. Local SQLite snapshot
store, not production authority. Excerpts cannot be published as full releases.
No appraisal, underwriting approval, or training label is produced.
"""
from __future__ import annotations
import calendar
import csv
import hashlib
import io
import re
import sqlite3
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

URL = 'https://www.fhfa.gov/hpi/download/quarterly_datasets/hpi_po_state.txt'
SCHEMA = '''CREATE TABLE IF NOT EXISTS br_hpi_snapshot (
 id TEXT PRIMARY KEY, source_url TEXT NOT NULL, observed_on TEXT NOT NULL,
 release_date TEXT, coverage TEXT NOT NULL CHECK(coverage='EXCERPT'),
 artifact_sha256 TEXT NOT NULL, artifact BLOB NOT NULL, row_count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS br_hpi_state_po (
 snapshot_id TEXT NOT NULL REFERENCES br_hpi_snapshot(id), state TEXT NOT NULL,
 yr INTEGER NOT NULL, qtr INTEGER NOT NULL CHECK(qtr BETWEEN 1 AND 4),
 nsa TEXT NOT NULL, sa TEXT NOT NULL, warning TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,state,yr,qtr));'''

def positive(value):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('positive finite decimal required') from None
    if not d.is_finite() or d <= 0:
        raise ValueError('positive finite decimal required')
    return d

def period(year, qtr):
    if type(year) is not int or type(qtr) is not int or not 1991 <= year <= 2100 or not 1 <= qtr <= 4:
        raise ValueError('valid quarterly period required')
    return year*4+qtr

def import_state_excerpt(db: sqlite3.Connection, data: bytes, *, expected_sha256: str, observed_on: str,
                         source_url: str = URL, parent_sha256: str | None = None):
    """Validate entire input before one atomic insert. No overwrite or latest alias."""
    d = date.fromisoformat(observed_on)
    if d.isoformat() != observed_on or len(data)>2_000_000:
        raise ValueError('invalid observation date or bounded input size')
    digest=hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError('artifact hash mismatch')
    reader=csv.reader(io.StringIO(data.decode('utf-8'),newline=''),delimiter='\t',strict=True)
    header=next(reader,[])
    required=['state','yr','qtr','indx_nsa','indx_sa']
    if header not in (required,required+['warning']):
        raise ValueError('unexpected state HPI layout')
    rows=[]; keys=set()
    for row in reader:
        if len(row) not in (5,6) or len(row)>len(header):
            raise ValueError('invalid row width')
        st,y,q,nsa,sa=row[:5]
        if not re.fullmatch(r'[A-Z]{2}',st):
            raise ValueError('invalid state code')
        y,q=int(y),int(q); period(y,q)
        if date(y,3*q,calendar.monthrange(y,3*q)[1])>d:
            raise ValueError('future observation period')
        k=(st,y,q)
        if k in keys: raise ValueError('duplicate observation')
        keys.add(k); rows.append((*k,str(positive(nsa)),str(positive(sa)),row[5] if len(row)==6 else ''))
    if not rows: raise ValueError('empty snapshot')
    identity = f'{source_url}|EXCERPT|{observed_on}|{digest}'
    if parent_sha256 is not None:
        identity += f"|{parent_sha256}"
    sid=hashlib.sha256(identity.encode()).hexdigest()
    if db.in_transaction:
        raise ValueError("snapshot import requires an idle connection")
    db.executescript(SCHEMA)
    with db:
        prior=db.execute('SELECT row_count,artifact_sha256,artifact FROM br_hpi_snapshot WHERE id=?',(sid,)).fetchone()
        if prior:
            existing=db.execute('SELECT state,yr,qtr,nsa,sa,warning FROM br_hpi_state_po WHERE snapshot_id=?',(sid,)).fetchall()
            if prior!=(len(rows),digest,data) or sorted(existing)!=sorted(rows):
                raise ValueError('snapshot integrity failure')
        else:
            db.execute('INSERT INTO br_hpi_snapshot VALUES (?,?,?,NULL,?,?,?,?)',(sid,source_url,observed_on,'EXCERPT',digest,data,len(rows)))
            db.executemany('INSERT INTO br_hpi_state_po VALUES (?,?,?,?,?,?,?)',[(sid,*r) for r in rows])
    return {'snapshot_id':sid,'rows':len(rows),'artifact_sha256':digest,'coverage':'EXCERPT','observed_on':observed_on,'replay':bool(prior)}

def import_master_state_po(db, data, *, expected_sha256, observed_on, state):
    """Project one traditional quarterly purchase-only state series into the excerpt store."""
    if len(data) > 32_000_000 or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Master HPI input exceeds bounds or has a mismatched hash")
    source = csv.DictReader(io.StringIO(data.decode("utf-8-sig"), newline=""), strict=True)
    if source.fieldnames != [
        "hpi_type", "hpi_flavor", "frequency", "level", "place_name", "place_id",
        "yr", "period", "index_nsa", "index_sa", "rstderr", "note",
    ]:
        raise ValueError("Unexpected master HPI layout")
    subset = io.StringIO(newline="")
    writer = csv.writer(subset, delimiter="\t", lineterminator="\n")
    writer.writerow(["state", "yr", "qtr", "indx_nsa", "indx_sa", "warning"])
    for row in source:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Invalid master HPI row width")
        if (row["hpi_type"], row["hpi_flavor"], row["frequency"], row["level"], row["place_id"]) == (
            "traditional", "purchase-only", "quarterly", "State", state
        ):
            writer.writerow([state, row["yr"], row["period"], row["index_nsa"], row["index_sa"], row["note"]])
    projected = subset.getvalue().encode("utf-8")
    receipt = import_state_excerpt(
        db, projected, expected_sha256=hashlib.sha256(projected).hexdigest(), observed_on=observed_on,
        source_url="https://www.fhfa.gov/hpi/download/monthly/hpi_master.csv",
        parent_sha256=expected_sha256,
    )
    return {**receipt, "master_sha256": expected_sha256, "projection": "TRADITIONAL_STATE_QUARTERLY_PURCHASE_ONLY"}


def value_state_po(db, *, snapshot_id, state, start, end, purchase_price, as_of, adjustment="NSA"):
    """Use one adjustment and one snapshot for both endpoints."""
    columns = {"NSA": "nsa", "SA": "sa"}
    if not isinstance(adjustment, str) or adjustment not in columns:
        raise ValueError("Unknown HPI adjustment")
    column = columns[adjustment]
    p=positive(purchase_price); a,b=period(*start),period(*end)
    if b<a: raise ValueError('reversed period')
    vintage=db.execute('SELECT observed_on,artifact_sha256 FROM br_hpi_snapshot WHERE id=?',(snapshot_id,)).fetchone()
    if not vintage: raise LookupError('unknown snapshot')
    if date.fromisoformat(as_of)<date.fromisoformat(vintage[0]): raise ValueError('look-ahead: snapshot not available')
    def get(t):
        r=db.execute(f'SELECT {column} FROM br_hpi_state_po WHERE snapshot_id=? AND state=? AND yr=? AND qtr=?',(snapshot_id,state,*t)).fetchone()
        if r is None: raise LookupError('requested observation missing; no fallback')
        return positive(r[0])
    x,y=get(start),get(end)
    with localcontext() as ctx:
        ctx.prec=40
        ratio=y/x
        value=(p*ratio).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        cagr=None if a==b else str(((ratio**(Decimal(4)/(b-a))-1)*100).quantize(Decimal('.0001')))
        growth=str(((ratio-1)*100).quantize(Decimal('.0001')))
    return {'snapshot_id':snapshot_id,'source_sha256':vintage[1],'observed_on':vintage[0], 'as_of':as_of,'state':state,'flavor':'purchase-only','frequency':'quarterly','adjustment':adjustment,'coverage':'EXCERPT','start':list(start),'end':list(end),'hpi_start':str(x),'hpi_end':str(y),'assumed_purchase_price':str(p),'index_implied_value':str(value),'appreciation_pct':growth,'cagr_pct':cagr,'appraisal':False,'valuation_band':None,'decision':'RESEARCH_ONLY'}

def compare_reported_growth(all_transactions, purchase_only):
    """Descriptive percentage-point gap; not a ground-truth error estimate."""
    a,b=Decimal(str(all_transactions)),Decimal(str(purchase_only))
    if not a.is_finite() or not b.is_finite() or min(a,b)<=-100: raise ValueError('invalid growth')
    return str(a-b)


def resolve_census_point(payload, *, longitude, latitude):
    """Read the source's covering geography candidates, never guess from ZIP.
    Input is a source response; no claim of official parcel boundary acceptance.
    """
    import math
    if not math.isfinite(longitude) or not math.isfinite(latitude) or not -180<=longitude<=180 or not -90<=latitude<=90:
        raise ValueError('invalid coordinates')
    unknown={'status':'UNKNOWN','county_fips':None,'tract_fips':None,'cbsa':None,'hud_entity':None,'pha':None,'county_candidates':[],'tract_candidates':[]}
    try:
        result=payload['result']; inp=result['input']; geo=result['geographies']
        point=inp['location']
        if (point['x'],point['y'])!=(longitude,latitude): raise ValueError('response coordinate mismatch')
        benchmark=inp['benchmark']; vintage=inp['vintage']
        for obj,key in [(benchmark,'benchmarkName'),(vintage,'vintageName')]:
            if not isinstance(obj['id'],str) or not obj['id'] or not isinstance(obj[key],str) or not obj[key]: raise ValueError('missing geography vintage')
        def codes(layer,width):
            rows=geo.get(layer,[])
            if not isinstance(rows,list): raise ValueError('invalid geography layer')
            ids=[r['GEOID'] for r in rows]
            if any(not isinstance(x,str) or not re.fullmatch(r'[0-9]{'+str(width)+'}',x) for x in ids): raise ValueError('invalid geography ID')
            return sorted(set(ids))
        counties= codes('Counties',5); tracts=codes('Census Tracts',11)
    except (KeyError,TypeError,AttributeError,ValueError):
        return unknown
    out={**unknown,'county_candidates':counties,'tract_candidates':tracts,'benchmark':benchmark,'vintage':vintage,'coordinates':[longitude,latitude]}
    if len(counties)==len(tracts)==1 and tracts[0][:5]==counties[0]:
        out.update(status='CENSUS_POINT_MATCH',county_fips=counties[0],tract_fips=tracts[0])
    elif len(counties)>1 or len(tracts)>1 or (counties and tracts):
        out['status']='AMBIGUOUS_OR_CONFLICT'
    return out


def resolve_retained_census_point(data, *, expected_sha256, observed_on, as_of,
                                  longitude, latitude):
    """Resolve only a bounded retained response available by the requested cutoff."""
    import json

    if not isinstance(data, bytes) or len(data) > 256_000:
        raise ValueError("Invalid Census response size")
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError("Census response digest mismatch")
    observed = date.fromisoformat(observed_on)
    cutoff = date.fromisoformat(as_of)
    if observed.isoformat() != observed_on or cutoff.isoformat() != as_of:
        raise ValueError("Canonical source and cutoff dates are required")
    if observed > cutoff:
        result = resolve_census_point({}, longitude=longitude, latitude=latitude)
        reason = "SOURCE_UNAVAILABLE_AT_CUTOFF"
    else:
        try:
            payload = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid Census response JSON") from exc
        result = resolve_census_point(payload, longitude=longitude, latitude=latitude)
        reason = None
    return {**result, "artifact_sha256": digest, "observed_on": observed_on, "as_of": as_of,
            "hold_reason": reason}


def apply_county_cbsa(point, crosswalk_bytes, *, expected_sha256, observed_on):
    """Attach a verified county crosswalk without changing HUD geography."""
    import json

    if not isinstance(crosswalk_bytes, bytes) or not 0 < len(crosswalk_bytes) <= 32_000:
        raise ValueError("Invalid CBSA crosswalk size")
    digest = hashlib.sha256(crosswalk_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError("CBSA crosswalk digest mismatch")
    observed = date.fromisoformat(observed_on)
    cutoff = date.fromisoformat(point["as_of"])
    if observed.isoformat() != observed_on:
        raise ValueError("Canonical crosswalk observation date required")
    result = {**point, "cbsa": None, "cbsa_crosswalk_sha256": digest}
    if observed > cutoff:
        return {**result, "cbsa_hold_reason": "CROSSWALK_UNAVAILABLE_AT_CUTOFF"}
    crosswalk = json.loads(crosswalk_bytes)
    code = crosswalk.get("cbsa")
    vintage = crosswalk.get("delineation_vintage")
    if (not isinstance(code, str) or not re.fullmatch(r"[0-9]{5}", code)
            or not isinstance(vintage, str) or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", vintage)):
        raise ValueError("Invalid CBSA code or delineation vintage")
    if observed.isoformat()[:7] < vintage:
        raise ValueError("Crosswalk observation precedes delineation vintage")
    if point["status"] != "CENSUS_POINT_MATCH" or point["county_fips"] != crosswalk.get("county_fips"):
        return {**result, "cbsa_hold_reason": "NO_EXACT_COUNTY_MATCH"}
    return {**result, "cbsa": code, "cbsa_delineation_vintage": vintage, "cbsa_hold_reason": None}


def apply_hud_fmr_area(point, receipt_bytes, *, expected_sha256):
    """Resolve area geography for the recorded cutoff's federal fiscal year."""
    import json

    if not isinstance(receipt_bytes, bytes) or not 0 < len(receipt_bytes) <= 32_000:
        raise ValueError("Invalid HUD receipt size")
    digest = hashlib.sha256(receipt_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError("HUD receipt digest mismatch")
    receipt = json.loads(receipt_bytes)
    cutoff = date.fromisoformat(point["as_of"])
    observed = date.fromisoformat(receipt["observed_date"])
    effective = date.fromisoformat(receipt["effective_on"])
    fiscal_year = cutoff.year + (cutoff.month >= 10)
    result = {**point, "hud_entity": None, "hud_fmr_area": None, "hud_fmr_receipt_sha256": digest}
    if observed > cutoff:
        return {**result, "hud_fmr_hold_reason": "SOURCE_UNAVAILABLE_AT_CUTOFF"}
    if receipt["fiscal_year"] != fiscal_year or effective > cutoff:
        return {**result, "hud_fmr_hold_reason": "NO_EFFECTIVE_FISCAL_YEAR_MATCH"}
    if point["status"] != "CENSUS_POINT_MATCH" or point["county_fips"] != receipt["county_fips"]:
        return {**result, "hud_fmr_hold_reason": "NO_EXACT_COUNTY_MATCH"}
    return {**result, "hud_fmr_area": receipt["area_name"], "hud_fmr_fiscal_year": fiscal_year,
            "hud_fmr_hold_reason": None}


def lookup_hud_safmr(geography, receipt_bytes, *, expected_sha256, postal_zip, bedrooms):
    """Look up an explicitly supplied postal ZIP in a pinned HUD schedule."""
    import json

    if not isinstance(postal_zip, str) or not re.fullmatch(r"[0-9]{5}", postal_zip):
        raise ValueError("A five-digit postal ZIP is required")
    if type(bedrooms) is not int or not 0 <= bedrooms <= 4:
        raise ValueError("Bedroom count must be between zero and four")
    if not isinstance(receipt_bytes, bytes) or not 0 < len(receipt_bytes) <= 32_000:
        raise ValueError("Invalid HUD ZIP receipt size")
    digest = hashlib.sha256(receipt_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError("HUD ZIP receipt digest mismatch")
    receipt = json.loads(receipt_bytes)
    result = {"postal_zip": postal_zip, "bedrooms": bedrooms, "safmr_usd": None,
              "receipt_sha256": digest, "pha_payment_standard_usd": None}
    if date.fromisoformat(receipt["observed_date"]) > date.fromisoformat(geography["as_of"]):
        return {**result, "hold_reason": "SOURCE_UNAVAILABLE_AT_CUTOFF"}
    if (receipt["example_postal_zip"] != postal_zip
            or receipt["fiscal_year"] != geography.get("hud_fmr_fiscal_year")
            or receipt["hud_area_name"] != geography.get("hud_fmr_area")):
        return {**result, "hold_reason": "NO_EXACT_ZIP_AREA_YEAR_MATCH"}
    amount = receipt["safmr_usd_by_bedroom"][str(bedrooms)]
    if type(amount) is not int or amount <= 0:
        raise ValueError("Invalid HUD schedule amount")
    return {**result, "safmr_usd": amount, "hold_reason": None}
