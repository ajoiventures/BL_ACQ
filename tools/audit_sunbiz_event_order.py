"""Audit native event sequences across retained Sunbiz daily files."""

import argparse
from collections import defaultdict
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from tools.stage_sunbiz_events import stage


def summarize_order(rows):
    documents = defaultdict(lambda: defaultdict(list))
    sequences = defaultdict(lambda: defaultdict(set))
    for artifact, document, sequence, digest in rows:
        documents[document][artifact].append(sequence)
        sequences[(document, sequence)][artifact].add(digest)

    shared = [groups for groups in documents.values() if len(groups) > 1]
    repeated = [groups for groups in sequences.values() if len(groups) > 1]
    inversions = 0
    for groups in shared:
        ranges = [groups[name] for name in sorted(groups)]
        if any(max(a) >= min(b) for a, b in zip(ranges, ranges[1:])):
            inversions += 1
    return {
        'documents_in_multiple_files': len(shared),
        'nonincreasing_sequence_documents': inversions,
        'cross_file_repeated_document_sequence': len(repeated),
        'cross_file_conflicting_document_sequence': sum(
            len(set().union(*groups.values())) > 1 for groups in repeated
        ),
    }


def audit(paths):
    if not 2 <= len(paths) <= 10 or len({path.name for path in paths}) != len(paths):
        raise ValueError('Select two to ten distinct daily event artifacts')
    with TemporaryDirectory() as directory:
        database = Path(directory) / 'events.sqlite'
        receipts = [stage(path, database) for path in sorted(paths, key=lambda path: path.name)]
        with closing(sqlite3.connect(database)) as db:
            rows = db.execute('SELECT artifact,document,sequence,row_sha256 FROM event_observation')
            order = summarize_order(rows)
    return {'artifacts': receipts, 'accepted': sum(item['accepted'] for item in receipts),
            **order, 'registry_updates': 0, 'commercial_release_authorized': False,
            'scope': 'Filename chronology and native sequence evidence only.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sources', nargs='+', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.sources), indent=2))
