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
from article_details import inspect_article, bigrams, dice
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
DIRECTION_PAIRS=[('상승','하락'),('증가','감소'),('매수','매도'),('흑자','적자'),('인상','인하'),('확대','축소'),('급등','급락'),('강세','약세'),('증설','축소'),('상향','하향'),('호조','부진'),('반등','하락')]
RELATED_LIMIT=4
EXTRA_FETCH_LIMIT=8

def title_key(title):
    text=re.sub(r'\[[^\]]*\]|\([^)]*\)|<[^>]*>',' ',str(title or ''))
    return re.sub(r'\s+',' ',re.sub(r'[^\w\s]',' ',text)).strip()

def numbers(title):
    """Number tokens from the raw title (brackets stripped, comma-grouping ignored)."""
    text=re.sub(r'\[[^\]]*\]|\([^)]*\)|<[^>]*>','',str(title or ''))
    return {token.replace(',','') for token in re.findall(r'\d+(?:[.,]\d+)?',text)}

def fingerprint_of(title):
    return re.sub(r'\W','',title).casefold()

def numbers_agree(x,y):
    """A rounded figure matches its precise one (5 vs 5.03), but 2.5 vs 2.8 or 2 vs 3 do not."""
    if x==y: return True
    return ('.' not in x and x==y.split('.')[0]) or ('.' not in y and y==x.split('.')[0])

def numbers_compatible(na,nb):
    """Every number of the shorter title has a match in the longer one; extras like '5개월 만에' are incidental."""
    small,large=sorted((na,nb),key=len)
    return all(any(numbers_agree(x,y) for y in large) for x in small)

