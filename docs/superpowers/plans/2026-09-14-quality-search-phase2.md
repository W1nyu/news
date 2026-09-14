# 아침 경제 2차 개선 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 요약 문장을 제목 연관 점수로 고르고, 같은 사건 기사를 수집 단계에서 대표 1건 + 관련 보도로 묶고, 요약 키워드 강조와 기간·언론사 검색 필터를 추가한다.

**Architecture:** `article_details.py`에 2-gram Dice 기반 문장 점수 함수를 두고 `inspect_article`이 제목·키워드 힌트를 받는다. `naver_pipeline.py`는 후보 검사 로직을 `examine()`으로 묶어 본 루프와 "한도 이후 유사 후보 추가 검사" 루프가 공유하며, `similar()`로 대표 기사의 `related`에 붙인다. 화면은 `app.js`의 필터 파이프라인(카테고리→언론사→기간→검색어)과 카드 렌더에 관련 보도 토글·요약 강조를 더한다.

**Tech Stack:** Python 3.14 표준 라이브러리 + beautifulsoup4, 순수 JS/CSS. 모델 API 없음.

**설계 문서:** `docs/superpowers/specs/2026-09-14-quality-search-phase2-design.md`

## Global Constraints

- 모델 API 호출 0회. 네이버 경제 8개 섹션 외 출처 금지. 서버 주소 `http://127.0.0.1:8765/` 고정.
- `schema_version` 4 유지(추가 필드만: 기사 `related`, `stats.related`).
- 관련 기사도 무료·발행 시각·기간 검증을 통과해야 한다. 미확인 기사는 관련으로도 넣지 않는다.
- 유사 판정: `title_key` 후 글자 2-gram Dice ≥ 0.45 **and** 숫자 집합이 같거나 한쪽이 빔 **and** 방향어 쌍 불일치 없음. `DIRECTION_PAIRS = [('상승','하락'),('증가','감소'),('매수','매도'),('흑자','적자'),('인상','인하'),('확대','축소'),('급등','급락'),('강세','약세')]`.
- 카드당 관련 최대 `RELATED_LIMIT = 4`, 한도 이후 섹션당 추가 본문 접근 최대 `EXTRA_FETCH_LIMIT = 8`.
- 요약: 후보 앞 12문장, 점수 = `dice(문장, 제목)*3 + 키워드 포함 수*1 + (숫자 또는 % 포함 시 0.5) − index*0.05`. 리드 항상 포함, 두 번째는 리드와 Dice < 0.6, 70단어 예산. `summary_method = '제목 연관 발췌'`.
- 순위(키워드 가중치)는 제목 기준 그대로. 요약 점수는 순위에 반영하지 않는다.
- 캐시 `inspector_version`을 3으로 올린다(요약 방식 변경).
- localStorage 키·형식은 1차와 같고 북마크 객체에 `related`, `keywords`를 더한다.
- 테스트: `python -m unittest discover -s scripts -p "test_*.py"` (루트에서), `node --check dist/app.js`. 출력은 깨끗해야 한다.
- 실제 수집(`python scripts/collector.py`)은 Task 7에서만 1회 실행한다.
- git: 각 Task 끝에 커밋.

---

## 파일 구조

| 파일 | 변경 |
|---|---|
| `scripts/article_details.py` | `bigrams`, `dice`, `pick_summary`; `inspect_article(page, source_id, title_hint=None, keywords=())` |
| `scripts/test_article_details.py` | 요약 선별 테스트 4개 |
| `scripts/naver_pipeline.py` | `title_key`, `similar`, `examine()` 분리, 관련 묶기, 추가 검사 루프, `stats.related` |
| `scripts/test_naver_pipeline.py` | `similar` 테스트, 묶기·상한 테스트 3개; 기존 fake_inspect 시그니처 수정 |
| `dist/index.html` | 툴바에 기간·언론사 선택, 직접 입력 행 |
| `dist/minimal.css` | 툴바 줄바꿈, 직접 입력 행, 관련 보도 목록 |
| `dist/app.js` | 필터 파이프라인, 언론사 목록, 관련 보도 토글, 요약 강조, 키워드 로드 |
| `README.md`, `AGENTS.md` | 요약 방식·묶기 기준·필터 설명 |

---

### Task 1: 요약 문장 선별 (`article_details.py`)

**Files:**
- Modify: `scripts/article_details.py`
- Test: `scripts/test_article_details.py`

