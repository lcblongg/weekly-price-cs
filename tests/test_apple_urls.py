"""URL sản phẩm nhập tay theo kênh: kiểm tra định dạng, lưu/sửa/xóa, trạng thái, CPS parent/child. Không gọi mạng."""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import apple_sources
from apple_rules import RuleError, normalize_url, plan, manual_urls

CURATED = {'version': 1, 'models': [{'name': 'iPhone 17 Pro Max', 'pattern': r'\biPhone\s+17\s+Pro\s+Max\b'}]}


def rule(**extra):
    return {'model': 'iPhone 17 Pro Max', 'color': 'Cam vũ trụ', 'aliases': [], **extra}


class NormalizeTests(unittest.TestCase):
    def test_valid_urls_cleaned(self):
        self.assertEqual(normalize_url('tgdd', 'https://www.thegioididong.com/dtdd/iphone-17-pro-max/?code=12&utm_source=fb#x'),
                         'https://www.thegioididong.com/dtdd/iphone-17-pro-max?code=12')
        self.assertEqual(normalize_url('cellphones', 'https://cellphones.com.vn/iphone-17-pro-max.html?product_id=112615&gclid=1'),
                         'https://cellphones.com.vn/iphone-17-pro-max.html?product_id=112615')
        self.assertEqual(normalize_url('fpt', 'https://fptshop.com.vn/dien-thoai/iphone-17-pro-max?sku=00912345'),
                         'https://fptshop.com.vn/dien-thoai/iphone-17-pro-max?sku=00912345')
        self.assertEqual(normalize_url('viettel', 'https://viettelstore.vn/dien-thoai/iphone-17-pro-max-pid123.html'),
                         'https://viettelstore.vn/dien-thoai/iphone-17-pro-max-pid123.html')
        self.assertEqual(normalize_url('phongvu', 'https://phongvu.vn/iphone-17-pro-max-256gb--p8960?sku=2609'),
                         'https://phongvu.vn/iphone-17-pro-max-256gb--p8960?sku=2609')

    def test_wrong_domain_scheme_or_listing_rejected(self):
        for channel, url in [('fpt', 'https://cellphones.com.vn/iphone-17.html'), ('tgdd', 'http://www.thegioididong.com/dtdd/a'),
                             ('tgdd', 'https://www.thegioididong.com.evil.vn/dtdd/a'), ('cellphones', 'https://cellphones.com.vn/mobile/apple.html'),
                             ('phongvu', 'https://phongvu.vn/c/iphone'), ('viettel', 'https://viettelstore.vn/dtdd-apple-iphone'),
                             ('tgdd', 'https://user:pass@www.thegioididong.com/dtdd/a'), ('cellphones', 'https://cellphones.com.vn/a.html?product_id=abc'),
                             ('amazon', 'https://amazon.com/x')]:
            with self.assertRaises(RuleError, msg=url):
                normalize_url(channel, url)


class SaveTests(unittest.TestCase):
    def test_add_edit_delete_urls_through_plan(self):
        urls = {'tgdd': ['https://www.thegioididong.com/dtdd/iphone-17-pro-max', 'https://www.thegioididong.com/dtdd/iphone-17-pro-max-512gb',
                         'https://www.thegioididong.com/dtdd/iphone-17-pro-max/'],
                'cellphones': [], 'fpt': ['  ']}
        colors, _ = plan([rule(urls=urls)], CURATED)
        saved = colors['products'][0]
        self.assertEqual(manual_urls(saved, 'tgdd'), urls['tgdd'][:2])        # trùng sau chuẩn hóa → một dòng
        self.assertEqual(set(saved['urls']), {'tgdd'})                         # kênh rỗng không lưu
        edited, _ = plan([rule(urls={'tgdd': [urls['tgdd'][1]]})], CURATED)    # sửa: chỉ giữ 1 URL
        self.assertEqual(manual_urls(edited['products'][0], 'tgdd'), [urls['tgdd'][1]])
        removed, _ = plan([rule(urls={})], CURATED)                            # xóa hết URL
        self.assertNotIn('urls', removed['products'][0])

    def test_invalid_url_blocks_whole_save(self):
        with self.assertRaises(RuleError):
            plan([rule(urls={'fpt': ['https://fptshop.com.vn/dien-thoai/x', 'https://cellphones.com.vn/x.html']})], CURATED)
        with self.assertRaises(RuleError):
            plan([rule(urls={'tgdd': [f'https://www.thegioididong.com/dtdd/m-{i}' for i in range(21)]})], CURATED)


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(apple_sources, 'CHECKS', Path(self.folder.name) / 'checks.json')
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.folder.cleanup()

    def test_status_lifecycle(self):
        url = 'https://www.thegioididong.com/dtdd/iphone-17-pro-max'
        self.assertEqual(apple_sources.status_for(rule(), 'tgdd', url)['status'], 'unchecked')
        apple_sources.record('iPhone 17 Pro Max', 'tgdd', url, 'valid', '2 biến thể', 'Cam vũ trụ', 'check')
        self.assertEqual(apple_sources.status_for(rule(), 'tgdd', url)['status'], 'valid')
        # Đổi màu yêu cầu: kết quả cũ không còn hiệu lực.
        self.assertEqual(apple_sources.status_for(rule(color='Bạc'), 'tgdd', url)['status'], 'unchecked')
        apple_sources.record('iPhone 17 Pro Max', 'tgdd', url, 'wrong_model', 'Trang là iPhone 17', 'Cam vũ trụ', 'worker')
        self.assertEqual(apple_sources.status_for(rule(), 'tgdd', url)['source'], 'worker')
        with self.assertRaises(ValueError):
            apple_sources.record('x', 'tgdd', url, 'ok', '', None, 'check')

    def test_classification(self):
        self.assertEqual(apple_sources.classify(apple_sources.WrongModel('x')), 'wrong_model')
        self.assertEqual(apple_sources.classify(apple_sources.ColorNotFound('x')), 'color_not_found')
        self.assertEqual(apple_sources.classify(Exception('CPS URL nhập tay: HTTP 403 — bị chặn truy cập')), 'access_error')
        self.assertEqual(apple_sources.classify(Exception('lỗi lạ')), 'access_error')  # không bao giờ thành hợp lệ