def similar(a,b):
    ka,kb=title_key(a),title_key(b)
    if dice(bigrams(ka),bigrams(kb))<0.45: return False
    if not numbers_compatible(numbers(a),numbers(b)): return False
    for left,right in DIRECTION_PAIRS:
        only_left=lambda k:left in k and right not in k
        only_right=lambda k:right in k and left not in k
        if (only_left(ka) and only_right(kb)) or (only_right(ka) and only_left(kb)): return False
    return True

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
    # Negative weights demote titles; they must not promote sentences inside a summary.
    summary_keywords=[r['keyword'] for r in rules if r['weight']>0]
    now=datetime.now(KST);started=time.monotonic();excluded=Counter();status=[];topics=[]
    report_date=target_date or now.date().isoformat()
    sections=config['sections']
    if progress: progress(0,len(sections),'')
    cache_path=DATA/'article-cache.json'
    try: cache=json.loads(cache_path.read_text(encoding='utf-8'))
    except (OSError,ValueError): cache={}
    used=set();titles=set();gathered=0;hits=0;selected_all=[]
    for index,section in enumerate(sections,1):
        selected=[]
        url=f"https://news.naver.com/breakingnews/section/101/{section['id']}"
        def examine(option):
            """Cached or fresh inspection plus time-window checks; counts the exclusion and returns details or None."""
            nonlocal hits
            key=hashlib.sha256(option['url'].encode()).hexdigest()
            cached=cache.get(key)
            if cached and cached.get('inspector_version')==3 and 0<=now.timestamp()-cached['checked_epoch']<config['cache_minutes']*60:
                details,reason=cached['details'],cached['reason'];hits+=1
            else:
                try:
                    page=fetch(option['url'])
                    details,reason=inspect_article(page,'naver',title_hint=option['title'],keywords=summary_keywords)
                    if details:
                        logo=BeautifulSoup(page,'html.parser').select_one('.media_end_head_top_logo img[alt]')
                        details['publisher']=logo.get('alt') if logo else '네이버 뉴스'
                    cache[key]={'checked_epoch':now.timestamp(),'details':details,'reason':reason,'inspector_version':3}
                except (OSError,ValueError):
                    excluded['fetch_error']+=1;return None
                time.sleep(.2)
            if reason: excluded[reason]+=1;return None
            if not valid_time(details.get('published_at'),now,config['max_age_hours']):
                excluded['date_outside_window']+=1;return None
            if target_date and published_date(details.get('published_at'))!=target_date:
                excluded['date_outside_target']+=1;return None
            return details
        def verified_title(option,details):
            """Dedupe by exact title; returns the title or None."""
            title=details.get('title') or option['title']
            fingerprint=fingerprint_of(title)
            if fingerprint in titles: excluded['duplicate']+=1;return None
            titles.add(fingerprint);return title
        def attach_related(option,details,title):
            """Attach to the first similar leader with room; a similar story is dropped only once every similar leader is full, never a new card."""
            similar_leaders=[leader for leader in selected_all if similar(title,leader['title'])]
            if not similar_leaders: return False
            used.add(option['url'])
            for leader in similar_leaders:
                if len(leader['related'])<RELATED_LIMIT:
                    leader['related'].append({'url':option['url'],'title':title,'source':details.get('publisher','네이버 뉴스'),'published_at':details['published_at'],'section':section['name']})
                    excluded['grouped']+=1
                    return True
            excluded['grouped_overflow']+=1
            return True
        try:
            options=candidates(fetch(url))[:section['candidate_limit']]
            if not options: raise ValueError('Section article list is empty')
            gathered+=len(options)
            # Preserve list order among equal scores; prefer user keywords.
            options.sort(key=lambda a:keyword_score(a['title'],rules),reverse=True)
            remaining=[]
            for option in options:
                if option['url'] in used: continue
                if len(selected)>=section['limit']: remaining.append(option);continue
                details=examine(option)
                if not details: continue
                title=verified_title(option,details)
                if not title or attach_related(option,details,title): continue
                used.add(option['url'])
                article={**option,**details,'title':title,'source_id':'naver','source':details.get('publisher','네이버 뉴스'),
                         'section_id':section['id'],'topic':section['name'],
                         'keyword_score':keyword_score(option['title'],rules),
                         'keyword_matches':[k for k in keywords if k.casefold() in title.casefold()],'related':[]}
                selected.append(article);selected_all.append(article)
            # After the quota, only read candidates whose titles look like an already selected story.
            extra=0
            for option in remaining:
                if extra>=EXTRA_FETCH_LIMIT: break
                if option['url'] in used or not any(len(l['related'])<RELATED_LIMIT and similar(option['title'],l['title']) for l in selected_all): continue
                extra+=1
                details=examine(option)
                if not details: continue
                title=verified_title(option,details)
                if title and not attach_related(option,details,title):
                    titles.discard(fingerprint_of(title));excluded['ungrouped']+=1
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
            'stats':{'selected':len(selected_all),'related':sum(len(a['related']) for a in selected_all),'collected':gathered,'topics':sum(bool(t['articles']) for t in topics),
                     'sources_ok':sum(s['status']=='ok' for s in status),'cache_hits':hits,'elapsed_seconds':round(time.monotonic()-started,1)},
            'notice':'네이버 경제 8개 섹션 | 발행일 확인 · 무료 기사 | 제목 연관 발췌'}

def save_report(payload):
    payload.pop('pdf_url',None)
    for folder in (DATA,PUBLIC):
        atomic_json(folder/f"{payload['date']}.json",payload)
    history=[];search=[];latest=None
    for path in sorted(DATA.glob('????-??-??.json'),reverse=True):
        try:
            report=json.loads(path.read_text(encoding='utf-8'))
            if report.get('schema_version')!=4: continue
            entry={'date':report['date'],'selected':report['stats']['selected']}
            rows=[{**a,'date':report['date'],'topic':topic['name']} for topic in report['topics'] for a in topic['articles']]
        except (OSError,ValueError,KeyError,TypeError): continue
        if latest is None: latest=report
        history.append(entry);search.extend(rows)
    for folder in (DATA,PUBLIC):
        atomic_json(folder/'history.json',history)
        atomic_json(folder/'latest.json',latest or payload)
    atomic_json(PUBLIC/'search.json',search)
    atomic_json(DATA/'run-status.json',{'ok':True,'date':payload['date'],'stats':payload['stats'],'sections':payload['source_results'],'excluded':payload['excluded']})
