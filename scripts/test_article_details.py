import unittest
from article_details import inspect_article, publication_date
from bs4 import BeautifulSoup

BODY = '한국은행은 오늘 통화정책 방향을 발표하고 금융시장 변화와 가계부채 추이를 점검할 계획이라고 밝혔다. ' * 5

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

if __name__ == '__main__':
    unittest.main()