class FakeHttp:
    def __init__(self, markup):
        self.markup = markup


class CpsResolveTests(unittest.TestCase):
    PAGE = ('<div class="related"><li data-product-id="999"></li></div>'
            '<ul class="list-variants"><li data-product-id="112617"></li><li data-product-id="112615"></li></ul>')

    def test_child_ids_only_from_color_block(self):
        self.assertEqual(apple_sources.cps_child_ids(self.PAGE), ['112617', '112615'])
        with self.assertRaises(Exception):
            apple_sources.cps_child_ids('<div>không có khối màu</div>')

    def run_resolve(self, url, parent_path='iphone-17-pro-max.html', parent_of='112588'):
        from adapters import cellphones as cps

        class Response:
            text = self.PAGE

        async def fetch(http, method, target, **kwargs):
            return Response()

        children = {i: {'general': {'product_id': int(i), 'name': f'iPhone 17 Pro Max 256GB-{i}'},
                        'filterable': {'parent_id': int(parent_of)}} for i in ('112617', '112615', '112613')}

        async def by_id(http, ids):
            return {i: children.get(i) for i in ids}

        async def graphql(http, query):
            return {'products': [{'general': {'product_id': 112588, 'name': 'iPhone 17 Pro Max 256GB', 'url_path': parent_path,
                                              'child_product': [112617, 112615, 112613]}, 'filterable': {'is_parent': True}}]}

        with patch('http_policy.fetch', fetch), patch.object(cps, 'products_by_id', by_id), patch.object(cps, 'graphql', graphql):
            return asyncio.run(apple_sources.cps_resolve(None, url))

    def test_parent_and_children_from_page(self):
        parent, kids = self.run_resolve('https://cellphones.com.vn/iphone-17-pro-max.html')
        self.assertEqual(parent['general']['product_id'], 112588)
        self.assertEqual(sorted(kids), ['112613', '112615', '112617'])  # cả màu không hiện trên trang vẫn tra theo cha

    def test_url_not_matching_parent_rejected(self):
        with self.assertRaises(Exception):
            self.run_resolve('https://cellphones.com.vn/iphone-17-pro-max.html', parent_path='iphone-17.html')
        with self.assertRaises(Exception):
            self.run_resolve('https://cellphones.com.vn/iphone-17-pro-max.html?product_id=999')


class WorkerSourceTests(unittest.TestCase):
    def test_manual_records_shape_used_by_workers(self):
        saved, _ = plan([rule(urls={'phongvu': ['https://phongvu.vn/iphone-17-pro-max--p1?sku=2']})], CURATED)
        records = apple_sources.manual_records(saved['products'][0], 'phongvu')
        self.assertEqual(records[0]['source_url'], 'https://phongvu.vn/iphone-17-pro-max--p1?sku=2')
        self.assertTrue(records[0]['config']['manual'])
        self.assertEqual(apple_sources.manual_records(saved['products'][0], 'fpt'), [])


if __name__ == '__main__':
    unittest.main()
