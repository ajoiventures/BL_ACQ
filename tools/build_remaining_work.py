"""Derive a complete unfinished-work view from the canonical ticket register.

No ticket state changes, runtime synchronization or worker dispatch occur here.
"""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
from tools.build_acquisition_ticket_plan import validate_graph

ROOT = Path(__file__).resolve().parents[1]


def workstream(ticket):
    n = int(ticket['id'][4:])
    if n in {35,36,39,40,41,90,114,115,123,124,125,126,127}:
        return 'Books, Academy and method application'
    if n in {61,62,63,64,65,66,67}:
        return 'Ives disposition and capital redeployment'
    if n in {27,28,29,30,31,32,33,34,48,49,50,51,52,53,54,58,59,60,72,74,76,79,85,86,116,117,118,119,120,121,122,132}:
        return '2–4 unit acquisition, interface and CUDA'
    if n in {13,21,22,23,25,26,55,80,81,82,83,97,98,99,100,101,102,108,111,112,113,131,138,139}:
        return 'Cities, Main Street and economic development'
    if n in {96,103,104,105,106}:
        return 'Data-center site selection'
    if n in {3,4,5,6,7,8,44,45}:
        return 'Existing property and family-office operations'
    if n in {68,69,70,84,87,88,89,91,92,93,94,95}:
        return 'Specialist acquisition and estate options'
    return 'Shared data, swarm, integration and production'


def main():
    source = ROOT / 'docs/session-tickets.json'
    raw = source.read_bytes()
    tickets = json.loads(raw)
    order = validate_graph(tickets)
    terminal = {'closed'}
    remaining = [t for t in tickets if t['status'] not in terminal]
    required = ['title', 'leader', 'owner', 'acceptance']
    for t in remaining:
        for field in required:
            if not t.get(field):
                raise ValueError(f'{t["id"]} missing {field}')
    by_id = {t['id']: t for t in tickets}
    rows=[]
    for t in remaining:
        wait=[d for d in t['dependencies'] if by_id[d]['status'] not in terminal]
        rows.append({**t, 'workstream':workstream(t),'unfinished_dependency_ids':wait,
                     'priority': t.get('priority') or 'Unassigned',
                     'stage': t.get('stage') or 'Unassigned',
                     'review_owner': t.get('review_owner') or 'Unassigned',
                     'deliverable': t.get('deliverable') or t['title'],
                     'remaining_scope': t.get('remaining_scope') or t['acceptance'],
                     'next_action': t.get('next_action') or 'Verify remaining acceptance criteria.',
                     'readiness':'BLOCKED' if t['status']=='blocked' else 'WAITING_ON_INPUTS' if wait else 'PREPARATION_CANDIDATE',
                     'readiness_note':'Preparation still requires the stated evidence and prerequisite checks.'})
    counts=dict(Counter(t['status'] for t in tickets))
    report={'schema_version':1,'mode':'DERIVED_READ_ONLY_REMAINING_WORK',
            'canonical_source':'docs/session-tickets.json','canonical_sha256':hashlib.sha256(raw).hexdigest(),
            'ticket_count':len(tickets),'remaining_ticket_count':len(remaining),'closed_ticket_count':counts.get('closed',0),'status_counts':counts,
            'local_delivery_ticket_ids':[t['id'] for t in tickets if t['status']=='delivered_local'],
            'all_unfinished_have_contracts':True,'dependency_dag_valid':True,'dependency_order':order,
            'runtime_sync_performed':False,'dispatch_performed':False,'rows':rows,
            'limits':['Only the recovered current register and indexed requests were reconciled; unrelated inaccessible records were not invented.',
                      'Prior local delivery is retained; historical artifacts were not all re-executed in this reconciliation.',
                      'Owner roles are proposed accountability, not a claim of staffing. Dates are observation dates, not deadlines.']}
    out=ROOT/'docs/acquisition'
    (out/'remaining-work.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    fields=['id','workstream','status','priority','stage','leader','owner','review_owner','title','deliverable',
            'dependencies','unfinished_dependency_ids','readiness','next_action','blocker','acceptance','evidence']
    with (out/'remaining-work.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for t in rows:
            writer.writerow({k:'; '.join(t.get(k,[])) if isinstance(t.get(k),list) else t.get(k,'') for k in fields})
    lines=['# Black River — remaining work ticket plan','',
           'This view is generated from the existing canonical ticket register; it does not create a second backlog or change application status.','',
           f'**{len(tickets)} total tickets; {len(remaining)} remaining; {counts.get("closed",0)} closed.** No production deployment or completed transaction is inferred.','',
           '| Status | Tickets |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in counts.items()]
    lines += ['','## Operating order','',
              '1. Keep the Ives evidence package and 2–4-unit buy box active under BR-T061–066 and BR-T076. Verify ownership, lawful units, T12, basis and capital mandate before relying on proceeds or exchange assumptions.',
              '2. Freeze shared data, evidence and Control Center contracts under BR-T048/049/051/056/116. Build one source-backed corridor workflow before expanding inventory.',
              '3. Build CUDA 2–4-unit batches (BR-T122), durable jobs (BR-T118), the operator interface (BR-T119), and map/design exchange (BR-T120). Benchmark actual GPU work under BR-T060; test two million and larger workloads separately under BR-T121.',
              '4. Continue book verification and Academy publication under BR-T114 and BR-T123–127. Integrate methods through existing BR-T057/112, then validate a real case under BR-T041/072.',
              '5. Close production identity, evidence storage and operations readiness under BR-T128–130. Advance specialist economic-development and data-center cases against their own evidence and demand gates.',
              '', 'Use at most three bounded workers plus an integrator. Planning readiness does not grant permission for external communications, filings, transactions or spending.','',
              '## Added deliverables','', '| Ticket | Deliverable | Status |','|---|---|---|']
    lines += [f'| {t["id"]} | {t["title"]} | {t["status"]} |' for t in rows if int(t['id'][4:])>=123]
    for group in dict.fromkeys(t['workstream'] for t in rows):
        lines+=['',f'## {group}','']
        for t in rows:
            if t['workstream']!=group:continue
            lines += [f'### {t["id"]} — {t["title"]}','',
                      f'**Status:** {t["status"]}. **Priority/queue:** {t["priority"]} / {t["stage"]}. **Owner:** {t["leader"]} / {t["owner"]}. **Reviewer:** {t["review_owner"]}.','',
                      f'**Remaining deliverable:** {t["remaining_scope"]}','',
                      f'**Next action:** {t["next_action"]}','',
                      f'**Dependencies:** {", ".join(t["dependencies"]) or "None recorded."} **Unfinished prerequisites:** {", ".join(t["unfinished_dependency_ids"]) or "None recorded."}','',
                      f'**Blocker or input limit:** {t.get("blocker") or "No additional blocker established; required inputs still need verification."}','',
                      f'**Current evidence:** {t["evidence"]}','',
                      '**Completion proof:** Exact artifact/input revision, acceptance-to-result mapping, observed execution mode and any review required by the deliverable. Retain unknowns and failed checks. Effort remains unestimated until the bounded slice is sized.','']
    lines += ['## Coverage and limits','']+[f'- {s}' for s in report['limits']]
    (out/'remaining-work.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['ticket_count','remaining_ticket_count','status_counts','all_unfinished_have_contracts','dependency_dag_valid']},indent=2))


if __name__=='__main__':
    main()
