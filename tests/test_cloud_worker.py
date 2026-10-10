"""Kiểm tra giao thức công bố cloud: atomic RPC, giữ SKU khác và chặn kênh không hợp lệ.
Không truy cập Supabase hoặc website thật.
"""
import tempfile,unittest,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from tools import cloud_worker as cw
from common import PipelineError
class CloudWorkerTests(unittest.TestCase):
 def test_bootstrap_uses_vietnam_dates_latest_sku_and_keeps_original_timestamps(self):
  first={'slug':'cellphones','sku':'a','observed_at':'2026-10-06T18:00:00Z','promo_price':100}
  last={**first,'observed_at':'2026-10-07T09:00:00+07:00','promo_price':None}
  previous={**first,'observed_at':'2026-10-06T10:00:00+07:00'}
  source={'slug':'cellphones','updated':'old'}
  data={'rows':[first,last,previous,{**last,'slug':'tgdd'}],'sources':[source]}
  snapshots=dict(cw.snapshot_payloads(data,'cellphones'))
  self.assertEqual(list(snapshots),['2026-10-06','2026-10-07'])
  self.assertEqual(snapshots['2026-10-07']['rows'],[last])
  self.assertEqual(snapshots['2026-10-07']['source']['updated'],last['observed_at'])
  self.assertEqual(source['updated'],'old')
 def test_bootstrap_rejects_naive_timestamp_instead_of_inventing_day(self):
  with self.assertRaises(PipelineError):
   list(cw.snapshot_payloads({'rows':[{'slug':'tgdd','sku':'a','observed_at':'2026-10-07T10:00:00'}]},'tgdd'))
 def settings(self):return {'apple_colors':{'revision':1,'value':{'version':1,'products':[{'model':'iPhone 17 Pro Max','color':None,'aliases':[]}]}},'apple_models':{'value':{'models':[]}}}
 def test_price_and_snapshot_are_one_rpc_and_other_model_retained(self):
  db=MagicMock();db.rpc.return_value.execute.return_value.data='run-id'
  row={'chain_name':'CellphoneS','sku':'cps-123','variant_id':'123','color_evidence':{'model':'iPhone 17 Pro Max','product_code':'123','verified_at':'2026-10-07T15:00:00+07:00'},'product_name':'iPhone 17 Pro Max 256GB','brand':'Apple','category':'Điện thoại','model_name':'iPhone 17 Pro Max','color':None,'promo_price':34990000,'original_price':None,'promo_text':'','source_url':'https://cellphones.com.vn/iphone-17-pro-max.html','observed_at':'2026-10-07T15:00:00+07:00'}
  old={'rows':[{'sku':'cps-old','apple_model':'iPhone 16','observed_at':'2026-10-06T10:00:00+07:00','promo_price':20000000}]}
  job={'id':'job','kind':'verify_prices','payload':{'model':'iPhone 17 Pro Max','channels':['cellphones'],'expected_revision':1}}
  with tempfile.TemporaryDirectory() as temp,patch.object(cw,'ROOT',Path(temp)),patch.object(cw,'materialize_catalog',return_value={'run_id':'catalog','ready':1,'total':1,'review':0}),patch.object(cw,'latest_payload',return_value=old),patch.object(cw,'run',return_value=SimpleNamespace(returncode=0)):
   folder=Path(temp)/'out/apple/cellphones/cps-apple-selected';folder.mkdir(parents=True)
   for name,data in [('prices.json',[row]),('issues.json',[{'source_url':'https://cellphones.com.vn/other.html','reason':'HTTP 403'}]),('summary.json',{'models':[]})]:(folder/name).write_text(json.dumps(data))
   result,status=cw.work(db,job,self.settings())
  self.assertEqual(status,'partial');self.assertTrue(result['dashboard_rebuilt'])
  db.rpc.assert_called_once();name,args=db.rpc.call_args.args
  self.assertEqual(name,'commit_dashboard_run');self.assertEqual(len(args['p_issues']),1)
  self.assertEqual(args['p_payload']['rows'][1],old['rows'][0]);self.assertEqual(args['p_rows'][0]['sku'],'cps-123')
  self.assertEqual(args['p_payload']['issues'][0]['chain'],'CPS')
 def test_missing_fresh_data_keeps_old_timestamp_and_reports_error(self):
  db=MagicMock();old={'rows':[{'sku':'old','apple_model':'iPhone 17 Pro Max','observed_at':'2026-10-06T10:00:00+07:00'}]}
  with tempfile.TemporaryDirectory() as temp,patch.object(cw,'ROOT',Path(temp)),patch.object(cw,'materialize_catalog',return_value={}),patch.object(cw,'latest_payload',return_value=old),patch.object(cw,'run',return_value=SimpleNamespace(returncode=1)):
   result,status=cw.work(db,{'id':'job','kind':'verify_prices','payload':{'model':'iPhone 17 Pro Max','channels':['cellphones']}},self.settings())
  self.assertEqual(status,'error');self.assertFalse(result['dashboard_rebuilt'])
  name,args=db.rpc.call_args.args;self.assertEqual(name,'publish_dashboard_snapshot')
  self.assertEqual(args['p_payload']['rows'][0]['observed_at'],old['rows'][0]['observed_at'])
  self.assertTrue(args['p_payload']['rows'][0]['stale_since'])
 def test_unknown_channel_and_old_configuration_fail_before_worker(self):
  for payload in [{'channels':['unknown']},{'expected_revision':0}]:
   with patch.object(cw,'run') as run:
    with self.assertRaises(PipelineError):cw.work(MagicMock(),{'id':'job','kind':'daily_prices','payload':payload},self.settings())
    run.assert_not_called()

 def test_checking_one_model_preserves_other_model_url_results(self):
  db=MagicMock();settings=self.settings();settings['apple_url_checks']={'value':{'rules':{'Other':{'model':'Other','color':'Đen'}},'statuses':{'Other':[{'status':'valid','url':'https://example/old'}]}}}
  outputs=[SimpleNamespace(stdout=json.dumps({'ok':True,'results':[]}),returncode=0),SimpleNamespace(stdout=json.dumps({'statuses':{'Other':[{'status':'unchecked'}],'iPhone 17 Pro Max':[{'status':'valid'}]}}),returncode=0)]
  with patch.object(cw,'run',side_effect=outputs):
   result,status=cw.work(db,{'id':'job','kind':'check_urls','payload':{'model':'iPhone 17 Pro Max'}},settings)
  saved=db.table.return_value.upsert.call_args.args[0]['value']
  self.assertEqual(status,'success');self.assertEqual(saved['statuses']['Other'][0]['status'],'valid')
  self.assertEqual(saved['rules']['iPhone 17 Pro Max']['color'],None)

 def test_pending_claim_expires_dead_leases_before_selecting_job(self):
  db=MagicMock();db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data=[{'id':'queued'}]
  self.assertEqual(cw.pending_job(db),'queued')
  db.table.return_value.update.assert_called_once()
  update=db.table.return_value.update.call_args.args[0]
  self.assertEqual(update['status'],'error')

 def test_config_followup_discovery_then_prices_without_telegram(self):
  for kind,payload,next_kind in [('config_update',{},'discovery'),('discovery',{'auto_prices':True},'daily_prices')]:
   db=MagicMock();cw.followup(db,{'id':'job','kind':kind,'payload':payload},'partial',{})
   queued=db.table.return_value.insert.call_args.args[0]
   self.assertEqual(queued['kind'],next_kind)
   self.assertEqual(set(queued['payload']['channels']),set(cw.CHAINS))
   self.assertFalse(queued['payload']['send_report'])

 def test_failed_step_does_not_queue_followup_and_conflict_is_visible(self):
  db=MagicMock();job={'id':'job','kind':'config_update','payload':{}}
  cw.followup(db,job,'error',{});db.table.assert_not_called()
  db.table.return_value.insert.return_value.execute.side_effect=RuntimeError('busy')
  cw.followup(db,job,'success',{})
  saved=db.table.return_value.update.call_args.args[0]
  self.assertIn('followup_warning',saved['result'])
