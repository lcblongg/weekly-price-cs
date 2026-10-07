"""Giá phải đọc từ SKU màu đã chọn; không đổi nhãn trên snapshot màu mặc định."""
import unittest
from mw_apple_colors import selected_variants,verify_quote
from common import PipelineError
class SelectionTests(unittest.TestCase):
 def data(self):
  return {'name':'iPhone 18 Pro Max 256GB','productCode':'11111111','filter':[{'label':'Phiên bản','values':[{'name':'256GB','url':'dtdd/iphone-18-pro-max','productCodes':['11111111','22222222']},{'name':'512GB','url':'dtdd/iphone-18-pro-max-512gb','productCodes':['33333333','44444444']}]},{'label':'Màu','values':[{'name':'Đen','code':'3','productCodes':['11111111','33333333']},{'name':'Đỏ Burgundy','code':'125','productCodes':['22222222','44444444']}]}]}
 def test_requested_color_overrides_default_sku_and_keeps_storage(self):
  selected=selected_variants(self.data(),'https://www.thegioididong.com/dtdd/iphone-18-pro-max',{'model':'iPhone 18 Pro Max','color':'Đỏ Burgundy'})
  self.assertEqual([i['variant_id'] for i in selected],['22222222','44444444'])
  self.assertTrue(selected[1]['url'].endswith('-512gb'))
 def test_no_color_match_cannot_take_default(self):
  with self.assertRaises(PipelineError):selected_variants(self.data(),'https://www.thegioididong.com/a',{'model':'iPhone 18 Pro Max','color':'Hồng'})
 def test_model_or_color_response_changed_is_rejected(self):
  rule={'model':'iPhone 18 Pro Max','color':'Đỏ Burgundy'};item=selected_variants(self.data(),'https://www.thegioididong.com/a',rule)[0]
  for quote in [{'variant_id':'11111111','product_name':'iPhone 18 Pro Max 256GB','color':'Đen'},{'variant_id':'22222222','product_name':'iPhone 18 Pro 256GB','color':'Đỏ Burgundy'},{'variant_id':'22222222','product_name':'iPhone 18 Pro Max 256GB','color':'Đen'}]:
   with self.assertRaises(PipelineError):verify_quote(quote,item,rule)
  self.assertEqual(verify_quote({'variant_id':'22222222','product_name':'iPhone 18 Pro Max 256GB','color':'Đỏ Burgundy'},item,rule)['canonical_color'],'Đỏ Burgundy')
 def test_model_specific_names_do_not_leak_to_other_model(self):
  data={'name':'MacBook Air 13 inch M5 16GB/512GB','filter':[{'label':'Màu','values':[{'name':'Xanh da trời nhạt','code':'41','productCodes':['11111111']}]}]}
  self.assertEqual(selected_variants(data,'https://www.thegioididong.com/a',{'model':'MacBook Air 13 M5','color':'Xanh Da Trời'})[0]['variant_id'],'11111111')
  data['name']='iPhone 18 Pro Max 256GB'
  with self.assertRaises(PipelineError):selected_variants(data,'https://www.thegioididong.com/a',{'model':'iPhone 18 Pro Max','color':'Xanh Da Trời'})
