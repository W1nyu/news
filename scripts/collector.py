"""Single low-cost entry point: python scripts/collector.py [--dry-run] [--date YYYY-MM-DD]."""
import argparse
import json
import sys
from datetime import datetime
from naver_pipeline import collect, save_report, atomic_json, collectable_dates, DATA, KST
from run_lock import collection_lock

PROGRESS=DATA/'progress.json'

def resolve_date(value):
    if value is None: return None
    allowed=collectable_dates()
    if value not in allowed: raise ValueError(f"수집 가능한 날짜는 {', '.join(allowed)} 입니다.")
    return value

def progress_writer(date):
    started=datetime.now(KST).isoformat(timespec='seconds')
    def write(done,total,section):
        try: atomic_json(PROGRESS,{'done':done,'total':total,'section':section,'date':date,'started_at':started})
        except OSError: pass
    return write

def clear_progress():
    try: PROGRESS.unlink(missing_ok=True)
    except OSError: pass

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--date',help='YYYY-MM-DD (오늘·어제·그제만 가능)')
    args=parser.parse_args()
    try: target=resolve_date(args.date)
    except ValueError as error:
        print(str(error),file=sys.stderr);return 3
    try:
        with collection_lock():
            try:
                payload=collect(target_date=target,progress=progress_writer(target or datetime.now(KST).date().isoformat()))
                if not payload['stats']['selected']:
                    atomic_json(DATA/'run-status.json',{'ok':False,'date':payload['date'],'error':'No verified articles','sections':payload['source_results'],'excluded':payload['excluded']})
                    print('No verified articles; previous report preserved.',file=sys.stderr)
                    return 1
                if args.dry_run: print(json.dumps(payload,ensure_ascii=False))
                else:
                    save_report(payload)
                    print(json.dumps({'ok':True,'date':payload['date'],**payload['stats']}))
            finally: clear_progress()
        return 0
    except RuntimeError as error:
        print(str(error),file=sys.stderr);return 2

if __name__=='__main__': raise SystemExit(main())
