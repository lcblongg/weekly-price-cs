"""Quy chuẩn Apple: thêm/sửa tên/xóa/đổi thứ tự nhất quán, chống xung đột, và Python ↔ TypeScript cùng kết quả."""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import apple_rules
from apple_rules import RuleError, literal_pattern, plan

ROOT = Path(__file__).resolve().parents[1]
CURATED = {'version': 1, 'models': [
    {'name': 'iPhone 17 Pro Max', 'pattern': r'\biPhone\s+17\s+Pro\s+Max\b'},
    {'name': 'iPhone 17 Pro', 'pattern': r'\biPhone\s+17\s+Pro(?!\s+Max)\b'},
    {'name': 'iPad Air M4 11', 'pattern': r'\biPad\s+Air\b(?=.*\bM4\b)(?=.*\b11\b)'},
]}


def product(model, color=None, aliases=()):
    return {'model': model, 'color': color, 'aliases': list(aliases)}


def canonical(models, name):
    hits = [m['name'] for m in models['models'] if re.search(m['pattern'], name, re.I)]
    return hits[0] if len(hits) == 1 else None


class PlanTests(unittest.TestCase):
    def test_new_model_gets_literal_rule_without_swallowing_pro(self):
        colors, models = plan([product('iPhone 17 Pro Max'), product('iPhone 19', 'Đen'), product('iPhone 19 Pro')], CURATED)
        generated = [m['name'] for m in models['models'] if m.get('generated')]
        self.assertEqual(generated, ['iPhone 19', 'iPhone 19 Pro'])
        self.assertEqual(canonical(models, 'Điện thoại iPhone 19 256GB Đen'), 'iPhone 19')
        self.assertEqual(canonical(models, 'iPhone 19 Pro 512GB'), 'iPhone 19 Pro')
        self.assertIsNone(canonical(models, 'iPhone 19e 128GB'))
        self.assertIsNone(canonical(models, 'iPhone 190'))
        # Thứ tự hiển thị = thứ tự người dùng; quy tắc viết tay chưa cấu hình màu vẫn được giữ ở cuối.
        self.assertEqual([m['name'] for m in models['models']][:3], ['iPhone 17 Pro Max', 'iPhone 19', 'iPhone 19 Pro'])
        self.assertIn('iPad Air M4 11', [m['name'] for m in models['models']])

    def test_rename_curated_keeps_source_matching(self):
        colors, models = plan([product('iPad Air 11 M4', 'Xám')], CURATED, [{'from': 'iPad Air M4 11', 'to': 'iPad Air 11 M4'}],
                              [product('iPad Air M4 11', 'Xám')])
        self.assertEqual(colors['products'][0]['previous_names'], ['iPad Air M4 11'])
        self.assertEqual(canonical(models, 'Máy tính bảng iPad Air M4 11 inch WiFi 128GB'), 'iPad Air 11 M4')
        self.assertNotIn('iPad Air M4 11', [m['name'] for m in models['models']])

    def test_rename_generated_regenerates_from_new_name(self):
        _, first = plan([product('iPhone 91')], CURATED)  # gõ nhầm
        colors, fixed = plan([product('iPhone 19')], first, [{'from': 'iPhone 91', 'to': 'iPhone 19'}], [product('iPhone 91')])
        self.assertNotIn('previous_names', colors['products'][0])  # bằng chứng cũ không được thừa kế
        self.assertEqual(canonical(fixed, 'iPhone 19 256GB'), 'iPhone 19')
        self.assertIsNone(canonical(fixed, 'iPhone 91 256GB'))

    def test_delete_drops_generated_rule_keeps_curated(self):
        _, first = plan([product('iPhone 19'), product('iPhone 17 Pro')], CURATED)
        _, after = plan([product('iPhone 17 Pro')], first)
        names = [m['name'] for m in after['models']]
        self.assertNotIn('iPhone 19', names)
        self.assertIn('iPhone 17 Pro Max', names)  # quy tắc viết tay không bị xóa theo màu

    def test_conflicts_and_invalid_input_rejected(self):
        for products, renames in [
            ([product('Apple Watch'), product('Apple Watch S11')], []),       # tên chung nuốt model khác
            ([product('iPhone 19'), product('IPHONE  19')], []),               # trùng không phân biệt hoa/thường
            ([product('iPhone 19', '')], []),                                  # màu rỗng không phải "không lọc"
            ([product('iPad Air M4 11')], [{'from': 'iPhone 17 Pro', 'to': 'iPad Air M4 11'}]),
        ]:
            with self.assertRaises(RuleError, msg=products):
                _, models = plan(products, CURATED, renames)

    def test_aliases_cleaned(self):
        colors, _ = plan([product('iPhone 19', 'Đen', ['Đen', 'Đen Huyền Bí', 'Đen Huyền Bí'])], CURATED)
        self.assertEqual(colors['products'][0]['aliases'], ['Đen Huyền Bí'])

    def test_apply_writes_both_files_atomically(self):
        with tempfile.TemporaryDirectory() as folder:
            colors_path, models_path = Path(folder) / 'c.json', Path(folder) / 'm.json'
            models_path.write_text(json.dumps(CURATED))
            colors_path.write_text(json.dumps({'version': 1, 'products': []}))
            apple_rules.apply([product('iPhone 19', 'Đen')], (), colors_path, models_path)
            self.assertEqual(json.loads(colors_path.read_text())['products'][0]['model'], 'iPhone 19')
            self.assertTrue(any(m['name'] == 'iPhone 19' for m in json.loads(models_path.read_text())['models']))
            before = colors_path.read_text()
            with self.assertRaises(RuleError):
                apple_rules.apply([product('Apple Watch'), product('Apple Watch S11')], (), colors_path, models_path)
            self.assertEqual(colors_path.read_text(), before)  # cấu hình lỗi không được ghi
            self.assertEqual(list(Path(folder).glob('*.tmp')), [])

    def test_current_project_config_is_consistent(self):
        colors = json.loads((ROOT / 'config/apple_colors.json').read_text())
        models = json.loads((ROOT / 'config/apple_models.json').read_text())
        plan(colors['products'], models)  # không được RuleError