**Interfaces:**
- Produces: `bigrams(text) -> set[str]`, `dice(a: set, b: set) -> float`, `pick_summary(sentences: list[str], title: str = '', keywords=()) -> list[str]`, `inspect_article(page, source_id, title_hint=None, keywords=())` (기존 2인자 호출 호환).

- [ ] **Step 1: 실패하는 테스트 작성**

`scripts/test_article_details.py`의 import를 `from article_details import inspect_article, publication_date, pick_summary, dice, bigrams`로 바꾸고, 모듈 상단에 상수와 클래스 안에 테스트를 추가한다:

```python
LEAD='정부가 오늘 새로운 경제 대책을 발표하며 시장 참여자들의 관심이 집중되고 있다.'
FILLERS=['관계자들은 향후 상황을 지켜보며 대응 방안을 논의할 예정이라고 전했다.',
         '전문가들은 이번 조치가 단기적으로는 큰 변화를 만들지 않을 것으로 보고 있다.',
         '한편 업계에서는 추가적인 세부 지침이 나올 때까지 신중한 태도를 유지하고 있다.',
         '시장에서는 정책 효과를 둘러싼 다양한 해석이 나오고 있으며 관련 논의가 이어지고 있다.']
RELATED='삼성전자 반도체 공장 증설 계획은 오는 2027년까지 20조원을 투자하는 내용이다.'
TITLE='삼성전자 반도체 공장 증설에 20조원 투자'
META='<meta property="article:published_time" content="2026-09-12T01:00:00+09:00">'
```

```python
    def test_bigrams_and_dice(self):
        self.assertEqual(bigrams('가 나다'),{'가나','나다'})
        self.assertEqual(dice(set(),set()),0.0)
        self.assertAlmostEqual(dice({'가나','나다'},{'가나','다라'}),0.5)

    def test_title_related_sentence_is_second(self):
        body=' '.join([LEAD,*FILLERS,RELATED])
        article,reason=inspect_article(META+'<div id="dic_area">'+body+'</div>','naver',title_hint=TITLE)
        self.assertIsNone(reason)
        self.assertEqual(article['summary'],[LEAD,RELATED])
        self.assertEqual(article['summary_method'],'제목 연관 발췌')

    def test_keyword_bonus_without_title(self):
        keyworded='금리 인상 여부가 시장의 최대 관심사로 떠오르고 있다는 분석이 나온다.'
        self.assertEqual(pick_summary([LEAD,FILLERS[0],keyworded],'',('금리',)),[LEAD,keyworded])

    def test_near_duplicate_of_lead_skipped(self):
        variant=LEAD.replace('집중되고','쏠리고')
        self.assertEqual(pick_summary([LEAD,variant,FILLERS[0]]),[LEAD,FILLERS[0]])

    def test_without_hints_falls_back_to_order(self):
        self.assertEqual(pick_summary([LEAD,*FILLERS]),[LEAD,FILLERS[0]])
        self.assertEqual(pick_summary([]),[])
```

- [ ] **Step 2: 실패 확인**

Run: `python -m unittest discover -s scripts -p "test_article_details.py" -v`
Expected: `ImportError: cannot import name 'pick_summary'`

- [ ] **Step 3: 구현**

`article_details.py`의 `publication_date` 앞에 추가:

```python
def bigrams(text):
    compact = re.sub(r'[\W_]+', '', str(text or ''))
    return {compact[i:i + 2] for i in range(len(compact) - 1)}

def dice(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if (a or b) else 0.0

def pick_summary(sentences, title='', keywords=()):
    """Lead sentence plus the sentence most related to the title, keywords and figures."""
    candidates = [s for s in sentences[:12] if s]
    if not candidates:
        return []
    title_set = bigrams(title)
    def score(item):
        index, sentence = item
        lowered = sentence.casefold()
        return (dice(bigrams(sentence), title_set) * 3
                + sum(1 for k in keywords if k and k.casefold() in lowered)
                + (0.5 if re.search(r'\d|%', sentence) else 0)
                - index * 0.05)
    lead = candidates[0]
    summary = [lead]
    budget = 70 - len(lead.split())
    lead_set = bigrams(lead)
    for _, sentence in sorted(enumerate(candidates[1:], 1), key=score, reverse=True):
        if sentence != lead and dice(bigrams(sentence), lead_set) < 0.6 and len(sentence.split()) <= budget:
            summary.append(sentence)
            break
    return summary
```

`inspect_article` 시그니처를 `def inspect_article(page, source_id, title_hint=None, keywords=()):`로 바꾸고, `# Select complete informative sentences...` 주석부터 `return {...}` 직전까지를 아래로 교체:

