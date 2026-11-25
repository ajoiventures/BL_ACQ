#!/usr/bin/env python3
"""Exercise the normal local API against an isolated database and retained excerpt.

No remote page fetch, AI provider, mail, transaction or standing watcher is run.
The output is a compact receipt summary, without duplicating source excerpts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',type=Path,default=ROOT/'docs/intelligence-flow/haines-source.json')
    parser.add_argument('--output',type=Path,help='Optional JSON receipt summary; the isolated runtime database is discarded.')
    args=parser.parse_args()
    fixture=json.loads(args.fixture.read_text())
    with tempfile.TemporaryDirectory(prefix='black-river-signal-demo-') as temporary:
        temporary=Path(temporary)
        os.environ['BR_DB']=str(temporary/'demo.db')
        os.environ['BR_SIGNAL_EVIDENCE_ROOT']=str(temporary/'evidence')
        os.environ['BR_FOUNDER_TOKEN']=secrets.token_hex(24)
        os.environ['BR_AUDIT_TOKEN']=secrets.token_hex(24)
        os.environ['BR_OPERATIONS_TOKEN']=secrets.token_hex(24)
        from fastapi.testclient import TestClient
        from backend.main import app,conn
        client=TestClient(app)
        headers={'Authorization':'Bearer '+os.environ['BR_FOUNDER_TOKEN']}
        def post(path,body,expected=200):
            response=client.post('/api/intelligence-flow'+path,headers=headers,json=body)
            if response.status_code!=expected:
                raise RuntimeError(f'{path}: expected {expected}, observed {response.status_code}: {response.text}')
            return response.json()
        fixture['request_id']='demo-capture'
        captured=post('/capture',fixture)
        source_id=captured['source_id']
        plan=post('/'+source_id+'/plan',{'request_id':'demo-plan','revision':captured['revision'],'disposition':'LINK_EXISTING'})
        release_body={'request_id':'demo-release','plan_id':plan['plan_id'],'plan_sha256':plan['plan_sha256']}
        executed=post('/'+source_id+'/release',release_body)
        replayed=post('/'+source_id+'/release',release_body)
        if replayed!=executed:
            raise RuntimeError('Exact retry did not replay the same receipt')
        changed={**fixture,'title':'Changed local test metadata'}
        post('/capture',changed,409)
        # Change an operator classification only; do not claim the publisher revised its article.
        revised={**fixture,'request_id':'demo-classification-revision',
                 'topic_tags':list(dict.fromkeys(fixture['topic_tags']+['INFORMATIONAL']))}
        if revised['topic_tags']==fixture['topic_tags']:
            revised['topic_tags']=[t for t in fixture['topic_tags'] if t!='INFORMATIONAL'] or ['ECONOMIC_DEVELOPMENT']
        current=post('/capture',revised)
        post('/'+source_id+'/release',{**release_body,'request_id':'demo-stale-release'},409)
        viewed=client.get('/api/intelligence-flow/'+source_id,headers=headers)
        if viewed.status_code!=200:
            raise RuntimeError('Could not read the source through the normal API')
        with conn() as db:
            run_count=db.execute('SELECT COUNT(*) FROM signal_runs').fetchone()[0]
            audit_count=db.execute("SELECT COUNT(*) FROM audit WHERE action LIKE 'SIGNAL_%'").fetchone()[0]
        summary={
            'executed_at':datetime.now(timezone.utc).isoformat(),
            'fixture':str(args.fixture.relative_to(ROOT)) if args.fixture.is_relative_to(ROOT) else args.fixture.name,
            'entrypoint':'backend.main.app /api/intelligence-flow',
            'source_url':fixture['source_url'],'published_at':fixture.get('published_at'),
            'source_id':source_id,'captured_revision':captured['revision'],
            'capture_kind':captured['source']['capture_kind'],
            'retained_excerpt_sha256':captured['source']['content_sha256'],
            'source_verification_status':captured['source']['verification_status'],
            'source_claim_count':len(captured['source']['source_claims']),
            'digest_sha256':captured['digest']['digest_sha256'],
            'topic_tags':fixture['topic_tags'],
            'ticket_links':[x['ticket_id'] for x in plan['links']],
            'excluded_links':plan['excluded_links'],
            'plan_id':plan['plan_id'],'plan_sha256':plan['plan_sha256'],
            'execution_status':executed['status'],
            'workers':[{k:r[k] for k in ('run_id','worker_id','mode','state','attempt','output_sha256')} for r in executed['runs']],
            'human_actions':executed['human_actions'],
            'exact_retry_replayed':replayed==executed,'different_payload_same_request_rejected':True,
            'input_classification_revision':current['revision'],
            'revision_test_scope':'Operator topic classification changed; no publisher revision is claimed.',
            'old_plan_release_rejected':True,
            'old_plan_marked_stale':not viewed.json()['plans'][0]['is_current'],
            'persisted_worker_runs':run_count,'audit_event_count':audit_count,
            'live_ai_provider':False,'continuous_monitoring':False,'outbound_messages_sent':0,
            'authority':executed['authority'],
            'runtime_evidence_retained':'Temporary isolated database and excerpt archive were used for this test and discarded; fixture and hashes remain reproducible.',
            'independent_acceptance':'PENDING',
        }
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
