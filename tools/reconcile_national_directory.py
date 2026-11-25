"""Normalize a supplied directory extract; preserve exact-key duplicate/conflict evidence.
Not an authoritative program ID resolver or network scraper. No missing row implies delisting.
"""
import argparse, csv, html, io, json, re, unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from tools.prepare_national_atlas import FIELDS, STATES, DESIGNATIONS, prepare, digest

def norm(s):
    return ' '.join(unicodedata.normalize('NFKC',s).casefold().split())
def key(row):
    return tuple(norm(row[k]) for k in ('name','city','state'))
def parse_markdown(text):
    """Conservative extraction from heading blocks with exactly one locality/status."""
    rows=[]; rejected=[]
    for i,b in enumerate(re.split(r'^### ',text,flags=re.M)[1:],1):
        name=b.splitlines()[0].strip()
        cities=re.findall(r'^\* ([^*\n]+), ([A-Z]{2})[ \t]*$',b,flags=re.M)
        status=re.findall(r'^(Accredited|Affiliate|MSA Partner Program)[ \t]*$',b,flags=re.M)
        if len(cities)!=1 or len(status)!=1:
            rejected.append({'block':i,'name':name,'reason':'ambiguous locality or designation'});continue
        city,state=cities[0]; rows.append(dict(name=name,city=city,state=state,designation='Partner' if status[0]=='MSA Partner Program' else status[0]))
    return rows,rejected

def parse_html(text):
    """Parse publisher location cards without expanding scope from map markers."""
    rows, rejected = [], []
    cards = re.findall(r'<article class="card--location">(.*?)</article>', text, re.S)
    if not cards:
        raise ValueError("No publisher location cards found")
    for index, card in enumerate(cards, 1):
        def plain(fragment):
            return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())

        names = re.findall(r"<h3\b[^>]*>(.*?)</h3>", card, re.S)
        localities = [re.fullmatch(r"(.+), ([A-Z]{2})", plain(item)) for item in re.findall(
            r'<li class="location-list__item">(.*?)</li>', card, re.S)]
        localities = [item for item in localities if item and item[2] in STATES]
        statuses = re.findall(
            r'<span\b[^>]*class="tag[^"]*"[^>]*>\s*(Accredited|Affiliate|MSA Partner Program)\s*</span>',
            card,
        )
        if len(names) != 1 or len(localities) != 1 or len(statuses) != 1 or not plain(names[0]):
            rejected.append({"block": index, "reason": "Ambiguous name, locality or designation"})
            continue
        city, state = localities[0].groups()
        rows.append({"name": plain(names[0]), "city": city, "state": state,
                     "designation": "Partner" if statuses[0] == "MSA Partner Program" else statuses[0]})
    return rows, rejected


def reconcile(rows,old_raw):
    old=list(csv.DictReader(io.StringIO(old_raw.decode('utf-8-sig'))))
    old_keys={key(r):r['program_key'] for r in old}
    groups=defaultdict(list)
    for row in rows:
        if set(row)!={'name','city','state','designation'} or not all(isinstance(v,str) and v.strip() for v in row.values()) or row['state'] not in STATES or row['designation'] not in DESIGNATIONS:
            raise ValueError('invalid source observation')
        groups[key(row)].append(row)
    normalized=[]; duplicates=[]; conflicts=[]
    for k,g in sorted(groups.items()):
        if len(g)>1: duplicates.append({'key':k,'observations':g})
        if len({r['designation'] for r in g})!=1:
            conflicts.append({'key':k,'observations':g});continue
        normalized.append(dict(program_key=old_keys.get(k,'msa:observed:'+digest(json.dumps(k,ensure_ascii=False).encode())[:24]),**g[0]))
    if len({r['program_key'] for r in normalized})!=len(normalized):raise ValueError('local ID collision')
    output=io.StringIO(newline='');w=csv.DictWriter(output,fieldnames=FIELDS);w.writeheader();w.writerows(normalized); raw=output.getvalue().encode()
    return raw,{'raw_count':len(rows),'unique_exact_keys':len(groups),'duplicates':duplicates,'conflicts':conflicts,'normalized_count':len(normalized),'counts':dict(Counter(r['designation'] for r in normalized))}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--previous',type=Path,required=True);p.add_argument('--format',choices=['tsv','markdown','html'],required=True);p.add_argument('--date',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    source=a.input.read_bytes(); old=a.previous.read_bytes(); rejects=[]
    if a.format=='markdown':rows,rejects=parse_markdown(source.decode('utf-8-sig'))
    elif a.format=='html':rows,rejects=parse_html(source.decode('utf-8-sig'))
    else:rows=[dict(zip(('name','city','state','designation'),r,strict=True)) for r in csv.reader(io.StringIO(source.decode('utf-8-sig')),delimiter='\t')]
    raw,report=reconcile(rows,old);result=prepare(raw,source_url='https://mainstreet.org/our-network/main-street-communities',observed_date=a.date,source_sha256=digest(raw),previous_raw=old)
    partners=[r for r in result['records'] if r['designation']=='Partner']; designated=[r for r in result['records'] if r['designation'] in {'Accredited','Affiliate'}];
    for r in partners:r['stages']=r['stages'][:1];r['decision']='PARTNER_SCOPE_REVIEW'
    for r in result['records']:
        if r['designation']=='Unknown':r['stages']=r['stages'][:1];r['decision']='DESIGNATION_REVIEW'
    result.update({'input_sha256':digest(source),'reconciliation':report,'rejected_blocks':rejects,'designated_research_records':len(designated),'partner_records':len(partners),'work_stage_count':sum(len(r['stages']) for r in result['records']),'source_completeness':'EXCERPT_OR_UNVERIFIED_RENDERED_CAPTURE','historical_keys_not_observed_in_this_input_are_not_delisted':True})
    annual = result["official_2026_announcement"]
    result["designated_count_delta_from_annual_announcement"] = {
        tier: report["counts"].get(tier, 0) - annual[tier] for tier in ("Accredited", "Affiliate")
    }
    if a.format == "html":
        result["source_completeness"] = "ALL_LOCATION_CARDS_IN_CAPTURED_HTML"
    a.output.mkdir(parents=True,exist_ok=False);(a.output/'normalized.csv').write_bytes(raw);(a.output/'queue.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
if __name__=='__main__':main()
