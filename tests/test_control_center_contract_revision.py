import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_control_center_contract_reconciles_current_source_without_claiming_deployment():
    d=json.loads((ROOT/'docs/acquisition/control-center/contract.json').read_text())
    assert hashlib.sha256((ROOT/d['source_path']).read_bytes()).hexdigest()==d['source_sha256']
    assert set(d['objects'])=={'property','cohort','run','task','review','action'}
    assert len(d['screen_routes'])==5 and d['scale_target']['minimum_acceptance_property_records']==2000000
    assert d['first_workload']['unit_count_classes']==[2,3,4] and not d['first_workload']['tax_use_code_sufficient_for_legal_units']
    assert not d['cuda_contract']['silent_fallback_allowed'] and not d['external_execution_enabled']
    assert not d['observed_local']['end_to_end_capacity_verified'] and d['observed_local']['verified_legal_unit_count'] is None
    assert d['discovery_contract']['broad_inventory_before_preferred_strategy'] and d['discovery_contract']['mandate_is_boundary_not_site_use']
    assert d['discovery_contract']['stages'].index('preliminary_feasibility')<d['discovery_contract']['stages'].index('concept_alternatives')
    for entry in d['local_api_source_routes']:
        assert f"@app.{entry['method'].lower()}('{entry['path']}')" in (ROOT/entry['source']).read_text()
