import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from naver_pipeline import ROOT, article_url, candidates, collect, valid_time, KST, collectable_dates, published_date, save_report, similar

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
        def fake_inspect(page,source,**kwargs):
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
        today_stamp=now-timedelta(minutes=1)
        if today_stamp.date()!=now.date(): today_stamp=now.replace(hour=0,minute=0,second=1,microsecond=0)
        yesterday_stamp=(now-timedelta(days=1)).replace(hour=12,minute=0,second=0,microsecond=0)
        def fake_inspect(page,source,**kwargs):
            n=int(page.removesuffix('</div>')[-1])
            stamp=today_stamp if n%2 else yesterday_stamp
            return {'title':page.removesuffix('</div>').rsplit('/',1)[-1],'published_at':stamp.isoformat(),'summary':['검증용 핵심 문장입니다.'],'access':'public_checked'},None
        calls=[]
        with patch('naver_pipeline.fetch',side_effect=fake_fetch),patch('naver_pipeline.inspect_article',side_effect=fake_inspect),patch('naver_pipeline.atomic_json'),patch('naver_pipeline.time.sleep'):
            report=collect(target_date=yesterday,progress=lambda d,t,s:calls.append((d,t,s)))
        self.assertEqual(report['date'],yesterday)
        self.assertTrue(all(published_date(a['published_at'])==yesterday for t in report['topics'] for a in t['articles']))
        self.assertGreater(report['stats']['selected'],0)
        self.assertGreater(report['excluded'].get('date_outside_target',0),0)
        self.assertEqual(calls[0],(0,8,''));self.assertEqual(len(calls),9);self.assertEqual(calls[-1][0],8)

    def test_similar_titles(self):
        self.assertTrue(similar('삼성전자가 반도체 공장 증설 발표','삼성전자는 반도체 공장 증설 발표'))
        self.assertTrue(similar('[단독] 삼성전자 반도체 공장 증설','삼성전자 반도체 공장 증설'))
        self.assertFalse(similar('코스피 2% 상승 마감','코스피 3% 상승 마감'))
        self.assertFalse(similar('코스피 2% 상승 마감','코스피 2% 하락 마감'))
        self.assertFalse(similar('삼성전자 반도체 공장 증설','한국은행 기준금리 동결 결정'))
        self.assertTrue(similar('환율 1,400원 돌파','환율 1400원 돌파'))
        self.assertFalse(similar('환율 1,400원 돌파','환율 1,500원 돌파'))
        self.assertFalse(similar('삼성전자 반도체 공장 증설 검토','삼성전자 반도체 공장 축소 검토'))
        self.assertFalse(similar('증권사, 목표주가 상향 조정','증권사, 목표주가 하향 조정'))

    def test_only_positive_keywords_feed_summary(self):
        rules=[{'keyword':'반도체','weight':3},{'keyword':'실적','weight':-2},{'keyword':'AI','weight':0}]
        page='<div class="section_latest_article"><a class="sa_text_title" href="https://n.news.naver.com/mnews/article/999/1">검증용 반도체 실적 기사 제목입니다</a></div>'
        with patch('naver_pipeline.fetch',return_value=page),patch('naver_pipeline.load_rules',return_value=rules),patch('naver_pipeline.inspect_article',return_value=(None,'date_missing')) as inspected,patch('naver_pipeline.atomic_json'),patch('naver_pipeline.time.sleep'):
            collect()
        self.assertEqual(inspected.call_args.kwargs['keywords'],['반도체'])

    def _grouping_run(self,variants_for,variants_first=False,inspect_title=None):
        """variants_for(event_index) -> list of variant suffixes; returns (report, fetch mock).
        inspect_title(url) -> title override for the verified article, or None to fall back to the list title."""
        events=['한국은행 기준금리 동결 결정','삼성전자 반도체 공장 증설 발표','서울 아파트 거래량 급감','원달러 환율 급등세 지속','정부 추경 편성 논의 착수','코스피 외국인 순매수 전환']
        def titles(sid):
            base=[f'{e} {sid}' for e in events]
            extra=[f'{e} {sid}{suffix}' for i,e in enumerate(events) for suffix in variants_for(i)]
            return extra+base if variants_first else base+extra
        def fake_fetch(url):
            if '/breakingnews/' in url:
                sid=url.rsplit('/',1)[-1]
                return '<div class="section_latest_article">'+''.join(f'<a class="sa_text_title" href="https://n.news.naver.com/mnews/article/999/{sid}{n:02d}">{t}</a>' for n,t in enumerate(titles(sid)))+'</div>'
            return '<div>'+url+'</div>'
        def fake_inspect(page,source,**kwargs):
            title=inspect_title(page.removeprefix('<div>').removesuffix('</div>')) if inspect_title else None
            return {'title':title,'published_at':(datetime.now(KST)-timedelta(minutes=1)).isoformat(),'summary':['검증용 핵심 문장입니다.'],'access':'public_checked'},None
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
        # 6 sections have limit 6 (1 list + 12 examine = 13 fetches each) and 2 have limit 3
        # (1 list + 3 leaders + 3 matching extras = 7 fetches each): 6*13+2*7=92.
        self.assertEqual(fetched.call_count,92)

    def test_similar_story_with_full_leader_is_dropped_not_selected(self):
        # Five variants of event 0 arrive first: the first becomes the card, four attach, then the original event-0 story overflows and never becomes a card.
        report,fetched=self._grouping_run(lambda i:[' 시장 반응',' 배경은',' 전망은',' 영향은',' 후속 조치'] if i==0 else [],variants_first=True)
        first=report['topics'][0]['articles']
        self.assertEqual(len(first),6)
        self.assertEqual(len(first[0]['related']),4)
        self.assertEqual(report['excluded']['grouped_overflow'],8)
        self.assertTrue(all(not similar(a['title'],first[0]['title']) for a in first[1:]))

    def test_ungrouped_extra_fetch_frees_fingerprint_for_later_sections(self):
        # One extra per section (event 0's variant) verifies to a completely different title
        # that matches no leader; the drop must free its fingerprint so later sections
        # (same variant text) are not wrongly rejected as duplicate.
        def inspect_title(url):
            index=int(url[-2:])
            return f'완전히 다른 검증 제목 {url[-2:]}' if index>=6 else None
        report,fetched=self._grouping_run(lambda i:[' 시장 반응'] if i==0 else [],inspect_title=inspect_title)
        self.assertGreater(report['excluded']['ungrouped'],0)
        self.assertEqual(report['stats']['related'],0)
        self.assertEqual(report['excluded'].get('duplicate',0),0)

    def test_related_cap_per_card(self):
        report,fetched=self._grouping_run(lambda i:[' 시장 반응',' 배경은',' 전망은',' 영향은',' 후속 조치',' 추가 발표'] if i==0 else [])
        first=report['topics'][0]['articles']
        self.assertEqual(len(first[0]['related']),4)
        # 6 limit-6 sections: 1+6+4=11 fetches each; 2 limit-3 sections: 1+3+4=8 each: 6*11+2*8=82.
        self.assertEqual(fetched.call_count,82)

    def test_extra_fetch_limit_per_section(self):
        report,fetched=self._grouping_run(lambda i:[' 시장 반응',' 배경은'] if i<5 else [])
        first=report['topics'][0]['articles']
        self.assertEqual(sum(len(a['related']) for a in first),8)
        # 6 limit-6 sections: 1+6+8=15 fetches each; 2 limit-3 sections: 1+3+6=10 each: 6*15+2*10=110.
        self.assertEqual(fetched.call_count,110)

    def test_save_report_survives_malformed_archive_file(self):
        def payload(date):
            return {'schema_version':4,'date':date,'generated_at':f'{date}T08:00:00+09:00','topics':[{'id':'259','name':'금융','articles':[{'url':f'https://n.news.naver.com/mnews/article/001/{date[-2:]}','title':f'{date} 기사','summary':['요약'],'published_at':f'{date}T07:00:00+09:00','source':'테스트','source_id':'naver'}]}],
                    'stats':{'selected':1},'source_results':[],'excluded':{}}
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder)/'data';public=Path(folder)/'public'
            data.mkdir(parents=True)
            (data/'2026-09-10.json').write_text(json.dumps({'schema_version':4,'date':'2026-09-10'}),encoding='utf-8')
            with patch('naver_pipeline.DATA',data),patch('naver_pipeline.PUBLIC',public):
                save_report(payload('2026-09-13'))
                self.assertEqual([h['date'] for h in json.loads((data/'history.json').read_text(encoding='utf-8'))],['2026-09-13'])

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
