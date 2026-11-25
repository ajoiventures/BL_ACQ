"""Read-only strategy research catalog. Does not approve deals or dispatch work."""
from pathlib import Path
from collections import Counter
import hashlib
import csv
import json

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'docs/acquisition/strategy-library/strategy-library.json'
STRATEGY_CSV = 'Black_River_Main_Street_83_Strategies.csv'
WORKFLOW_BOOK = 'Black_River_Main_Street_83_Strategies_Workflows.xlsx'
WORKFLOW_BOOK_SHA256 = 'b268e08212bd0c2d480edf435305bf496255f820087ca68c69364861b1879546'
WORKFLOW_EXTRACT_SHA256 = 'e96983549522a690ae6f5895db74c7c827c5739e13c4373ab0acf92e25873c64'

def load_catalog(path=CATALOG):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if (set(data['source_hashes']) != {STRATEGY_CSV, WORKFLOW_BOOK}
            or data['source_hashes'][WORKFLOW_BOOK] != WORKFLOW_BOOK_SHA256):
        raise ValueError('Strategy source revision manifest mismatch')
    for name, expected in data['source_hashes'].items():
        if Path(name).name != name or hashlib.sha256((path.parent/name).read_bytes()).hexdigest() != expected:
            raise ValueError('Strategy source revision mismatch')
    records = data['records']; tasks = data['work_packages']
    with (path.parent/STRATEGY_CSV).open(encoding='utf-8-sig',newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        if list(reader) != [r['source'] for r in records]:
            raise ValueError('Strategy catalog source rows mismatch')
    ids = [r['source']['ID'] for r in records]
    if ids != [f'SMF-{n:02d}' for n in range(1,84)]:
        raise ValueError('Strategy ID coverage mismatch')
    if Counter(t['strategy_id'] for t in tasks) != Counter({i:4 for i in ids}):
        raise ValueError('Strategy work package coverage mismatch')
    roles={'Acquisition & Negotiation','Finance & Risk','Built Environment & Intelligence','Landlord & Operations'}
    if any({t['source_role'] for t in tasks if t['strategy_id']==i}!=roles for i in ids):
        raise ValueError('Missing or duplicate strategy specialist role')
    if len({t['work_package_id'] for t in tasks}) != len(tasks):
        raise ValueError('Duplicate strategy work package')
    extract = (CATALOG.parent / 'workflow_extract.json').read_bytes()
    if hashlib.sha256(extract).hexdigest() != WORKFLOW_EXTRACT_SHA256:
        raise ValueError('Strategy workflow extract revision mismatch')
    workbook = json.loads(extract)
    workbook_rows = [dict(zip(fields, row[1:], strict=True)) for row in workbook['master']]
    if workbook_rows != [r['source'] for r in records] or workbook['flywheels'] != data['flywheels']:
        raise ValueError('Strategy workbook rows or flywheels mismatch')
    assignments = {(r['ID'], r['Expert leader']): (r['Required work'], r['Hard diligence gate'])
                   for r in workbook['assignments']}
    if assignments != {(t['strategy_id'], t['source_role']): (t['source_work'], t['gate']) for t in tasks}:
        raise ValueError('Strategy workbook assignments mismatch')
    known = {r['id'] for r in json.loads((ROOT/'docs/session-tickets.json').read_text(encoding="utf-8"))}
    if any(set(r['ticket_ids'])-known for r in records+tasks):
        raise ValueError('Unknown ticket reference')
    if any(r['authority']!='NONE' or r['eligibility']!='UNKNOWN' or r['legal_verification']!='UNVERIFIED' for r in records):
        raise ValueError('Research catalog must not authorize strategy eligibility')
    if any(t['state']!='RESEARCH_ONLY' for t in tasks):
        raise ValueError('Research work packages must not claim dispatch')
    return data

def prepare_strategy(strategy_id, case_ref):
    """Prepare a named, unverified case research packet, not an eligibility evaluation."""
    if not isinstance(case_ref,str) or not case_ref.strip() or len(case_ref)>200:
        raise ValueError('A bounded case reference is required')
    catalog=load_catalog()
    record=next((r for r in catalog['records'] if r['source']['ID']==strategy_id),None)
    if record is None:
        raise ValueError('Unknown strategy ID')
    packet={'case_ref':case_ref.strip(),'strategy':record,'work_packages':[t for t in catalog['work_packages'] if t['strategy_id']==strategy_id], 'source_hashes':catalog['source_hashes'],'eligibility':'UNKNOWN','status':'PREPARATION_ONLY','dispatch_performed':False,'external_authority':False,'financial_authority':False}
    packet['packet_sha256']=hashlib.sha256(json.dumps(packet,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    return packet
