"""Development-only report assertions (not daily operation)."""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'data/latest.json').read_text(encoding='utf-8'))
sections=json.loads((ROOT/'config/sections.json').read_text(encoding='utf-8'))['sections']
articles=[a for t in report['topics'] for a in t['articles']]
assert len({a['url'] for a in articles})==len(articles)
for topic,section in zip(report['topics'],sections):
    assert topic['id']==section['id']
    assert section['minimum']<=len(topic['articles'])<=section['limit']
for a in articles:
    assert urlparse(a['url']).hostname=='n.news.naver.com' and a['source_id']=='naver'
    assert a['access']=='public_checked' and a['date_evidence'] and a['summary']
    delta=datetime.fromisoformat(report['generated_at'])-datetime.fromisoformat(a['published_at'])
    assert 0<=delta.total_seconds()<=72*3600
    assert not re.search(r'유료\s*(기사|플랫폼|콘텐츠|컨텐츠)|회원\s*전용',' '.join(a['summary']))
assert 'pdf_url' not in report
print(json.dumps({'verified':True,'selected':len(articles),'sections':{t['name']:len(t['articles']) for t in report['topics']}},ensure_ascii=False))
