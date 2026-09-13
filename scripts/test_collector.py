import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import collector
from naver_pipeline import collectable_dates

class CollectorTests(unittest.TestCase):
    def test_resolve_date(self):
        allowed=collectable_dates()
        self.assertIsNone(collector.resolve_date(None))
        self.assertEqual(collector.resolve_date(allowed[2]),allowed[2])
        for bad in ('2020-01-01','2026-9-1','내일','2099-12-31'):
            with self.assertRaises(ValueError): collector.resolve_date(bad)

    def test_progress_writer_and_cleanup(self):
        with tempfile.TemporaryDirectory() as folder,patch('collector.PROGRESS',Path(folder)/'progress.json'):
            write=collector.progress_writer('2026-09-14')
            write(0,8,'');write(3,8,'산업/재계')
            data=json.loads(collector.PROGRESS.read_text(encoding='utf-8'))
            self.assertEqual((data['done'],data['total'],data['section'],data['date']),(3,8,'산업/재계','2026-09-14'))
            self.assertIn('started_at',data)
            collector.clear_progress();self.assertFalse(collector.PROGRESS.exists())
            collector.clear_progress()

    def test_main_returns_3_for_bad_date(self):
        with patch('sys.argv',['collector.py','--date','2000-01-01']):
            self.assertEqual(collector.main(),3)

    def test_main_passes_date_and_clears_progress(self):
        allowed=collectable_dates()
        with tempfile.TemporaryDirectory() as folder,patch('collector.PROGRESS',Path(folder)/'progress.json'),\
             patch('sys.argv',['collector.py','--date',allowed[1]]),\
             patch('collector.collect',return_value={'date':allowed[1],'stats':{'selected':1},'source_results':[],'excluded':{}}) as fake,\
             patch('collector.save_report') as saved,patch('collector.collection_lock'):
            code=collector.main()
        self.assertEqual(code,0)
        self.assertEqual(fake.call_args.kwargs['target_date'],allowed[1])
        self.assertTrue(callable(fake.call_args.kwargs['progress']))
        saved.assert_called_once()
        self.assertFalse((Path(folder)/'progress.json').exists())

if __name__=='__main__': unittest.main()
