"""Run the pinned local diagnostic; do not publish to the acquisition database."""
import argparse,json
from backend.core.state_parcel_research import load_pinned,reconcile_excerpt

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('excerpt');p.add_argument('pilot');p.add_argument('--excerpt-sha',required=True);p.add_argument('--pilot-sha',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();r=reconcile_excerpt(load_pinned(a.excerpt,a.excerpt_sha),load_pinned(a.pilot,a.pilot_sha));r.update(excerpt_sha256=a.excerpt_sha,pilot_sha256=a.pilot_sha)
    with open(a.output,'x') as f:json.dump(r,f,indent=2);f.write('\n')
if __name__=='__main__':main()
