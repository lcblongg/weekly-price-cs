"""Bot thu thập link + bot lấy giá theo file chọn. Không gọi mạng, không ghi Supabase."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import lay_gia_link  # noqa: E402
import thu_thap_link  # noqa: E402
from apple_rules import RuleError  # noqa: E402


def sheet(rows):
    from openpyxl import Workbook
    folder = tempfile.mkdtemp()
    path = Path(folder) / 'chon.xlsx'
    book = Workbook()
    for row in rows:
        book.active.append(row)
    book.save(path)
    return path


class ChoiceTests(unittest.TestCase):
    def test_groups_by_model_with_channel_color_names_as_aliases(self):
        path = sheet([['Model', 'Màu', 'Link', 'Ghi chú'],
                      ['iPhone 17 Pro Max', 'Cam vũ trụ', 'https://www.thegioididong.com/dtdd/iphone-17-pro-max?code=0131491005414', ''],
                      ['iPhone 17 Pro Max', 'Cam Vũ Trụ', 'https://fptshop.com.vn/dien-thoai/iphone-17-pro-max?sku=00930756', 'x'],
                      ['iPhone 17 Pro Max', 'Cosmic Orange', 'https://cellphones.com.vn/iphone-17-pro-max.html', ''],
                      [None, None, None, None],
                      ['AirPods 4', 'Trắng', 'https://phongvu.vn/airpods-4--s250902982?sku=250902982', '']])
        products = lay_gia_link.build_products(lay_gia_link.read_choices(path))
        self.assertEqual([p['model'] for p in products], ['iPhone 17 Pro Max', 'AirPods 4'])
        first = products[0]
        self.assertEqual(first['color'], 'Cam vũ trụ')
        self.assertEqual(first['aliases'], ['Cosmic Orange'])                 # khác hoa/thường không thành alias
        self.assertEqual(sorted(first['urls']), ['cellphones', 'fpt', 'tgdd'])

    def test_invalid_rows_stop_before_running(self):
        path = sheet([['Model', 'Màu', 'Link'],
                      ['iPhone 17', '', 'https://www.thegioididong.com/dtdd/iphone-17'],
                      ['iPhone 17', 'Đen', 'https://example.com/iphone-17'],
                      ['iPhone 17', 'Đen', 'https://www.thegioididong.com/not-a-product']])
        with self.assertRaises(RuleError) as caught:
            lay_gia_link.build_products(lay_gia_link.read_choices(path))
        message = str(caught.exception)
        for row in ('Dòng 2', 'Dòng 3', 'Dòng 4'):
            self.assertIn(row, message)

    def test_header_required_and_empty_file_rejected(self):
        with self.assertRaises(RuleError):
            lay_gia_link.read_choices(sheet([['Tên', 'Link']]))
        with self.assertRaises(RuleError):
            lay_gia_link.build_products(lay_gia_link.read_choices(sheet([['Model', 'Màu', 'Link']])))


class CollectTests(unittest.TestCase):
    def test_mw_link_pins_color_code_and_rows_described(self):
        self.assertEqual(thu_thap_link.pinned_link('tgdd', {'url': 'https://www.thegioididong.com/dtdd/iphone-17', 'variant_id': '123'}),
                         'https://www.thegioididong.com/dtdd/iphone-17?code=123')
        url = 'https://fptshop.com.vn/dien-thoai/iphone-duo?sku=00930756'
        self.assertEqual(thu_thap_link.pinned_link('fpt', {'url': url, 'variant_id': '00930756'}), url)
        row = thu_thap_link.describe_row('fpt', {'source_url': url, 'status': 'review', 'reason': 'Hết hàng',
                                                 'config': {'discovered_name': 'iPhone 17 Pro Max 256GB Cam Vũ Trụ', 'color': 'Cam Vũ Trụ', 'category': 'Điện thoại'}})
        self.assertEqual((row['Kênh'], row['Model'], row['Dung lượng'], row['Màu']), ('FPT', 'iPhone 17 Pro Max', '256GB', 'Cam Vũ Trụ'))
        self.assertTrue(row['Tình trạng'].startswith('Cần kiểm tra'))


if __name__ == '__main__':
    unittest.main()
