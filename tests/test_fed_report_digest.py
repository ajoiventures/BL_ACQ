import json, hashlib
from collections import Counter
from pathlib import Path
from tools.digest_fed_report import OUT, ROOT, section, disposition

def test_fed_report_digest_lossless_and_no_promotion():
    c=json.loads((ROOT/'site_academy/fed-2025-skill-candidates.json').read_text(encoding="utf-8"))
    d=OUT/c['source']['source_id']; pages=[json.loads(x) for x in (d/'pages.jsonl').read_text(encoding="utf-8").splitlines()]; units=[json.loads(x) for x in (d/'units.jsonl').read_text(encoding="utf-8").splitlines()]; links=[json.loads(x) for x in (OUT/'unit-dispositions.jsonl').read_text(encoding="utf-8").splitlines()]
    assert len(pages)==204 and len(units)==len(links)==c['source']['candidate_units']
    assert len({u['unit_id'] for u in units})==len(units)
    assert len(c['skills'])==55 and c['accepted_count']==0
    for p in pages:
        ps=[u for u in units if u['pdf_page']==p['pdf_page']]
        assert ''.join(u['text'] for u in ps)==p['text']
        assert hashlib.sha256(p['text'].encode()).hexdigest()==p['text_sha256']
    assert all(u['unit_id']==l['unit_id'] and u['text_sha256']==l['text_sha256'] and not l['training_label_eligible'] for u,l in zip(units,links))
    ids={s['id'] for s in c['skills']}
    assert all(set(l['page_level_skill_candidates'])<=ids for l in links)
    assert all(s['authority']=='NONE' and not s['training_label_eligible'] for s in c['skills'])
    assert dict(Counter(l['provisional_disposition'] for l in links))==c['unit_triage_counts']

def test_fed_report_section_and_temporal_distinctions():
    assert section(171)=='G Statistical tables'
    assert disposition(171,'2025 12.3')=='TABLE_OR_NOTE_REQUIRES_CELL_VALIDATION'
    assert disposition(157,'Effective 2026')=='DATED_POLICY_ACTION_CHECK_CURRENT_STATUS'
    assert disposition(165,'Pending')=='HISTORICAL_LITIGATION_CHECK_CURRENT_STATUS'
