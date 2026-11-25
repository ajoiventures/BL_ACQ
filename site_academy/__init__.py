"""Site assessment curriculum and locally executable analytical workflows."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent

def catalog():
    entries = []
    for filename, source in [('acquisition.json', 'Black River · Acquisition and Town Development'), ('planning.json', 'Kelly · Community Planning (contents-derived exercises)'), ('skills.json', 'LaGro · Site Analysis'), ('market-skills.json', 'Market Structure Tool'), *[(f'econ{i}.json', 'O’Sullivan · Urban Economics') for i in (1,2,3)]]:
        for row in json.loads((ROOT / filename).read_text(encoding="utf-8")):
            entries.append({**row, 'reference': source})
    return entries

def readable(value):
    if isinstance(value, list):
        return '\n'.join(f'• {readable(item)}' for item in value)
    if isinstance(value, dict):
        return '\n'.join(f'{key} — {readable(item)}' for key, item in value.items())
    return str(value)
