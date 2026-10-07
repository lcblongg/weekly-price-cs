"""Hợp nhất kết quả discovery (dry-run) từ lượt đầy đủ + các lượt chạy lại nguồn lỗi, theo từng kênh.

Kiểm tra bắt buộc:
- mỗi nguồn Excel của kênh xuất hiện đúng một lần ở trạng thái thành công trong kết quả hợp nhất;
- dòng sản phẩm của một nguồn chỉ lấy từ lượt mà nguồn đó thành công (không trộn dòng của lượt lỗi);
- loại trùng SKU/link như bot thật.
Bản hợp nhất luôn có published=false: chỉ dùng để chạy thử bot giá/dashboard, KHÔNG công bố lên Supabase.
Catalog production phải do một lượt discovery thành công trọn vẹn của kênh tạo ra.

python tools/merge_discovery.py --base artifacts/full/run1 --rerun artifacts/full/rerun --out artifacts/full/merged
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chains import CHAINS, slug  # noqa: E402
from discover_products import reject_duplicate_skus  # noqa: E402
from import_sources import prepare  # noqa: E402


def load_base(base):
    rows = json.loads((Path(base) / 'discovery.json').read_text(encoding='utf-8'))
    sources = json.loads((Path(base) / 'discovery-sources.json').read_text(encoding='utf-8'))
    return rows, sources


def load_rerun(rerun):
    rows, sources = [], []
    for directory in sorted(Path(rerun).iterdir()):
        if (directory / 'catalog.json').exists():
            rows += json.loads((directory / 'catalog.json').read_text(encoding='utf-8'))
            sources += json.loads((directory / 'sources.json').read_text(encoding='utf-8'))
    return rows, sources


def key(item):
    # Dòng Excel (sheet theo kênh) là định danh nguồn; listing_urls có thể đã gộp nhiều nguồn khi trùng link.
    return item['chain_name'], item.get('input_row')


def row_key(row):
    return row['chain_name'], row['config'].get('input_row')


def main(args):
    excel = prepare(args.input, args.adapters, None)
    expected = {(s['chain_name'], s.get('input_row')) for s in excel}
    runs = [load_base(args.base)] + [load_rerun(path) for path in args.rerun]
    chosen = {}
    for index, (_, sources) in enumerate(runs):
        for source in sources:
            if source['status'] == 'Đã tìm link':
                chosen[key(source)] = (index, source)  # lượt sau ghi đè lượt trước cho cùng nguồn
    missing = sorted(expected - set(chosen))
    extra = sorted(set(chosen) - expected)
    if extra:
        raise SystemExit(f'Nguồn không có trong Excel: {extra}')
    out = Path(args.out)
    report = {}
    for name in CHAINS.values():
        rows = []
        for index, (run_rows, _) in enumerate(runs):
            for row in run_rows:
                if row['chain_name'] != name:
                    continue
                pick = chosen.get(row_key(row))
                if pick and pick[0] == index:
                    rows.append(row)
        reject_duplicate_skus(rows)
        sources = [chosen[k][1] for k in sorted(chosen, key=lambda k: (k[1] or 0)) if k[0] == name]
        failed = [k for k in missing if k[0] == name]
        directory = out / slug(name)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / 'catalog.json').write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding='utf-8')
        (directory / 'sources.json').write_text(json.dumps(sources, ensure_ascii=False, indent=1), encoding='utf-8')
        counts = Counter(r['status'] for r in rows)
        summary = {'chain_name': name, 'stage': 'discovery-merged', 'published': False,
                   'sources': sum(1 for k in expected if k[0] == name), 'sources_ok': len(sources),
                   'sources_still_failed': [{'input_row': k[1]} for k in failed],
                   'links': len(rows), 'ready': counts['ready'], 'review': counts['review'],
                   'excluded': sum(s.get('excluded', 0) for s in sources),
                   'note': 'Hợp nhất từ nhiều lượt dry-run; chỉ để thử nghiệm, không công bố'}
        (directory / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
        report[name] = summary
    print(json.dumps({n: {k: v for k, v in s.items() if k in ('sources', 'sources_ok', 'links', 'ready', 'review', 'excluded')}
                      | {'still_failed': len(s['sources_still_failed'])} for n, s in report.items()}, ensure_ascii=False, indent=1))
    return 1 if missing else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True, help='Lượt đầy đủ (discovery.json + discovery-sources.json)')
    parser.add_argument('--rerun', action='append', default=[], help='Thư mục --out của lượt chạy lại (có thể lặp)')
    parser.add_argument('--out', required=True)
    parser.add_argument('--input', default='inputs/data.xlsx')
    parser.add_argument('--adapters', default='config/retailer_adapters.json')
    raise SystemExit(main(parser.parse_args()))
