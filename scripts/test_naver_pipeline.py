import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from naver_pipeline import ROOT, article_url, candidates, collect, valid_time, KST, collectable_dates, published_date, save_report

class NaverPipelineTests(unittest.TestCase):
    def test_external_domain_rejected(self):
        self.assertIsNone(article_url('https://evil.example/article/001/123'))
        self.assertEqual(article_url('https://n.news.naver.com/mnews/hotissue/article/001/123?x=1'), 'https://n.news.naver.com/mnews/article/001/123')

    def test_only_section_list_not_sidebar(self):
        page='<a class="sa_text_title" href="https://n.news.naver.com/mnews/article/001/123">제외할 다른 추천 기사</a><div class="section_latest_article"><a class="sa_text_title" href="https://n.news.naver.com/mnews/article/001/456">실제 경제 섹션에 실린 기사</a></div>'
        self.assertEqual(len(candidates(page)),1)

    def test_dates_reject_future_naive_and_old(self):
        now=datetime.now(KST)
        self.assertFalse(valid_time(None,now,72))
        self.assertFalse(valid_time(now.replace(tzinfo=None).isoformat(),now,72))
        self.assertFalse(valid_time((now+timedelta(seconds=1)).isoformat(),now,72))
        self.assertFalse(valid_time((now-timedelta(hours=73)).isoformat(),now,72))
        self.assertTrue(valid_time((now-timedelta(hours=1)).isoformat(),now,72))

    def test_quota_and_all_eight_sections(self):
        sections=json.loads((ROOT/'config/sections.json').read_text(encoding='utf-8'))['sections']
        def fake_fetch(url):
            if '/breakingnews/' in url:
                sid=url.rsplit('/',1)[-1]
                return '<div class="section_latest_article">'+''.join(f'<a class="sa_text_title" href="https://n.news.naver.com/mnews/article/999/{sid}{n}">검증용 경제 기사 제목 {sid} {n}</a>' for n in range(12))+'</div>'
            return '<div>'+url+'</div>'
        def fake_inspect(page,source):
            return {'title':page.removesuffix('</div>').rsplit('/',1)[-1], 'published_at':(datetime.now(KST)-timedelta(minutes=1)).isoformat(), 'summary':['검증용 핵심 문장입니다.'], 'access':'public_checked'},None
        with patch('naver_pipeline.fetch',side_effect=fake_fetch),patch('naver_pipeline.inspect_article',side_effect=fake_inspect),patch('naver_pipeline.atomic_json'),patch('naver_pipeline.time.sleep'):
            report=collect()
        self.assertEqual(len(report['topics']),8)
        self.assertEqual(report['stats']['selected'],42)
        self.assertEqual([len(t['articles']) for t in report['topics']],[s['limit'] for s in sections])
        self.assertTrue(all(a['source_id']=='naver' for t in report['topics'] for a in t['articles']))

    def test_shortfall_keeps_safety_filters(self):
        page='<div class="section_latest_article"><a class="sa_text_title" href="https://n.news.naver.com/mnews/article/999/9000">발행일 없는 검증용 기사 제목</a></div>'
        with patch('naver_pipeline.fetch',return_value=page),patch('naver_pipeline.inspect_article',return_value=(None,'date_missing')),patch('naver_pipeline.atomic_json'),patch('naver_pipeline.time.sleep'):
            report=collect()
        self.assertEqual(report['stats']['selected'],0)
        self.assertTrue(all(s['status']=='shortfall' and s['shortfall']==3 for s in report['source_results']))

    def test_collectable_dates_three_days_kst(self):
        now=datetime(2026,9,14,0,30,tzinfo=KST)
        self.assertEqual(collectable_dates(now),['2026-09-14','2026-09-13','2026-09-12'])

    def test_published_date_uses_kst_midnight_boundary(self):
        self.assertEqual(published_date('2026-09-13T23:59:59+09:00'),'2026-09-13')
        self.assertEqual(published_date('2026-09-14T00:00:00+09:00'),'2026-09-14')
        self.assertEqual(published_date('2026-09-13T15:00:00+00:00'),'2026-09-14')
        self.assertIsNone(published_date(None));self.assertIsNone(published_date('nope'))

    def test_target_date_filters_and_progress_called(self):
        now=datetime.now(KST);yesterday=(now-timedelta(days=1)).date().isoformat()
        def fake_fetch(url):
            if '/breakingnews/' in url:
                sid=url.rsplit('/',1)[-1]
                return '<div class="section_latest_article">'+''.join(f'<a class="sa_text_title" href="https://n.news.naver.com/mnews/article/999/{sid}{n}">검증용 경제 기사 제목 {sid} {n}</a>' for n in range(12))+'</div>'
            return '<div>'+url+'</div>'
        def fake_inspect(page,source):
            n=int(page.removesuffix('</div>')[-1])
            stamp=(now-timedelta(minutes=1)) if n%2 else (now-timedelta(days=1))
            return {'title':page.removesuffix('</div>').rsplit('/',1)[-1],'published_at':stamp.isoformat(),'summary':['검증용 핵심 문장입니다.'],'access':'public_checked'},None
        calls=[]
        with patch('naver_pipeline.fetch',side_effect=fake_fetch),patch('naver_pipeline.inspect_article',side_effect=fake_inspect),patch('naver_pipeline.atomic_json'),patch('naver_pipeline.time.sleep'):
            report=collect(target_date=yesterday,progress=lambda d,t,s:calls.append((d,t,s)))
        self.assertEqual(report['date'],yesterday)
        self.assertTrue(all(published_date(a['published_at'])==yesterday for t in report['topics'] for a in t['articles']))
        self.assertGreater(report['stats']['selected'],0)
        self.assertGreater(report['excluded'].get('date_outside_target',0),0)
        self.assertEqual(calls[0],(0,8,''));self.assertEqual(len(calls),9);self.assertEqual(calls[-1][0],8)

    def test_save_report_keeps_latest_date(self):
        def payload(date):
            return {'schema_version':4,'date':date,'generated_at':f'{date}T08:00:00+09:00','topics':[{'id':'259','name':'금융','articles':[{'url':f'https://n.news.naver.com/mnews/article/001/{date[-2:]}','title':f'{date} 기사','summary':['요약'],'published_at':f'{date}T07:00:00+09:00','source':'테스트','source_id':'naver'}]}],
                    'stats':{'selected':1},'source_results':[],'excluded':{},'pdf_url':'reports/x.pdf'}
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder)/'data';public=Path(folder)/'public'
            with patch('naver_pipeline.DATA',data),patch('naver_pipeline.PUBLIC',public):
                save_report(payload('2026-09-13'))
                save_report(payload('2026-09-12'))
                latest=json.loads((data/'latest.json').read_text(encoding='utf-8'))
                self.assertEqual(latest['date'],'2026-09-13')
                self.assertEqual(json.loads((public/'latest.json').read_text(encoding='utf-8'))['date'],'2026-09-13')
                self.assertNotIn('pdf_url',latest)
                self.assertEqual([h['date'] for h in json.loads((data/'history.json').read_text(encoding='utf-8'))],['2026-09-13','2026-09-12'])
                self.assertEqual(json.loads((data/'run-status.json').read_text(encoding='utf-8'))['date'],'2026-09-12')
                self.assertEqual(len(json.loads((public/'search.json').read_text(encoding='utf-8'))),2)

if __name__=='__main__': unittest.main()
