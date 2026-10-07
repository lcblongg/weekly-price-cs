"""Kiểm tra URL nhập tay của MỘT model đã lưu: đúng domain/định dạng → đọc trang → đúng model chuẩn → có biến thể
đúng màu yêu cầu. Dùng chính hàm xác minh của worker; không ghi giá, không ghi Supabase, không gửi Telegram.
stdin: {"model": "...", "channels": ["tgdd", ...] (tùy chọn)}. Kết quả ghi vào artifacts/apple-url-checks.json.
Chỉ kiểm tra cấu hình ĐÃ LƯU, để kết quả khớp đúng những gì worker sẽ làm."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import apple_sources  # noqa: E402
from apple_preferences import load, key  # noqa: E402
from apple_rules import URL_CHANNELS, manual_urls, normalize_url, RuleError  # noqa: E402

MAX_URLS = 40


async def check_tgdd(http, browser, rule, url):
    from adapters import tgdd
    from mw_apple_colors import selected_variants
    _, queries = await tgdd.detail(http, url)
    data = (queries.get('PRODUCT_DETAIL') or {}).get('data') or {}
    variants = selected_variants(data, url, rule)
    return f'{len(variants)} biến thể đúng model/màu: ' + ', '.join(sorted({str(v["color_evidence"].get("version") or v["variant_id"]) for v in variants}))


async def check_cps(http, browser, rule, url):
    from cps_apple_colors import selected_quote
    parent, children = await apple_sources.cps_resolve(http, url)
    base = 'https://cellphones.com.vn/' + parent['general']['url_path'].lstrip('/')
    chosen = []
    for pid, child in children.items():
        if not child:
            continue
        result = selected_quote(parent, child, rule, base)  # sai model → WrongModel
        if result is not None:
            chosen.append(pid)
    if not chosen:
        raise apple_sources.ColorNotFound(f'CPS: sản phẩm cha {parent["general"]["product_id"]} không có mã màu con đúng {rule["color"]}')
    return f'Cha {parent["general"]["product_id"]} ({parent["general"]["name"]}); mã màu đúng yêu cầu: {", ".join(chosen)}'


async def check_remaining(slug, http, browser, rule, url):
    from scrape_remaining_apple import palette, matches
    from product_standard import canonical_model
    options, _ = await palette(slug, http, browser, {'url': url})
    same = [v for v in options if canonical_model(v['name']) == rule['model']]
    if not same:
        raise apple_sources.WrongModel(f'Trang là {options[0]["name"] if options else "sản phẩm không xác định"}, không phải {rule["model"]}')
    wanted = [v for v in same if matches(rule, v['color'])]
    if not wanted:
        raise apple_sources.ColorNotFound('Màu trên trang: ' + ', '.join(sorted({str(v['color']) for v in same})))
    return f'{len(wanted)} biến thể đúng model/màu: ' + ', '.join(str(v['variant_id']) for v in wanted)


async def main():
    import fcntl
    lock = open(ROOT / 'artifacts/apple-url-check.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # không chạy chồng hai lượt kiểm tra URL
    except BlockingIOError:
        print(json.dumps({'ok': False, 'error': 'Đang có một lượt kiểm tra URL khác; thử lại sau'}, ensure_ascii=False))
        return 2
    from http_policy import client
    from playwright.async_api import async_playwright
    payload = json.loads(sys.stdin.read() or '{}')
    config = load()
    rule = next((r for r in config['products'] if key(r['model']) == key(payload.get('model'))), None)
    if not rule:
        print(json.dumps({'ok': False, 'error': 'Model chưa được lưu; lưu cấu hình trước khi kiểm tra URL'}, ensure_ascii=False))
        return 2
    channels = [c for c in (payload.get('channels') or URL_CHANNELS) if c in URL_CHANNELS]
    jobs = [(c, u) for c in channels for u in manual_urls(rule, c)]
    if len(jobs) > MAX_URLS:
        print(json.dumps({'ok': False, 'error': f'Tối đa {MAX_URLS} URL mỗi lượt kiểm tra'}, ensure_ascii=False))
        return 2
    results = []
    async with client(timeout=35) as http, async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            for channel, url in jobs:
                try:
                    if normalize_url(channel, url) != url:
                        raise RuleError('URL đã đổi định dạng; lưu lại cấu hình')
                    if channel == 'tgdd':
                        detail = await check_tgdd(http, browser, rule, url)
                    elif channel == 'cellphones':
                        detail = await check_cps(http, browser, rule, url)
                    else:
                        detail = await check_remaining(channel, http, browser, rule, url)
                    status = 'valid'
                except RuleError as exc:
                    status, detail = 'invalid_url', str(exc)
                except Exception as exc:
                    status = apple_sources.classify(exc)
                    detail = str(exc) if str(exc) else f'Lỗi kỹ thuật {type(exc).__name__}'
                apple_sources.record(rule['model'], channel, url, status, detail, rule['color'], 'check')
                results.append({'channel': channel, 'url': url, 'status': status, 'label': apple_sources.LABELS[status], 'detail': detail})
        finally:
            await browser.close()
    print(json.dumps({'ok': True, 'model': rule['model'], 'results': results}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