```python
    # Select complete informative sentences, keeping quotations short.
    sentences = re.split(r'(?<=[.!?。])\s+', text)
    eligible = [s.strip() for s in sentences if 25 <= len(s.strip()) <= 220 and not s.strip().endswith('?') and not re.search(r'무단|재배포|저작권|기자\s*=|구독|ⓒ', s)]
    cleaned = []
    for sentence in eligible:
        sentence = re.sub(r'^.*?\[(?:\s*이코노미21[^\]]*|앵커)\]\s*', '', sentence)
        if sentence and sentence not in cleaned:
            cleaned.append(sentence)
    title_text = title_hint or (title.get('content') if title else '') or ''
    summary = pick_summary(cleaned, title_text, keywords)
    if not summary:
        return None, 'unverified'
```

반환 dict의 `'summary_method': '본문 핵심 문장 발췌'`를 `'summary_method': '제목 연관 발췌'`로 바꾼다.

- [ ] **Step 4: 통과 확인**

Run: `python -m unittest discover -s scripts -p "test_*.py"`
Expected: `OK` (기존 `test_free_article_uses_body`도 통과)

- [ ] **Step 5: 커밋**

`git add -A && git commit -m "feat: title-related summary sentence selection"`

---

### Task 2: 유사 기사 묶기 (`naver_pipeline.py`)

**Files:**
- Modify: `scripts/naver_pipeline.py` (`collect` 루프 재구성, 새 함수)
- Test: `scripts/test_naver_pipeline.py`

**Interfaces:**
- Consumes: `article_details.bigrams`, `article_details.dice`, `inspect_article(page,'naver',title_hint=,keywords=)`.
- Produces: `title_key(title) -> str`, `similar(a, b) -> bool`, 기사 dict에 `related: list[{url,title,source,published_at,section}]`, `stats['related']`, 캐시 `inspector_version` 3, `excluded['grouped']`.

- [ ] **Step 1: 기존 테스트의 fake_inspect 시그니처 수정**

`scripts/test_naver_pipeline.py`에서 `def fake_inspect(page,source):`(두 곳)를 `def fake_inspect(page,source,**kwargs):`로 바꾼다. import 줄에 `similar` 추가:
`from naver_pipeline import ROOT, article_url, candidates, collect, valid_time, KST, collectable_dates, published_date, save_report, similar`

- [ ] **Step 2: 실패하는 테스트 작성**

클래스 안에 추가:

```python
    def test_similar_titles(self):
        self.assertTrue(similar('삼성전자가 반도체 공장 증설 발표','삼성전자는 반도체 공장 증설 발표'))
        self.assertTrue(similar('[단독] 삼성전자 반도체 공장 증설','삼성전자 반도체 공장 증설'))
        self.assertFalse(similar('코스피 2% 상승 마감','코스피 3% 상승 마감'))
        self.assertFalse(similar('코스피 2% 상승 마감','코스피 2% 하락 마감'))
        self.assertFalse(similar('삼성전자 반도체 공장 증설','한국은행 기준금리 동결 결정'))

    def _grouping_run(self,variants_for):
        """variants_for(event_index) -> list of variant suffixes; returns (report, fetch mock)."""
        events=['한국은행 기준금리 동결 결정','삼성전자 반도체 공장 증설 발표','서울 아파트 거래량 급감','원달러 환율 급등세 지속','정부 추경 편성 논의 착수','코스피 외국인 순매수 전환']
        def titles(sid):
            base=[f'{e} {sid}' for e in events]
            extra=[f'{e} {sid}{suffix}' for i,e in enumerate(events) for suffix in variants_for(i)]
            return base+extra
        def fake_fetch(url):
            if '/breakingnews/' in url:
                sid=url.rsplit('/',1)[-1]
                return '<div class="section_latest_article">'+''.join(f'<a class="sa_text_title" href="https://n.news.naver.com/mnews/article/999/{sid}{n:02d}">{t}</a>' for n,t in enumerate(titles(sid)))+'</div>'
            return '<div>'+url+'</div>'
        def fake_inspect(page,source,**kwargs):
            return {'title':None,'published_at':(datetime.now(KST)-timedelta(minutes=1)).isoformat(),'summary':['검증용 핵심 문장입니다.'],'access':'public_checked'},None
        # Neutral keyword rules keep Naver list order so the variants land after the quota.
        with patch('naver_pipeline.fetch',side_effect=fake_fetch) as fetched,patch('naver_pipeline.inspect_article',side_effect=fake_inspect),patch('naver_pipeline.load_rules',return_value=[]),patch('naver_pipeline.atomic_json'),patch('naver_pipeline.time.sleep'):
            return collect(),fetched

    def test_similar_titles_group_as_related(self):
        report,fetched=self._grouping_run(lambda i:[' 시장 반응'])
        sections=json.loads((ROOT/'config/sections.json').read_text(encoding='utf-8'))['sections']
        self.assertEqual([len(t['articles']) for t in report['topics']],[s['limit'] for s in sections])
        first=report['topics'][0]['articles']
        self.assertEqual(sum(len(a['related']) for a in first),6)
        self.assertTrue(all(len(a['related'])==1 and a['related'][0]['section']=='금융' for a in first))
        self.assertEqual(report['stats']['related'],sum(len(a['related']) for t in report['topics'] for a in t['articles']))
        self.assertEqual(report['excluded']['grouped'],report['stats']['related'])
        self.assertEqual(fetched.call_count,8*(1+12))

    def test_related_cap_per_card(self):
        report,fetched=self._grouping_run(lambda i:[' 시장 반응',' 배경은',' 전망은',' 영향은',' 후속 조치',' 추가 발표'] if i==0 else [])
        first=report['topics'][0]['articles']
        self.assertEqual(len(first[0]['related']),4)
        self.assertEqual(fetched.call_count,8*(1+6+4))

    def test_extra_fetch_limit_per_section(self):
        report,fetched=self._grouping_run(lambda i:[' 시장 반응',' 배경은'] if i<5 else [])
        first=report['topics'][0]['articles']
        self.assertEqual(sum(len(a['related']) for a in first),8)
        self.assertEqual(fetched.call_count,8*(1+6+8))
```

