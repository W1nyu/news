import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from keyword_settings import keyword_score, validate_rules, save_rules, load_rules


class KeywordTests(unittest.TestCase):
    def test_signed_additive_score_and_stable_order(self):
        rules=[{'keyword':'반도체','weight':5},{'keyword':'실적','weight':-2},{'keyword':'AI','weight':3}]
        self.assertEqual(keyword_score('반도체 실적 ai',rules),6)
        self.assertEqual(keyword_score('실적 실적',rules),-2)
        titles=['실적','일반 뉴스','반도체','다른 뉴스']
        self.assertEqual(sorted(titles,key=lambda t:keyword_score(t,rules),reverse=True),['반도체','일반 뉴스','다른 뉴스','실적'])

    def test_invalid_and_duplicate(self):
        for rules in (None,[{'keyword':'','weight':1}],[{'keyword':'AI','weight':101}],
                      [{'keyword':'AI','weight':True}],[{'keyword':'AI','weight':1.5}],
                      [{'keyword':'AI','weight':1},{'keyword':' ai ','weight':2}]):
            with self.assertRaises(ValueError): validate_rules(rules)

    def test_persist_edit_delete_and_preserve_on_error(self):
        with tempfile.TemporaryDirectory() as folder,patch('keyword_settings.PATH',Path(folder)/'keywords.json'):
            rules=[{'keyword':'금리','weight':-5}]
            save_rules(rules);self.assertEqual(load_rules(),rules)
            with self.assertRaises(ValueError):save_rules([{'keyword':'','weight':0}])
            self.assertEqual(load_rules(),rules)
            save_rules([]);self.assertEqual(load_rules(),[])

    def test_legacy_keywords(self):
        with patch('keyword_settings.PATH') as path:
            path.read_text.return_value=json.dumps({'keywords':['AI']})
            self.assertEqual(load_rules(),[{'keyword':'AI','weight':1}])
