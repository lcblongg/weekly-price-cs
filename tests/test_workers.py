"""Worker theo kênh: chọn kênh, đầu ra độc lập, lỗi cô lập, tổng hợp báo cáo, toàn vẹn dữ liệu. Không gọi mạng."""
import asyncio
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import apple_jobs
import discover_products
import scraper
import telegram_reporter
from chains import resolve
from common import PipelineError
from errors import classify
from adapters import registry


class ChainSelectionTests(unittest.TestCase):
    def test_aliases_all_and_invalid(self):
        self.assertEqual(resolve(['mw', 'cps']), ['TGDD', 'CellphoneS'])
        self.assertEqual(resolve(['viettel,pv', 'fpt']), ['Viettel Store', 'Phong Vũ', 'FPT Shop'])
        self.assertEqual(len(resolve(['all'])), 5)
        self.assertEqual(resolve(['tgdd', 'TGDD']), ['TGDD'])
        for bad in (['amazon'], [], ['']):
            with self.assertRaises(PipelineError):
                resolve(bad)

    def test_error_classification(self):
        self.assertEqual(classify('Phong Vũ chi tiết: HTTP 403 — bị chặn truy cập, không lưu giá'), 'blocked')
        self.assertEqual(classify('Viettel: HTTP 403 trên nguồn HTTP công khai'), 'blocked')
        self.assertEqual(classify('FPT Shop: HTTP 429'), 'rate_limited')
        self.assertEqual(classify('robots.txt không cho cào TGDD'), 'robots')
        self.assertEqual(classify('CellphoneS: biến thể hết hàng tại khu vực mặc định'), 'out_of_stock')
        self.assertEqual(classify('Lỗi kỹ thuật KeyError'), 'technical')


def source(chain, row):
    return {'chain_name': chain, 'seeds': [f'https://example/{chain}/{row}'], 'category': 'Điện thoại',
            'brand': 'X', 'input_row': row, 'product_url_pattern': '.*'}


class DiscoveryWorkerTests(unittest.TestCase):
    def test_failed_source_isolated_and_not_published(self):
        ready = lambda chain, i: {'chain_name': chain, 'source_url': f'https://x/{chain}/{i}', 'status': 'ready', 'reason': '',
                                  'config': {'sku': f'{chain}-{i}', 'url': f'https://x/{chain}/{i}', 'listing_urls': []}}

        async def fake(src, http, browser, now):
            if src['chain_name'] == 'TGDD' and src['input_row'] == 2:
                raise PipelineError('TGDD: trang danh mục HTTP 403')
            return [ready(src['chain_name'], src['input_row'])], {'listed': 1, 'excluded': [], 'color_variants_skipped': 0, 'notes': []}

        with tempfile.TemporaryDirectory() as out, patch.object(discover_products, 'discover_source', fake), \
                patch.object(discover_products, 'database') as db, patch.object(apple_jobs,'LOCKS',Path(out)/'locks'):
            args = Namespace(dry_run=False, json_only=True)
            old_catalog=Path(out)/'tgdd'/'catalog.json';old_catalog.parent.mkdir()
            old_catalog.write_text(json.dumps([ready('TGDD',999)]))

            async def both():
                return await asyncio.gather(
                    discover_products.discover_chain('TGDD', [source('TGDD', 1), source('TGDD', 2)], None, None, out, args, 'now', True),
                    discover_products.discover_chain('Phong Vũ', [source('Phong Vũ', 1)], None, None, out, args, 'now', True))
            db.return_value.rpc.return_value.execute.return_value.data = 'run-pv'
            tgdd, pv = asyncio.run(both())
            self.assertEqual((tgdd['status'], tgdd['published'], tgdd['sources_failed']), ('failed', False, 1))
            self.assertEqual(tgdd['failed_sources'][0]['error_kind'], 'blocked')
            self.assertTrue(tgdd['retained_catalog'])
            self.assertEqual(json.loads(old_catalog.read_text())[0]['config']['sku'],'TGDD-999')
            self.assertEqual(len(json.loads(old_catalog.with_name('catalog.failed.json').read_text())),1)
            self.assertEqual((pv['status'], pv['published'], pv['discovery_run_id']), ('ok', True, 'run-pv'))
            # Chỉ kênh thành công được ghi lên Supabase, và chỉ catalog của chính kênh đó.
            calls = db.return_value.rpc.call_args_list
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0].args[1]['p_chain'], 'Phong Vũ')
            for slug, count in (('tgdd', 1), ('phongvu', 1)):
                folder = Path(out) / slug
                self.assertEqual(len(json.loads((folder / 'catalog.json').read_text())), count)
                self.assertTrue((folder / 'summary.json').exists() and (folder / 'worker.log').exists())


class Quote:
    def __init__(self, failing=()):
        self.failing = set(failing)

    async def read_product(self, item, http, browser):
        if item['url'] in self.failing:
            raise PipelineError('HTTP 403 — bị chặn truy cập, không lưu giá')
        return {'variant_id': item['variant_id'], 'original_price': None, 'promo_price': 2_000_000, 'promo_text': 'Quà'}