- [ ] **Step 3: 실패 확인**

Run: `python -m unittest discover -s scripts -p "test_naver_pipeline.py" -v`
Expected: `ImportError: cannot import name 'similar'`

- [ ] **Step 4: 구현**

`naver_pipeline.py` import에 `from article_details import inspect_article, bigrams, dice`. `CHECKPOINTS` 아래에 추가:

```python
DIRECTION_PAIRS=[('상승','하락'),('증가','감소'),('매수','매도'),('흑자','적자'),('인상','인하'),('확대','축소'),('급등','급락'),('강세','약세')]
RELATED_LIMIT=4
EXTRA_FETCH_LIMIT=8

def title_key(title):
    text=re.sub(r'\[[^\]]*\]|\([^)]*\)|<[^>]*>',' ',str(title or ''))
    return re.sub(r'\s+',' ',re.sub(r'[^\w\s]',' ',text)).strip()

def similar(a,b):
    ka,kb=title_key(a),title_key(b)
    if dice(bigrams(ka),bigrams(kb))<0.45: return False
    na,nb=set(re.findall(r'\d+(?:[.,]\d+)?',ka)),set(re.findall(r'\d+(?:[.,]\d+)?',kb))
    if na and nb and na!=nb: return False
    for left,right in DIRECTION_PAIRS:
        only_left=lambda k:left in k and right not in k
        only_right=lambda k:right in k and left not in k
        if (only_left(ka) and only_right(kb)) or (only_right(ka) and only_left(kb)): return False
    return True
```

`collect()`에서 `used=set();titles=set();gathered=0;hits=0` 줄을 `used=set();titles=set();gathered=0;hits=0;selected_all=[]`로 바꾸고, `for index,section in enumerate(sections,1):` 안의 `selected=[]`부터 `status.append(...)` 직전까지(후보 순회 전체)를 아래로 교체:

```python
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
                    details,reason=inspect_article(page,'naver',title_hint=option['title'],keywords=keywords)
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
            fingerprint=re.sub(r'\W','',title).casefold()
            if fingerprint in titles: excluded['duplicate']+=1;return None
            titles.add(fingerprint);return title
        def attach_related(option,details,title):
            """Attach to the first similar leader; a similar story whose leaders are full is dropped, never a new card."""
            for leader in selected_all:
                if not similar(title,leader['title']): continue
                used.add(option['url'])
                if len(leader['related'])<RELATED_LIMIT:
                    leader['related'].append({'url':option['url'],'title':title,'source':details.get('publisher','네이버 뉴스'),'published_at':details['published_at'],'section':section['name']})
                    excluded['grouped']+=1
                else: excluded['grouped_overflow']+=1
                return True
            return False
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
                if title: attach_related(option,details,title)
```

