"""Bảo vệ contract HTTP Viettel: phân trang đủ và không chấp nhận catalog lỗi."""
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs
import httpx
from adapters.viettel import catalog_request, parse_cards, listing_links, response_ok
from common import PipelineError

SEED = 'https://viettelstore.vn/dtdd-apple-iphone'
PARAMS = {'path':'ProductList5Col2026','PaginationVisiable':0,'CatID':'010001',
          'ManID':'1','Tags':'','PageSize':1,'CurrentPage':1,'SpecOrder':'DangHot',
          'SpecFilter':'','FeatureFilter':'','PriceFrom':-1,'PriceTo':-1,'isHot':''}

def shell(params=PARAMS):
    fields=','.join(f"'{key}':{value!r}" for key,value in params.items())
    return "<script>function GenProductList(div,callback){$('#x').load('/Site/_Sys/GetUserControlAsync.aspx',{"+fields+"},callback);}</script>"

def cards(identifier='1', total=2, brand='1'):
    return f'<div class="product-item"><a data-id="{identifier}" data-name="iPhone 16 128GB" data-brand="{brand}" href="/iphone-pid{identifier}.html">Tên</a></div><input id="RecordCountSP" value="{total}">'

class ParserTests(unittest.TestCase):
    def test_catalog_parameters(self):
        self.assertEqual(catalog_request(shell())['ManID'],'1')
        with self.assertRaises(PipelineError): catalog_request('<html>Access denied</html>')

    def test_search_keyword_must_match_seed(self):
        params={**PARAMS,'KeyWord':'airpods','CatID':'','ManID':'0'}
        seed='https://viettelstore.vn/ket-qua-tim-kiem.html?keyword=airpods'
        self.assertEqual(catalog_request(shell(params),seed)['KeyWord'],'airpods')
        with self.assertRaises(PipelineError): catalog_request(shell(params),seed.replace('airpods','iphone'))

    def test_missing_total_is_failure_not_empty(self):
        with self.assertRaises(PipelineError): parse_cards('<html></html>')
        self.assertEqual(parse_cards('<input id="RecordCountSP" value="0">'),([],0))

class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def discover(self, mode):
        requests=[]
        def handler(request):
            requests.append(request)
            if request.method=='GET': body=shell()
            else:
                page=parse_qs(request.content.decode())['CurrentPage'][0]
                body=cards('1' if mode=='duplicate' else page,brand='2' if mode=='wrong_brand' else '1')
            return httpx.Response(200,text=body,headers={'content-type':'text/html'})
        source={'chain_name':'Viettel Store','seeds':[SEED],'max_pages':3,'max_candidates':10,
                'product_url_pattern':r'^https://viettelstore\.vn/.*-pid\d+\.html$'}
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch('adapters.viettel.robots_allowed',new=AsyncMock()), patch('adapters.viettel.asyncio.sleep',new=AsyncMock()):
                result=await listing_links(source,client)
        return result, requests

    async def test_reads_all_pages(self):
        links,requests=await self.discover('ok')
        self.assertEqual(len(links),2)
        self.assertEqual([r.method for r in requests],['GET','POST','POST'])

    async def test_rejects_duplicate_and_wrong_brand(self):
        for mode in ['duplicate','wrong_brand']:
            with self.assertRaises(PipelineError): await self.discover(mode)

    async def test_403_is_reported_without_retry(self):
        calls=[]
        def handler(request):
            calls.append(request);return httpx.Response(403)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(PipelineError,'HTTP 403'): await response_ok(client,'GET',SEED)
        self.assertEqual(len(calls),1)

class QuoteTests(unittest.TestCase):
    def test_prices_exclude_conditional_discounts(self):
        html=cards(total=1).replace('</a>', '</a><div class="price">20.000.000 ₫</div><div class="price-old">21.000.000 ₫</div><p class="promotion-text">Thu cũ giảm 2.000.000đ ...</p>')
        rows,total=parse_cards(html,quotes=True)
        self.assertEqual(rows[0]['promo_price'],20000000)
        self.assertEqual(rows[0]['original_price'],21000000)
        self.assertFalse(rows[0]['promotion_complete'])
        self.assertIn('Thu cũ',rows[0]['promo_text'])

    def test_contact_price_not_zero(self):
        html=cards(total=1).replace('</a>','</a><div class="price">Liên hệ</div>')
        row=parse_cards(html,quotes=True)[0][0]
        self.assertIsNone(row['promo_price'])
        self.assertTrue(row['price_error'])

    def test_multiple_price_regions_fail(self):
        html=cards(total=1).replace('</a>','</a><div class="price">20.000.000đ</div><div class="price">19.000.000đ</div>')
        with self.assertRaises(PipelineError): parse_cards(html,quotes=True)
