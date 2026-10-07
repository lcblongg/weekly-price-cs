"""Kiểm tra ingestion workbook và export trong môi trường bot (không gọi mạng)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from openpyxl import load_workbook
from import_sources import read_sources, build_sources
from excel_export import export_discovery
from common import PipelineError
import json

ROOT = Path(__file__).resolve().parents[1]


class ExcelSourceTests(unittest.TestCase):
    def test_user_workbook_all_sources_preserved(self):
        rows = read_sources(ROOT / 'inputs/data.xlsx')
        self.assertEqual(len(rows), 86)
        self.assertEqual({r['chain_name'] for r in rows}, {'TGDD', 'CellphoneS', 'FPT Shop', 'Viettel Store', 'Phong Vũ'})
        # Không làm mất query lọc hãng / tìm kiếm trong hai nguồn Airpods.
        self.assertTrue(any('phone_accessory_brands=apple-chinh-hang' in r['url'] for r in rows))
        self.assertTrue(any('keyword=airpods&sort=SearchResult' in r['url'] for r in rows))

    def test_scope_not_silently_reduced_to_iphone(self):
        rows = read_sources(ROOT / 'inputs/data.xlsx')
        adapters = json.loads((ROOT / 'config/retailer_adapters.json').read_text())
        sources = build_sources(rows, adapters)
        self.assertEqual(len(sources), 86)
        self.assertEqual(sum(s['identity_family'] == 'iphone' for s in sources), 5)
        self.assertTrue(any(s['brand'] == 'Lenovo' and s['category'] == 'Máy tính xách tay' for s in sources))
        self.assertTrue(all(s['seeds'] == [r['url']] for s, r in zip(sources, rows)))

    def test_unknown_category_fails_not_dropped(self):
        with self.assertRaises(PipelineError):
            build_sources([dict(chain_name='TGDD',category='Khác',brand='X',url='https://www.thegioididong.com/test',input_sheet='MWG',input_row=2)],
                          {'TGDD': {'category_url_patterns': {}}})

    def test_export_preserves_diagnostics_and_literal_names(self):
        # Kiểm tra workbook do bot tạo trên runner: tên lấy từ web không được chạy như công thức.
        rows = [dict(chain_name='TGDD',source_url='https://www.thegioididong.com/dtdd/iphone-16',
                     status='review',reason='Thiếu dung lượng',config={'discovered_name':'=HYPERLINK("https://evil.example")',
                     'category':'Điện thoại','brand':'Apple','listing_urls':['https://www.thegioididong.com/dtdd-apple-iphone']})]
        diagnostics = [dict(chain_name='TGDD',category='Điện thoại',brand='Apple',url='https://www.thegioididong.com/dtdd-apple-iphone',
                            count=1,status='Đã tìm link',error=''),
                       dict(chain_name='FPT Shop',category='Điện thoại',brand='Apple',url='https://fptshop.com.vn/dien-thoai/apple-iphone',
                            count=0,status='Lỗi quét nguồn',error='HTTP lỗi')]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'result.xlsx'
            export_discovery(rows,diagnostics,target)
            book=load_workbook(target,data_only=False)
            try:
                self.assertEqual(book['Link sản phẩm']['D2'].data_type,'s')
                self.assertIsInstance(book['Link sản phẩm']['I2'].value,datetime)
                self.assertEqual(book['Nguồn quét']['F3'].value,'Lỗi quét nguồn')
                self.assertEqual(book['Link sản phẩm'].freeze_panes,'D2')
            finally:
                book.close()


if __name__ == '__main__':
    unittest.main()