`status.append(...)` 줄과 그 뒤는 그대로 둔다. 반환 dict의 `'stats'`에 `'related':sum(len(a['related']) for a in selected_all)`를 추가한다(`'selected':len(used)` 뒤).

주의: `'selected':len(used)`는 관련 기사 URL도 포함하게 되므로 `'selected':len(selected_all)`로 바꾼다(대표 기사 수). `collector.py`는 `stats['selected']`가 0인지로 실패를 판단하므로 의미가 유지된다.

- [ ] **Step 5: 통과 확인**

Run: `python -m unittest discover -s scripts -p "test_*.py"`
Expected: `OK`. `test_quota_and_all_eight_sections`의 `stats['selected']==42`도 유지되어야 한다(같은 sid 안에서 `'2590'`·`'2591'`처럼 숫자가 달라 유사 판정되지 않음).

- [ ] **Step 6: 커밋**

`git add -A && git commit -m "feat: group similar stories as related articles during collection"`

---

### Task 3: 화면 — 기간·언론사 필터

**Files:**
- Modify: `dist/index.html`, `dist/minimal.css`, `dist/app.js`

**Interfaces:**
- Produces: `state.range/from/to/publisher`, `kstDate(value)`, `rangeBounds()`, `baseArticles()`, `renderPublishers(list)`, `searchText(a)`. Task 4가 `searchText`·`baseArticles`를 그대로 쓴다.

- [ ] **Step 1: `index.html` 툴바 교체**

`<div class="toolbar">…</div>` 한 줄을 아래 두 줄로 바꾼다:

```html
    <div class="toolbar"><label><span class="sr-only">보고서 날짜</span><select id="date"><option value="">최신 보고서</option></select></label><label class="search"><span class="sr-only">전체 날짜 검색</span><input id="search" type="search" placeholder="전체 날짜에서 뉴스 검색" autocomplete="off"></label><label><span class="sr-only">기간</span><select id="range" disabled><option value="all">전체 기간</option><option value="7">최근 7일</option><option value="30">최근 30일</option><option value="custom">직접 입력</option></select></label><label><span class="sr-only">언론사</span><select id="publisher"><option value="">전체 언론사</option></select></label></div>
    <div id="range-custom" class="range-custom" hidden><label>시작일 <input id="from" type="date"></label><span>~</span><label>종료일 <input id="to" type="date"></label></div>
```

- [ ] **Step 2: CSS 추가**

`dist/minimal.css` 끝에 한 줄 추가:

```css
.toolbar{flex-wrap:wrap}.toolbar select{min-width:150px}.toolbar select:disabled{opacity:.5;cursor:not-allowed}.range-custom{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:-10px 0 22px;font-size:13px;color:#657268}.range-custom input{height:40px;border:1px solid #dce3dd;border-radius:8px;padding:0 10px;font:inherit;color:inherit;margin-left:6px;background:#fff}@media(max-width:600px){.toolbar select{width:100%}.range-custom{flex-direction:column;align-items:stretch}.range-custom span{display:none}}
```

- [ ] **Step 3: `app.js` 필터 파이프라인**

`state` 선언에 `range:'all',from:'',to:'',publisher:'',keywords:[]`를 추가한다.

`function reportArticles(){...}` 바로 아래에 추가:

```js
const kstDate=value=>{const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(d);};
function shiftDate(iso,days){const d=new Date(`${iso}T00:00:00Z`);d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
function rangeBounds(){if(!state.query||state.range==='all')return null;if(state.range==='custom'){let from=state.from,to=state.to;if(from&&to&&from>to)[from,to]=[to,from];return {from,to};}const days=Number(state.range);return {from:shiftDate(state.today||kstDate(Date.now()),-(days-1)),to:''};}
function inRange(a,bounds){if(!bounds)return true;const d=kstDate(a.published_at);return Boolean(d)&&(!bounds.from||d>=bounds.from)&&(!bounds.to||d<=bounds.to);}
function baseArticles(){if(state.category===SAVED)return [...state.bookmarks.values()].sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))||String(b.published_at||'').localeCompare(String(a.published_at||'')));return state.query?state.index:reportArticles();}
function renderPublishers(list){const counts=new Map();list.forEach(a=>{if(a.source)counts.set(a.source,(counts.get(a.source)||0)+1);});const options=[...counts].sort((x,y)=>y[1]-x[1]||x[0].localeCompare(y[0]));if(!counts.has(state.publisher))state.publisher='';$('publisher').innerHTML='<option value="">전체 언론사</option>'+options.map(([s,n])=>`<option value="${esc(s)}">${esc(s)} (${n})</option>`).join('');$('publisher').value=state.publisher;}
function searchText(a){return [a.title,a.source,a.topic,a.date,...(Array.isArray(a.summary)?a.summary:[]),...(Array.isArray(a.related)?a.related.map(r=>r&&r.title):[])].join(' ').toLocaleLowerCase();}
```

