"""Inspect a bounded, explicitly supplied NAL-layout sample; never import it."""
import argparse
import json
from pathlib import Path
from backend.core.nal_intake import probe_nal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--encoding',required=True);p.add_argument('--county',required=True)
    p.add_argument('--year',required=True,type=int);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=probe_nal(a.input,expected_sha256=a.sha256,encoding=a.encoding,county=a.county,year=a.year)
    with a.output.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('mode','records_seen','production_accepted')},indent=2))

if __name__=='__main__':main()
