"""Offline source reconciliation; requires openpyxl, does not change the catalog."""
import csv,json
from pathlib import Path
from collections import Counter
from openpyxl import load_workbook
from backend.core.strategy_library import CATALOG,load_catalog
from backend.core.acquisition_runs import sha

def audit():
    c=load_catalog();root=CATALOG.parent
    csv_path=next(root.glob('Black_River*.csv'))
    # Explicit original filename, not the derived work package table.
    csv_path=root/'Black_River_Main_Street_83_Strategies.csv'
    with csv_path.open(encoding='utf-8-sig',newline='') as f: original=list(csv.DictReader(f))
    workbook=load_workbook(root/'Black_River_Main_Street_83_Strategies_Workflows.xlsx',read_only=True,data_only=True)
    def rows(sheet):
        vals=list(workbook[sheet].values); header=list(vals[4][1:]); return [dict(zip(header,r[1:])) for r in vals[5:] if len(r)>1 and r[1] is not None]
    try:
        master=rows('01 Master Strategies'); assignments=rows('02 Four Leader Plans'); flywheels=rows('04 Flywheels')
        gates=rows('03 Buy Box Flow'); verification=rows('05 Verification')
    finally:workbook.close()
    assert original==master==[r['source'] for r in c['records']]
    source={(r['ID'],r['Expert leader']):r for r in assignments}
    assert len(source)==len(assignments)==332
    for p in c['work_packages']:
        row=source[(p['strategy_id'],p['source_role'])]
        assert row['Required work']==p['source_work'] and row['Hard diligence gate']==p['gate'] and row['Status']=='Research' and row['Assignee']=='Unassigned'
        assert row['Strategy']==next(r['Strategy'] for r in original if r['ID']==p['strategy_id'])
    assert flywheels==c['flywheels']
    return {'strategy_rows':len(master),'assignment_rows':len(assignments),'flywheels':len(flywheels),'gate_rows':gates,'verification_rows':verification,'source_hashes':c['source_hashes'],'catalog_digest':sha(c),'result':'SOURCE_PARITY_PASSED','independent_review':'PENDING'}
if __name__=='__main__': print(json.dumps(audit(),indent=2,ensure_ascii=False))
