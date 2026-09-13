"""Bounded, deterministic Naver section collection. No model or API key needed."""
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup
from article_details import inspect_article
from keyword_settings import load_rules, keyword_score

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
PUBLIC=ROOT/'dist/data'
KST=timezone(timedelta(hours=9))
CHECKPOINTS={
 '금융':'금리와 자금조달 조건의 변화, 금융상품 적용 대상을 확인하세요.',
 '증권':'가격 변화와 실적·수급을 구분하고 지표의 기준 시점을 확인하세요.',
 '산업/재계':'투자·수주 발표의 규모와 실제 매출 반영 시점을 확인하세요.',
 '부동산':'정책 적용 지역과 시행일, 실거래 및 대출 조건을 확인하세요.',
 '글로벌 경제':'국가별 정책 발표와 환율·원자재 가격의 연결을 확인하세요.',
 '경제일반':'통계의 기준 기간과 정책의 시행일·적용 대상을 확인하세요.',
 '중기/벤처':'자금조달 규모와 사업화 계획, 지원 조건을 확인하세요.',
 '생활경제':'가격·소비 변화가 생활비에 미치는 영향을 확인하세요.'}

def atomic_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,path)

def fetch(url):
    if urlparse(url).hostname not in ('news.naver.com','n.news.naver.com'):
        raise ValueError('Only Naver news is allowed')
    req=Request(url,headers={'User-Agent':'MorningEconomyBriefing/2.0 (personal local reader)','Accept-Language':'ko-KR'})
    with urlopen(req,timeout=15) as response:
        if urlparse(response.url).hostname not in ('news.naver.com','n.news.naver.com'):
            raise ValueError('Unexpected redirect')
        return response.read(3_000_000).decode(response.headers.get_content_charset() or 'utf-8',errors='replace')

def article_url(raw):
    if urlparse(raw).hostname not in ('news.naver.com','n.news.naver.com'):
        return None
    match=re.search(r'/article/(\d{3})/(\d+)',urlparse(raw).path)
    return f'https://n.news.naver.com/mnews/article/{match[1]}/{match[2]}' if match else None

def candidates(page):
    soup=BeautifulSoup(page,'html.parser')
    # Restrict to the actual section article list, excluding sidebar recommendations.
    links=soup.select('.section_latest_article .sa_text_title')
    results=[];seen=set()
    for a in links:
        url=article_url(a.get('href',''))
        title=a.get_text(' ',strip=True)
        if url and url not in seen and len(title)>=10:
            seen.add(url);results.append({'url':url,'title':title})
    return results

def valid_time(value, now, age):
    try:
        stamp=datetime.fromisoformat(value)
        if stamp.tzinfo is None: return False
        return 0 <= (now-stamp).total_seconds() <= age*3600
    except (TypeError,ValueError): return False

def collectable_dates(now=None):
    today=(now or datetime.now(KST)).date()
    return [(today-timedelta(days=i)).isoformat() for i in range(3)]

def published_date(value):
    try: return datetime.fromisoformat(value).astimezone(KST).date().isoformat()
    except (TypeError,ValueError,AttributeError): return None