`render()` 안에서 `const saved=state.category===SAVED;`부터 `if(state.query)articles=articles.filter(...)` 줄까지를 아래로 교체:

```js
  const saved=state.category===SAVED;
  let articles=baseArticles();renderPublishers(articles);
  if(state.category!=='전체'&&!saved)articles=articles.filter(a=>a.topic===state.category);
  if(state.publisher)articles=articles.filter(a=>a.source===state.publisher);
  const bounds=rangeBounds();if(bounds)articles=articles.filter(a=>inRange(a,bounds));
  if(state.query)articles=articles.filter(a=>searchText(a).includes(state.query));
  $('range').disabled=!state.query;$('range-custom').hidden=!(state.query&&state.range==='custom');
```

`$('more').onclick=...` 줄 아래에 핸들러 추가:

```js
$('range').onchange=()=>{state.range=$('range').value;state.limit=18;render();};
$('from').onchange=()=>{state.from=$('from').value;state.limit=18;render();};
$('to').onchange=()=>{state.to=$('to').value;state.limit=18;render();};
$('publisher').onchange=()=>{state.publisher=$('publisher').value;state.limit=18;render();};
```

- [ ] **Step 4: 구문 검사와 브라우저 확인**

Run: `node --check dist/app.js` → 출력 없음.
브라우저(`http://127.0.0.1:8765/` 강제 새로고침): (1) 툴바에 기간(비활성)·언론사 선택이 보인다. (2) 언론사 목록이 `언론사명 (n)` 건수 순이고 선택하면 카드가 그 언론사만 남는다. (3) 검색어를 입력하면 기간이 활성화되고 `최근 7일`을 고르면 오래된 결과가 빠진다. (4) `직접 입력`이면 날짜 입력 두 개가 나타나고 시작>종료로 넣어도 동작한다. (5) 400px 폭에서 세로 배치, 가로 스크롤 없음. (6) 콘솔 오류 없음.

- [ ] **Step 5: 커밋**

`git add -A && git commit -m "feat: publisher and published-date range filters"`

---

### Task 4: 화면 — 관련 보도 토글, 요약 키워드 강조

**Files:**
- Modify: `dist/app.js`, `dist/minimal.css`

**Interfaces:**
- Consumes: 기사 `related`, `GET /api/keywords` (`{rules:[{keyword,weight}]}`), Task 3의 `baseArticles`.
- Produces: `state.keywords`, `keywordsFor(a)`, `relatedList(a)`, `loadKeywords()`.

- [ ] **Step 1: CSS 추가**

`dist/minimal.css` 끝에 한 줄 추가:

```css
.related-toggle{align-self:flex-start;border:0;background:none;padding:0;color:#37563f;font-size:13px;text-decoration:underline;text-underline-offset:3px}.related{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:6px;font-size:13px;line-height:1.5}.related li{display:flex;gap:8px;align-items:baseline;min-width:0}.related span{color:#24704f;font-weight:700;flex-shrink:0}.related a{text-decoration:none;min-width:0;overflow-wrap:anywhere}.related a:hover{text-decoration:underline}.related time{color:#8a958b;flex-shrink:0;font-size:12px}.related li.read a{color:#a2ada4}.card p mark{background:#f3f7dc}
```

- [ ] **Step 2: `app.js` 키워드 로드·카드·핸들러**

`function card(a,extra='')` 줄 **앞**에 추가:

```js
function keywordsFor(a){return state.category===SAVED&&Array.isArray(a.keywords)?a.keywords:state.keywords;}
function relatedList(a){const items=(Array.isArray(a.related)?a.related:[]).filter(r=>r&&typeof r.url==='string');if(!items.length)return '';return `<button type="button" class="related-toggle" aria-expanded="false">관련 보도 ${items.length}건 ▸</button><ul class="related" hidden>${items.map(r=>`<li class="${state.read.has(r.url)?'read':''}"><span>${esc(r.source)}</span><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-related="${esc(r.url)}">${esc(r.title)}</a><time>${esc(dateText(r.published_at))}</time></li>`).join('')}</ul>`;}
async function loadKeywords(){try{const data=await json('/api/keywords');state.keywords=(data.rules||[]).map(r=>r&&r.keyword).filter(k=>typeof k==='string'&&k);}catch{state.keywords=[];}render();}
```

