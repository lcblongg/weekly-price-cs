import unittest
from adapters.fptshop import variant_color
class FPTColorTests(unittest.TestCase):
 def test_attribute_color_not_catalog_or_name_part_number(self):
  state={'variants':{'skuSlugs':[{'sku':'001','attributes':[{'key':{'propertyName':'Color','displayValue':'Đỏ Burgundy'}}]},{'sku':'002','attributes':[{'key':{'propertyName':'Color','displayValue':'Đen'}}]}]}}
  self.assertEqual(variant_color(state,'001'),'Đỏ Burgundy');self.assertEqual(variant_color(state,'002'),'Đen');self.assertEqual(variant_color(state,'003'),'')
 def test_ambiguous_color_not_guessed(self):
  attrs=[{'key':{'propertyName':'Color','displayValue':x}} for x in ['Đen','Bạc']]
  self.assertEqual(variant_color({'variants':{'skuSlugs':[{'sku':'001','attributes':attrs}]}},'001'),'')

class CatalogColorTests(unittest.TestCase):
 def test_apple_colors_kept_even_same_price_or_out_of_stock(self):
  from discover_products import representatives
  rows=[{'name':'iPhone 17 Pro 256GB '+color,'url':'u'+str(i),'variant_id':str(i),'group':'g','listing_price':100,'stock':0} for i,color in enumerate(['Bạc','Cam Vũ Trụ','Xanh Đậm'])]
  chosen,skipped=representatives('FPT Shop',rows)
  self.assertEqual(len(chosen),3);self.assertEqual(skipped,0)

class PVColorTests(unittest.TestCase):
 def test_macbook_palette_and_exact_selected_sku(self):
  from adapters.phongvu import color_rows,selected_color
  product={'productInfo':{'sku':'2'},'productOptions':{'rows':[{'title':'Màu sắc','code':'macbook_mausac','options':[{'sku':'1','label':'Bạc','selected':False},{'sku':'2','label':'Vàng Citrus','selected':True}]}]}}
  self.assertEqual(len(color_rows(product)),1);self.assertEqual(selected_color(product),'Vàng Citrus')
  product['productInfo']['sku']='1';self.assertEqual(selected_color(product),'')

class FPTStatusTests(unittest.IsolatedAsyncioTestCase):
 async def test_discontinued_keeps_status_not_historical_variant_price(self):
  from unittest.mock import patch,AsyncMock
  from types import SimpleNamespace
  from adapters.fptshop import read_product
  state={'productAdvanceInfo':None,'productStatus':{'buttonCode':'EXPLORE_OTHER_PRODUCT','statusOnWeb':'ngung_kinh_doanh'},'variants':{'sku':'001','variantResult':{'skus':[{'code':'001','name':'iPhone 16 256GB Đen','price':27590000}]},'skuSlugs':[{'sku':'001','attributes':[{'key':{'propertyName':'Color','displayValue':'Đen'}}]}]}}
  url='https://fptshop.com.vn/dien-thoai/iphone-16?sku=001'
  with patch('adapters.fptshop.fetch',new=AsyncMock(return_value=SimpleNamespace(text='',url=url))),patch('adapters.fptshop.flight',return_value=''),patch('adapters.fptshop.object_after',return_value=state):row=await read_product({'url':url,'variant_id':'001'},None)
  self.assertIsNone(row['promo_price']);self.assertIn('Ngừng kinh doanh',row['promo_text']);self.assertEqual(row['color'],'Đen')

class WatchBodyColorTests(unittest.TestCase):
 def test_watch_color_uses_case_attribute_not_band_color(self):
  from adapters.phongvu import selected_color
  p={'productInfo':{'sku':'1'},'productOptions':{'rows':[{'code':'smartwatch_bandcolor','title':'Band color','options':[{'selected':True,'sku':'1','label':'Black(S/M)'}]}]},'productDetail':{'attributeGroups':[{'name':'Màu sắc','value':' Đen / Jet Black '}]}}
  self.assertEqual(selected_color(p),'Đen / Jet Black')
