"""Public article inspection and transparent extractive summaries; no login bypass."""
import json
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

SELECTORS = {
    'naver': '#dic_area', 'daum': '.article_view',
    'hankyung': '#articletxt, .article-body',
    'mk': '.news_cnt_detail_wrap, #article_body',
    'economy21': '#article-view-content-div',
}
CHECKPOINTS = {
    '기준금리·통화정책': '다음 통화정책 발표와 시장금리 변화를 함께 확인하세요.',
    '환율·외환': '환율 변동이 수입 원가와 수출기업 실적에 미치는 영향을 확인하세요.',
    '물가·생활경제': '일시적 가격 변동인지, 소비자물가 전반으로 확산되는지 확인하세요.',
    '부동산·가계대출': '정책 시행일, 적용 대상과 실제 대출 조건을 확인하세요.',
    '증시·투자': '가격 움직임과 기업 실적·수급 변화를 구분해 확인하세요.',
    '반도체·AI': '투자 발표가 실제 매출과 이익으로 연결되는 시점을 확인하세요.',
}

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

def publication_date(soup):
    candidates = []
    for meta in soup.select('meta[property="article:published_time"], meta[name="pubdate"], meta[itemprop="datePublished"]'):
        candidates.append((meta.get('content'), 'publication metadata'))
    for stamp in soup.select('.media_end_head_info_datestamp_time[data-date-time], time[itemprop="datePublished"][datetime]'):
        candidates.append((stamp.get('data-date-time') or stamp.get('datetime'), 'publication element'))
    def walk(value):
        if isinstance(value, dict):
            types = value.get('@type', [])
            if isinstance(types, str): types = [types]
            if any(t in ('NewsArticle', 'Article', 'ReportageNewsArticle') for t in types):
                candidates.append((value.get('datePublished'), 'article structured data'))
            for item in value.values(): walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    for script in soup.select('script[type="application/ld+json"]'):
        try: walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError): pass
    for raw, evidence in candidates:
        if not isinstance(raw, str) or not re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}', raw):
            continue
        try:
            stamp = datetime.fromisoformat(raw.replace('Z', '+00:00'))
            if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone(timedelta(hours=9)))
            return stamp.isoformat(), evidence
        except ValueError: continue
    return None, None

def inspect_article(page, source_id, title_hint=None, keywords=()):
    soup = BeautifulSoup(page, 'html.parser')
    # Machine-readable paid-access declarations take precedence over a teaser.
    if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', page, re.I):
        return None, 'paid'
    for meta in soup.select('meta'):
        key = str(meta.get('name', meta.get('property', ''))).lower()
        val = str(meta.get('content', '')).lower()
        if key in ('isaccessibleforfree', 'article:paid', 'paid', 'premium') and val in ('false' if key == 'isaccessibleforfree' else 'true', '1'):
            return None, 'paid'
    body = soup.select_one(SELECTORS[source_id])
    if body is None:
        return None, 'unverified'
    # Check declarations before removing headings or emphasis from the summary body.
    visible = soup.get_text(' ', strip=True)
    if re.search(r'유료\s*(?:기사|콘텐츠|컨텐츠|플랫폼)|구독자\s*전용|프리미엄\s*전용|회원\s*전용|구독\s*후\s*(?:읽|이용)|로그인\s*후\s*(?:읽|이용)|기사의?\s*전문.*구독', visible):
        return None, 'paid'
    for node in body.select('script, style, iframe, figure, .ad, .advertisement, strong, h2, h3, .img_desc, .end_photo_org'):
        node.decompose()
    text = body.get_text(' ', strip=True)
    if len(text) < 250:
        return None, 'unverified'
    title = soup.select_one('meta[property="og:title"]')
    published_value, date_evidence = publication_date(soup)
    if not published_value:
        return None, 'date_unknown'
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
    return {'title': title.get('content') if title else None,
            'published_at': published_value,
            'date_evidence': date_evidence,
            'summary': summary, 'summary_method': '제목 연관 발췌',
            'access': 'public_checked'}, None
