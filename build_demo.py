"""Dựng web/data/demo.json từ đúng kết quả chạy thử bot giá theo kênh (<dir>/<kênh>/prices.json, issues.json,
summary.json). Thời điểm thu thập = finished_at của chính worker kênh đó. Không tạo giá/ngày giả:
chỉ ngày đã chạy thật; các ngày khác trong tuần để trống trên dashboard.
"""
import argparse
import os
import json
from datetime import datetime, timedelta
from pathlib import Path

from common import TZ


def main(args):
    rows, issues, parts = [], [], []
    for summary_path in sorted(Path(args.prices).glob('*/summary.json')):
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        if summary.get('stage') != 'prices' or summary.get('status') not in ('ok', 'degraded'):
            parts.append(f"{summary.get('chain_name')}: {summary.get('status')} (không đưa vào demo)")
            continue
        captured = datetime.fromisoformat(summary['finished_at']).astimezone(TZ)
        day = captured.date()
        extra = {'run_id': 'dry-run', 'captured_at': captured.isoformat(timespec='seconds'),
                 'business_date': day.isoformat(), 'week_start': (day - timedelta(days=day.weekday())).isoformat()}
        chain_rows = json.loads((summary_path.parent / 'prices.json').read_text(encoding='utf-8'))
        chain_issues = json.loads((summary_path.parent / 'issues.json').read_text(encoding='utf-8'))
        for row in chain_rows:
            when=datetime.fromisoformat(row.get('observed_at') or summary['finished_at']).astimezone(TZ)
            date=when.date()
            rows.append({**row,**extra,'captured_at':when.isoformat(timespec='seconds'),'business_date':date.isoformat(),'week_start':(date-timedelta(days=date.weekday())).isoformat()})
        issues += [{**item, **extra} for item in chain_issues]
        limited = (summary.get('catalog') or {}).get('limited_to')
        parts.append(f"{summary['chain_name']} {len(chain_rows)} bản ghi giá/trạng thái / {len(chain_issues)} cần kiểm tra"
                     + (f" (giới hạn {limited} link)" if limited else '') + f" lúc {captured:%H:%M}")
    coverage=[]
    for summary_path in sorted(Path(getattr(args, 'discovery', 'artifacts/full/merged')).glob('*/summary.json')):
        summary=json.loads(summary_path.read_text(encoding='utf-8'))
        if summary.get('sources') is not None:
            coverage.append(summary)
    total_sources=sum(s['sources'] for s in coverage)
    ok_sources=sum(s.get('sources_ok',0) for s in coverage)
    source_path=Path(getattr(args, 'source_manifest', 'artifacts/full/run1/discovery-sources.json'))
    source_names={}
    if source_path.exists():
        source_names={(r['chain_name'],r.get('input_row')):r.get('brand','') for r in json.loads(source_path.read_text(encoding='utf-8'))}
    warnings=[]
    for s in coverage:
        for failed in s.get('sources_still_failed',[]):
            # Nguồn Excel phải tra theo input_row; không giả vờ có giá của nguồn thất bại.
            warnings.append(f"{s['chain_name']} {source_names.get((s['chain_name'],failed.get('input_row')),'')} (Excel dòng {failed.get('input_row')}) chưa đầy đủ")
    coverage_note=(f'Danh mục {ok_sources}/{total_sources} nguồn; ' + '; '.join(warnings) + '. ') if warnings else ''
    days = sorted({r['business_date'] for r in rows})
    scope = (coverage_note + f'Chạy thử bot giá ngày {", ".join(days)} (dry-run, chưa ghi Supabase): ' + '; '.join(parts)
             + '. Chỉ có dữ liệu của ngày chạy thử; các ngày khác để trống.')
    catalog=[]
    for path in sorted(Path(getattr(args, 'discovery', 'artifacts/full/merged')).glob('*/catalog.json')):
        for item in json.loads(path.read_text(encoding='utf-8')):
            config=item['config']
            name=config.get('product_name') or config.get('discovered_name') or 'Chưa xác định tên'
            model=config.get('model_name')
            if not model:
                from identity import describe
                from common import PipelineError
                try: model=describe(name,config.get('category',''),config.get('brand','')).get('model_name')
                except PipelineError: pass
            catalog.append({**{k:config.get(k) for k in ('chain_name','sku','product_name','category','brand','model_name','discovered_at')},
                            'sku':config.get('sku') or '', 'product_name':name,'model_name':model,
                            'source_url':item['source_url'],'status':item['status'],'reason':item.get('reason','')})
    catalog_map={(p['chain_name'],p['source_url']):p for p in catalog}
    for issue in issues:
        metadata=catalog_map.get((issue['chain_name'],issue['source_url']),{})
        if not issue.get('model_name'):issue['model_name']=metadata.get('model_name')
        if not issue.get('product_name'):issue['product_name']=metadata.get('product_name') or 'Chưa xác định tên'
    target=Path(args.output);temporary=target.with_suffix(f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps({'rows': rows, 'issues': issues, 'catalog': catalog, 'prices_source':str(Path(args.prices)), 'scope': scope,
                                             'captured_at': max((r['captured_at'] for r in rows), default=None)},
                                            ensure_ascii=False, indent=1), encoding='utf-8')
    temporary.replace(target)
    print(scope)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prices', default='artifacts/full/prices', help='Thư mục --out của scraper (mỗi kênh một thư mục)')
    parser.add_argument('--source-manifest', default='artifacts/full/run1/discovery-sources.json', help='Danh sách nguồn gốc để đặt tên nguồn lỗi')
    parser.add_argument('--discovery', default='artifacts/full/merged', help='Summary discovery để giữ cảnh báo nguồn thiếu')
    parser.add_argument('--output', default='web/data/demo.json')
    main(parser.parse_args())
