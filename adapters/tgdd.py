"""Thế Giới Di Động.

Danh mục: Playwright mở trang danh mục và bấm "Xem thêm" như người dùng cho tới hết, rồi đọc thẻ sản phẩm.
TGDD đang A/B hai giao diện (Next.js mới và giao diện cũ); cả hai đều được hỗ trợ và luôn đối chiếu số thẻ
với tổng sản phẩm chính trang công bố. Mỗi thẻ có các nút phiên bản (RAM/ROM, cỡ mặt...) — mỗi phiên bản là
một trang riêng và được theo dõi riêng.

Chi tiết: HTTP thường, đọc JSON server-render (PRODUCT_DETAIL + ưu đãi thanh toán). Màu được khóa bằng
`?code=<mã sản phẩm>` mà chính TGDD dùng. robots.txt yêu cầu Crawl-delay 5 giây, được tôn trọng.
"""
import asyncio
import html
from price_availability import annotate, explicit_status
import re
from urllib.parse import urlsplit, parse_qs

from common import PipelineError, vnd
from http_policy import fetch, ensure_allowed, wait_turn, USER_AGENT
from scraper import validate_url
from adapters.nextflight import flight, object_after

CHAIN = 'TGDD'
BASE = 'https://www.thegioididong.com'
PREFIX = {'Điện thoại': '/dtdd/', 'Máy tính bảng': '/may-tinh-bang/', 'Máy tính xách tay': '/laptop/',
          'Đồng hồ thông minh': '/dong-ho-thong-minh/', 'Airpods': '/tai-nghe/'}

NEW_CARDS = """(prefix) => [...document.querySelectorAll('div[data-model-code][data-product-code]')].map(card => ({
  code: card.getAttribute('data-product-code'), model: card.getAttribute('data-model-code'),
  links: [...card.querySelectorAll('a[href]')].map(a => a.getAttribute('href')).filter(h => h && h.startsWith(prefix)),
  name: (card.querySelector('h3') || {}).innerText || ''}))"""
OLD_CARDS = """(prefix) => [...document.querySelectorAll('ul.listproduct li.item[data-id]:not(.merge__item)')].map(li => {
  const a = li.querySelector('a.main-contain');
  const versions = [...li.querySelectorAll('.prods-group li[data-url]')].map(x => x.getAttribute('data-url'));
  return {code: li.getAttribute('data-productcode'), model: li.getAttribute('data-id'),
          links: [a && a.getAttribute('href')].concat(versions).filter(h => h && h.startsWith(prefix)),
          name: a ? (a.getAttribute('data-name') || '') : ''}; })"""


def _forget_ab_cookies(http):
    # Không giữ cookie phân nhóm A/B giữa các request: mỗi lượt là một khách mới, không giả danh ai.
    for cookie in list(http.cookies.jar):
        if cookie.domain.endswith('thegioididong.com'):
            http.cookies.jar.clear(cookie.domain, cookie.path, cookie.name)


async def _expand(page, ui):
    """Bấm 'Xem thêm' cho tới khi trang không còn nút. Mỗi lượt chờ tối đa 30s, bấm lại một lần nếu chưa tải."""
    cards = 'ul.listproduct li.item[data-id]:not(.merge__item)' if ui == 'old' else 'div[data-model-code][data-product-code]'
    for _ in range(40):
        if ui == 'old':
            button = page.locator('.view-more a:visible', has=page.locator('.remain'))
        else:
            button = page.locator('span:visible', has_text=re.compile(r'^Xem thêm \d+'))
        if await button.count() == 0:
            return True
        before = await page.locator(cards).count()
        for click in range(2):
            if await button.count() == 0:
                break
            await button.first.click()
            for _ in range(60):
                await asyncio.sleep(0.5)
                if await page.locator(cards).count() > before:
                    break
            else:
                continue
            break
        if await page.locator(cards).count() <= before:
            # Nút còn nhưng không tải thêm (một số thẻ không render): dừng, để bước đối chiếu tổng quyết định
            # (đọc ≥80% → cảnh báo kèm số liệu; ít hơn → lỗi nguồn).
            return False
        await asyncio.sleep(2)
    raise PipelineError('TGDD: quá nhiều lượt Xem thêm; kiểm tra lại trang danh mục')


