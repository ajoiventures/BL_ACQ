import csv,io
from tools.reconcile_national_directory import reconcile,parse_markdown
HEADER=b'program_key,name,city,state,designation\nmsa:old,College Park,Orlando,FL,Accredited\n'
def row(name='College Park',city='Orlando',state='FL',designation='Accredited'):
    return dict(name=name,city=city,state=state,designation=designation)
def test_duplicates_conflicts_and_old_identity():
    raw,r=reconcile([row(),row('COLLEGE PARK'),row(city='Other'),row(city='Other',designation='Affiliate')],HEADER)
    out=list(csv.DictReader(io.StringIO(raw.decode())))
    assert len(out)==1 and out[0]['program_key']=='msa:old'
    assert r['raw_count']==4 and len(r['duplicates'])==2 and len(r['conflicts'])==1

def test_parser_rejects_ambiguous_or_missing():
    rows,rejects=parse_markdown('### A\n* City, FL\nAccredited\n### B\n* City, FL\nAffiliate\nAccredited\n### C\n* City, FL\nMSA Partner Program\n')
    assert [r['designation'] for r in rows]==['Accredited','Partner'] and len(rejects)==1
