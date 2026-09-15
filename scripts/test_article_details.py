import unittest
from article_details import inspect_article, publication_date, pick_summary, dice, bigrams
from bs4 import BeautifulSoup

BODY = '한국은행은 오늘 통화정책 방향을 발표하고 금융시장 변화와 가계부채 추이를 점검할 계획이라고 밝혔다. ' * 5
LEAD='정부가 오늘 새로운 경제 대책을 발표하며 시장 참여자들의 관심이 집중되고 있다.'
FILLERS=['관계자들은 향후 상황을 지켜보며 대응 방안을 논의할 예정이라고 전했다.',
         '전문가들은 이번 조치가 단기적으로는 큰 변화를 만들지 않을 것으로 보고 있다.',
         '한편 업계에서는 추가적인 세부 지침이 나올 때까지 신중한 태도를 유지하고 있다.',
         '시장에서는 정책 효과를 둘러싼 다양한 해석이 나오고 있으며 관련 논의가 이어지고 있다.']
RELATED='삼성전자 반도체 공장 증설 계획은 오는 2027년까지 20조원을 투자하는 내용이다.'
TITLE='삼성전자 반도체 공장 증설에 20조원 투자'
META='<meta property="article:published_time" content="2026-09-12T01:00:00+09:00">'

class ArticleTests(unittest.TestCase):
    def test_paid_schema_excludes_even_with_body(self):
        article, reason = inspect_article('<script>{"isAccessibleForFree":false}</script><div id="dic_area">' + BODY + '</div>', 'naver')
        self.assertIsNone(article)
        self.assertEqual(reason, 'paid')

    def test_teaser_excluded(self):
        self.assertEqual(inspect_article('<div id="dic_area">짧은 미리보기</div>', 'naver')[1], 'unverified')

    def test_unknown_markup_excluded(self):
        self.assertEqual(inspect_article('<main>' + BODY + '</main>', 'naver')[1], 'unverified')

    def test_free_article_uses_body(self):
        article, reason = inspect_article('<meta property="article:published_time" content="2026-09-12T01:00:00+09:00"><div id="dic_area">' + BODY + '</div>', 'naver')
        self.assertIsNone(reason)
        self.assertTrue(article['summary'])
        self.assertLessEqual(sum(len(s.split()) for s in article['summary']), 70)

    def test_members_only_excluded(self):
        self.assertEqual(inspect_article('<div id="dic_area">회원 전용 ' + BODY + '</div>', 'naver')[1], 'paid')

    def test_paid_platform_and_emphasis_checked_before_cleanup(self):
        self.assertEqual(inspect_article('<div id="dic_area"><strong>투자 전문 유료 플랫폼에 실린 기사입니다.</strong>'+BODY+'</div>','naver')[1],'paid')

    def test_unknown_date_excluded(self):
        self.assertEqual(inspect_article('<div id="dic_area">'+BODY+'</div>', 'naver')[1], 'date_unknown')

    def test_modified_date_is_not_publication(self):
        self.assertEqual(publication_date(BeautifulSoup('<meta property="article:modified_time" content="2026-09-12T01:00:00+09:00"><time datetime="2026-09-12T01:00:00+09:00"></time>', 'html.parser')), (None,None))

    def test_invalid_date_is_rejected(self):
        self.assertEqual(publication_date(BeautifulSoup('<meta property="article:published_time" content="2026-99-12T01:00:00">','html.parser')), (None,None))

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

    def test_byline_prefix_stripped_from_lead(self):
        body=' '.join(['[이데일리 최정훈 기자] '+LEAD,*FILLERS,RELATED])
        article,reason=inspect_article(META+'<div id="dic_area">'+body+'</div>','naver')
        self.assertIsNone(reason)
        self.assertEqual(article['summary'][0],LEAD)

    def test_keyword_bonus_without_title(self):
        keyworded='금리 인상 여부가 시장의 최대 관심사로 떠오르고 있다는 분석이 나온다.'
        self.assertEqual(pick_summary([LEAD,FILLERS[0],keyworded],'',('금리',)),[LEAD,keyworded])

    def test_near_duplicate_of_lead_skipped(self):
        variant=LEAD.replace('집중되고','쏠리고')
        self.assertEqual(pick_summary([LEAD,variant,FILLERS[0]]),[LEAD,FILLERS[0]])

    def test_without_hints_falls_back_to_order(self):
        self.assertEqual(pick_summary([LEAD,*FILLERS]),[LEAD,FILLERS[0]])
        self.assertEqual(pick_summary([]),[])

if __name__ == '__main__':
    unittest.main()
