"""Cào danh sách SKU được quản lý trong config/products.json.
Chỉ commit khi TẤT CẢ sản phẩm thành công; không gửi báo cáo trên dữ liệu dở dang.
"""
import argparse
from datetime import datetime
import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from playwright.async_api import async_playwright
from common import PipelineError, database, weeks, vnd, https_url, TZ
from business_calendar import fiscal_period

LOG = logging.getLogger('scraper')
DOMAINS = {
    'TGDD': 'thegioididong.com', 'FPT Shop': 'fptshop.com.vn',
    'CellphoneS': 'cellphones.com.vn', 'Viettel Store': 'viettelstore.vn',
    'Phong Vũ': 'phongvu.vn',
}


def validate_url(chain, url):
    https_url(url)
    host = urlparse(url).hostname
    domain = DOMAINS[chain]
    if host not in (domain, 'www.' + domain):
        raise PipelineError('Tên miền không khớp đại lý')


async def robots_allowed(client, chain, url):
    """Không vượt robots.txt/CAPTCHA. Hỗ trợ wildcard `*`/`$` (robotparser chuẩn thì không)."""
    from http_policy import ensure_allowed
    try:
        await ensure_allowed(client, url, chain)
    except PipelineError as exc:
        if 'robots.txt không cho' in str(exc):
            raise PipelineError(f'robots.txt không cho cào {chain}') from None
        raise


async def one_text(page, selector, required=True):
    if not selector:
        if required:
            raise PipelineError('Thiếu selector bắt buộc')
        return None
    locator = page.locator(selector)
    await locator.first.wait_for(state='visible', timeout=15000)
    if await locator.count() != 1:
        raise PipelineError('Selector phải trỏ đúng một phần tử')
    return (await locator.inner_text()).strip()


async def extract(page, item, client=None):
    if item.get("price_transport") == "viettel_http":
        from adapters.viettel_detail import extract_product
        if client is None:
            async with httpx.AsyncClient(timeout=40,follow_redirects=True) as http_client:
                return await extract_product(item,http_client,page.context.browser)
        return await extract_product(item,client,page.context.browser)
    response = await page.goto(item['url'], wait_until='domcontentloaded', timeout=45000)
    if response is None or response.status >= 400:
        raise PipelineError('Trang sản phẩm trả lỗi HTTP')
    validate_url(item['chain_name'], page.url)
    # Chỉ selector giá bán trực tiếp; không dùng giá thu cũ/VNPAY/trả góp.
    name = await one_text(page, item['selectors']['name'])
    if not all(token.casefold() in name.casefold() for token in item['verify_tokens']):
        raise PipelineError('Tên trang không khớp model/dung lượng đã cấu hình')
    promo = vnd(await one_text(page, item['selectors']['promo_price']))
    original_text = await one_text(page, item['selectors'].get('original_price'), False)
    original = vnd(original_text) if original_text else None
    if original is not None and original < promo:
        raise PipelineError('Giá gốc nhỏ hơn giá bán; cần kiểm tra selector')
    notes = []
    # Không có selector => chưa kiểm chứng CTKM, không suy diễn là không có KM.
    if not item['selectors'].get('promotions'):
        raise PipelineError('Phải cấu hình vùng CTKM trước khi chạy production')
    for selector in item['selectors']['promotions']:
        text = await one_text(page, selector)
        if text:
            notes.append(' '.join(text.split()))
    return dict(chain_name=item['chain_name'], sku=item['sku'],
                product_name=item['product_name'], original_price=original,
                promo_price=promo, promo_text='\n'.join(notes), source_url=page.url)


