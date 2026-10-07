"""Kiểm tra logic adapter 5 đại lý, robots.txt và định danh — không gọi website thật."""
import asyncio
import json
import unittest

import robots
from common import PipelineError
from identity import describe, chain_sku, OutOfScope, storage_of
from discover_products import representatives
from adapters.nextflight import flight, balanced, object_after
from adapters.tgdd import is_flash, normalize_href, flash_notes
from adapters.fptshop import promotion_notes
from adapters.cellphones import color_of, _filters, page_counts
import scraper


class RobotsTests(unittest.TestCase):
    def test_wildcards_and_longest_rule(self):
        groups = robots.parse('User-agent: *\nCrawl-delay: 5\nDisallow: /*sort=\nDisallow: /search?*\nAllow: /search?ok$\n')
        self.assertFalse(robots.allowed(groups, 'https://x.vn/dien-thoai?sort=gia'))
        self.assertFalse(robots.allowed(groups, 'https://x.vn/search?q=a'))
        self.assertTrue(robots.allowed(groups, 'https://x.vn/search?ok'))
        self.assertTrue(robots.allowed(groups, 'https://x.vn/dien-thoai/samsung'))
        self.assertEqual(robots.crawl_delay(groups), 5)

    def test_rules_after_new_agent_belong_to_that_group(self):
        # Cấu trúc thật của CellphoneS: các Disallow nằm sau "User-agent: Googlebot-image".
        text = 'User-agent: *\nUser-agent: Googlebot\nDisallow:\nUser-agent: Googlebot-image\nDisallow:\nDisallow: /*?*\n'
        groups = robots.parse(text)
        self.assertTrue(robots.allowed(groups, 'https://c.vn/a.html?x=1'))
        self.assertFalse(robots.allowed(groups, 'https://c.vn/a.html?x=1', agent='googlebot-image'))

    def test_specific_agent_group_overrides_star(self):
        groups = robots.parse('User-agent: *\nDisallow: /\nUser-agent: WeeklyPriceCS\nAllow: /\n')
        self.assertTrue(robots.allowed(groups, 'https://x.vn/a'))


class IdentityTests(unittest.TestCase):
    def check(self, name, category, model, storage=None):
        result = describe(name, category)
        self.assertEqual(result['model_name'], model, name)
        if storage is not None:
            self.assertEqual(result['storage'], storage, name)

    def test_phone_families(self):
        self.check('Samsung Galaxy A27 A276B 5G (6G+128G) Hồng', 'Điện thoại', 'Galaxy A27', '128GB')
        self.check('Samsung Galaxy S26 Ultra 5G 12GB 256GB', 'Điện thoại', 'Galaxy S26 Ultra', '256GB')
        self.check('Samsung Galaxy Z Fold8 Ultra 5G 12GB 256GB Tím SM-F976', 'Điện thoại', 'Galaxy Z Fold8 Ultra', '256GB')
        self.check('Điện thoại Apple iPhone 18 Pro 256GB - Đỏ Burgundy (MJRR4X/A)', 'Điện thoại', 'iPhone 18 Pro', '256GB')
        self.check('Xiaomi Redmi Note 15 Pro 5G 8GB/256GB', 'Điện thoại', 'Redmi Note 15 Pro', '256GB')
        self.check('OPPO Reno15 F 5G 8GB/256GB', 'Điện thoại', 'OPPO Reno15 F', '256GB')
        self.check('iPhone 17 Pro Max 2TB', 'Điện thoại', 'iPhone 17 Pro Max', '2TB')

    def test_tablet_laptop_watch_airpods(self):
        self.check('Máy tính bảng Samsung Galaxy Tab S10 FE+ WiFi 8GB/128GB', 'Máy tính bảng', 'Galaxy Tab S10 FE Plus', '128GB')
        self.check('iPad Air M3 11 inch WiFi 128GB', 'Máy tính bảng', 'iPad Air 11 M3 WiFi', '128GB')
        self.check('OPPO Pad SE WiFi 4GB 128GB', 'Máy tính bảng', 'OPPO Pad SE', '128GB')
        self.check('MacBook Air 13 inch M4 16GB/256GB', 'Máy tính xách tay', 'MacBook Air 13 M4', '256GB')
        self.check('Asus Vivobook 15 X1504VA Core 7 150U (BQ295W)', 'Máy tính xách tay', 'Asus Vivobook 15')
        self.check('Samsung Galaxy Watch Ultra2 LTE Đen', 'Đồng hồ thông minh', 'Galaxy Watch Ultra 2 LTE')
        self.check('Apple Watch Series 11 GPS 42mm viền nhôm', 'Đồng hồ thông minh', 'Apple Watch S11')
        self.check('Tai nghe chụp tai chống ồn Apple AirPods Max 2 2026', 'Airpods', 'AirPods Max 2')
        self.check('Tai nghe Bluetooth Apple AirPods 5 2026 Sạc Có Dây (MKFW4)', 'Airpods', 'AirPods 5')

    def test_unknown_model_is_unclassified_not_guessed(self):
        self.assertIsNone(describe('Điện thoại Nokia 3210 4G', 'Điện thoại')['model_name'])

    def test_out_of_scope_items(self):
        for name, category in [('iPhone 16 128GB cũ đẹp', 'Điện thoại'), ('Tai nghe Bluetooth Powerbeats Pro 2', 'Airpods'),
                               ('Apple Mac mini M5 Pro 24GB 1TB', 'Máy tính xách tay'), ('Laptop Dell trưng bày', 'Máy tính xách tay')]:
            with self.assertRaises(OutOfScope, msg=name):
                describe(name, category)

    def test_ram_not_taken_as_storage(self):
        self.assertEqual(storage_of('Galaxy A07s A077F (4G+64GB)'), '64GB')
        self.assertEqual(storage_of('Galaxy S26 Ultra 16GB/1TB'), '1TB')

    def test_chain_sku_is_variant_locked(self):
        self.assertEqual(chain_sku('TGDD', '0131491005309'), 'tgdd-0131491005309')
        self.assertNotEqual(chain_sku('CellphoneS', '125129'), chain_sku('CellphoneS', '125130'))
        with self.assertRaises(PipelineError):
            chain_sku('FPT Shop', '')


