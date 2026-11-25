"""Exercise the normal planning API with a source-reported population baseline.

Growth rates are hypothetical. The temporary demonstration database is discarded;
the fixture and returned calculation receipts can be retained and reproduced.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    fixture = json.loads((ROOT / 'docs/cities-planning/haines-scenarios.json').read_text())
    with tempfile.TemporaryDirectory(prefix='black-river-city-demo-') as temporary:
        os.environ['BR_DB'] = str(Path(temporary) / 'city.db')
        os.environ['BR_FOUNDER_TOKEN'] = secrets.token_hex(24)
        os.environ['BR_AUDIT_TOKEN'] = secrets.token_hex(24)
        os.environ['BR_OPERATIONS_TOKEN'] = secrets.token_hex(24)
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        headers = {'Authorization': 'Bearer ' + os.environ['BR_FOUNDER_TOKEN']}
        response = client.post('/api/cities-planning/project', headers=headers, json=fixture)
        response.raise_for_status()
        report = response.json()
        replay = client.post('/api/cities-planning/project', headers=headers, json=fixture)
        replay.raise_for_status()
        if replay.json() != report:
            raise RuntimeError('Exact replay changed the report')
        restored = client.get('/api/cities-planning/' + report['forecast_id'], headers=headers)
        restored.raise_for_status()
        if restored.json() != report:
            raise RuntimeError('Saved history did not retain the report')
        expected = [47134, 50758, 55933]
        if [s['projected_population'] for s in report['scenarios']] != expected:
            raise RuntimeError('Scenario results differ from independently checked reference values')
        result = {
            'entrypoint': 'backend.main.app /api/cities-planning',
            'fixture': 'docs/cities-planning/haines-scenarios.json',
            'report': report,
            'exact_retry_replayed': True,
            'saved_history_retrieved': True,
            'reference_population_results_matched': True,
            'accuracy_evaluated': False,
            'external_actions': 0,
            'runtime_retention': 'Temporary test database discarded; fixture and report retained.',
        }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
