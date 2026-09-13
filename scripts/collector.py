"""Single low-cost entry point: python scripts/collector.py [--dry-run]."""
import argparse
import json
import sys
from naver_pipeline import collect, save_report, atomic_json, DATA
from run_lock import collection_lock

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        with collection_lock():
            payload=collect()
            if not payload['stats']['selected']:
                atomic_json(DATA/'run-status.json',{'ok':False,'error':'No verified articles','sections':payload['source_results'],'excluded':payload['excluded']})
                print('No verified articles; previous report preserved.',file=sys.stderr)
                return 1
            if args.dry_run: print(json.dumps(payload,ensure_ascii=False))
            else:
                save_report(payload)
                print(json.dumps({'ok':True,'date':payload['date'],**payload['stats']}))
        return 0
    except RuntimeError as error:
        print(str(error),file=sys.stderr);return 2

if __name__=='__main__': raise SystemExit(main())
