"""Read-only national roster observation and bounded district work-queue preparation.
Keys are locally assigned research references, not publisher IDs or verified district IDs.
No designation changes, spatial membership or capital eligibility inferred from absence.
"""
import argparse, csv, hashlib, io, json, re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
FIELDS=['program_key','name','city','state','designation']
STAGES=[('roster_identity','BR-T138','SW-02'),('boundary_and_jurisdiction','BR-T120','SW-01'),('adopted_plans_and_permissions','BR-T023','SW-03'),('parcel_source_and_legal_units','BR-T049','SW-01'),('corridor_market_baseline','BR-T097','SW-04'),('transportation_policy_access','BR-T139','SW-01'),('lagro_site_inventory_synthesis','BR-T112','SW-01'),('site_derived_strategy_discovery','BR-T135','SW-04'),('preliminary_feasibility','BR-T054','SW-05'),('concept_and_quantities','BR-T055','SW-08'),('investment_comparison','BR-T136','SW-05'),('independent_acceptance','BR-T072','SW-13')]
DESIGNATIONS={'Accredited','Affiliate','Partner','Unknown'}
STATES=set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY AS GU MP PR VI'.split())
def digest(raw): return hashlib.sha256(raw).hexdigest()
def prepare(raw,*,source_url,observed_date,source_sha256,previous_raw=None):
    if digest(raw)!=source_sha256: raise ValueError('source digest mismatch')
    if not source_url.startswith('https://') or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',observed_date): raise ValueError('source metadata required')
    def parse(data):
        r=csv.DictReader(io.StringIO(data.decode('utf-8-sig')),strict=True)
        if r.fieldnames!=FIELDS: raise ValueError('unexpected roster schema')
        out={}
        for row in r:
            if None in row or any(not isinstance(row[k],str) or not row[k].strip() for k in FIELDS): raise ValueError('missing roster fields')
            key=row['program_key']
            if not re.fullmatch(r'[a-z0-9][a-z0-9:_-]{1,160}',key) or key in out: raise ValueError('invalid or duplicate local key')
            if row['state'] not in STATES or row['designation'] not in DESIGNATIONS: raise ValueError('invalid jurisdiction or designation')
            out[key]=row
        return out
    rows=parse(raw); old=parse(previous_raw) if previous_raw is not None else {}
    return {'mode':'RESEARCH_QUEUE_ONLY','source_url':source_url,'observed_date':observed_date,'normalized_excerpt_sha256':source_sha256,'publisher_roster_complete':False,'official_2026_announcement':{'total':1291,'Accredited':838,'Affiliate':453,'as_of':'2026-05-06','url':'https://mainstreet.org/the-latest/news/main-spotlight-celebrating-1291-nationally-designated-main-street-programs-in-2026'},'observed_program_records':len(rows),'designation_counts':dict(Counter(r['designation'] for r in rows.values())), 'added_keys':sorted(rows.keys()-old.keys()),'changed_keys':sorted(k for k in rows.keys()&old.keys() if rows[k]!=old[k]),'not_observed_keys':sorted(old.keys()-rows.keys()),'removal_inferred':False,'accepted_district_boundaries':0,'offer_ready':0,'records':[dict(r,identity_state='PROVISIONAL_LOCAL_KEY',district_ids=[],decision=('HOLD' if r['designation'] in {'Accredited','Affiliate'} else 'PARTNER_SCOPE_REVIEW' if r['designation']=='Partner' else 'DESIGNATION_REVIEW'),stages=[{'stage':s,'ticket_id':t,'owner':o,'status':'PREPARE' if i==0 else 'WAITING_FOR_INPUTS','depends_on':STAGES[i-1][0] if i else None} for i,(s,t,o) in enumerate(STAGES if r['designation'] in {'Accredited','Affiliate'} else STAGES[:1])]) for k,r in sorted(rows.items())]}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--source-url',required=True);p.add_argument('--observed-date',required=True);p.add_argument('--previous',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=prepare(a.input.read_bytes(),source_url=a.source_url,observed_date=a.observed_date,source_sha256=a.sha256,previous_raw=a.previous.read_bytes() if a.previous else None)
    with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2,ensure_ascii=False);f.write('\n')
if __name__=='__main__':main()
