"""Giao diện MW cũ phải khóa đúng màu/SKU và giữ giá dù hết hàng."""
import unittest
from adapters.tgdd_legacy import parse
from common import PipelineError
HTML='''<h1>Máy tính bảng iPad Air M4 11 inch WiFi 512GB</h1><div class="box_right"><div class="box03 color"><a class="item act" data-code="2440931001230" data-color="44">Đen - Xám</a><a class="item" data-code="2440931001229" data-color="9">Tím</a></div><div class="box04 notselling"><p class="box-price-present">29.390.000₫</p><strong class="productstatus">Hết hàng tạm thời</strong><div class="block__promo">Quà tặng theo điều kiện</div></div></div><script>document.productCode = '2440931001230';throw Error('không chạy');</script>'''
class LegacyTests(unittest.TestCase):
 def test_exact_selected_color_and_out_of_stock_keeps_price(self):
  data=parse(HTML,'https://www.thegioididong.com/x');quote=data['_legacy_quote']
  self.assertEqual(quote['variant_id'],'2440931001230');self.assertEqual(quote['color'],'Đen - Xám');self.assertEqual(quote['promo_price'],29390000);self.assertIn('Hết hàng',quote['promo_text']);self.assertNotIn('không chạy',quote['promo_text'])
 def test_wrong_active_color_rejected(self):
  with self.assertRaises(PipelineError):parse(HTML.replace("document.productCode = '2440931001230'","document.productCode = '2440931001229'"),'https://www.thegioididong.com/x')
 def test_ambiguous_price_not_used(self):
  with self.assertRaises(PipelineError):parse(HTML.replace('</strong>','</strong><p class="box-price-present">20.000.000₫</p>'),'https://www.thegioididong.com/x')
 def test_only_status_is_valid_snapshot(self):
  quote=parse(HTML.replace('<p class="box-price-present">29.390.000₫</p>',''),'https://www.thegioididong.com/x')['_legacy_quote']
  self.assertIsNone(quote['promo_price']);self.assertIn('[Tình trạng]',quote['promo_text'])

 def test_online_display_price_excludes_original_price(self):
  html=HTML.replace('box04 notselling','box_saving').replace('<p class="box-price-present">29.390.000₫</p>','<div class="bs_price"><strong>29.390.000₫</strong><em>32.000.000₫</em></div>')
  self.assertEqual(parse(html,'https://www.thegioididong.com/x')['_legacy_quote']['promo_price'],29390000)