def load_catalog(args, chain):
    """(items ready, review_rows, meta) cho đúng một kênh. File có thể là catalog.json của discovery
    (dạng {status, config}) hoặc danh sách cấu hình thủ công."""
    if getattr(args, 'catalog', 'file') == 'discovery':
        from catalog import fetch_discovered
        items, meta = fetch_discovered(database(), chain=chain)
        review = meta.pop('review_rows', [])
    else:
        data = json.loads(Path(args.config).read_text(encoding='utf-8'))
        if isinstance(data, list) and data and isinstance(data[0], dict) and 'status' in data[0] and 'config' in data[0]:
            data = [row for row in data if row['chain_name'] == chain]
            items = [row['config'] for row in data if row['status'] == 'ready']
            review = [row for row in data if row['status'] != 'ready']
            meta = {'run_id': None, 'total': len(data), 'ready': len(items), 'review': len(review)}
        else:
            items, review, meta = [item for item in data if item.get('chain_name') == chain], [], None
    items = [item for item in items if item['chain_name'] == chain]
    review = [row for row in review if row['chain_name'] == chain]
    # Kiểm tra trùng SKU/link trên TOÀN BỘ catalog trước khi lấy mẫu, để mẫu không che lỗi trùng.
    if items:validate_items(items)
    elif not review:raise PipelineError('Catalog không có link để đọc')
    review_urls = [row['source_url'] for row in review]
    if len(set(review_urls)) != len(review_urls) or set(review_urls) & {item['url'] for item in items}:
        raise PipelineError('Catalog có link trùng giữa các dòng; chạy lại discovery')
    limit = getattr(args, 'limit', None)
    if limit:
        if not args.dry_run:
            raise PipelineError('--limit chỉ dùng cho dry-run')
        items, review = sample_by_source(items, limit), sample_by_source(review, max(1, limit // 5))
        if meta:
            meta = {**meta, 'limited_to': limit}
    return items, review, meta


def sample_by_source(entries, limit):
    """Mẫu giới hạn cho dry-run: xoay vòng theo từng nguồn Excel (dòng input_row) để mọi danh mục/hãng đều có mặt,
    thay vì lấy N link đầu (chỉ toàn điện thoại)."""
    groups = {}
    for entry in entries:
        config = entry.get('config', entry)
        groups.setdefault(config.get('input_row'), []).append(entry)
    picked, queues = [], [list(g) for _, g in sorted(groups.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))]
    while len(picked) < limit and any(queues):
        for queue in queues:
            if queue and len(picked) < limit:
                picked.append(queue.pop(0))
    return picked


def validate_items(items):
    if not isinstance(items, list) or not items:
        raise PipelineError('Danh mục sản phẩm không được rỗng')
    seen = set()
    for item in items:
        if item.get('verified') is not True:
            raise PipelineError('Danh mục có selector chưa được kiểm chứng; đọc README trước')
        validate_url(item['chain_name'], item['url'])
        key = (item['chain_name'], item['sku'])
        if key in seen or ('url', item['url']) in seen or not item.get('verify_tokens') or not item.get('product_name'):
            raise PipelineError('SKU/link trùng hoặc thiếu thông tin xác minh')
        seen.add(key)
        seen.add(('url', item['url']))


def issue(item, reason, stage='price', url=None):
    from errors import classify
    return {'stage': stage, 'chain_name': item['chain_name'], 'sku': item.get('sku') or '',
            'product_name': item.get('product_name') or item.get('discovered_name') or '',
            'category': item.get('category', ''), 'brand': item.get('brand', ''), 'model_name': item.get('model_name'),
            'source_url': url or item['url'], 'reason': reason, 'error_kind': classify(reason)}


def price_row(item, quote):
    from identity import chain_sku
    sku = chain_sku(item['chain_name'], quote.get('sku_key') or quote['variant_id'])
    if sku != item['sku']:
        raise PipelineError('Biến thể nguồn trả về khác biến thể đã khóa; cần khám phá lại')
    # NULL chỉ khi adapter đã đọc được trạng thái rõ ràng của đúng SKU.
    if quote.get('promo_price') is None:
        if not str(quote.get('promo_text','')).startswith('[Tình trạng] '):raise PipelineError('Không có giá hoặc trạng thái đã xác minh')
    else:vnd(str(quote['promo_price']))
    from product_standard import canonical_model,display_name
    model=canonical_model(quote.get('product_name')) or canonical_model(item['product_name']) or item.get('model_name')
    name=display_name(item['product_name'],item.get('storage'))
    variant = ' · '.join(x for x in (item.get('storage'), item.get('color'), item['product_name'] if name!=item['product_name'] else None) if x)
    return dict(chain_name=item['chain_name'], sku=item['sku'], product_name=name,
                original_price=quote['original_price'], promo_price=quote['promo_price'],
                promo_text=quote['promo_text'], source_url=item['url'], category=item.get('category', ''),
                brand=item.get('brand', ''), model_name=model, variant_label=variant,
                variant_id=str(quote['variant_id']), storage=item.get('storage'), color=quote.get('color',item.get('color')),
                source_product_name=quote.get('product_name') or item.get('source_product_name'),
                promotion_complete=quote.get('promotion_complete', True), observed_at=datetime.now(TZ).isoformat())


async def scrape_chain(items, http, browser, rows, issues):
    """Một đại lý: tuần tự (http_policy giãn cách theo host). Lỗi từng sản phẩm → mục cần kiểm tra."""
    from adapters.registry import ADAPTERS
    adapter = ADAPTERS[items[0]['chain_name']]
    quotes = {}
    if hasattr(adapter, 'read_many'):
        try:
            quotes = await adapter.read_many(items, http, browser)
        except PipelineError as exc:
            quotes = {str(item['variant_id']): exc for item in items}
    for item in items:
        last = None
        for attempt in range(2):
            try:
                quote = quotes.get(str(item['variant_id'])) if quotes else await adapter.read_product(item, http, browser)
                if isinstance(quote, Exception):
                    raise quote
                rows.append(price_row(item, quote))
                last = None
                break
            except Exception as exc:
                last = str(exc) if isinstance(exc, PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'
                from errors import classify
                if quotes or classify(last) in ('out_of_stock', 'preorder', 'blocked', 'robots', 'variant_changed'):
                    break  # Lỗi rõ ràng (hoặc bị chặn): thử lại không đổi kết quả và không nên dồn request.
                await asyncio.sleep(3)
        if last:
            LOG.warning('Cần kiểm tra %s / %s: %s', item['chain_name'], item['sku'], last)
            issues.append(issue(item, last))


async def recheck_review(review, http, browser, rows, issues):
    """Đọc lại link review mỗi ngày; lỗi discovery cũ không phải kết quả giá hôm nay.
    Chỉ đưa vào bảng khi adapter đã xác minh mã biến thể và giá hoặc trạng thái.
    """
    from adapters.registry import ADAPTERS
    from identity import describe, chain_sku
    from collections import Counter
    counts=Counter((r['chain_name'],str(r['config'].get('variant_id'))) for r in review if r['config'].get('variant_id') and r['chain_name']!='Viettel Store')
    eligible=[]
    for row in review:
        item=row['config'] | {'chain_name':row['chain_name'],'url':row['source_url']}
        if 'Nhiều URL cùng SKU' in row.get('reason','') or (item.get('variant_id') and counts[(row['chain_name'],str(item['variant_id']))]>1 and row['chain_name']!='Viettel Store'):
            issues.append(issue(item,'Catalog chưa xác minh duy nhất SKU/link; giữ lại để kiểm tra','catalog'));continue
        if not item.get('variant_id') and row['chain_name'] not in ('Viettel Store','TGDD'):
            issues.append(issue(item,'Catalog chưa có mã biến thể để đọc giá an toàn; cần khám phá lại','catalog'));continue
        eligible.append(item)
    if not eligible:return
    adapter=ADAPTERS[eligible[0]['chain_name']]
    batch=None
    if hasattr(adapter,'read_many'):
        try: batch=await adapter.read_many(eligible,http,browser)
        except PipelineError as exc: batch={str(i['variant_id']):exc for i in eligible}
    for item in eligible:
        try:
            validate_url(item['chain_name'],item['url'])
            quote=batch.get(str(item['variant_id'])) if batch is not None else await adapter.read_product(item,http,browser)
            if isinstance(quote,Exception):raise quote
            if not isinstance(quote,dict):raise PipelineError('Không nhận được dữ liệu giá của mã biến thể')
            actual=str(quote.get('variant_id') or '')
            if not actual or (item.get('variant_id') and str(item['variant_id'])!=actual):raise PipelineError('Biến thể trả về khác mã catalog; cần khám phá lại')
            sku=chain_sku(item['chain_name'],quote.get('sku_key') or actual)
            if item.get('sku') and item['sku']!=sku:raise PipelineError('SKU trả về khác mã catalog; cần khám phá lại')
            if any(r['chain_name']==item['chain_name'] and r['sku']==sku for r in rows):raise PipelineError('SKU đã có giá từ link khác; giữ link trùng để kiểm tra')
            meta=describe(quote['product_name'],item.get('category',''),item.get('brand',''))
            sale=vnd(str(quote['promo_price'])) if quote.get('promo_price') is not None else None
            if sale is None and not str(quote.get('promo_text','')).startswith('[Tình trạng] '):raise PipelineError('Không có giá hoặc trạng thái đã xác minh')
            listed=quote.get('original_price')
            if sale is None:listed=None
            if listed is not None and sale is not None and vnd(str(listed))<sale:raise PipelineError('Giá gốc nhỏ hơn giá hiển thị')
            locked={**item,**meta,'sku':sku,'product_name':quote['product_name'],'variant_id':actual,'color':quote.get('color',item.get('color',''))}
            rows.append(price_row(locked,{**quote,'promo_price':sale,'original_price':listed}))
        except Exception as exc:
            reason=str(exc) if isinstance(exc,PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'
            issues.append(issue(item,reason,'price'))


def write_json(path, data):
    temporary = Path(str(path) + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


async def scrape_one(chain, args, http, browser):
    from apple_jobs import channel_lock, Busy
    from chains import slug
    try:
        with channel_lock(slug(chain)):
            return await _scrape_one(chain, args, http, browser)
    except Busy as exc:
        return {'chain_name':chain,'stage':'prices','status':'failed','message':str(exc),'error_kind':'busy'}


async def _scrape_one(chain, args, http, browser):
    """Worker một kênh. Luôn ghi summary.json (kể cả khi lỗi) để bộ tổng hợp báo cáo đúng tình trạng."""
    from chains import slug
    from errors import classify
    from collections import Counter
    directory = Path(args.out) / slug(chain)
    directory.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(f'scraper.{slug(chain)}')
    handler = logging.FileHandler(directory / 'worker.log', mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    log.handlers = [handler]
    summary = {'chain_name': chain, 'stage': 'prices', 'dry_run': bool(args.dry_run), 'status': 'running',
               'started_at': datetime.now(TZ).isoformat()}
    try:
        items, review, catalog_meta = load_catalog(args, chain)
        if items:validate_items(items)
        summary['catalog'] = catalog_meta
        rows, issues = [], []
        adapted = [item for item in items if item.get('adapter')]
        legacy = [item for item in items if not item.get('adapter')]
        if adapted:
            await scrape_chain(adapted, http, browser, rows, issues)
        for item in legacy:
            # Chế độ thủ công cũ (selector tự cấu hình): lỗi → mục cần kiểm tra như adapter.
            context = await browser.new_context(locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh')
            try:
                await robots_allowed(http, item['chain_name'], item['url'])
                page = await context.new_page()
                rows.append(await extract(page, item, http))
            except Exception as exc:
                issues.append(issue(item, str(exc) if isinstance(exc, PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'))
            finally:
                await context.close()
        await recheck_review(review,http,browser,rows,issues)
        expected = len(items) + len(review)
        if len(rows) + len(issues) != expected:
            raise PipelineError('Số giá + số mục cần kiểm tra không khớp catalog; không ghi dữ liệu')
        write_json(directory / 'issues.json', issues)
        price_issues = [i for i in issues if i['stage'] == 'price']
        summary.update(expected=expected, catalog_ready=len(items), catalog_review=len(review), prices=len(rows), numeric_prices=sum(r['promo_price'] is not None for r in rows), status_only=sum(r['promo_price'] is None for r in rows),
                       price_failures=len(price_issues), review_rechecked=len(review), issues=len(issues),
                       issues_by_kind=dict(Counter(i['error_kind'] for i in issues)),
                       blocked=sum(i['error_kind'] == 'blocked' for i in issues))
        if not rows:
            raise PipelineError('Không đọc được giá hay trạng thái nào cho kênh này; không ghi dữ liệu')
        # Giữ giá cũ cho SKU lỗi của lượt này; không xóa lịch sử/giá do lỗi truy cập.
        previous_path = directory / 'prices.json'
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else []
        failed_skus = {i.get('sku'):i.get('reason') for i in issues if i.get('sku')}
        fresh_skus = {r['sku'] for r in rows}
        retained = [{**r,'stale_since':datetime.now(TZ).isoformat(),'stale_reason':failed_skus[r['sku']]} for r in previous if r.get('sku') in failed_skus and r['sku'] not in fresh_skus]
        write_json(previous_path, rows + retained)
        summary['retained_stale'] = len(retained)
        # Mất >50% giá so với link ready: vẫn lưu phần đọc được nhưng đánh dấu suy giảm.
        summary['status'] = 'degraded' if len(rows) < 0.5 * len(items) else 'ok'
        if args.dry_run:
            summary['message'] = 'Dry-run: chưa ghi Supabase'
        else:
            year, week = weeks()[0]
            # Không retry thao tác ghi: phản hồi mất sau commit có thể tạo lượt thứ hai.
            run_id = database().rpc('commit_chain_price_run', {
                'p_chain': chain, 'p_year': year, 'p_week': week, 'p_rows': rows, 'p_issues': issues,
                'p_expected': expected, 'p_catalog_run': (catalog_meta or {}).get('run_id')}).execute().data
            summary.update(run_id=run_id, year=year, week=week, fiscal_period=fiscal_period())
    except Exception as exc:
        message = str(exc) if isinstance(exc, PipelineError) else f'Lỗi kỹ thuật {type(exc).__name__}'
        summary.update(status='failed', message=message, error_kind=classify(message))
        summary['last_failed_update'] = {'at':datetime.now(TZ).isoformat(),'reason':message}
        log.error('%s: %s', chain, message)
    summary['finished_at'] = datetime.now(TZ).isoformat()
    write_json(directory / 'summary.json', summary)
    log.info('Kết thúc %s: %s', chain, json.dumps({k: summary.get(k) for k in ('status', 'expected', 'prices', 'issues', 'message')}, ensure_ascii=False))
    handler.close()
    return summary


async def run(args):
    import http_policy
    from chains import resolve
    chains = resolve(args.chain)
    async with http_policy.client() as http, async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            summaries = await asyncio.gather(*(scrape_one(chain, args, http, browser) for chain in chains))
        finally:
            await browser.close()
    for item in summaries:
        LOG.info('%s: %s — %s giá / %s link, %s cần kiểm tra%s', item['chain_name'], item['status'], item.get('prices', 0),
                 item.get('expected', 0), item.get('issues', 0), f" ({item['message']})" if item.get('message') else '')
    if any(item['status'] != 'ok' for item in summaries):
        raise PipelineError('Có kênh lỗi hoặc suy giảm; các kênh khác vẫn đã lưu. Xem summary.json từng kênh')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description='Bot giá/CTKM hằng ngày theo từng kênh')
    parser.add_argument('--chain', action='append', required=True,
                        help='tgdd|cellphones|viettel|fpt|phongvu|all (lặp lại hoặc ngăn cách bằng dấu phẩy)')
    parser.add_argument('--out', default='artifacts/prices', help='Thư mục gốc; mỗi kênh một thư mục con')
    parser.add_argument('--catalog', choices=['file', 'discovery'], default='discovery',
                        help='discovery = catalog Supabase mới nhất của kênh; file = --config')
    parser.add_argument('--config', default='config/products.json',
                        help='catalog.json của discovery (dry-run) hoặc cấu hình thủ công')
    parser.add_argument('--limit', type=int, help='Dry-run: chỉ cào N link đầu của mỗi kênh')
    parser.add_argument('--dry-run', action='store_true')
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        LOG.error('Dừng bot: %s', str(exc) if isinstance(exc, PipelineError) else type(exc).__name__)
        raise SystemExit(1)