`card()`를 교체:

```js
function card(a,extra=''){const saved=state.bookmarks.has(a.url);const keys=keywordsFor(a);return `<article class="card${state.read.has(a.url)?' read':''}" data-url="${esc(a.url)}"><div class="card-top"><span class="category">${esc(a.topic)}</span><button type="button" class="bookmark" data-bookmark="${esc(a.url)}" aria-pressed="${saved}" aria-label="${saved?'북마크 해제':'북마크'}">${saved?'★':'☆'}</button></div><h2><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${highlight(a.title,a.keyword_matches)}</a></h2>${(Array.isArray(a.summary)?a.summary:[]).map(s=>`<p>${highlight(s,keys)}</p>`).join('')}<div class="meta">${esc(a.source)} · ${esc(dateText(a.published_at))} 발행</div>${relatedList(a)}${extra}</article>`;}
```

`toggleBookmark`의 저장 객체에 `related:(Array.isArray(a.related)?a.related:[]),keywords:state.keywords,`를 `keyword_matches:` 앞에 추가한다.

`$('articles').onclick` 핸들러에서 `const link=e.target.closest('h2 a');` 줄 **앞**에 두 줄 추가:

```js
  const toggle=e.target.closest('.related-toggle');if(toggle){const list=toggle.nextElementSibling;const open=list.hidden;list.hidden=!open;toggle.setAttribute('aria-expanded',String(open));toggle.textContent=toggle.textContent.replace(/[▸▾]$/,open?'▾':'▸');return;}
  const rel=e.target.closest('[data-related]');if(rel){markRead(rel.dataset.related);rel.closest('li').classList.add('read');return;}
```

`auxclick` 리스너를 교체:

```js
$('articles').addEventListener('auxclick',e=>{if(e.button!==1)return;const rel=e.target.closest('[data-related]');if(rel){markRead(rel.dataset.related);rel.closest('li').classList.add('read');return;}const link=e.target.closest('h2 a');if(link){markRead(link.closest('.card').dataset.url);link.closest('.card').classList.add('read');}});
```

시작 줄 `loadReport();loadArchive();poll();`을 `loadReport();loadArchive();loadKeywords();poll();`로 바꾼다.

`$('keyword-form').onsubmit` 안에서 저장 성공 직후(`$('keyword-status').textContent='저장했습니다. ...';` 앞)에 `state.keywords=(data.rules||[]).map(r=>r.keyword);render();`를 추가한다.

- [ ] **Step 3: 구문 검사와 브라우저 확인**

Run: `node --check dist/app.js` → 출력 없음.
브라우저: 현재 보고서는 1차 데이터라 `related`가 없으므로 (1) 요약 문장 안 키워드(`금리`, `AI` 등)에 연한 배경이 보인다, (2) 키워드 설정에서 키워드를 추가·저장하면 새로고침 없이 요약 강조가 바뀐다, (3) 콘솔에 오류가 없다. 관련 보도 토글은 Task 7의 실제 수집 후 확인한다. 임시로 콘솔에서 `state.report.topics[0].articles[0].related=[{url:'https://n.news.naver.com/mnews/article/001/1',title:'테스트 관련 기사',source:'테스트',published_at:'2026-09-14T09:00:00+09:00',section:'금융'}];render()`를 실행해 토글 펼침·접힘과 링크 읽음 처리를 확인한다.

- [ ] **Step 4: 커밋**

`git add -A && git commit -m "feat: related-story toggle and keyword highlight in summaries"`

---

### Task 5: 문서 갱신

**Files:**
- Modify: `README.md`, `AGENTS.md`

- [ ] **Step 1: README 수정**

다음 문단을 정확히 교체한다.

(1) 3행 소개문을:
```
네이버 경제 8개 섹션에서 발행 시각이 확인된 무료 기사를 선별하고, 날짜별 요약·검색·헤드라인·북마크와 같은 사건을 묶은 관련 보도를 제공합니다. 수집·요약 발췌에 모델 API를 사용하지 않습니다.
```

