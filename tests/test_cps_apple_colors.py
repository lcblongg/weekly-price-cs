"""Màu/giá CPS phải cùng mã con và model, giữ giá khi stock API bằng 0."""
import unittest
from cps_apple_colors import selected_quote
from common import PipelineError
class CPSTests(unittest.TestCase):
 def setUp(self):
  self.parent={'general':{'product_id':10,'name':'iPhone 17 Pro 256GB','child_product':[11,12]}}
  self.child={'general':{'product_id':12,'name':'iPhone 17 Pro 256GB-Cam Vũ Trụ','url_path':'iphone.html'},'filterable':{'parent_id':10,'price':35000000,'special_price':32000000,'stock':0}}
  self.rule={'model':'iPhone 17 Pro','color':'Cam vũ trụ'}
 def test_exact_color_sku_and_stock_keeps_price(self):
  q=selected_quote(self.parent,self.child,self.rule,'https://cellphones.com.vn/iphone.html');self.assertEqual(q['promo_price'],32000000);self.assertEqual(q['variant_id'],'12');self.assertEqual(q['color'],'Cam vũ trụ');self.assertIn('hết hàng',q['promo_text']);self.assertEqual(q['color_evidence']['product_code'],'12')
 def test_other_color_not_renamed(self):
  self.child['general']['name']='iPhone 17 Pro 256GB-Bạc';self.assertIsNone(selected_quote(self.parent,self.child,self.rule,'https://cellphones.com.vn/iphone.html'))
 def test_wrong_model_or_parent_rejected(self):
  self.child['general']['name']='iPhone 17 Pro Max 256GB-Cam Vũ Trụ'
  with self.assertRaises(PipelineError):selected_quote(self.parent,self.child,self.rule,'https://cellphones.com.vn/iphone.html')
  self.child['general']['name']='iPhone 17 Pro 256GB-Cam Vũ Trụ';self.child['filterable']['parent_id']=99
  with self.assertRaises(PipelineError):selected_quote(self.parent,self.child,self.rule,'https://cellphones.com.vn/iphone.html')
 def test_color_suffix_cannot_be_variant_description(self):
  self.child['general']['name']='iPhone 17 Pro 256GB-Cam Vũ Trụ | Trả góp';self.assertIsNone(selected_quote(self.parent,self.child,self.rule,'https://cellphones.com.vn/iphone.html'))
