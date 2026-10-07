"""Kiểm chứng adapter chi tiết bằng HTML/JSON giả lập, không gọi đại lý thật."""
import unittest
import httpx
from unittest.mock import AsyncMock,patch
from playwright.async_api import async_playwright
from adapters.viettel_detail import read_product,extract_product
from common import PipelineError

URL='https://viettelstore.vn/dien-thoai/iphone-16-128gb-pid123.html'
RULE='11111111-1111-1111-1111-111111111111'
SECOND='22222222-2222-2222-2222-222222222222'
INFO=f'''<h1>iPhone 16 128GB</h1><input id="ProductTitle" value="iPhone 16 128GB"><input id="ProductId" value="123"><input id="meta-url" value="{URL}"><div class="normal-order"></div><div class="frame-promotion-header">Áp dụng trong tháng</div><div class="box-promotion"><div class="promo-content">Thu cũ giảm 2 triệu</div></div><script>throw new Error('Không được chạy');</script>'''
RULES=f'''<ul class="option-color-product"><label class="color-check active" id="{RULE}" title="Đen"><input data-erp="111"></label><label class="color-check" id="{SECOND}" title="Trắng"><input data-erp="222"></label></ul>'''

class DetailTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pw=await async_playwright().start()
        self.browser=await self.pw.chromium.launch()
        self.calls=[]
        self.robots_patch=patch("adapters.viettel_detail.robots_allowed",new=AsyncMock())
        self.robots_patch.start()

    async def asyncTearDown(self):
        await self.browser.close();await self.pw.stop();self.robots_patch.stop()

    def client(self,mode='ok'):
        def handler(request):
            self.calls.append(request)
            if request.method=='GET': body=f'<link rel="canonical" href="{URL}">' if mode=='new_template' else '<script>loadInfoProduct(123, 123);</script>'
            elif request.url.path.endswith('ProductRule_GetPriceByRule'):
                import json
                data=json.loads(request.content)
                erp='222' if data['id']==SECOND else '111'
                return httpx.Response(200,json={'d':{'stt':1,'data':{
                    'PriceDisplayType':'0','Price':'21000000','SellPrice':'0' if mode in ('ooszero','contact') else '20000000',
                    'Erp_Product_ID':'999' if mode=='wrong_erp' else erp,
                    'SaleState':'1' if mode=='preorder' else '0','AmounInstock':'0' if mode in ('oos','ooszero') else '10'}}})
            else:
                from urllib.parse import parse_qs
                self.assertEqual(request.headers['X-Requested-With'],'XMLHttpRequest')
                action=parse_qs(request.content.decode())['action'][0]
                if action=='get-block-info-product': body=INFO+('<div class="price-product"><span class="new-price">'+('15.290.000 ₫' if mode=='page_price' else 'Liên hệ' if mode=='contact' else 'Tạm hết hàng')+'</span></div><input id="HiddenPriceNoFormat" value="4990000">' if mode in ('page_price','page_oos','contact') else '')
                elif action=='get-list-rule-by-product': body='<ul class="option-color-product"></ul>' if mode in ('page_price','page_oos') else RULES
                elif action=='get-product-promotion-erp': body=f'<input id="HiddenHasPromotionOffer" value="{1 if mode=="offer" else 0}"><input id="HiddenMinDiscountAmount" value="0">'
                elif action=='get-payment-promotion': body='<html>Lỗi</html>' if mode=='bad_payment' else '<!-- BEGIN BlockPaymentPromotion --><div class="frame-promotion">VNPAY giảm tối đa 500.000đ<script>Không lấy script</script></div>'
                else: raise AssertionError(action)
            return httpx.Response(200,text=body,headers={'content-type':'text/html'})
        return httpx.AsyncClient(transport=httpx.MockTransport(handler),follow_redirects=True)

    async def test_rules_only_does_not_read_default_price(self):
        async with self.client('wrong_erp') as client:
            row=await read_product(URL,client,self.browser,rules_only=True)
        self.assertEqual(len(row['variants']),2)
        self.assertFalse(any(r.url.path.endswith('ProductRule_GetPriceByRule') for r in self.calls))

    async def test_selected_rule_stays_locked_not_default(self):
        async with self.client() as client:
            row=await read_product(URL,client,self.browser,SECOND)
        self.assertEqual(row['variant']['erp_id'],'222')
        self.assertEqual(row['promo_price'],20000000)
        self.assertEqual(row['original_price'],21000000)
        self.assertIn('Thu cũ',row['promo_text']);self.assertIn('VNPAY',row['promo_text'])
        self.assertNotIn('Không lấy script',row['promo_text'])
        self.assertTrue(row['promotion_complete'])

    async def test_price_and_promotion_failures_do_not_publish(self):
        for mode in ['wrong_erp']:
            async with self.client(mode) as client:
                with self.assertRaises(PipelineError,msg=mode): await read_product(URL,client,self.browser)

    async def test_promotion_failure_keeps_verified_price_with_warning(self):
        for mode in ['offer','bad_payment']:
            async with self.client(mode) as client:
                row=await read_product(URL,client,self.browser)
            self.assertEqual(row['promo_price'],20000000)
            self.assertFalse(row['promotion_complete'])
            self.assertIn('CTKM chưa xác minh',row['promo_text'])

    async def test_shown_price_preserved_when_out_of_stock_or_preorder(self):
        for mode in ['preorder','oos']:
            async with self.client(mode) as client:
                row=await read_product(URL,client,self.browser)
                self.assertEqual(row['promo_price'],20000000)
                self.assertIn('[Tình trạng]',row['promo_text'])

    async def test_changed_rule_requires_review(self):
        async with self.client() as client:
            with self.assertRaisesRegex(PipelineError,'biến thể'): await read_product(URL,client,self.browser,'missing')

    async def test_extract_checks_identity_and_erp(self):
        item={'source_product_name':'iPhone 16 128GB','url':URL,'variant_rule_id':RULE,'variant_erp_id':'111',
              'verify_tokens':['iPhone 16','128GB'],'sku':'sku','product_name':'iPhone 16 128GB · Đen'}
        async with self.client() as client:
            row=await extract_product(item,client,self.browser)
            self.assertEqual(row['sku'],'sku');self.assertEqual(row['product_name'],item['product_name'])
            with self.assertRaisesRegex(PipelineError,'ERP'): await extract_product({**item,'variant_erp_id':'222'},client,self.browser)

    async def test_stock_status_with_zero_placeholder_has_null_price(self):
        async with self.client('ooszero') as client:
            row=await read_product(URL,client,self.browser)
        self.assertIsNone(row['promo_price']);self.assertIsNone(row['original_price'])
        self.assertIn('hết hàng',row['promo_text'])

    async def test_new_template_verified_by_canonical_and_fragment(self):
        async with self.client('new_template') as client:
            result=await read_product(URL,client,self.browser)
        self.assertEqual(result['variant']['erp_id'],'111')
        self.assertEqual(result['promo_price'],20000000)

    async def test_product_page_price_does_not_invent_color_or_erp(self):
        async with self.client('page_price') as client:
            result=await read_product(URL,client,self.browser)
        self.assertEqual(result['promo_price'],15290000)
        self.assertEqual(result['variant']['rule_id'],'product-123')
        self.assertIsNone(result['variant']['color'])
        async with self.client('page_price') as client:
            with self.assertRaises(PipelineError):await read_product(URL,client,self.browser,RULE)

    async def test_oos_label_does_not_use_hidden_old_price(self):
        async with self.client('page_oos') as client:
            result=await read_product(URL,client,self.browser)
        self.assertIsNone(result['promo_price'])
        self.assertIn('Tạm hết hàng',result['promo_text'])

    async def test_contact_only_for_verified_default_variant(self):
        async with self.client('contact') as client:
            result=await read_product(URL,client,self.browser)
        self.assertIsNone(result['promo_price']);self.assertIn('Liên hệ',result['promo_text'])
        async with self.client('contact') as client:
            with self.assertRaises(PipelineError):await read_product(URL,client,self.browser,SECOND)
