import json
import tempfile
import unittest
from pathlib import Path
from telegram_watchlist import filter_report_rows
from common import PipelineError

class GroupWatchlistTests(unittest.TestCase):
    def test_exact_models_and_previous_use_separate_group_config(self):
        rows=[{'category':'Điện thoại','model_name':'iPhone 16','chain_name':c} for c in ['TGDD','FPT Shop']]
        rows += [{'category':'Điện thoại','model_name':'iPhone 16 Pro'}, {'product_name':'Unknown'}]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'group.json'
            path.write_text(json.dumps({'version':1,'hidden_models':[{'category':'Điện thoại','model_name':'IPHONE 16'}]}))
            current, previous=filter_report_rows(rows,rows,path)
            self.assertEqual(current,rows[2:]);self.assertEqual(previous,rows[2:])
        self.assertEqual(filter_report_rows(rows,rows,None),(rows,rows))
    def test_invalid_config_fails_instead_of_sending_wrong_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'group.json';path.write_text('{}')
            with self.assertRaises(PipelineError): filter_report_rows([],[],path)