def normalize_href(href, prefix):
    """Giao diện mới đôi khi sinh link lặp tiền tố ('/dong-ho-thong-minh//dong-ho-thong-minh/x')."""
    path = href.split('?')[0].split('#')[0]
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 2 and all(p == parts[0] for p in parts[:-1]) and '/' + parts[0] + '/' == prefix:
        return prefix + parts[-1]
    return path


async def _open_listing(browser, seed, prefer_new=4):
    """Mở trang danh mục; ưu tiên giao diện mới (danh mục đầy đủ hơn), tối đa vài lượt khách mới."""
    for attempt in range(prefer_new):
        context = await browser.new_context(locale='vi-VN', timezone_id='Asia/Ho_Chi_Minh', user_agent=USER_AGENT)
        page = await context.new_page()
        response = await page.goto(seed, wait_until='domcontentloaded', timeout=60000)
        if response is None or response.status != 200:
            await context.close()
            raise PipelineError(f'TGDD: trang danh mục HTTP {response.status if response else "?"}')
        validate_url(CHAIN, page.url)
        await page.wait_for_timeout(2500)
        ui = 'old' if await page.locator('ul.listproduct li.item[data-id]:not(.merge__item)').count() else 'new'
        if ui == 'new' or attempt == prefer_new - 1:
            return context, page, ui
        await context.close()
        await asyncio.sleep(5)  # Crawl-delay giữa hai lượt mở


async def _read_cards(page, ui, prefix, source):
    if ui == 'new':
        markup = await page.content()
        totals = set(re.findall(r'"totalProduct\\?":(\d+)', markup))
        if len(totals) != 1:
            raise PipelineError('TGDD: không đọc được tổng sản phẩm của danh mục')
        total = int(totals.pop())
        # Thẻ sản phẩm render phía client; chờ thẻ xuất hiện thay vì đọc khi trang còn trống.
        try:
            await page.wait_for_selector('div[data-model-code][data-product-code]', timeout=20000)
        except Exception:
            pass
    else:
        remain = page.locator('.view-more .remain')
        extra = int((await remain.first.inner_text()).strip()) if await remain.count() else 0
        total = await page.locator('ul.listproduct li.item[data-id]:not(.merge__item)').count() + extra
    if total > source.get('max_candidates', 500):
        raise PipelineError('TGDD: danh mục vượt max_candidates; không cắt bớt âm thầm')
    await _expand(page, ui)
    return total, await page.evaluate(NEW_CARDS if ui == 'new' else OLD_CARDS, prefix)


async def listing(source, http, browser):
    if browser is None:
        raise PipelineError('TGDD: danh mục cần trình duyệt để bấm Xem thêm')
    prefix = PREFIX.get(source.get('category', ''))
    if not prefix:
        raise PipelineError('TGDD: chưa có tiền tố URL cho danh mục này')
    found, notes = {}, []
    for seed in source['seeds']:
        validate_url(CHAIN, seed)
        await ensure_allowed(http, seed, CHAIN)
        await wait_turn(http, seed)
        for attempt in range(3):
            context, page, ui = await _open_listing(browser, seed)
            try:
                total, cards = await _read_cards(page, ui, prefix, source)
            finally:
                await context.close()
            if len(cards) >= 0.8 * total:
                break
            # Một lượt A/B render thiếu thẻ: mở lại như khách mới, vẫn giữ Crawl-delay.
            await asyncio.sleep(5)
        # Cùng một model có thể hiện ở 2 thẻ (sản phẩm nổi bật được nhắc lại): gộp theo mã model, giữ mọi link phiên bản.
        merged = {}
        for card in cards:
            if not card.get('model'):
                raise PipelineError('TGDD: thẻ sản phẩm thiếu mã model')
            if card['model'] in merged:
                merged[card['model']]['links'] += card['links']
                merged[card['model']]['name'] = merged[card['model']]['name'] or card['name']
            else:
                merged[card['model']] = {**card, 'links': list(card['links'])}
        repeated = len(cards) - len(merged)
        cards = list(merged.values())
        if len(cards) < 0.8 * total:
            raise PipelineError(f'TGDD: chỉ đọc được {len(cards)}/{total} thẻ; không dùng danh mục thiếu nhiều')
        label = f'Giao diện {"mới" if ui == "new" else "cũ"}'
        if repeated:
            notes.append(f'{label}: {repeated} thẻ lặp cùng model đã gộp')
        if len(cards) != total:
            # TGDD đang A/B hai giao diện với số liệu khác nhau; ghi rõ độ lệch thay vì bỏ qua âm thầm.
            notes.append(f'{label}: đọc {len(cards)} model, trang công bố {total} — THIẾU {total - len(cards)}')
        else:
            notes.append(f'{label}: đủ {total} model')
        for card in cards:
            if not card['links']:
                raise PipelineError('TGDD: thẻ sản phẩm không có link chi tiết')
            for href in dict.fromkeys(normalize_href(h, prefix) for h in card['links']):
                url = BASE + href
                validate_url(CHAIN, url)
                if not re.search(source['product_url_pattern'], url):
                    raise PipelineError(f'TGDD: link phiên bản không khớp nhóm hàng của nguồn ({href})')
                found.setdefault(url, {'url': url, 'name': ' '.join(card['name'].split()), 'model_code': card['model']})
    return found, {'notes': notes}