class ProofTests(unittest.TestCase):
    def quote(self, proof_model, color='Xám'):
        return {'chain_name': 'CellphoneS', 'brand': 'Apple', 'promo_price': 1, 'variant_id': '9', 'color': color,
                'product_name': 'iPad Air M4 11 inch WiFi 128GB', 'source_product_name': 'iPad Air M4 11 inch WiFi 128GB',
                'color_evidence': {'model': proof_model, 'canonical_color': color, 'product_code': '9',
                                   'website_color_id': 1, 'verified_at': '2026-10-06T10:00:00+07:00'}}

    def test_old_proof_valid_only_through_recorded_rename(self):
        from apple_preferences import presentation
        import product_standard
        original = list(product_standard.RULES)
        product_standard.RULES[:] = [('iPad Air 11 M4', re.compile(r'\biPad\s+Air\b(?=.*\bM4\b)(?=.*\b11\b)', re.I))]
        try:
            renamed = {'products': [{'model': 'iPad Air 11 M4', 'color': 'Xám', 'aliases': [], 'previous_names': ['iPad Air M4 11']}]}
            self.assertEqual(presentation(self.quote('iPad Air M4 11'), renamed)['apple_selection'], 'selected')
            no_history = {'products': [{'model': 'iPad Air 11 M4', 'color': 'Xám', 'aliases': []}]}
            self.assertEqual(presentation(self.quote('iPad Air M4 11'), no_history)['apple_selection'], 'needs_verified_color')
            recolored = {'products': [{'model': 'iPad Air 11 M4', 'color': 'Bạc', 'aliases': [], 'previous_names': ['iPad Air M4 11']}]}
            self.assertNotEqual(presentation(self.quote('iPad Air M4 11'), recolored)['apple_selection'], 'selected')
        finally:
            product_standard.RULES[:] = original


class CrossLanguageTests(unittest.TestCase):
    """TypeScript (dashboard/thứ tự) phải nhận diện giống hệt Python (bot)."""

    def test_typescript_matches_python(self):
        tsx = ROOT / 'web/node_modules/.bin/tsx'
        if not tsx.exists():
            self.skipTest('Chưa cài web/node_modules')
        import product_standard
        names = ['iPhone 17 Pro Max 256GB Cam vũ trụ', 'Điện thoại iPhone 17 Pro 256GB', 'iPhone 17e 128GB', 'iPhone 17 256GB',
                 'iPhone Air 256GB', 'iPhone 16 Plus 128GB', 'iPad Air M4 11 inch WiFi', 'MacBook Air 13 inch M5 16GB/256GB',
                 'Apple Watch Series 11 GPS 42mm', 'AirPods 4 chống ồn', 'AirPods Pro 3', 'AirPods 5 sạc ko dây', 'iPhone 19 Pro']
        comparison = ROOT / 'web/data/comparison.json'
        if comparison.exists():
            names += sorted({r['product_name'] for r in json.loads(comparison.read_text())['rows']})[:600]
        samples = ['iPhone 19', 'iPhone 19 Pro', 'AirPods 5 sạc ko dây', 'iPad Pro M6 13', 'MacBook Neo 2']
        probes = ['Điện thoại iPhone 19 256GB', 'iPhone 19 Pro Max 1TB', 'iPhone 19e', 'AirPods 5 sạc ko dây (MKFT4)',
                  'iPad Pro M6 13 inch WiFi', 'MacBook Neo 2 13 inch', 'MacBook Neo 2 Pro']
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / 'probe.ts'
            script.write_text(
                f"import {{canonicalAppleModel,literalPattern}} from '{(ROOT / 'web/lib/product-standard.ts').as_posix()}';\n"
                f"const names={json.dumps(names, ensure_ascii=False)};const samples={json.dumps(samples, ensure_ascii=False)};"
                f"const probes={json.dumps(probes, ensure_ascii=False)};\n"
                "console.log(JSON.stringify({canonical:names.map(n=>canonicalAppleModel(n)),"
                "literal:samples.map(s=>probes.map(p=>new RegExp(literalPattern(s),'i').test(p)))}));\n", encoding='utf-8')
            output = subprocess.run([str(tsx), str(script)], cwd=ROOT / 'web', capture_output=True, text=True, timeout=120)
        self.assertEqual(output.returncode, 0, output.stderr[-500:])
        result = json.loads(output.stdout.strip().splitlines()[-1])
        expected = [product_standard.canonical_model(n) for n in names]
        mismatches = [(n, p, t) for n, p, t in zip(names, expected, result['canonical']) if p != t]
        self.assertEqual(mismatches, [])
        python_literal = [[bool(re.search(literal_pattern(s), p, re.I)) for p in probes] for s in samples]
        self.assertEqual(result['literal'], python_literal)


if __name__ == '__main__':
    unittest.main()
