"""Kiểm tra một quy chuẩn Apple (nháp) trên dữ liệu đã có — CHỈ ĐỌC, không gọi website, không ghi file.
stdin: {"rule": {model,color,aliases}, "rename_from": "tên cũ"|null}
Dùng chính bộ nhận diện của bot với quy tắc nháp, nên kết quả khớp những gì bot sẽ làm sau khi lưu.
Bằng chứng màu cũ (đổi màu/đổi tên sau khi xác minh) KHÔNG được tính là đúng màu."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apple_rules import RuleError, key, plan, COLORS, MODELS  # noqa: E402

CHAINS = [('tgdd', 'mw-apple-selected', 'MW'), ('cellphones', 'cps-apple-selected', 'CPS'),
          ('fpt', 'fpt-apple-selected', 'FPT'), ('viettel', 'viettel-apple-selected', 'VIETTEL'),
          ('phongvu', 'phongvu-apple-selected', 'PV')]


def snapshot(slug, folder):
    base = 'artifacts/status-repair/tgdd' if slug == 'tgdd' else f'artifacts/full-refresh/display/{slug}'
    rows = []
    for path in (f'{base}/prices.json', f'artifacts/{slug}-review-full/{slug}/prices.json', f'artifacts/{folder}/prices.json'):
        file = ROOT / path
        if file.exists():
            rows += json.loads(file.read_text(encoding='utf-8'))
    return rows


def source_name(row):
    return row.get('source_product_name') or row.get('product_name') or row.get('discovered_name') or ''


def main():
    payload = json.loads(sys.stdin.read() or '{}')
    rule = payload.get('rule') or {}
    current = json.loads(COLORS.read_text(encoding='utf-8'))['products']
    old = payload.get('rename_from')
    products = [p for p in current if p['model'] not in (old, rule.get('model'))] + [rule]
    renames = [{'from': old, 'to': rule.get('model')}] if old and old != rule.get('model') else []
    try:
        colors, models = plan(products, json.loads(MODELS.read_text(encoding='utf-8')), renames, current)
    except RuleError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    model = ' '.join(rule['model'].split())
    planned = next(p for p in colors['products'] if p['model'] == model)
    proof_names = {key(model), *(key(n) for n in planned.get('previous_names', []))}
    compiled = [(m['name'], re.compile(m['pattern'], re.I)) for m in models['models']]

    def canonical(name):
        hits = [n for n, p in compiled if p.search(name or '')]
        return hits[0] if len(hits) == 1 else None

    wanted = {key(rule.get('color'))} | {key(a) for a in rule.get('aliases', [])} if rule.get('color') else set()
    checks = []
    for slug, folder, label in CHAINS:
        catalog_file = ROOT / f'artifacts/full/merged/{slug}/catalog.json'
        catalog = json.loads(catalog_file.read_text(encoding='utf-8')) if catalog_file.exists() else []
        links = [r for r in catalog if canonical(source_name(r['config'])) == model]
        rows = {}
        for row in snapshot(slug, folder):
            if canonical(source_name(row)) == model:
                rows.setdefault(row.get('sku'), row)
        verified = stale = 0
        for row in rows.values():
            proof = row.get('color_evidence') or {}
            if not rule.get('color'):
                verified += 1
            elif (key(proof.get('model')) in proof_names and key(proof.get('canonical_color')) in wanted
                  and str(proof.get('product_code')) == str(row.get('variant_id'))
                  and proof.get('website_color_id') is not None and proof.get('verified_at')):
                verified += 1
            elif proof:
                stale += 1  # đã xác minh cho model/màu khác: phải chạy lại bot, không dùng
        colors = sorted({str(r.get('color') or '') for r in rows.values()} - {''})
        checks.append({'chain': label, 'links': len(links), 'links_ready': sum(r['status'] == 'ready' for r in links),
                       'records': len(rows), 'verified': verified, 'stale_proofs': stale, 'colors': colors,
                       'color_available': (not wanted) or any(key(c) in wanted for c in colors)})
    print(json.dumps({'ok': True, 'checks': checks}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
