"""Loopback-only local dashboard with same-origin manual collection."""
import json
import subprocess
import sys
import threading
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from keyword_settings import load_rules, save_rules
from naver_pipeline import collectable_dates, DATA, KST

ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
STATUS={'running':False,'message':'수집 대기 중','ok':None,'date':None}
MESSAGES={0:'수집 완료',1:'검증을 통과한 기사가 없어 이전 보고서를 유지합니다.',2:'다른 수집이 실행 중입니다.',3:'수집할 수 없는 날짜입니다.'}

def read_json(path):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): return None

def status_payload(now=None):
    now=now or datetime.now(KST)
    latest=read_json(DATA/'latest.json')
    progress=read_json(DATA/'progress.json') if STATUS['running'] else None
    return {**STATUS,'progress':progress if isinstance(progress,dict) else None,'today':now.date().isoformat(),
            'latest_date':latest.get('date') if isinstance(latest,dict) else None,'collectable_dates':collectable_dates(now)}

def parse_collect_request(raw,allowed):
    if not raw.strip(): return None
    body=json.loads(raw)
    if not isinstance(body,dict): raise ValueError('요청 형식이 올바르지 않습니다.')
    date=body.get('date')
    if date is None: return None
    if not isinstance(date,str) or date not in allowed: raise ValueError(f"수집 가능한 날짜는 {', '.join(allowed)} 입니다.")
    return None if date==allowed[0] else date

def run_collection(date):
    try:
        command=[sys.executable,str(ROOT/'scripts/collector.py')]+(['--date',date] if date else [])
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600)
        STATUS.update(ok=result.returncode==0,message=MESSAGES.get(result.returncode,'수집 실행 오류. 이전 보고서를 유지합니다.'))
    except Exception:
        STATUS.update(ok=False,message='수집 실행 오류. 이전 보고서를 유지합니다.')
    finally:
        STATUS['running']=False
        LOCK.release()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(ROOT/'dist'),**kwargs)
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        super().end_headers()
    def send_json(self,status,data):
        body=json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def read_body(self,limit):
        size=int(self.headers.get('Content-Length','0') or 0)
        if not 0<=size<=limit: raise ValueError('요청 데이터가 너무 큽니다.')
        return self.rfile.read(size) if size else b''
    def do_GET(self):
        if self.path=='/api/status': return self.send_json(200,status_payload())
        if self.path=='/api/keywords': return self.send_json(200,{'rules':load_rules()})
        if urlparse(self.path).path in ('/','/index.html'):
            version=hashlib.sha256((ROOT/'dist/app.js').read_bytes()+(ROOT/'dist/minimal.css').read_bytes()).hexdigest()[:12]
            body=(ROOT/'dist/index.html').read_text(encoding='utf-8').replace('__ASSET_VERSION__',version).encode('utf-8')
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        return super().do_GET()
    def do_POST(self):
        if self.path not in ('/api/collect','/api/keywords'): return self.send_json(404,{'error':'not found'})
        if self.headers.get('Host')!='127.0.0.1:8765' or self.headers.get('Origin')!='http://127.0.0.1:8765' or self.headers.get('X-Briefing-Request')!='collect':
            return self.send_json(403,{'error':'same-origin requests only'})
        if self.path=='/api/keywords':
            try:
                raw=self.read_body(32768)
                if not raw: raise ValueError('설정 데이터가 비어 있습니다.')
                body=json.loads(raw)
                if not isinstance(body,dict): raise ValueError('설정 형식이 올바르지 않습니다.')
                return self.send_json(200,{'rules':save_rules(body.get('rules'))})
            except (ValueError,UnicodeError) as error:
                return self.send_json(400,{'error':str(error)})
        try: date=parse_collect_request(self.read_body(4096),collectable_dates())
        except (ValueError,UnicodeError) as error:
            return self.send_json(400,{'error':str(error) if not isinstance(error,json.JSONDecodeError) else '요청 형식이 올바르지 않습니다.'})
        if not LOCK.acquire(blocking=False): return self.send_json(409,status_payload())
        STATUS.update(running=True,ok=None,date=date,message=f'{date} 뉴스를 수집하고 있습니다.' if date else '뉴스를 수집하고 있습니다.')
        threading.Thread(target=run_collection,args=(date,),daemon=True).start()
        self.send_json(202,status_payload())

class LocalServer(ThreadingHTTPServer):
    allow_reuse_address=False

if __name__=='__main__':
    print('http://127.0.0.1:8765/',flush=True)
    LocalServer(('127.0.0.1',8765),Handler).serve_forever()
