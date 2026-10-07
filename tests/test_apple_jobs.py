"""Job xác minh giá: công bố đúng model/kênh, giữ dữ liệu cũ khi lỗi, khóa chống chạy chồng. Không gọi mạng."""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import apple_jobs  # noqa: E402

RULE = {'model': 'iPhone 17 Pro Max', 'color': 'Cam vũ trụ', 'aliases': []}


def row(sku, price=1_000_000, model='iPhone 17 Pro Max', color='Cam vũ trụ', observed='2026-10-06T10:00:00+07:00', text=''):
    return {'sku': sku, 'variant_id': sku, 'model_name': model, 'promo_price': price, 'promo_text': text, 'observed_at': observed,
            'color_evidence': {'model': model, 'canonical_color': color, 'product_code': sku, 'website_color_id': 1, 'verified_at': observed}}


class Runner(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        with patch.dict(os.environ, {'WPCS_JOB_ARTIFACTS': self.folder.name}):
            importlib.reload(apple_jobs)
            import apple_job
            self.job = importlib.reload(apple_job)

    def tearDown(self):
        importlib.reload(apple_jobs)
        self.folder.cleanup()

    def test_only_verified_rows_publishable(self):
        valid = self.job.valid_row
        self.assertTrue(valid(row('1'), RULE))
        self.assertTrue(valid(row('2', price=None, text='[Tình trạng] Hết hàng'), RULE))     # chỉ có trạng thái: hợp lệ
        self.assertFalse(valid(row('3', price=None), RULE))                                   # NULL không trạng thái
        self.assertFalse(valid(row('4', price=0), RULE))                                      # không bao giờ giá 0
        self.assertFalse(valid(row('5', color='Bạc'), RULE))                                  # bằng chứng màu khác
        self.assertFalse(valid(row('6', model='iPhone 17 Pro'), RULE))                        # model khác
        bad = row('7')
        bad['color_evidence']['product_code'] = '999'
        self.assertFalse(valid(bad, RULE))                                                    # SKU không khớp mã đã chọn

    def test_missing_website_color_id_rejected(self):
        bad=row('missing-color-id')
        bad['color_evidence'].pop('website_color_id')
        self.assertFalse(self.job.valid_row(bad,RULE))

    def test_publish_replaces_only_model_and_keeps_unverified_as_stale(self):
        target = Path(self.folder.name) / 'cps-apple-selected'
        target.mkdir()
        other = row('o1', model='iPhone 16')
        (target / 'prices.json').write_text(json.dumps([other, row('a'), row('b')]))
        (target / 'issues.json').write_text(json.dumps([{'model_name': 'iPhone 16', 'reason': 'x'}, {'model_name': 'iPhone 17 Pro Max', 'reason': 'cũ'}]))
        (target / 'summary.json').write_text(json.dumps({'models': [{'model': 'iPhone 16', 'status': 'ok'}, {'model': 'iPhone 17 Pro Max', 'status': 'ok'}]}))
        kept = self.job.publish('cellphones', 'cps-apple-selected', RULE, [row('a', 990_000, observed='2026-10-07T10:00:00+07:00')],
                                [{'model_name': 'iPhone 17 Pro Max', 'reason': 'mới'}], 'job1', '2026-10-07T10:00:00+07:00')
        prices = json.loads((target / 'prices.json').read_text())
        self.assertEqual(kept, 1)
        self.assertIn(other, prices)                                                          # model khác giữ nguyên
        by_sku = {r['sku']: r for r in prices}
        self.assertEqual(by_sku['a']['promo_price'], 990_000)
        self.assertIn('stale_since', by_sku['b'])                                             # không đọc lại được: giữ + cảnh báo
        self.assertEqual(by_sku['b']['observed_at'], '2026-10-06T10:00:00+07:00')
        issues = json.loads((target / 'issues.json').read_text())
        self.assertEqual(sorted(i['reason'] for i in issues), ['mới', 'x'])
        summary = json.loads((target / 'summary.json').read_text())
        self.assertEqual({m['model']: m['status'] for m in summary['models']}, {'iPhone 16': 'ok', 'iPhone 17 Pro Max': 'partial'})

    def test_failed_channel_keeps_old_rows_and_warns(self):
        target = Path(self.folder.name) / 'fpt-apple-selected'
        target.mkdir()
        (target / 'prices.json').write_text(json.dumps([row('a', observed='2026-10-06T09:00:00+07:00')]))
        (target / 'summary.json').write_text(json.dumps({'models': [{'model': 'iPhone 17 Pro Max', 'status': 'ok'}]}))
        before = (target / 'prices.json').read_text()
        kept, at = self.job.mark_stale('fpt-apple-selected', RULE, '2026-10-07T10:00:00+07:00', 'HTTP 403', 'job2')
        self.assertEqual((kept, at), (1, '2026-10-06T09:00:00+07:00'))
        self.assertEqual((target / 'prices.json').read_text(), before)                         # không đổi giá cũ
        summary = json.loads((target / 'summary.json').read_text())
        self.assertEqual(summary['models'][0]['last_failed_update']['reason'], 'HTTP 403')


class LockTests(unittest.TestCase):
    def test_channel_lock_blocks_second_holder(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(apple_jobs, 'LOCKS', Path(folder)):
            with apple_jobs.channel_lock('fpt'):
                code = subprocess.run([sys.executable, '-c', (
                    f"import sys;sys.path.insert(0,{str(ROOT)!r});import apple_jobs;from pathlib import Path;apple_jobs.LOCKS=Path({folder!r})\n"
                    "try:\n with apple_jobs.channel_lock('fpt'):sys.exit(0)\nexcept apple_jobs.Busy:sys.exit(3)")]).returncode
                self.assertEqual(code, 3)
                other = subprocess.run([sys.executable, '-c', (
                    f"import sys;sys.path.insert(0,{str(ROOT)!r});import apple_jobs;from pathlib import Path;apple_jobs.LOCKS=Path({folder!r})\n"
                    "with apple_jobs.channel_lock('tgdd'):pass")]).returncode
                self.assertEqual(other, 0)                                                    # kênh khác không bị chặn

    def test_cli_worker_detection(self):
        listing = '\n'.join([
            '101 /x/.venv/bin/python tools/scrape_mw_apple.py iPhone 17',
            '102 /x/.venv/bin/python /abs/tools/scrape_remaining_apple.py viettel',
            '103 /x/.venv/bin/python tools/scrape_remaining_apple.py',
            '104 /bin/zsh -c python tools/scrape_cps_apple.py',            # shell bao ngoài: không tính
            '105 grep scrape_mw_apple.py',
            '106 /x/.venv/bin/python tools/scrape_cps_apple.py --cached'])
        with patch('subprocess.run') as run:
            run.return_value.stdout = listing
            found = apple_jobs.running_workers(exclude={106})
        self.assertEqual(found, {'tgdd': [101], 'viettel': [102, 103], 'fpt': [103], 'phongvu': [103]})

    def test_orphan_job_marked_error(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(apple_jobs, 'JOBS', Path(folder)):
            (Path(folder) / 'j1').mkdir()
            apple_jobs.write_state('j1', {'id': 'j1', 'model': 'x', 'created_at': 'a', 'status': 'running', 'runner_pid': 999999,
                                         'channels': {'fpt': {'status': 'running'}}})
            self.assertIsNone(apple_jobs.active_job())
            state = apple_jobs.read_state('j1')
            self.assertEqual((state['status'], state['channels']['fpt']['status']), ('error', 'error'))
            with self.assertRaises(ValueError):
                apple_jobs.job_dir('../x')

    def test_fingerprint_changes_with_rule(self):
        with tempfile.TemporaryDirectory() as folder:
            colors, models = Path(folder) / 'c.json', Path(folder) / 'm.json'
            models.write_text(json.dumps({'version': 1, 'models': []}))
            colors.write_text(json.dumps({'version': 1, 'products': [RULE, {'model': 'iPhone 16', 'color': 'Đen', 'aliases': []}]}))
            with patch.object(apple_jobs, 'COLORS', colors), patch.object(apple_jobs, 'MODELS', models):
                first, rule = apple_jobs.rule_fingerprint('iPhone 17 Pro Max')
                colors.write_text(json.dumps({'version': 1, 'products': [RULE, {'model': 'iPhone 16', 'color': 'Bạc', 'aliases': []}]}))
                self.assertEqual(apple_jobs.rule_fingerprint('iPhone 17 Pro Max')[0], first)   # model khác đổi: không ảnh hưởng
                colors.write_text(json.dumps({'version': 1, 'products': [{**RULE, 'aliases': ['Cam']}]}))
                self.assertNotEqual(apple_jobs.rule_fingerprint('iPhone 17 Pro Max')[0], first)


if __name__ == '__main__':
    unittest.main()
