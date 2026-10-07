"""Kiểm tra các lỗi có thể tạo cảnh báo giá sai hoặc làm hỏng HTML."""
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from common import weeks, TZ, vnd
from telegram_reporter import analyze, render, pack, utf16_size, load_week
from scraper import extract


def row(price=10_000_000, promo='', sku='iphone-16-128gb'):
    return dict(chain_name='TGDD', sku=sku, product_name='iPhone <16> & 128GB',
                promo_price=price, promo_text=promo)


class LogicTests(unittest.TestCase):
    def test_iso_new_year(self):
        self.assertEqual(weeks(datetime(2021, 1, 4, tzinfo=TZ)), ((2021, 1), (2020, 53)))

    def test_strict_thresholds_and_or(self):
        self.assertFalse(analyze([row(9_700_000)], [row()])[0])  # đúng 3%, không vượt
        self.assertTrue(analyze([row(9_699_999)], [row()])[0])
        self.assertTrue(analyze([row(29_499_999)], [row(30_000_000)])[0])  # chỉ vượt 500k
        self.assertFalse(analyze([row(29_500_000)], [row(30_000_000)])[0])

    def test_missing_baseline_and_variant(self):
        self.assertEqual(analyze([row(promo='Tặng quà')], []), ([], [], 1))
        self.assertFalse(analyze([row(sku='iphone-16-256gb')], [row()])[0])

    def test_promo_change(self):
        self.assertTrue(analyze([row(promo='Tặng voucher 500k')], [row(promo='Tặng voucher 200k')])[1])
        self.assertFalse(analyze([row(promo=' TẶNG  QUÀ ')], [row(promo='tặng quà')])[1])

    def test_money(self):
        for text in ['19.990.000đ', '19,990,000 VND', '19990000', '19 990 000 ₫']:
            self.assertEqual(vnd(text), 19_990_000)
        for text in ['0đ', 'Liên hệ', '19.990.000đ 21.000.000đ', '1.99 triệu', '1,999.00']:
            with self.assertRaises(ValueError):
                vnd(text)

    def test_snapshot_pagination(self):
        db = MagicMock()
        run_query = MagicMock()
        price_query = MagicMock()
        db.table.side_effect = lambda name: run_query if name == 'scrape_runs' else price_query
        for name in ('select', 'eq', 'order', 'limit'):
            getattr(run_query, name).return_value = run_query
        run_query.execute.return_value.data = [dict(id='run', product_count=501)]
        for name in ('select', 'eq', 'order', 'range'):
            getattr(price_query, name).return_value = price_query
        price_query.execute.side_effect = [MagicMock(data=[row()] * 500), MagicMock(data=[row()])]
        self.assertEqual(len(load_week(db, 2026, 41)), 501)
        self.assertEqual(price_query.range.call_args_list[1].args, (500, 999))

    def test_incomplete_snapshot_rejected(self):
        db = MagicMock()
        query = MagicMock()
        db.table.return_value = query
        for name in ('select', 'eq', 'order', 'limit', 'range'):
            getattr(query, name).return_value = query
        query.execute.side_effect = [MagicMock(data=[dict(id='run', product_count=2)]), MagicMock(data=[row()])]
        with self.assertRaises(ValueError):
            load_week(db, 2026, 41)

    def test_html_and_chunking(self):
        messages = render([row(9_000_000, 'Tặng <quà> & voucher')], [row()], (2026, 41), 'https://example.com')
        self.assertIn('&lt;16&gt; &amp;', '\n'.join(messages))
        chunks = pack(['<b>' + '🎁' * 700 + '</b>'] * 10)
        self.assertTrue(all(utf16_size(c) <= 3800 for c in chunks))
        self.assertTrue(all(c.count('<b>') == c.count('</b>') for c in chunks))


class ExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_extraction(self):
        page = MagicMock()
        page.goto = AsyncMock(return_value=MagicMock(status=200))
        page.url = 'https://cellphones.com.vn/iphone-16.html'
        def locate(selector):
            loc = MagicMock()
            loc.first.wait_for = AsyncMock()
            loc.count = AsyncMock(return_value=1)
            loc.inner_text = AsyncMock(return_value={
                'h1': 'iPhone 16 128GB', '.price': '19.990.000đ',
                '.original': '22.990.000đ', '.promo': 'Tặng voucher 500.000đ',
            }[selector])
            return loc
        page.locator.side_effect = locate
        item = dict(url=page.url, chain_name='CellphoneS', sku='iphone-16-128gb',
                    product_name='iPhone 16 128GB', verify_tokens=['iPhone 16', '128GB'],
                    selectors=dict(name='h1', promo_price='.price', original_price='.original', promotions=['.promo']))
        result = await extract(page, item)
        self.assertEqual(result['promo_price'], 19_990_000)
        self.assertEqual(result['original_price'], 22_990_000)
        self.assertEqual(result['promo_text'], 'Tặng voucher 500.000đ')

    async def test_ambiguous_price_fails(self):
        page = MagicMock()
        page.goto = AsyncMock(return_value=MagicMock(status=200))
        page.url = 'https://www.thegioididong.com/dtdd/iphone-16'
        locator = MagicMock()
        locator.first.wait_for = AsyncMock()
        locator.count = AsyncMock(return_value=2)
        page.locator.return_value = locator
        item = dict(url=page.url, chain_name='TGDD', selectors={'name': 'h1'}, verify_tokens=['iPhone'])
        with self.assertRaises(ValueError):
            await extract(page, item)


if __name__ == '__main__':
    unittest.main()
