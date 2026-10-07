import json,unittest
from adapters.viettel_preorder import tree_rows
from common import PipelineError
class PreorderTests(unittest.TestCase):
 def test_json_and_website_wrapper_only(self):
  row={'Product_ID':'1','Title':"Phone's name"}
  self.assertEqual(tree_rows(json.dumps({'stt':1,'data':[row]})),[row])
  text="{ stt: 1, msg: 'OK', data: '"+json.dumps([row]).replace("'","\\'")+"' }"
  self.assertEqual(tree_rows(text),[row])
 def test_executable_or_wrong_contract_rejected(self):
  for text in ["{stt:1,msg:'OK',data:'[]'};process.exit()", "{stt:0,msg:'OK',data:'[]'}", '{"stt":1,"data":{}}', 'null']:
   with self.assertRaises(PipelineError):tree_rows(text)