class RepresentativeTests(unittest.TestCase):
    def test_same_price_colors_keep_one_different_keep_all(self):
        same = [{'url': f'u{i}', 'variant_id': str(i), 'group': 'g', 'listing_price': 100, 'stock': 1} for i in range(3)]
        diff = [{'url': 'a', 'variant_id': '7', 'group': 'h', 'listing_price': 100, 'stock': 1},
                {'url': 'b', 'variant_id': '8', 'group': 'h', 'listing_price': 120, 'stock': 1}]
        chosen, skipped = representatives('FPT Shop', same + diff)
        self.assertEqual(sorted(c['variant_id'] for c in chosen), ['0', '7', '8'])
        self.assertEqual(skipped, 2)

    def test_prefers_in_stock_color(self):
        rows = [{'url': 'a', 'variant_id': '1', 'parent_id': 'p', 'listing_price': 9, 'stock': 0},
                {'url': 'b', 'variant_id': '2', 'parent_id': 'p', 'listing_price': 9, 'stock': 4}]
        self.assertEqual(representatives('CellphoneS', rows)[0][0]['variant_id'], '2')


class ParserTests(unittest.TestCase):
    def test_next_flight_json_only(self):
        payload = json.dumps('0:{"a":1}\n1:{"initialState":{"x":"}{","y":[1,2]}}\n')[1:-1]
        markup = f'<script>self.__next_f.push([1,"{payload}"])</script>'
        text = flight(markup)
        self.assertEqual(object_after(text, '"initialState":'), {'x': '}{', 'y': [1, 2]})
        with self.assertRaises(PipelineError):
            flight('<html>no data</html>')
        with self.assertRaises(PipelineError):
            balanced('{"a":', 0)

    def test_tgdd_gold_hour_not_used_as_regular_price(self):
        normal = {'price': 9290000, 'saleProgramTypeId': 0}
        gold = {'price': 8590000, 'saleProgramTypeId': 0, 'htmlIdRule': {'groupId': 'GoldHour.Promotion'},
                'startDate': '2026-10-06T09:00:00', 'endDate': '2026-10-06T12:00:00', 'stockQuantity': {'maxQuantity': 5}}
        self.assertFalse(is_flash(normal))
        self.assertTrue(is_flash(gold))
        self.assertIn('8.590.000đ', flash_notes([gold])[0])
        self.assertIn('5 suất', flash_notes([gold])[0])

    def test_tgdd_duplicated_prefix_link(self):
        self.assertEqual(normalize_href('/dong-ho-thong-minh//dong-ho-thong-minh/garmin-x?utm=1', '/dong-ho-thong-minh/'),
                         '/dong-ho-thong-minh/garmin-x')
        self.assertEqual(normalize_href('/dtdd/samsung-a27', '/dtdd/'), '/dtdd/samsung-a27')

    def test_fpt_promotions_summarized_not_subtracted(self):
        promotion = {'included': [{'name': 'Giảm ngay 1,600,000đ'}],
                     'other': [{'programType': 'TradeIn', 'name': 'Thu cũ đổi mới giảm thêm 4,000,000đ', 'discountPrice': 4000000},
                               {'programType': 'TradeIn', 'name': 'Thu cũ đổi mới giảm thêm 800,000đ', 'discountPrice': 800000},
                               {'programType': 'PriceOnline', 'name': 'Online', 'finalPrice': 1}],
                     'payment': [{'name': 'Giảm 300.000đ qua thẻ'}]}
        notes = promotion_notes(promotion, {'finalPrice': 11490000, 'name': 'Giảm 2 triệu khi mua online', 'expireDate': '2026-10-07T08:46:13'})
        self.assertIn('Thu cũ đổi mới giảm thêm đến 4.000.000đ', notes)
        self.assertTrue(any(n.startswith('Giá online giới hạn 11.490.000đ') for n in notes))
        self.assertEqual(sum('Thu cũ' in n for n in notes), 1)

    def test_cellphones_filters_and_colors(self):
        query = _filters('491', 'https://cellphones.com.vn/x.html?phone_accessory_brands=apple-chinh-hang')
        self.assertIn('phone_accessory_brands: {in: ["apple-chinh-hang"]}', query)
        self.assertIn('use_nice_uri: true', query)
        with self.assertRaises(PipelineError):
            _filters('491', 'https://cellphones.com.vn/x.html?phone_accessory_brands=a%22%7D')
        self.assertEqual(color_of('Samsung Galaxy S26 Ultra 12GB 256GB-Tím Cobalt', ''), 'Tím Cobalt')
        markup = '<div class="product-info-container product-item"></div>' * 20 + '<a class="btn-show-more">Xem thêm 46 sản phẩm'
        self.assertEqual(page_counts(markup), 66)


