"""Bot Chủ nhật: đọc 86 nguồn trong Excel, tìm link sản phẩm qua adapter từng đại lý, xác nhận bằng cách
đọc thật giá/CTKM của đúng biến thể, rồi lưu catalog (ready/review) cho bot giá hằng ngày.

- ready: đã đọc được giá bán + CTKM của biến thể đã khóa (mã màu/dung lượng gốc của nguồn).
- review: link thuộc phạm vi nhưng chưa đọc được giá (hết hàng, đặt trước, đổi cấu trúc...) — giữ kèm lý do.
- excluded: sản phẩm có trên trang danh mục nhưng ngoài phạm vi (hàng cũ, phụ kiện, máy bàn) — chỉ ghi chẩn đoán.
Không cần nhập URL từng sản phẩm. Một nguồn lỗi → không publish catalog thiếu nguồn lên Supabase.
"""
import argparse
import asyncio
import json
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

import http_policy
from common import PipelineError, database, TZ
from scraper import validate_url
from identity import describe, chain_sku, OutOfScope
from adapters.registry import ADAPTERS
from chains import resolve, slug as chain_slug
from errors import classify

LOG = logging.getLogger('discovery')


def validate_sources(sources):
    if not isinstance(sources, list) or not sources:
        raise PipelineError('Nguồn khám phá phải là danh sách không rỗng')
    for source in sources:
        if not source.get('seeds'):
            raise PipelineError('Nguồn phải có trang danh mục')
        for url in source['seeds']:
            validate_url(source['chain_name'], url)
        re.compile(source['product_url_pattern'])
        if not 1 <= source.get('max_pages', 10) <= 50:
            raise PipelineError('max_pages phải trong khoảng 1–50')
        if not 1 <= source.get('max_candidates', 200) <= 1000:
            raise PipelineError('max_candidates phải trong khoảng 1–1000')
        if not 1 <= source.get('scroll_rounds', 6) <= 30:
            raise PipelineError('scroll_rounds phải trong khoảng 1–30')


def group_key(chain, candidate):
    """Các màu của cùng một phiên bản cấu hình. Không xác định được → mỗi link là một nhóm riêng."""
    if chain == 'FPT Shop':
        return candidate['group']
    if chain == 'CellphoneS':
        return candidate['parent_id']
    if chain == 'Phong Vũ':
        return candidate['group']  # productId của Phong Vũ: các màu của cùng một phiên bản cấu hình
    return candidate['url']


def representatives(chain, candidates):
    """Một màu đại diện cho mỗi phiên bản; nếu các màu có giá khác nhau thì giữ tất cả màu."""
    groups = defaultdict(list)
    for candidate in candidates:
        groups[group_key(chain, candidate)].append(candidate)
    chosen, skipped = [], 0
    for members in groups.values():
        from product_standard import canonical_model
        # Apple: giữ mọi mã màu để người dùng đổi màu theo dõi mà không thiếu catalog.
        if any(canonical_model(m.get('parent_name') or m.get('name')) for m in members):
            chosen += members
            continue
        prices = {m.get('listing_price') for m in members}
        if len(members) == 1 or None in prices or len(prices) > 1:
            chosen += members
            continue
        in_stock = [m for m in members if (m.get('stock') is None or m.get('stock') > 0)
                    and 'hết' not in str(m.get('listing_status', '')).lower()]
        pick = sorted(in_stock or members, key=lambda m: str(m.get('variant_id') or m['url']))[0]
        chosen.append(pick)
        skipped += len(members) - 1
    return chosen, skipped


def candidate_row(source, candidate, status, reason, config):
    return {'chain_name': source['chain_name'], 'source_url': candidate['url'], 'status': status,
            'reason': reason, 'config': config}


def base_config(source, candidate, now):
    sku = chain_sku(source['chain_name'], candidate['variant_id']) if candidate.get('variant_id') and source['chain_name'] != 'Viettel Store' else ''
    return {'chain_name': source['chain_name'], 'url': candidate['url'], 'discovered_name': candidate.get('name', ''),
            'sku': sku, 'product_name': candidate.get('name', ''),
            'category': source.get('category', ''), 'brand': source.get('brand', ''),
            'listing_urls': source['seeds'], 'input_sheet': source.get('input_sheet', ''),
            'input_row': source.get('input_row'), 'discovered_at': now,
            'variant_id': candidate.get('variant_id'), 'parent_id': candidate.get('parent_id'),
            'color': candidate.get('color', '')}


