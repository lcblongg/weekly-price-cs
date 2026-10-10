import unittest
import os
from unittest.mock import patch
from tools import run_data as data
from apple_rules import RuleError

HEADER=['Tên sản phẩm','Màu','MW','CPS','FPT','Viettel','Phong Vũ']
class DataInputTests(unittest.TestCase):
    def test_cps_manual_mode_never_fetches_parent_ids_from_full_catalog(self):
        from tools.scrape_cps_apple import catalog_parent_ids
        catalog=[{'config':{'brand':'Apple','parent_id':123}}]
        with patch.dict(os.environ,{'WPCS_SELECTED_ONLY':'1'}):self.assertEqual(catalog_parent_ids(catalog),[])
        with patch.dict(os.environ,{'WPCS_SELECTED_ONLY':'0'}):self.assertEqual(catalog_parent_ids(catalog),['123'])
    def test_blank_links_remain_missing_not_invented(self):
        rows=data.parse_rows([HEADER,['iPhone 17','Đen',None,None,None,None,None]])
        self.assertEqual(rows[0]['model'],'iPhone 17')
        self.assertFalse(rows[0].get('urls'))
    def test_multiple_links_and_duplicate_rows_keep_distinct_variants(self):
        a='https://fptshop.com.vn/dien-thoai/iphone-17?sku=123'
        b='https://fptshop.com.vn/dien-thoai/iphone-17?sku=456'
        rows=data.parse_rows([HEADER,['iPhone 17','Đen',None,None,a+'\n'+b,None,None],['iPhone 17','Đen',None,None,a,None,None]])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['urls']['fpt'],[a,b])
    def test_all_five_domains_route_to_real_worker_slugs(self):
        urls=['https://www.thegioididong.com/dtdd/iphone-17','https://cellphones.com.vn/iphone-17.html','https://fptshop.com.vn/dien-thoai/iphone-17','https://viettelstore.vn/dien-thoai/iphone-17-pid123.html','https://phongvu.vn/iphone-17--s123']
        rules=data.parse_rows([HEADER,['iPhone 17',None,*urls]])
        self.assertEqual(set(rules[0]['urls']),{'tgdd','cellphones','fpt','viettel','phongvu'})
    def test_wrong_domain_formula_non_apple_and_conflicting_color_fail(self):
        bad=[['iPhone 17','Đen','https://hoanghamobile.com/iphone-17'],['iPhone 17','Đen',None,'=HYPERLINK("url")'],['Samsung S26','Đen']]
        for row in bad:
            with self.assertRaises(RuleError):data.parse_rows([HEADER,row])
        with self.assertRaises(RuleError):data.parse_rows([HEADER,['iPhone 17','Đen'],['iPhone 17','Trắng']])
    def test_old_hoangha_layout_cannot_be_used_as_five_channels(self):
        with self.assertRaises(RuleError):data.parse_rows([['Tên sản phẩm','Màu','Link','Bỏ trả góp'],['iPhone 17','Đen','https://hoanghamobile.com/iphone-17']])
    def test_empty_links_run_fails_before_database_or_configuration(self):
        with patch.object(data.sys,'argv',['run_data.py']),patch.object(data.Path,'read_bytes',return_value=b'file'),patch.object(data,'read_products',return_value=[{'model':'iPhone 17','urls':{}}]),patch.object(data,'database') as db:
            with self.assertRaises(RuleError):data.main()
            db.assert_not_called()
