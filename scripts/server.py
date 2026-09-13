"""Loopback-only local dashboard with same-origin manual collection."""
import json
import subprocess
import sys
import threading
import hashlib
from urllib.parse import urlparse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from keyword_settings import load_rules, save_rules

ROOT=Path(__file__).resolve().parents[1]
LOCK=threading.Lock()
STATUS={'running':False,'message':'수집 대기 중','ok':None}
def run_collection():
    try:
        result=subprocess.run([sys.executable,str(ROOT/'scripts/collector.py')],cwd=ROOT,capture_output=True,timeout=600)
        STATUS.update(ok=result.returncode==0,message='수집과 보고서 생성 완료' if result.returncode==0 else '수집 실패. 이전 보고서를 유지합니다.')
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
    def do_GET(self):
        if self.path=='/api/status': return self.send_json(200,STATUS)
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
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=32768: raise ValueError('설정 데이터가 너무 크거나 비어 있습니다.')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict): raise ValueError('설정 형식이 올바르지 않습니다.')
                return self.send_json(200,{'rules':save_rules(body.get('rules'))})
            except (ValueError,UnicodeError) as error:
                return self.send_json(400,{'error':str(error)})
        if not LOCK.acquire(blocking=False): return self.send_json(409,STATUS)
        STATUS.update(running=True,ok=None,message='뉴스를 수집하고 보고서를 만들고 있습니다.')
        threading.Thread(target=run_collection,daemon=True).start()
        self.send_json(202,STATUS)

class LocalServer(ThreadingHTTPServer):
    allow_reuse_address=False

if __name__=='__main__':
    print('http://127.0.0.1:8765/',flush=True)
    LocalServer(('127.0.0.1',8765),Handler).serve_forever()