def ready_config(source, candidate, quote, now):
    meta = describe(candidate.get('parent_name') or candidate.get('name') or quote['product_name'],
                    source['category'], source.get('brand', ''))
    color = quote.get('color') or candidate.get('color') or ''
    name = quote['product_name']
    if color and color.casefold() not in name.casefold():
        name += ' · ' + color
    config = base_config(source, candidate, now)
    # SKU = mã đại lý + mã biến thể gốc ổn định (Viettel: mã ERP theo màu, vì rule_id dùng chung nhiều sản phẩm).
    config.update({'sku': chain_sku(source['chain_name'], quote.get('sku_key') or quote['variant_id']), 'product_name': name,
                   'source_product_name': quote['product_name'], 'variant_id': quote['variant_id'],
                   'color': color, 'category': meta['category'], 'model_name': meta['model_name'],
                   'storage': meta['storage'], 'url': candidate['url'], 'verified': True, 'adapter': source['chain_name'],
                   'price_scope': quote.get('price_scope', ''), 'verify_tokens': [quote['variant_id']]})
    if quote.get('variant_erp_id'):
        config['variant_erp_id'] = quote['variant_erp_id']
    return config


async def discover_source(source, http, browser, now):
    adapter = ADAPTERS[source['chain_name']]
    found = await adapter.listing(source, http, browser)
    listing_notes = []
    if isinstance(found, tuple):
        found, meta = found
        listing_notes = meta.get('notes', [])
    if not found:
        raise PipelineError('Không tìm thấy sản phẩm; không commit danh mục rỗng')
    excluded, candidates = [], []
    for url, candidate in found.items():
        candidate.setdefault('url', url)
        try:
            # Thẻ không có tên (giao diện mới TGDD): chưa phán đoán phạm vi, để bước đọc chi tiết quyết định.
            if candidate.get('name', '').strip():
                describe(candidate['name'], source['category'], source.get('brand', ''))
        except OutOfScope as exc:
            excluded.append({'url': url, 'name': candidate.get('name', ''), 'reason': str(exc)})
            continue
        if hasattr(adapter, 'variants') and 'children' in candidate:
            candidates += await adapter.variants(http, candidate)
        else:
            candidates.append(candidate)
    chosen, skipped = representatives(source['chain_name'], candidates)
    rows = []
    batch = {}
    if hasattr(adapter, 'read_many'):
        batch = await adapter.read_many(chosen, http, browser)
    for candidate in chosen:
        try:
            if batch:
                quote = batch[str(candidate['variant_id'])]
                if isinstance(quote, Exception):
                    raise quote
            else:
                quote = await adapter.read_product(candidate, http, browser)
            rows.append(candidate_row(source, candidate, 'ready', '', ready_config(source, candidate, quote, now)))
        except OutOfScope as exc:
            excluded.append({'url': candidate['url'], 'name': candidate.get('name', ''), 'reason': str(exc)})
        except Exception as exc:
            reason = str(exc) if isinstance(exc, PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'
            config = base_config(source, candidate, now)
            rows.append(candidate_row(source, candidate, 'review', reason, config))
    return rows, {'listed': len(found), 'excluded': excluded, 'color_variants_skipped': skipped,
                  'notes': listing_notes}


def reject_duplicate_skus(rows):
    groups = {}
    for row in rows:
        if row['status'] == 'ready':
            key = (row['chain_name'], row['config']['sku'])
            groups.setdefault(key, []).append(row)
    for group in groups.values():
        if len(group) > 1:
            urls = {row['config']['url'] for row in group}
            if len(urls) == 1:
                # Cùng một link xuất hiện ở hai nguồn (ví dụ AirPods nằm cả ở danh mục chung): giữ một dòng,
                # gộp danh sách nguồn; không phải hai biến thể khác nhau.
                keep = group[0]
                for row in group[1:]:
                    keep['config']['listing_urls'] = sorted(set(keep['config']['listing_urls'] + row['config']['listing_urls']))
                    row['status'] = 'duplicate'
                continue
            # Không chọn link đầu tiên tùy tiện: có thể khác màu hoặc tình trạng.
            for row in group:
                row.update(status='review', reason='Nhiều URL cùng SKU; cần làm rõ biến thể')
                row['config']['verified'] = False
    rows[:] = [row for row in rows if row['status'] != 'duplicate']
    dedupe_source_urls(rows)


def dedupe_source_urls(rows):
    """Một link chỉ một dòng/kênh (khóa chính catalog). Cùng link từ hai nguồn Excel: giữ dòng ready nếu có,
    gộp danh sách trang danh mục — không làm mất nguồn nào, không tạo hai dòng mâu thuẫn."""
    kept = {}
    for row in rows:
        key = (row['chain_name'], row.get('source_url') or row['config'].get('url'))
        if key not in kept:
            kept[key] = row
            continue
        old = kept[key]
        merged = sorted(set(old['config'].get('listing_urls', []) + row['config'].get('listing_urls', [])))
        if old['status'] != 'ready' and row['status'] == 'ready':
            kept[key] = row
        kept[key]['config']['listing_urls'] = merged
    rows[:] = list(kept.values())


def setup_chain_log(name, directory):
    """Log riêng cho từng kênh (không chứa secret: chỉ URL công khai và thông điệp nghiệp vụ)."""
    logger = logging.getLogger(f'discovery.{chain_slug(name)}')
    handler = logging.FileHandler(Path(directory) / 'worker.log', mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.handlers = [handler]
    logger.propagate = True
    return logger


def write_json(path, data):
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


async def discover_chain(name, sources, http, browser, out_dir, args, now, publish):
    from apple_jobs import channel_lock, Busy
    try:
        with channel_lock(chain_slug(name)):
            return await _discover_chain(name, sources, http, browser, out_dir, args, now, publish)
    except Busy as exc:
        return {'chain_name':name,'stage':'discovery','status':'failed','sources':len(sources),'message':str(exc),'error_kind':'busy'}


async def _discover_chain(name, sources, http, browser, out_dir, args, now, publish):
    """Một worker = một kênh. Lỗi kênh này không ảnh hưởng kênh khác; luôn ghi summary."""
    directory = Path(out_dir) / chain_slug(name)
    directory.mkdir(parents=True, exist_ok=True)
    log = setup_chain_log(name, directory)
    started = datetime.now(TZ).isoformat()
    rows, diagnostics = [], []
    summary = {'chain_name': name, 'stage': 'discovery', 'started_at': started, 'dry_run': bool(args.dry_run),
               'sources': len(sources), 'status': 'running',
               'input_rows': [{k: s.get(k) for k in ('category', 'brand', 'input_sheet', 'input_row')} | {'url': s['seeds'][0]} for s in sources]}
    try:
        for source in sources:
            diagnostic = dict(chain_name=name, category=source.get('category', ''), brand=source.get('brand', ''),
                              url=source['seeds'][0], input_row=source.get('input_row'),
                              count=0, ready=0, review=0, excluded=0, status='Chưa quét', error='', error_kind='')
            try:
                found_rows, info = await discover_source(source, http, browser, now)
                rows.extend(found_rows)
                diagnostic.update(count=info['listed'], ready=sum(r['status'] == 'ready' for r in found_rows),
                                  review=sum(r['status'] == 'review' for r in found_rows),
                                  excluded=len(info['excluded']), excluded_items=info['excluded'],
                                  color_variants_skipped=info['color_variants_skipped'],
                                  notes=info['notes'], status='Đã tìm link')
                log.info('%s / %s / %s: %s link, %s ready, %s review, %s ngoài phạm vi', name,
                         source.get('category', ''), source.get('brand', ''), info['listed'],
                         diagnostic['ready'], diagnostic['review'], diagnostic['excluded'])
            except Exception as exc:
                message = str(exc) if isinstance(exc, PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'
                diagnostic.update(status='Lỗi quét nguồn', error=message, error_kind=classify(message))
                log.warning('%s / %s / %s: %s', name, source.get('category', ''), source.get('brand', ''), message)
            diagnostics.append(diagnostic)
        reject_duplicate_skus(rows)
        failures = [d for d in diagnostics if d['status'] == 'Lỗi quét nguồn']
        catalog_path = directory / 'catalog.json'
        if failures and catalog_path.exists():
            write_json(directory / 'catalog.failed.json', rows)
            summary['retained_catalog'] = True
        else:
            write_json(catalog_path, rows)
        write_json(directory / 'sources.json', diagnostics)
        if not args.json_only:
            from excel_export import export_discovery
            export_discovery(rows, diagnostics, directory / 'product_links.xlsx')
        ready = sum(r['status'] == 'ready' for r in rows)
        review_kinds = Counter(classify(r['reason']) for r in rows if r['status'] == 'review')
        summary.update(sources_ok=len(diagnostics) - len(failures), sources_failed=len(failures),
                       failed_sources=[{k: d[k] for k in ('category', 'brand', 'url', 'error', 'error_kind')} for d in failures],
                       links=len(rows), ready=ready, review=len(rows) - ready, review_by_kind=dict(review_kinds),
                       excluded=sum(d.get('excluded', 0) for d in diagnostics))
        if failures:
            # Không công bố catalog thiếu nguồn: bản thành công trước đó trên Supabase vẫn được bot giá dùng.
            summary.update(status='failed', published=False,
                           message=f'{len(failures)}/{len(sources)} nguồn lỗi; giữ catalog thành công trước đó')
        elif not ready:
            summary.update(status='failed', published=False, message='Không có link ready; không công bố')
        elif publish:
            run_id = database().rpc('commit_discovery_chain', {'p_chain': name, 'p_rows': rows}).execute().data
            summary.update(status='ok', published=True, discovery_run_id=run_id)
        else:
            summary.update(status='ok', published=False, message='Dry-run: chưa ghi Supabase')
    except Exception as exc:
        message = str(exc) if isinstance(exc, PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'
        summary.update(status='failed', published=False, message=message, error_kind=classify(message))
        log.error('%s: %s', name, message)
    summary['finished_at'] = datetime.now(TZ).isoformat()
    write_json(directory / 'summary.json', summary)
    log.info('Kết thúc %s: %s', name, json.dumps({k: summary.get(k) for k in ('status', 'links', 'ready', 'review', 'sources_failed')}, ensure_ascii=False))
    for handler in log.handlers:
        handler.close()
    return summary


async def run(args):
    chains = resolve(args.chain)
    if args.sources:
        sources = json.loads(Path(args.sources).read_text(encoding='utf-8'))
    else:
        from import_sources import prepare
        sources = prepare(args.input, args.adapters, output_dir=None)  # không ghi file dùng chung giữa các worker
    validate_sources(sources)
    from scope import brands, in_scope
    allowed = brands()
    sources = [s for s in sources if in_scope(s.get('brand'), allowed)]  # config/scope.json: chỉ hãng trong phạm vi
    if args.limit_sources:
        if not args.dry_run or args.limit_sources < 1:
            raise PipelineError('--limit-sources chỉ dùng cho dry-run và phải > 0')
    by_chain = {}
    for source in sources:
        if source['chain_name'] in chains:
            by_chain.setdefault(source['chain_name'], []).append(source)
    if args.limit_sources:
        by_chain = {name: items[:args.limit_sources] for name, items in by_chain.items()}
    missing = [name for name in chains if name not in by_chain]
    if missing:
        raise PipelineError('Excel không có nguồn cho kênh: ' + ', '.join(missing))
    publish = not args.dry_run and not args.limit_sources
    now = datetime.now(TZ).isoformat()
    async with http_policy.client() as http, async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            # Các kênh khác host chạy song song; trong một kênh tuần tự để tôn trọng giãn cách.
            summaries = await asyncio.gather(*(discover_chain(name, by_chain[name], http, browser, args.out, args, now, publish)
                                               for name in chains))
        finally:
            await browser.close()
    for item in summaries:
        LOG.info('%s: %s — %s link, %s ready, %s review, %s/%s nguồn lỗi%s', item['chain_name'], item['status'],
                 item.get('links', 0), item.get('ready', 0), item.get('review', 0), item.get('sources_failed', 0),
                 item['sources'], f" ({item['message']})" if item.get('message') else '')
    if any(item['status'] != 'ok' for item in summaries):
        raise PipelineError('Có kênh discovery thất bại; xem summary.json từng kênh')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description='Bot Chủ nhật: tìm link + catalog theo từng kênh')
    parser.add_argument('--chain', action='append', required=True,
                        help='tgdd|cellphones|viettel|fpt|phongvu|all (lặp lại hoặc ngăn cách bằng dấu phẩy)')
    parser.add_argument('--out', default='artifacts/discovery', help='Thư mục gốc; mỗi kênh một thư mục con')
    parser.add_argument('--input', default='inputs/data.xlsx')
    parser.add_argument('--adapters', default='config/retailer_adapters.json')
    parser.add_argument('--sources', help='JSON nguồn thay thế Excel, chỉ dùng khi chỉ định rõ')
    parser.add_argument('--limit-sources', type=int, help='Dry-run: chỉ thử N nguồn đầu của mỗi kênh')
    parser.add_argument('--json-only', action='store_true', help='Không xuất XLSX')
    parser.add_argument('--dry-run', action='store_true')
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        LOG.error('Discovery dừng: %s', str(exc) if isinstance(exc, PipelineError) else type(exc).__name__)
        raise SystemExit(1)