def _queries(markup):
    data = object_after(flight(markup), '"queries":', 0)
    return {q['queryKey'][0]: (q.get('state') or {}).get('data') for q in data if q.get('queryKey')}


async def detail(http, url):
    """Trang chi tiết giao diện mới. Gặp giao diện cũ (A/B) thì quên cookie và hỏi lại, tối đa 3 lần."""
    for attempt in range(6):
        _forget_ab_cookies(http)
        response = await fetch(http, 'GET', url, label='TGDD chi tiết')
        validate_url(CHAIN, str(response.url))
        if 'self.__next_f' in response.text:
            return response, _queries(response.text)
        if re.search(r'document\.productCode\s*=',response.text):
            from adapters.tgdd_legacy import parse
            data=parse(response.text,str(response.url))
            return response, {'PRODUCT_DETAIL':{'data':data}}
    raise PipelineError('TGDD: sau 6 lần trang chi tiết vẫn không có dữ liệu giá server-render (thường là máy chưa mở bán hoặc trang tải bằng JS); không ghi giá')


def _text(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', str(value or ''))).split())


def promotion_notes(detail_data, payments):
    notes = []
    prices=detail_data.get('productPrices') or []
    normal = [p for p in prices if not is_flash(p)]
    selected=normal or prices
    promotions = (selected[0].get('promotions') or {}) if selected else {}
    for group in promotions.get('giftPromotions') or []:
        gifts = ', '.join(_text(g.get('displayName') or g.get('name')) for g in group.get('lstGift') or [])
        if gifts:
            notes.append(f"{_text(group.get('title')) or 'Quà tặng'} {gifts}".strip())
    for key in ('discountPromotions', 'normalPromotions'):
        for promo in promotions.get(key) or []:
            text = _text(promo.get('content') or promo.get('title')).replace(' Xem chi tiết', '')
            if text:
                notes.append(text)
    for offer in payments or []:
        if offer.get('isActivated', True) and offer.get('saleName'):
            notes.append('Thanh toán: ' + _text(offer['saleName']))
    return list(dict.fromkeys(notes))


def is_flash(entry):
    """Giá giờ vàng/flash: chương trình loại khác 0, nhóm GoldHour/FlashSale hoặc giới hạn số suất."""
    group = str((entry.get('htmlIdRule') or {}).get('groupId') or '')
    return (int(entry.get('saleProgramTypeId') or 0) != 0 or bool(re.search(r'gold\s*hour|flash', group, re.I))
            or bool((entry.get('stockQuantity') or {}).get('maxQuantity')))


def flash_notes(entries):
    notes = []
    for entry in entries:
        limit = (entry.get('stockQuantity') or {}).get('maxQuantity')
        window = f"{str(entry.get('startDate',''))[11:16]}–{str(entry.get('endDate',''))[11:16]} {str(entry.get('endDate',''))[:10]}"
        notes.append(f"Giá giới hạn (giờ vàng/online) {int(entry['price']):,}đ, {window}".replace(',', '.')
                     + (f', tối đa {limit} suất' if limit else ''))
    return notes


def color_of(detail_data, code):
    # MW có cả nhóm “Màu” và “Màu sắc master”; đều khóa màu bằng productCodes.
    names={v['name'] for group in detail_data.get('filter') or []
           if group.get('label') in ('Màu','Màu sắc','Màu sắc master')
           for v in group.get('values') or [] if str(code) in {str(c) for c in v.get('productCodes') or []}}
    return next(iter(names)) if len(names)==1 else ''


async def read_product(item, http, browser=None):
    url = item['url']
    validate_url(CHAIN, url)
    locked = item.get('variant_id')
    target = url + (f'?code={locked}' if locked else '')
    response, queries = await detail(http, target)
    detail_data = (queries.get('PRODUCT_DETAIL') or {}).get('data')
    if not detail_data:
        raise PipelineError('TGDD: thiếu dữ liệu giá trên trang chi tiết')
    code = str(detail_data.get('productCode') or '')
    if not re.fullmatch(r'\d{8,20}', code):
        raise PipelineError('TGDD: thiếu mã sản phẩm của biến thể')
    if locked and code != str(locked):
        raise PipelineError('TGDD: trang không trả đúng màu đã khóa; cần khám phá lại')
    if urlsplit(str(response.url)).path != urlsplit(url).path and not locked:
        raise PipelineError('TGDD: trang chuyển hướng sang sản phẩm khác')
    if detail_data.get('_legacy_quote'):
        return detail_data['_legacy_quote']
    explicit=explicit_status(detail_data)
    if detail_data.get('hiddenPrice') or (not detail_data.get('productPrices') and explicit):
        payments=(queries.get('FETCH_PRODUCT_PAYMENT_OFFER') or {}).get('data')
        return {'chain_name':CHAIN,'product_name':detail_data['name'],'source_url':url,'variant_id':code,'color':color_of(detail_data,code),'promo_price':None,'original_price':None,'promo_text':annotate('\n'.join(promotion_notes(detail_data,payments)),explicit or 'Liên hệ; website ẩn giá của sản phẩm.'),'promotion_complete':payments is not None}
    prices = detail_data.get('productPrices') or []
    # Chương trình thường (saleProgramTypeId 0) là giá bán; giờ vàng/flash giới hạn suất chỉ ghi chú.
    normal = [p for p in prices if not is_flash(p)]
    if len({(p.get('price'), p.get('sysPrice')) for p in normal}) != 1:
        raise PipelineError('TGDD: không xác định duy nhất giá bán thường; cần kiểm tra')
    price = normal[0]
    flash = [p for p in prices if p not in normal and p.get('price')]
    preorder=bool(price.get('expectedPrice') or detail_data.get('crmPreorderCode'))
    availability='mã màu chưa cho đặt mua tại khu vực mặc định.' if price.get('isCanBuy') is False else None
    if preorder:availability='Sản phẩm đặt trước; xác minh điều kiện/tiền cọc trên trang.'
    availability=explicit or availability
    raw_price=price.get('price')
    sale = vnd(str(raw_price)) if raw_price else None
    if sale is None and not availability:raise PipelineError('TGDD: bot chưa đọc được giá hoặc trạng thái của SKU')
    listed = vnd(str(price['sysPrice'])) if price.get('sysPrice') else None
    if listed is not None and sale is not None and listed < sale:
        raise PipelineError('TGDD: giá niêm yết thấp hơn giá bán')
    payments = (queries.get('FETCH_PRODUCT_PAYMENT_OFFER') or {}).get('data')
    return {'chain_name': CHAIN, 'product_name': detail_data['name'], 'source_url': url, 'variant_id': code,
            'color': color_of(detail_data, code), 'promo_price': sale,
            'original_price': listed if listed and sale is not None and listed > sale else None,
            'promo_text': annotate('\n'.join(flash_notes(flash) + promotion_notes(detail_data, payments)),availability),
            'promotion_complete': payments is not None,
            'price_scope': 'Giá bán TGDD của mã màu đã khóa, khu vực mặc định website; quà/thu cũ/thanh toán chỉ ghi chú'}
