"""Development-only report assertions and PDF contact sheet (not daily operation)."""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from pypdf import PdfReader
from PIL import Image, ImageOps, ImageDraw

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
reader=PdfReader(ROOT/'output/pdf/economy-report.pdf')
normalize=lambda text: re.sub(r'\s','',text)
pdftext=normalize(''.join(p.extract_text() for p in reader.pages))
assert all(normalize(a['title']) in pdftext for a in articles)
assert len(reader.outline)==8
assert all(abs(float(p.mediabox.width)-595.28)<1 for p in reader.pages)
paths=sorted((ROOT/'tmp/pdfs').glob('final-*.png'))
if paths:
    sheet=Image.new('RGB',(5*284,((len(paths)+4)//5)*420),'#ddd')
    for i,path in enumerate(paths):
        thumb=ImageOps.contain(Image.open(path).convert('RGB'),(278,394))
        x,y=(i%5)*284,(i//5)*420
        sheet.paste(thumb,(x,y));ImageDraw.Draw(sheet).text((x+8,y+399),str(i+1),fill='black')
    sheet.save(ROOT/'tmp/pdfs/contact.png')
print(json.dumps({'verified':True,'selected':len(articles),'pages':len(reader.pages),'sections':{t['name']:len(t['articles']) for t in report['topics']}},ensure_ascii=False))
