"""Prepare a read-only strategy work packet. No worker dispatch or deal approval."""
import argparse,json
from backend.core.strategy_library import prepare_strategy

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('strategy_id');p.add_argument('case_ref')
    args=p.parse_args();print(json.dumps(prepare_strategy(args.strategy_id,args.case_ref),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
