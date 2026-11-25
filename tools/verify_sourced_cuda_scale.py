"""Replay three pinned Florida final rolls through the bounded CPU/CUDA screen."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import perf_counter
from zipfile import ZipFile

import numpy as np
from backend.core import acquisition_batch
from backend.core.acquisition_batch import FIELDS, screen, summarize


def digest_file(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def digest_record(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def replay(archive, pin):
    if digest_file(archive) != pin['archive_sha256']:
        raise ValueError(f'Archive digest changed: {archive}')
    seen, units = set(), []
    counts, times, cuda_stages = Counter(), Counter(), Counter()
    identities, results = hashlib.sha256(), hashlib.sha256()

    def flush():
        unknown = np.full(len(units), -1, dtype=np.int64)
        values = dict.fromkeys(FIELDS, unknown)
        values['reported_units'] = np.asarray(units, dtype=np.int64)
        outputs = []
        for backend in ('cpu_reference', 'cuda'):
            start = perf_counter()
            output, detail = screen(values, backend)
            times[backend] += perf_counter() - start
            if detail['backend'] != backend:
                raise ValueError('Unexpected execution backend')
            if backend == 'cuda':
                for stage in ('transfer_in_s', 'compute_s', 'transfer_out_s'):
                    cuda_stages[stage] += detail[stage]
            outputs.append(output)
        cpu, cuda = outputs
        for key, value in cpu.items():
            if not np.array_equal(value, cuda[key]):
                raise ValueError(f'Backend mismatch: {key}')
            results.update(value.tobytes())
        counts.update(summarize(cpu))
        units.clear()

    with ZipFile(archive) as zipped, zipped.open(pin['member']) as raw:
        rows = csv.DictReader(io.TextIOWrapper(raw, encoding=pin['encoding'], newline=''), strict=True)
        for row in rows:
            if (row['CO_NO'], row['ASMNT_YR'], row['FILE_T']) != (pin['dor_code'], str(pin['assessment_year']), 'R'):
                raise ValueError('Roll scope mismatch')
            key = row['PARCEL_ID'].strip()
            if not key or key in seen:
                raise ValueError('Missing or duplicate parcel identity')
            seen.add(key)
            identities.update(f"{pin['county_fips']}:{key}\n".encode('utf-8'))
            reported = row['NO_RES_UNTS'].strip()
            units.append(int(reported) if reported.isascii() and reported.isdecimal() and 0 < int(reported) <= 100_000 else -1)
            if len(units) == 50_000:
                flush()
        if units:
            flush()
    if len(seen) != pin['distinct_roll_parcels'] or counts['unknown'] != len(seen) or counts['eligible']:
        raise ValueError('Coverage or eligibility mismatch')
    if any(counts[f'reported_{u}'] != pin['reported_residential_unit_buckets'].get(str(u), 0) for u in (2, 3, 4)):
        raise ValueError('Reported unit counts differ from source receipt')
    return {'county_fips': pin['county_fips'], 'archive_sha256': pin['archive_sha256'], 'source_url': pin['source_url'],
            'rows': len(seen), 'identity_sha256': identities.hexdigest(), 'output_sha256': results.hexdigest(),
            'counts': dict(counts), 'screen_wall_seconds': dict(times),
            'cuda_stage_seconds': dict(cuda_stages)}


def checkpointed_replay(archive, pin, directory):
    if directory is None:
        return replay(archive, pin), False
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (pin['county_fips'] + '.json')
    fingerprint = digest_record({
        'pin': pin, 'verifier_sha256': digest_file(Path(__file__)),
        'screen_sha256': digest_file(Path(acquisition_batch.__file__)),
    })
    if path.exists():
        entry = json.loads(path.read_bytes())
        result = entry['result']
        if (entry['input_sha256'] != fingerprint or entry['result_sha256'] != digest_record(result)
                or digest_file(archive) != pin['archive_sha256']):
            raise ValueError(f'Stale or invalid checkpoint: {path}')
        return result, True

    result = replay(archive, pin)
    temporary = None
    try:
        with NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'input_sha256': fingerprint, 'result': result,
                       'result_sha256': digest_record(result)}, stream)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archives', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--checkpoint-dir', type=Path)
    args = parser.parse_args()
    root = Path('docs/acquisition/source-contract-review')
    start = perf_counter()
    counties = []
    resumed = []
    for code in ('23', '62', '16'):
        pin = json.loads((root / f'fdor-{code}-final-roll-coverage.json').read_bytes())
        county, reused = checkpointed_replay(args.archives / f'fdor-nal-{code}.zip', pin, args.checkpoint_dir)
        counties.append(county)
        if reused:
            resumed.append(county['county_fips'])
    total = sum(county['rows'] for county in counties)
    if total < 2_000_000 or len({county['county_fips'] for county in counties}) != len(counties):
        raise ValueError('Distinct sourced scale threshold not met')
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump({'scope': 'Public sourced numeric screening. Lawful units and economics unknown. Geometry and production admissions excluded.',
                   'distinct_parcels': total, 'parity': True, 'batch_limit': 50_000, 'wall_seconds': perf_counter()-start,
                   'resumed_counties': resumed, 'counties': counties}, stream, indent=2)
        stream.write('\n')
    print(total)


if __name__ == '__main__':
    main()