def collect(target_date=None,progress=None):
    config=json.loads((ROOT/'config/sections.json').read_text(encoding='utf-8'))
    rules=load_rules()
    keywords=[r['keyword'] for r in rules]
    now=datetime.now(KST);started=time.monotonic();excluded=Counter();status=[];topics=[]
    report_date=target_date or now.date().isoformat()
    sections=config['sections']
    if progress: progress(0,len(sections),'')
    cache_path=DATA/'article-cache.json'
    try: cache=json.loads(cache_path.read_text(encoding='utf-8'))
    except (OSError,ValueError): cache={}
    used=set();titles=set();gathered=0;hits=0
    for index,section in enumerate(sections,1):
        selected=[]
        url=f"https://news.naver.com/breakingnews/section/101/{section['id']}"
        try:
            options=candidates(fetch(url))[:section['candidate_limit']]
            if not options: raise ValueError('Section article list is empty')
            gathered+=len(options)
            # Preserve list order among equal scores; prefer user keywords.
            options.sort(key=lambda a:keyword_score(a['title'],rules),reverse=True)
            for option in options:
                if option['url'] in used: continue
                key=hashlib.sha256(option['url'].encode()).hexdigest()
                cached=cache.get(key)
                if cached and cached.get('inspector_version')==2 and 0<=now.timestamp()-cached['checked_epoch']<config['cache_minutes']*60:
                    details,reason=cached['details'],cached['reason'];hits+=1
                else:
                    try:
                        page=fetch(option['url'])
                        details,reason=inspect_article(page,'naver')
                        if details:
                            logo=BeautifulSoup(page,'html.parser').select_one('.media_end_head_top_logo img[alt]')
                            details['publisher']=logo.get('alt') if logo else '네이버 뉴스'
                        cache[key]={'checked_epoch':now.timestamp(),'details':details,'reason':reason,'inspector_version':2}
                    except (OSError,ValueError):
                        excluded['fetch_error']+=1;continue
                    time.sleep(.2)
                if reason: excluded[reason]+=1;continue
                if not valid_time(details.get('published_at'),now,config['max_age_hours']):
                    excluded['date_outside_window']+=1;continue
                if target_date and published_date(details.get('published_at'))!=target_date:
                    excluded['date_outside_target']+=1;continue
                title=details.get('title') or option['title']
                fingerprint=re.sub(r'\W','',title).casefold()
                if fingerprint in titles: excluded['duplicate']+=1;continue
                titles.add(fingerprint);used.add(option['url'])
                selected.append({**option,**details,'title':title,'source_id':'naver','source':details.get('publisher','네이버 뉴스'),
                                 'section_id':section['id'],'topic':section['name'],
                                 'keyword_score':keyword_score(option['title'],rules),
                                 'keyword_matches':[k for k in keywords if k.casefold() in title.casefold()]})
                if len(selected)>=section['limit']: break
            status.append({'id':section['id'],'name':section['name'],'status':'ok' if len(selected)>=section['minimum'] else 'shortfall','count':len(selected),'minimum':section['minimum'],'target':section['limit'], 'shortfall':max(0,section['minimum']-len(selected))})
        except (OSError,ValueError) as error:
            status.append({'id':section['id'],'name':section['name'],'status':'error','count':0,'message':str(error)[:120]})
        topics.append({'id':section['id'],'name':section['name'],'articles':selected,'article_count':len(selected),
                       'checkpoint':CHECKPOINTS[section['name']]})
        if progress: progress(index,len(sections),section['name'])
        time.sleep(.2)
    cache={k:v for k,v in cache.items() if now.timestamp()-v['checked_epoch']<72*3600}
    atomic_json(cache_path,cache)
    return {'schema_version':4,'date':report_date,'generated_at':datetime.now(KST).isoformat(timespec='seconds'),
            'timezone':'Asia/Seoul','keywords':keywords,'keyword_rules':rules,'topics':topics,'source_results':status,'excluded':dict(excluded),
            'stats':{'selected':len(used),'collected':gathered,'topics':sum(bool(t['articles']) for t in topics),
                     'sources_ok':sum(s['status']=='ok' for s in status),'cache_hits':hits,'elapsed_seconds':round(time.monotonic()-started,1)},
            'notice':'네이버 경제 8개 섹션 | 발행일 확인 · 무료 기사 | 본문 핵심 문장 발췌'}

def save_report(payload):
    payload.pop('pdf_url',None)
    for folder in (DATA,PUBLIC):
        atomic_json(folder/f"{payload['date']}.json",payload)
        atomic_json(folder/'latest.json',payload)
    history=[];search=[]
    for path in sorted(DATA.glob('????-??-??.json'),reverse=True):
        try: report=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError): continue
        if report.get('schema_version')!=4: continue
        history.append({'date':report['date'],'selected':report['stats']['selected']})
        for topic in report['topics']:
            search.extend({**a,'date':report['date'],'topic':topic['name']} for a in topic['articles'])
    atomic_json(DATA/'history.json',history);atomic_json(PUBLIC/'history.json',history)
    atomic_json(PUBLIC/'search.json',search)
    atomic_json(DATA/'run-status.json',{'ok':True,'date':payload['date'],'stats':payload['stats'],'sections':payload['source_results'],'excluded':payload['excluded']})