(2) "## 화면" 목록의 `- **키워드 강조**: ...` 줄을:
```
- **키워드 강조**: 제목과 요약에서 내 키워드와 일치한 부분에 배경색을 표시합니다.
- **관련 보도**: 같은 사건을 다룬 다른 언론사 기사는 대표 카드 아래 `관련 보도 n건`으로 접혀 있습니다(카드당 최대 4건). 관련 기사도 무료·발행 시각 검증을 통과한 것만 붙습니다.
- **기간·언론사 필터**: 검색 중에는 발행일 기준 기간(최근 7일/30일/직접 입력)을, 모든 화면에서 언론사를 골라 볼 수 있습니다.
```

(3) "무료 본문·발행 시각 검증을 통과한 기사만 남깁니다." 문단 끝에 한 문장 추가:
```
 제목의 글자 2-gram 유사도가 0.45 이상이고 숫자·방향어(상승/하락 등)가 어긋나지 않으면 같은 사건으로 보고 먼저 선택된 기사의 관련 보도로 묶습니다. 한도를 채운 뒤에는 이미 선택된 기사와 비슷한 제목만 섹션당 최대 8건 더 확인합니다.
```

(4) "요약은 본문 핵심 문장 발췌입니다." 문장을:
```
요약은 본문 문장 발췌입니다. 첫 문장(리드)과, 제목·내 키워드·수치와 가장 연관된 문장 하나를 고릅니다(제목 연관 발췌).
```

- [ ] **Step 2: AGENTS.md 수정**

(1) 고정 요구사항의 `- 섹션은 네이버에서 받은 분류를 그대로 사용한다. ...` 줄 다음에 추가:
```
- 유사 기사 판정은 제목 기준이다: `[…]`·괄호 제거 후 글자 2-gram Dice ≥ 0.45, 숫자 집합이 같거나 한쪽이 비어 있고, 방향어 쌍(상승/하락·증가/감소·매수/매도·흑자/적자·인상/인하·확대/축소·급등/급락·강세/약세)이 어긋나지 않을 때 같은 사건으로 본다. 관련 기사는 카드당 4건, 한도 이후 추가 본문 접근은 섹션당 8건까지다. 관련 기사도 무료·발행 시각·기간 검증을 통과해야 한다. 요약 점수는 순위에 반영하지 않는다.
```

(2) `- 요약은 본문 핵심 문장 발췌다. ...` 줄을:
```
- 요약은 본문 문장 발췌다(리드 + 제목·키워드·수치 연관 문장, `summary_method: 제목 연관 발췌`). AI 분석이나 증권사 의견으로 표현하지 않는다. 근거 없는 수치·전망·일정을 만들지 않는다.
```

(3) UI 허용 목록 줄에서 `키워드 강조, 키워드 설정 메뉴만 둔다.`를 `키워드 강조(제목·요약), 관련 보도 토글, 기간·언론사 필터, 키워드 설정 메뉴만 둔다.`로 바꾼다.

- [ ] **Step 3: 커밋**

`git add -A && git commit -m "docs: summary scoring, related grouping and search filters"`

---

### Task 6: 최종 검증 (실제 수집 1회)

- [ ] **Step 1: 자동 검증**

Run: `python -m unittest discover -s scripts -p "test_*.py"` → `OK`, 잡음 없음. `node --check dist/app.js` → 출력 없음.

- [ ] **Step 2: 실제 수집**

Run: `python scripts/collector.py; echo $LASTEXITCODE` → `{"ok": true, ..., "related": n}` 와 `0`.
Run: `python scripts/verify_report.py` → `{"verified": true, ...}`.
Run: `python -c "import json;d=json.load(open('data/latest.json',encoding='utf-8'));a=[a for t in d['topics'] for a in t['articles']];print(d['stats'],sum(1 for x in a if x['related']),a[0]['summary_method'])"` → `related` 수와 `제목 연관 발췌` 확인.

- [ ] **Step 3: 서버 재시작과 브라우저 확인**

PowerShell: `Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -like '*scripts*server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; Start-Process python -ArgumentList 'scripts/server.py' -WorkingDirectory (Get-Location) -WindowStyle Hidden`
브라우저에서: 관련 보도 토글 펼침·접힘, 관련 링크 읽음 처리, 요약 강조, 언론사 필터, 검색 + 기간 필터, 저장함 카드에 관련 보도 유지, 400px 폭, 콘솔 오류 0.

- [ ] **Step 4: 설계 문서 대조**

`docs/superpowers/specs/2026-09-14-quality-search-phase2-design.md` 1~6절 항목마다 구현 위치를 확인한다.