class FakeAdapter:
    def __init__(self, results):
        self.results = results

    async def read_product(self, item, http, browser):
        value = self.results[item['url']]
        if isinstance(value, Exception):
            raise value
        return value


class ScraperTests(unittest.TestCase):
    def test_failures_become_issues_and_rows_keep_lock(self):
        items = [
            {'chain_name': 'Phong Vũ', 'url': 'https://phongvu.vn/a--s1', 'sku': 'pv-1', 'variant_id': '1', 'product_name': 'A', 'category': 'Điện thoại'},
            {'chain_name': 'Phong Vũ', 'url': 'https://phongvu.vn/b--s2', 'sku': 'pv-2', 'variant_id': '2', 'product_name': 'B', 'category': 'Điện thoại'},
            {'chain_name': 'Phong Vũ', 'url': 'https://phongvu.vn/c--s3', 'sku': 'pv-3', 'variant_id': '3', 'product_name': 'C', 'category': 'Điện thoại'},
        ]
        quote = lambda vid: {'variant_id': vid, 'original_price': None, 'promo_price': 1_000_000, 'promo_text': ''}
        fake = FakeAdapter({items[0]['url']: quote('1'), items[1]['url']: PipelineError('Phong Vũ: SKU hiện không bán (hết hàng)'),
                            items[2]['url']: quote('99')})
        from adapters import registry
        original = registry.ADAPTERS['Phong Vũ']
        registry.ADAPTERS['Phong Vũ'] = fake
        try:
            rows, issues = [], []
            asyncio.run(scraper.scrape_chain(items, None, None, rows, issues))
        finally:
            registry.ADAPTERS['Phong Vũ'] = original
        self.assertEqual([r['sku'] for r in rows], ['pv-1'])
        self.assertEqual(len(rows) + len(issues), len(items))
        reasons = {i['sku']: i['reason'] for i in issues}
        self.assertIn('hết hàng', reasons['pv-2'])
        self.assertIn('khác biến thể', reasons['pv-3'])


if __name__ == '__main__':
    unittest.main()
