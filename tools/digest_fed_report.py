"""Offline source-index and draft skill crosswalk; no approved Academy promotion."""
import json, csv, hashlib, re
from pathlib import Path
from collections import Counter
from tools.audit_book_corpus import index_pdf

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'docs/intelligence-flow/fed-2025/2025-annual-report.pdf'
OUT=ROOT/'docs/intelligence-flow/fed-2025/academy-digest'
SEEDS=ROOT/'site_academy/fed-2025-skill-seeds.tsv'

def section(p):
    for end, name in [(6,'Front matter'),(8,'1 Overview'),(16,'2 Monetary policy'),(24,'3 Financial stability'),(44,'4 Supervision'),(72,'5 Payments and oversight'),(90,'6 Consumer and community'),(130,'A Organization'),(132,'B FOMC minutes'),(136,'C Audits'),(156,'D Budgets'),(164,'E Policy actions'),(170,'F Litigation'),(202,'G Statistical tables'),(204,'Back matter')]:
        if p<=end:return name
    raise ValueError('page outside report')

def disposition(p,text):
    s=section(p); t=text.strip()
    if not t:return 'WHITESPACE'
    if s in ('Front matter','Back matter'):return 'REFERENCE_OR_FRONT_MATTER'
    if s.startswith('G '):return 'TABLE_OR_NOTE_REQUIRES_CELL_VALIDATION'
    if s.startswith('A '):return 'INSTITUTIONAL_DIRECTORY_OR_GOVERNANCE'
    if s.startswith('B '):return 'DATED_POLICY_SOURCE_OR_REFERENCE'
    if s.startswith('F '):return 'HISTORICAL_LITIGATION_CHECK_CURRENT_STATUS'
    if s.startswith('E '):return 'DATED_POLICY_ACTION_CHECK_CURRENT_STATUS'
    if re.match(r'^(Table|Figure|Note:|Source:|\d+\s+See\b)',t):return 'VISUAL_OR_REFERENCE_REVIEW'
    if re.search(r'\b(202[0-6]|percent|billion|million|basis points)\b',t,re.I):return 'DATED_OBSERVATION_OR_NUMERICAL_CLAIM'
    if re.search(r'\b(proposed|rule|statutory|regulation|requirement|law)\b',t,re.I):return 'POLICY_OR_APPLICABILITY_REVIEW'
    return 'METHOD_OR_CONTEXT_CANDIDATE'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    summary=index_pdf(SOURCE,OUT)
    source_dir=OUT/summary['source_id']; manifest=json.loads((source_dir/'manifest.json').read_text())
    tickets={t['id'] for t in json.loads((ROOT/'docs/session-tickets.json').read_text())}
    cards=[]
    for i,row in enumerate(csv.reader(SEEDS.open(),delimiter='\t'),1):
        a,b,title,method,output,ticket=row; a,b=int(a)+6,int(b)+6; tid='BR-T'+ticket
        assert tid in tickets and 7<=a<=b<=202
        cards.append({'id':f'FED25-S{i:03d}','title':title,'source_id':summary['source_id'],'source_sha256':summary['source_sha256'],'pdf_pages':[a,b],'printed_pages':[a-6,b-6],'method_adaptation':method,'practice_deliverable':output,'ticket_ids':[tid,'BR-T124','BR-T127'],'status':'DRAFT_SOURCE_REVIEW','review_owner':'SW-13','authority':'NONE','training_label_eligible':False,'limitations':'Black River adaptation; review cited source passages, current applicability and domain inputs before operational use.'})
    cnt=Counter(); sections=Counter(); mapped=0; pages=Counter()
    with (source_dir/'units.jsonl').open() as src,(OUT/'unit-dispositions.jsonl').open('w') as dst:
        for line in src:
            u=json.loads(line); p=u['pdf_page']; kind=disposition(p,u['text']); links=[c['id'] for c in cards if c['pdf_pages'][0]<=p<=c['pdf_pages'][1]]
            cnt[kind]+=1; sections[section(p)]+=1; pages[p]+=1; mapped+=bool(links)
            dst.write(json.dumps({'unit_id':u['unit_id'],'pdf_page':p,'text_sha256':u['text_sha256'],'section':section(p),'provisional_disposition':kind,'page_level_skill_candidates':links,'status':'AUTOMATED_TRIAGE_NOT_INDIVIDUALLY_REVIEWED','training_label_eligible':False})+'\n')
    assert sum(cnt.values())==summary['candidate_units']
    assert all(pages[x['pdf_page']]==x['unit_count'] for x in manifest['pages'])
    catalog={'schema_version':1,'source':summary,'status':'DRAFT_ONLY','skill_count':len(cards),'accepted_count':0,'skills':cards,'unit_triage_counts':dict(cnt),'section_unit_counts':dict(sections),'units_with_page_level_skill_links':mapped,'note':'Page range links are routing candidates, not sentence-level semantic endorsements. No current-rate, lending or investment authority.'}
    (ROOT/'site_academy/fed-2025-skill-candidates.json').write_text(json.dumps(catalog,indent=2)+'\n')
    print(json.dumps({k:v for k,v in catalog.items() if k!='skills'},indent=2))
if __name__=='__main__':main()
