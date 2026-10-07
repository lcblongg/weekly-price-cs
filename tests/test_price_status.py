"""Giá và trạng thái độc lập; link review phải đọc lại, không tái dùng lỗi cũ."""
import unittest
from unittest.mock import AsyncMock,patch
from adapters.cellphones import quote
from common import PipelineError
from scraper import recheck_review
from identity import chain_sku
class StatusTests(unittest.IsolatedAsyncioTestCase):
    def test_cps_out_of_stock_keeps_displayed_price(self):
        product={'general':{'name':'iPhone 16 128GB','url_path':'iphone-16.html'},'filterable':{'stock':0,'price':20000000,'special_price':19000000}}
        result=quote({'variant_id':'123'},product)
        self.assertEqual(result['promo_price'],19000000)
        self.assertIn('[Tình trạng]',result['promo_text'])
        product['filterable']['price']=0;product['filterable']['special_price']=0
        result=quote({'variant_id':'123'},product)
        self.assertIsNone(result['promo_price']);self.assertIsNone(result['original_price'])
        product['filterable'].pop('stock')
        with self.assertRaises(PipelineError):quote({'variant_id':'123'},product)
    async def test_review_rechecked_into_status_record(self):
        config={'variant_id':'123','category':'Điện thoại','brand':'Apple','url':'https://cellphones.com.vn/iphone-16.html'}
        review=[{'chain_name':'CellphoneS','source_url':config['url'],'config':config,'reason':'Hết hàng hôm qua'}]
        result={'variant_id':'123','product_name':'iPhone 16 128GB','promo_price':None,'original_price':None,'promo_text':'[Tình trạng] Ngừng kinh doanh'}
        rows=[];issues=[]
        with patch('adapters.cellphones.read_many',new=AsyncMock(return_value={'123':result})) as reader:
            await recheck_review(review,None,None,rows,issues)
            reader.assert_awaited_once()
        self.assertEqual(len(rows),1);self.assertEqual(issues,[])
        self.assertEqual(rows[0]['sku'],chain_sku('CellphoneS','123'))
        self.assertIsNone(rows[0]['promo_price'])
    async def test_missing_status_does_not_become_zero_or_success(self):
        config={'variant_id':'123','url':'https://cellphones.com.vn/iphone-16.html'}
        review=[{'chain_name':'CellphoneS','source_url':config['url'],'config':config}]
        rows=[];issues=[]
        with patch('adapters.cellphones.read_many',new=AsyncMock(return_value={'123':{'variant_id':'123','product_name':'iPhone 16 128GB','promo_price':None,'promo_text':''}})):
            await recheck_review(review,None,None,rows,issues)
        self.assertEqual(rows,[]);self.assertEqual(len(issues),1)

    async def test_tgdd_hidden_price_and_explicit_discontinued(self):
        from adapters.tgdd import read_product
        from price_availability import explicit_status
        import httpx
        url='https://www.thegioididong.com/dtdd/iphone-16'
        queries={'PRODUCT_DETAIL':{'data':{'name':'iPhone 16 128GB','productCode':'12345678','hiddenPrice':True,'statusText':'Ngừng kinh doanh'}},'FETCH_PRODUCT_PAYMENT_OFFER':{'data':{}}}
        with patch('adapters.tgdd.detail',new=AsyncMock(return_value=(httpx.Response(200,request=httpx.Request('GET',url)),queries))):
            result=await read_product({'url':url,'variant_id':'12345678'},None)
        self.assertIsNone(result['promo_price']);self.assertIn('Ngừng kinh doanh',result['promo_text'])
        self.assertIsNone(explicit_status({'name':'Ngừng kinh doanh','sellable':False}))

    async def test_tgdd_review_resolves_real_id_before_publishing(self):
        url='https://www.thegioididong.com/dtdd/samsung-galaxy-a07'
        review=[{'chain_name':'TGDD','source_url':url,'config':{'brand':'Samsung','category':'Điện thoại'}}]
        rows=[];issues=[]
        with patch('adapters.tgdd.read_product',new=AsyncMock(return_value={'variant_id':'12345678','product_name':'Samsung Galaxy A07 128GB','promo_price':3500000,'original_price':None,'promo_text':''})):
            await recheck_review(review,None,None,rows,issues)
        self.assertEqual(issues,[]);self.assertEqual(rows[0]['sku'],'tgdd-12345678');self.assertEqual(rows[0]['variant_id'],'12345678')
