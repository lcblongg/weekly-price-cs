"""Không dùng website/DB thật; kiểm tra các lỗi có thể ghép nhầm sản phẩm."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from catalog import clean_url, iphone_identity, fetch_discovered
from discover_products import reject_duplicate_skus, validate_sources
from common import PipelineError


class DiscoveryTests(unittest.TestCase):
    def test_tracking_removed_variant_preserved(self):
        url = clean_url('CellphoneS', 'https://cellphones.com.vn/mobile/apple.html',
                        '/iphone-16.html?utm_source=a&color=blue&storage=128#price')
        self.assertEqual(url, 'https://cellphones.com.vn/iphone-16.html?color=blue&storage=128')
        with self.assertRaises(PipelineError):
            clean_url('CellphoneS', 'https://cellphones.com.vn/', 'https://evil.example/item')

    def test_identity_distinguishes_variants(self):
        pro = iphone_identity('Apple iPhone 16 Pro Max 256GB | Chính hãng VN/A')
        normal = iphone_identity('iPhone 16 128GB')
        self.assertEqual(pro['sku'], 'apple-iphone-16-pro-max-256gb')
        self.assertNotEqual(pro['sku'], normal['sku'])
        self.assertEqual(iphone_identity('iPhone 16e 128GB')['sku'], 'apple-iphone-16e-128gb')
        self.assertEqual(iphone_identity('iPhone Air 1TB')['sku'], 'apple-iphone-air-1tb')

    def test_unknown_used_or_ambiguous_identity_requires_review(self):
        for name in ['iPhone 16', 'iPhone 16 128GB 256GB', 'iPhone 16 128GB cũ',
                     'iPhone 16 128GB xách tay', 'iPad Air 128GB', 'iPhone 16 64TB',
                     'iPhone 16 128GB và iPhone 15 128GB']:
            with self.assertRaises(PipelineError, msg=name):
                iphone_identity(name)

    def test_duplicate_sku_all_review(self):
        rows = [dict(chain_name='TGDD',status='ready',config={'sku':'same','verified':True,'url':f'https://x/{i}','listing_urls':[]}) for i in range(2)]
        rows.append(dict(chain_name='FPT Shop',status='ready',config={'sku':'same','verified':True,'url':'https://x/0','listing_urls':[]}))
        reject_duplicate_skus(rows)
        self.assertEqual([r['status'] for r in rows], ['review','review','ready'])
        self.assertFalse(rows[0]['config']['verified'])

    def test_review_and_ready_same_link_kept_once(self):
        from discover_products import dedupe_source_urls
        rows = [dict(chain_name='TGDD', source_url='https://x/a', status='review', reason='Hết hàng', config={'listing_urls': ['s1']}),
                dict(chain_name='TGDD', source_url='https://x/a', status='ready', reason='', config={'listing_urls': ['s2']}),
                dict(chain_name='FPT Shop', source_url='https://x/a', status='review', reason='', config={'listing_urls': ['s3']})]
        dedupe_source_urls(rows)
        self.assertEqual([(r['chain_name'], r['status']) for r in rows], [('TGDD', 'ready'), ('FPT Shop', 'review')])
        self.assertEqual(rows[0]['config']['listing_urls'], ['s1', 's2'])

    def test_same_link_from_two_sources_kept_once(self):
        # Cùng một link xuất hiện ở hai trang danh mục: không phải hai biến thể, giữ một dòng và gộp nguồn.
        rows = [dict(chain_name='TGDD',status='ready',config={'sku':'tgdd-1','url':'https://x/a','listing_urls':[f'https://seed/{i}']}) for i in range(2)]
        reject_duplicate_skus(rows)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['config']['listing_urls'], ['https://seed/0', 'https://seed/1'])

    def fake_db(self, run, rows):
        db, query = MagicMock(), MagicMock()
        db.table.return_value = query
        for name in ['select','eq','order','limit','range']:
            getattr(query,name).return_value = query
        query.execute.side_effect = [MagicMock(data=[run]), MagicMock(data=rows)]
        return db

    def test_ready_only_and_review_count(self):
        now = datetime.now(timezone.utc)
        run = dict(id='run',completed_at=now.isoformat(),candidate_count=2,ready_count=1)
        rows = [dict(chain_name='TGDD',source_url='https://x/1',reason='',status='ready',config={'verified':True}),
                dict(chain_name='TGDD',source_url='https://x/2',reason='Hết hàng',status='review',config={})]
        items, meta = fetch_discovered(self.fake_db(run,rows),now=now)
        self.assertEqual(items,[{'verified':True}])
        self.assertEqual(meta['review'],1)
        # Link review được mang sang bot giá để hiển thị lý do, không biến mất.
        self.assertEqual(meta['review_rows'][0]['reason'],'Hết hàng')

    def test_stale_catalog_rejected(self):
        now = datetime.now(timezone.utc)
        run = dict(id='run',completed_at=(now-timedelta(days=9)).isoformat(),candidate_count=1,ready_count=1)
        with self.assertRaises(PipelineError):
            fetch_discovered(self.fake_db(run,[]),now=now)

    def test_incomplete_catalog_rejected(self):
        now = datetime.now(timezone.utc)
        run = dict(id='run',completed_at=now.isoformat(),candidate_count=2,ready_count=1)
        with self.assertRaises(PipelineError):
            fetch_discovered(self.fake_db(run,[dict(status='ready',config={})]),now=now)

    def test_invalid_listing_limit_rejected(self):
        with self.assertRaises(PipelineError):
            validate_sources([dict(chain_name='TGDD', seeds=['https://www.thegioididong.com/dtdd'],
                                   product_url_pattern='iphone',max_pages=0)])


if __name__ == '__main__':
    unittest.main()
