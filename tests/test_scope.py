"""Phạm vi hãng (config/scope.json): chỉ Apple; Excel 86 nguồn giữ nguyên. Không gọi mạng."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import scope  # noqa: E402


class ScopeTests(unittest.TestCase):
    def test_repository_scope_is_apple_only(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('WPCS_SCOPE', None)
            self.assertEqual(scope.brands(), {'apple'})
            self.assertTrue(scope.in_scope(' apple '))
            self.assertFalse(scope.in_scope('Samsung'))
            self.assertFalse(scope.in_scope(''))

    def test_empty_list_means_all_and_invalid_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 's.json'
            path.write_text(json.dumps({'version': 1, 'brands': []}))
            self.assertTrue(scope.in_scope('Samsung', scope.brands(path)))
            path.write_text(json.dumps({'version': 2, 'brands': 'Apple'}))
            with self.assertRaises(ValueError):
                scope.brands(path)

    def test_excel_apple_sources_cover_five_categories(self):
        from import_sources import prepare
        sources = prepare(ROOT / 'inputs/data.xlsx', ROOT / 'config/retailer_adapters.json', output_dir=None)
        self.assertEqual(len(sources), 86)                                   # Excel không đổi
        apple = [s for s in sources if scope.in_scope(s.get('brand'), {'apple'})]
        self.assertEqual(len(apple), 24)                                      # Viettel không có nguồn MacBook
        self.assertEqual({s['category'] for s in apple}, {'Điện thoại', 'Máy tính bảng', 'Máy tính xách tay', 'Đồng hồ thông minh', 'Airpods'})


if __name__ == '__main__':
    unittest.main()
