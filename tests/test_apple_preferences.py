"""Cấu hình màu Apple áp dụng ở lớp hiển thị; không trộn model hoặc SKU."""
import unittest
from apple_preferences import load,model_of,presentation
class AppleTests(unittest.TestCase):
 def setUp(self):self.config=load()
 def test_user_list_exactly_36_and_blank_colors_are_no_filter(self):
  self.assertEqual(len(self.config['products']),36)
  row=presentation({'product_name':'Tai nghe Bluetooth Apple AirPods 4 chống ồn','sku':'a','brand':'Apple'},self.config)
  self.assertEqual(row['display_name'],'AirPods 4 with ANC');self.assertEqual(row['apple_selection'],'selected')
 def test_name_storage_and_color_do_not_change_source_or_sku(self):
  source={'product_name':'Điện thoại iPhone 18 Pro Max 256GB · Đỏ Burgundy','color':'Đỏ Burgundy','sku':'tgdd-123','brand':'Apple'}
  row=presentation(source,self.config)
  self.assertEqual(row['display_name'],'iPhone 18 Pro Max 256GB');self.assertEqual(row['apple_selection'],'selected')
  self.assertEqual(row['sku'],source['sku']);self.assertEqual(row['product_name'],source['product_name'])
 def test_model_suffix_and_chip_are_exact(self):
  for name,expected in [('iPhone 18 Pro Max 256GB','iPhone 18 Pro Max'),('iPhone 18 Pro 256GB','iPhone 18 Pro'),('MacBook Pro 14 inch M5 Pro 24GB/512GB','MacBook Pro 14 M5 Pro'),('iPad Air 11 inch M4 WiFi 128GB','iPad Air M4 11'),('Apple Watch Series 11 42mm GPS','Apple Watch S11'),('AirPods 5 sạc không dây','AirPods 5 sạc ko dây')]:self.assertEqual(model_of(name),expected)
  row=presentation({'product_name':'MacBook Pro 14 inch M5 Pro 24GB/512GB','color':'Đen Không Gian','brand':'Apple'},self.config)
  self.assertEqual(row['apple_selection'],'unconfigured')
 def test_missing_color_and_alias_not_guessed(self):
  source={'product_name':'MacBook Air 13 inch M5 16GB/512GB','color':'Xanh da trời nhạt','brand':'Apple'}
  self.assertEqual(presentation(source,self.config)['apple_selection'],'other_color')
  self.assertEqual(presentation({**source,'color':''},self.config)['apple_selection'],'unknown_color')
  rule=next(r for r in self.config['products'] if r['model']=='MacBook Air 13 M5');rule['aliases']=['Xanh da trời nhạt']
  self.assertEqual(presentation(source,self.config)['apple_selection'],'selected')
 def test_blank_airpods_variants_not_merged(self):
  rows=[presentation({'product_name':'AirPods 4','sku':'a'},self.config),presentation({'product_name':'AirPods 4 ANC','sku':'b'},self.config)]
  self.assertEqual([r['display_name'] for r in rows],['AirPods 4','AirPods 4 with ANC']);self.assertEqual([r['sku'] for r in rows],['a','b'])

 def test_mw_price_requires_variant_evidence_not_renamed_color(self):
  row={'chain_name':'TGDD','product_name':'iPhone 18 Pro Max 256GB','color':'Đỏ Burgundy','sku':'tgdd-123','variant_id':'123','promo_price':41990000}
  self.assertEqual(presentation(row,self.config)['apple_selection'],'needs_verified_color')
  evidence={'model':'iPhone 18 Pro Max','canonical_color':'Đỏ Burgundy','product_code':'123','website_color_id':'125','verified_at':'2026-10-06T17:00:00+07:00'}
  self.assertEqual(presentation({**row,'color_evidence':evidence},self.config)['apple_selection'],'selected')
  evidence['product_code']='124'
  self.assertEqual(presentation({**row,'color_evidence':evidence},self.config)['apple_selection'],'needs_verified_color')