DOMAIN = {'TGDD': 'www.thegioididong.com', 'Phong Vũ': 'phongvu.vn', 'FPT Shop': 'fptshop.com.vn'}


def catalog_row(chain, code, i, status='ready'):
    config = {'chain_name': chain, 'url': f'https://{DOMAIN[chain]}/{i}', 'sku': f'{code}-{i}', 'variant_id': str(i),
              'product_name': f'Máy {i}', 'verified': True, 'adapter': chain, 'verify_tokens': [str(i)], 'category': 'Điện thoại'}
    return {'chain_name': chain, 'source_url': config['url'], 'status': status,
            'reason': '' if status == 'ready' else 'Hết hàng', 'config': config}


class PriceWorkerTests(unittest.TestCase):
    def setUp(self):
        # Unit test dùng khóa riêng, không tranh khóa hoặc ảnh hưởng bot thật đang chạy.
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        locks = patch.object(apple_jobs, 'LOCKS', Path(folder.name))
        locks.start()
        self.addCleanup(locks.stop)

    def run_workers(self, out, adapters, limit=None):
        rows = [catalog_row('Phong Vũ', 'pv', i) for i in range(4)] + [catalog_row('Phong Vũ', 'pv', 9, 'review')]
        rows += [catalog_row('FPT Shop', 'fpt', i) for i in range(3)]
        path = Path(out) / 'catalog.json'
        path.write_text(json.dumps(rows))
        args = Namespace(out=out, catalog='file', config=str(path), dry_run=True, limit=limit)
        originals = dict(registry.ADAPTERS)
        registry.ADAPTERS.update(adapters)
        try:
            with patch.object(scraper, 'validate_url', lambda chain, url: None):
                async def go():
                    return await asyncio.gather(scraper.scrape_one('Phong Vũ', args, None, None),
                                                scraper.scrape_one('FPT Shop', args, None, None))
                return asyncio.run(go())
        finally:
            registry.ADAPTERS.clear()
            registry.ADAPTERS.update(originals)

    def test_price_failures_keep_previous_prices_with_explicit_stale_marker(self):
        with tempfile.TemporaryDirectory() as out:
            self.run_workers(out, {'Phong Vũ':Quote(), 'FPT Shop':Quote()})
            target=Path(out)/'phongvu'/'prices.json'
            previous=json.loads(target.read_text())
            failed_urls={f'https://phongvu.vn/{i}' for i in range(5)}
            pv,_=self.run_workers(out, {'Phong Vũ':Quote(failing=failed_urls), 'FPT Shop':Quote()})
            self.assertEqual(pv['status'],'failed')
            self.assertEqual(json.loads(target.read_text()),previous)
            self.assertIn('last_failed_update',pv)
            pv,_=self.run_workers(out, {'Phong Vũ':Quote(failing={'https://phongvu.vn/1'}), 'FPT Shop':Quote()})
            retained=[r for r in json.loads(target.read_text()) if r.get('stale_since')]
            self.assertEqual(len(retained),1)
            self.assertIn('403',retained[0]['stale_reason'])

    def test_independent_outputs_and_integrity(self):
        with tempfile.TemporaryDirectory() as out:
            pv, fpt = self.run_workers(out, {'Phong Vũ': Quote(failing={'https://phongvu.vn/1'}), 'FPT Shop': Quote()})
            self.assertEqual((pv['status'], pv['prices'], pv['issues'], pv['expected']), ('ok', 3, 2, 5))
            self.assertEqual(pv['blocked'], 1)
            self.assertEqual((fpt['status'], fpt['prices'], fpt['expected']), ('ok', 3, 3))
            prices = json.loads((Path(out) / 'phongvu' / 'prices.json').read_text())
            issues = json.loads((Path(out) / 'phongvu' / 'issues.json').read_text())
            self.assertEqual(len(prices) + len(issues), pv['expected'])
            self.assertTrue(all(p['chain_name'] == 'Phong Vũ' for p in prices))
            self.assertEqual({i['stage'] for i in issues}, {'price'})
            self.assertTrue((Path(out) / 'fpt' / 'prices.json').exists())

    def test_one_worker_failure_does_not_affect_other(self):
        with tempfile.TemporaryDirectory() as out:
            everything = {f'https://phongvu.vn/{i}' for i in range(4)}
            pv, fpt = self.run_workers(out, {'Phong Vũ': Quote(failing=everything), 'FPT Shop': Quote()})
            self.assertEqual(pv['status'], 'failed')
            self.assertIn('Không đọc được giá hay trạng thái nào', pv['message'])
            self.assertFalse((Path(out) / 'phongvu' / 'run.json').exists())
            self.assertEqual(fpt['status'], 'ok')

    def test_limited_sample_covers_every_source(self):
        items = [{'chain_name': 'TGDD', 'input_row': row, 'url': f'u{row}-{i}'} for row in (2, 3, 4) for i in range(10)]
        picked = scraper.sample_by_source(items, 6)
        self.assertEqual(sorted({p['input_row'] for p in picked}), [2, 3, 4])
        self.assertEqual(len(picked), 6)

    def test_duplicates_detected_before_sampling(self):
        with tempfile.TemporaryDirectory() as out:
            rows = [catalog_row('TGDD', 'tgdd', i) for i in range(5)]
            rows.append(catalog_row('TGDD', 'tgdd', 4))   # dòng trùng nằm cuối, ngoài mẫu 2 dòng đầu
            path = Path(out) / 'c.json'
            path.write_text(json.dumps(rows))
            with self.assertRaises(PipelineError):
                scraper.load_catalog(Namespace(catalog='file', config=str(path), dry_run=True, limit=2), 'TGDD')

    def test_out_of_stock_is_issue_not_zero_price(self):
        with tempfile.TemporaryDirectory() as out:
            class OOS(Quote):
                async def read_product(self, item, http, browser):
                    if item['url'].endswith('/2'):
                        raise PipelineError('Phong Vũ: SKU hiện không bán (hết hàng/ngừng kinh doanh)')
                    return await super().read_product(item, http, browser)
            pv, _ = self.run_workers(out, {'Phong Vũ': OOS(), 'FPT Shop': Quote()})
            prices = json.loads((Path(out) / 'phongvu' / 'prices.json').read_text())
            issues = json.loads((Path(out) / 'phongvu' / 'issues.json').read_text())
            self.assertTrue(all(p['promo_price'] > 0 for p in prices))
            self.assertNotIn('pv-2', {p['sku'] for p in prices})
            self.assertEqual([i['error_kind'] for i in issues if i['sku'] == 'pv-2'], ['out_of_stock'])

    def test_limit_only_for_dry_run(self):
        with tempfile.TemporaryDirectory() as out:
            path = Path(out) / 'c.json'
            path.write_text(json.dumps([catalog_row('TGDD', 'tgdd', i) for i in range(5)]))
            with self.assertRaises(PipelineError):
                scraper.load_catalog(Namespace(catalog='file', config=str(path), dry_run=False, limit=2), 'TGDD')
            items, _, _ = scraper.load_catalog(Namespace(catalog='file', config=str(path), dry_run=True, limit=2), 'TGDD')
            self.assertEqual(len(items), 2)


