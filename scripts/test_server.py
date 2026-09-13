import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import server
from naver_pipeline import KST

class ServerTests(unittest.TestCase):
    def test_parse_collect_request(self):
        allowed=['2026-09-14','2026-09-13','2026-09-12']
        self.assertIsNone(server.parse_collect_request(b'',allowed))
        self.assertIsNone(server.parse_collect_request(b'{}',allowed))
        self.assertIsNone(server.parse_collect_request(b'{"date":null}',allowed))
        self.assertEqual(server.parse_collect_request(b'{"date":"2026-09-12"}',allowed),'2026-09-12')
        for raw in (b'{"date":"2026-09-11"}',b'{"date":5}',b'[1]',b'not json',b'{"date":"2026-9-12"}'):
            with self.assertRaises(ValueError): server.parse_collect_request(raw,allowed)

    def test_status_payload_fields(self):
        now=datetime(2026,9,14,9,0,tzinfo=KST)
        with tempfile.TemporaryDirectory() as folder,patch('server.DATA',Path(folder)):
            (Path(folder)/'latest.json').write_text(json.dumps({'date':'2026-09-13'}),encoding='utf-8')
            (Path(folder)/'progress.json').write_text(json.dumps({'done':2,'total':8,'section':'증권','date':'2026-09-14'}),encoding='utf-8')
            with patch.dict(server.STATUS,{'running':False}):
                idle=server.status_payload(now)
            with patch.dict(server.STATUS,{'running':True}):
                busy=server.status_payload(now)
        self.assertEqual(idle['today'],'2026-09-14');self.assertEqual(idle['latest_date'],'2026-09-13')
        self.assertEqual(idle['collectable_dates'],['2026-09-14','2026-09-13','2026-09-12'])
        self.assertIsNone(idle['progress']);self.assertEqual(busy['progress']['done'],2)

    def test_status_payload_without_files(self):
        with tempfile.TemporaryDirectory() as folder,patch('server.DATA',Path(folder)),patch.dict(server.STATUS,{'running':True}):
            payload=server.status_payload()
        self.assertIsNone(payload['latest_date']);self.assertIsNone(payload['progress'])

    def test_messages_cover_exit_codes(self):
        self.assertEqual(set(server.MESSAGES),{0,1,2,3})

if __name__=='__main__': unittest.main()
