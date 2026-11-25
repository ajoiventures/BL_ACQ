"""Regenerate the offline, searchable study handbook from the canonical catalog."""
from collections import defaultdict
from html import escape
from pathlib import Path
from . import catalog, readable

def build(destination):
    groups = defaultdict(list)
    for item in catalog():
        key = f"{item['reference']} · Chapter {item['chapter']}" if 'chapter' in item else 'Market workbook'
        groups[key].append(item)
    parts = ['''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Black River · Site study field manual</title><style>
*{box-sizing:border-box}body{max-width:65rem;margin:auto;padding:2rem;font:17px/1.55 system-ui;background:#191c1c;color:#ede8df}
h1,h2{font-family:Georgia,serif;font-weight:500}h2{margin-top:2rem;color:#d6ac81}section{border-bottom:1px solid #444}summary{padding:.8rem 0;cursor:pointer}
dd{margin:0 0 1rem;white-space:pre-line}dt{font-weight:bold;color:#d6ac81}input{font:inherit;width:min(100%,36rem);padding:.6rem;background:#252b2b;color:white;border:1px solid #9c8872}
small{color:#ccc}details{padding:.3rem}details[open]{background:#222727;padding:1rem}a{color:#dfbf9d}</style>
<main><h1>Site study field manual</h1><p>Black River Skills Academy</p>
<label>Find a skill, method, source or role<br><input id="search" type="search"></label>''']
    for group,items in groups.items():
        parts.append(f'<section><h2>{escape(group)} <small>({len(items)})</small></h2>')
        for row in items:
            fields = [('Source',row['reference']+' · '+readable(row.get('pages') or row.get('cells'))),
                      ('Inputs',row['inputs']),('Procedure',row['procedure']),('Deliverable',row['output']),
                      ('Acceptance test',row['acceptance'])]
            fields.extend((key.capitalize(),row[key]) for key in ('tool','equation','problem','answer') if key in row)
            parts.append(f"<details><summary>{escape(row['title'])} <small> · {escape(row['id'])} · {escape(row['owner'])}</small></summary><dl>")
            for label, val in fields:
                parts.append(f'<dt>{label}</dt><dd>{escape(readable(val))}</dd>')
            parts.append('</dl></details>')
        parts.append('</section>')
    parts.append('''</main><script>const search=document.querySelector('#search');search.oninput=()=>{const term=search.value.toLowerCase();for(const group of document.querySelectorAll('section')){let matches=0;for(const item of group.querySelectorAll('details')){item.hidden=!item.textContent.toLowerCase().includes(term);if(!item.hidden)matches++}group.hidden=!matches}}</script></html>''')
    Path(destination).write_text('\n'.join(parts),encoding='utf8')

if __name__=='__main__':
    build(Path(__file__).with_name('field-manual.html'))