class AggregatorTests(unittest.TestCase):
    def test_combined_report_states_every_channel(self):
        with tempfile.TemporaryDirectory() as out:
            base = Path(out) / 'prices'
            row = {'chain_name': 'Phong Vũ', 'sku': 'pv-1', 'product_name': 'Galaxy A57', 'promo_price': 1, 'promo_text': ''}
            for slug, summary, prices in [
                ('phongvu', {'chain_name': 'Phong Vũ', 'stage': 'prices', 'status': 'ok', 'expected': 2, 'prices': 1, 'issues': 1, 'catalog_ready': 1, 'blocked': 0}, [row]),
                ('tgdd', {'chain_name': 'TGDD', 'stage': 'prices', 'status': 'failed', 'message': 'TGDD: HTTP 403 — bị chặn truy cập'}, None)]:
                (base / slug).mkdir(parents=True)
                (base / slug / 'summary.json').write_text(json.dumps(summary))
                if prices is not None:
                    (base / slug / 'prices.json').write_text(json.dumps(prices))
            args = Namespace(summaries=str(base), out=str(Path(out) / 'report'), local=True, dry_run=True, chains='all')
            states = telegram_reporter.daily_report(args)
            self.assertEqual(states['TGDD']['status'], 'failed')
            self.assertEqual(states['CellphoneS']['status'], 'missing')
            html = (Path(out) / 'report' / 'report.html').read_text()
            for text in ('Tình trạng 5 kênh', 'TGDD: ❌ Lỗi', 'Phong Vũ: ✅ Đủ — 1/2 link có giá', 'CellphoneS: ❌ Không có kết quả'):
                self.assertIn(text, html)

    def test_manual_rerun_marks_unselected_as_skipped(self):
        with tempfile.TemporaryDirectory() as out:
            states = telegram_reporter.collect_summaries(out, ['TGDD'])
            self.assertEqual(states['TGDD']['status'], 'missing')
            self.assertEqual(states['FPT Shop']['status'], 'skipped')
            import discovery_status
            self.assertEqual(discovery_status.collect(out, ['TGDD'])['Phong Vũ']['status'], 'skipped')
            self.assertEqual(discovery_status.collect(out)['Phong Vũ']['status'], 'missing')

    def test_duplicate_summaries_rejected(self):
        with tempfile.TemporaryDirectory() as out:
            for name in ('a', 'b'):
                (Path(out) / name).mkdir()
                (Path(out) / name / 'summary.json').write_text(json.dumps({'chain_name': 'TGDD', 'stage': 'prices', 'status': 'ok'}))
            with self.assertRaises(PipelineError):
                telegram_reporter.collect_summaries(out)


if __name__ == '__main__':
    unittest.main()
