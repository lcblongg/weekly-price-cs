"""FPT Shop: danh mục qua API tìm kiếm công khai mà trang danh mục tự gọi; giá/CTKM từ dữ liệu
server-render của trang chi tiết `?sku=` (đúng màu + dung lượng). Không thực thi JS nguồn.
"""
import re
from price_availability import annotate, explicit_status
from urllib.parse import urlsplit, parse_qs

from common import PipelineError, vnd
from http_policy import fetch, ensure_allowed
from scraper import validate_url
from adapters.nextflight import flight, object_after

CHAIN = 'FPT Shop'
API = 'https://papi.fptshop.com.vn/gw/v1/public/fulltext-search-service/category'
PAGE = 24  # kích thước trang của chính website; trang lớn hơn làm thứ tự không ổn định


async def _page(http, slug, kind, skip):
    response = await fetch(http, 'POST', API, label='FPT Shop API danh mục',
                           json={'skipCount': skip, 'maxResultCount': PAGE, 'slug': slug, 'categoryType': kind})
    try:
        data = response.json()
        return int(data['totalCount']), data.get('items') or []
    except (ValueError, KeyError, TypeError):
        raise PipelineError('FPT Shop: API danh mục đổi cấu trúc') from None


async def _all_models(http, slug, kind, total, first):
    """Đọc đủ model. API xếp theo điểm nên thứ tự có thể đổi giữa hai request: đọc các cửa sổ chồng lấn
    và gộp theo mã model cho tới khi tập model đúng bằng tổng API báo. Không đủ/vượt tổng → lỗi."""
    models = {str(m.get('code')): m for m in first if m.get('code')}
    windows = [skip for offset in (0, PAGE // 2, PAGE // 4, 3 * PAGE // 4) for skip in range(offset, total, PAGE)]
    for skip in windows:
        if len(models) >= total:
            break
        if skip == 0:
            continue
        again, items = await _page(http, slug, kind, skip)
        if again != total:
            raise PipelineError('FPT Shop: tổng sản phẩm đổi trong lúc phân trang; chạy lại')
        for model in items:
            if not model.get('code'):
                raise PipelineError('FPT Shop: model thiếu mã')
            models[str(model['code'])] = model
    if len(models) != total:
        raise PipelineError(f'FPT Shop: đọc được {len(models)}/{total} model sau khi đọc chồng lấn; không dùng danh mục thiếu')
    return models


async def listing(source, http, browser=None):
    found = {}
    for seed in source['seeds']:
        validate_url(CHAIN, seed)
        await ensure_allowed(http, seed, CHAIN)
        slug = urlsplit(seed).path.strip('/')
        if urlsplit(seed).query or not re.fullmatch(r'[a-z0-9-]+/[a-z0-9-]+', slug):
            raise PipelineError('FPT Shop: link danh mục không đúng dạng <nhóm>/<hãng>')
        # Trang danh mục thường và trang chuyên trang hãng dùng hai loại khác nhau; phải đúng một loại có dữ liệu.
        probes = {kind: await _page(http, slug, kind, 0) for kind in ('category', 'specializedPage')}
        kinds = [kind for kind, (total, _) in probes.items() if total > 0]
        if len(kinds) != 1:
            raise PipelineError('FPT Shop: không xác định được danh mục (rỗng hoặc trùng loại trang)')
        kind = kinds[0]
        total, items = probes[kind]
        if total > source.get('max_candidates', 500):
            raise PipelineError('FPT Shop: danh mục vượt max_candidates; không cắt bớt âm thầm')
        models = await _all_models(http, slug, kind, total, items)
        if len(models) != total:
            raise PipelineError('FPT Shop: số model đọc được khác tổng API báo')
        for model in models.values():
            for sku in model.get('skus') or []:
                code = str(sku.get('sku', ''))
                if not code.isdigit():
                    raise PipelineError('FPT Shop: SKU thiếu mã')
                url = 'https://fptshop.com.vn/' + str(sku.get('slug', '')).lstrip('/')
                validate_url(CHAIN, url)
                if not urlsplit(url).query:
                    url += '?sku=' + code  # Trang riêng của phiên bản: vẫn khóa màu bằng ?sku=.
                if parse_qs(urlsplit(url).query).get('sku') != [code]:
                    raise PipelineError('FPT Shop: link SKU không khóa đúng mã biến thể')
                attrs = {v.get('propertyName', '').lower(): v.get('displayValue', '') for v in sku.get('variants') or []}
                found[url] = {'url': url, 'variant_id': code, 'group': code_group(model, attrs),
                              'name': ' '.join(x for x in (sku.get('displayName') or model.get('displayName', ''), attrs.get('color', '')) if x),
                              'color': attrs.get('color', ''), 'listing_price': sku.get('currentPrice'),
                              'listing_status': (sku.get('productStatus') or {}).get('displayName', '')}
    return found


def code_group(model, attrs):
    # Cùng model + cùng các thuộc tính trừ màu = cùng phiên bản cấu hình.
    rest = sorted((k, v) for k, v in attrs.items() if k != 'color')
    return str(model.get('code')) + '|' + '|'.join(f'{k}={v}' for k, v in rest)


def money(value):
    return f'{int(value):,}'.replace(',', '.') + 'đ'


def promotion_notes(promotion, online):
    notes, best = [], {}
    for item in promotion.get('included') or []:
        notes.append(item.get('name', ''))
    if online:
        notes.append(f"Giá online giới hạn {money(online['finalPrice'])}: {online['name']} (đến {str(online.get('expireDate',''))[:16].replace('T',' ')})")
    for item in promotion.get('other') or []:
        kind = item.get('programType', '')
        if kind == 'PriceOnline':
            continue
        if kind in ('TradeIn', 'BTS', 'education', 'BundleSuggestions'):
            label = {'TradeIn': 'Thu cũ đổi mới giảm thêm đến', 'BTS': 'Ưu đãi HSSV/tân sinh viên giảm đến',
                     'education': 'Ưu đãi HSSV/tân sinh viên giảm đến', 'BundleSuggestions': 'Trợ giá khi mua kèm đến'}[kind]
            amount = int(item.get('discountPrice') or 0)
            written = re.search(r'\d{1,3}(?:[.,]\d{3})+', item.get('name', ''))
            if not amount and written:
                amount = int(re.sub(r'\D', '', written[0]))
            best[label] = max(best.get(label, 0), amount)
        else:
            notes.append(item.get('name', ''))
    notes += [f'{label} {money(amount)}' for label, amount in best.items() if amount]
    for key in ('payment', 'extra'):
        notes += [item.get('name', '') for item in promotion.get(key) or []]
    return [n.strip() for n in dict.fromkeys(notes) if n and n.strip()]


def variant_color(state,code):
    colors=set()
    for entry in (state.get('variants') or {}).get('skuSlugs') or []:
        if str(entry.get('sku'))!=str(code):continue
        for attr in entry.get('attributes') or []:
            value=attr.get('key') or {}
            if str(value.get('propertyName','')).casefold()=='color' and value.get('displayValue'):colors.add(str(value['displayValue']).strip())
    return next(iter(colors)) if len(colors)==1 else ''

async def read_product(item, http, browser=None):
    url = item['url']
    validate_url(CHAIN, url)
    response = await fetch(http, 'GET', url, label='FPT Shop chi tiết')
    validate_url(CHAIN, str(response.url))
    state = object_after(flight(response.text), '"initialState":')
    try:
        info = state['productAdvanceInfo']
        variants = state['variants']['variantResult']['skus']
    except (KeyError, TypeError):
        raise PipelineError('FPT Shop: trang chi tiết đổi cấu trúc') from None
    code = str(item['variant_id'])
    if info is None:
        selected=[v for v in variants if str(v.get('code'))==code]
        status=explicit_status(state.get('productStatus'))
        if str(state['variants'].get('sku'))!=code or len(selected)!=1 or not status:
            raise PipelineError('FPT Shop: thiếu chi tiết giá và chưa xác minh trạng thái của đúng SKU')
        # variant.price có thể là giá lịch sử. Không dùng khi khối giá hiện tại đã bị gỡ.
        return {'chain_name':CHAIN,'product_name':selected[0].get('name') or selected[0].get('displayName'),'source_url':str(response.url),'variant_id':code,'color':variant_color(state,code),'promo_price':None,'original_price':None,'promo_text':annotate('Nguồn không trả khối giá hiện tại của SKU; không lấy giá lưu trong danh sách biến thể.',status),'promotion_complete':False,'price_scope':'Trạng thái website của đúng SKU, không hiện giá hiện tại'}
    if str(info.get('sku')) != code:
        raise PipelineError('FPT Shop: trang trả SKU khác SKU đã khóa; cần khám phá lại')
    match = [v for v in variants if str(v.get('code')) == code]
    if len(match) != 1:
        raise PipelineError('FPT Shop: không tìm thấy đúng một biến thể đã khóa')
    variant = match[0]
    button=(state.get('productStatus') or {}).get('buttonCode')
    availability=('đặt trước, cần xác minh ngày giao hàng.' if button=='PRE_ORDER' else 'biến thể chưa cho đặt mua tại khu vực mặc định.' if (button is not None and button not in ('ORDER','BUY_NOW')) or (variant.get('inventory') is not None and int(variant['inventory'])<=0) else None)
    availability=explicit_status(state.get('productStatus')) or availability
    promotion = info.get('promotion') or {}
    online = [p for p in promotion.get('other') or [] if p.get('programType') == 'PriceOnline' and p.get('finalPrice')]
    # Giá bán thường = finalPrice của SKU (sau giảm trực tiếp). Giá online giới hạn suất/khung giờ chỉ ghi chú,
    # để lịch sử giá không dao động theo suất flash (cùng quy ước với TGDD).
    raw=info.get('finalPrice') or info.get('price')
    sale = vnd(str(raw)) if raw else None
    shown = vnd(str(variant['price'])) if variant.get('price') else None
    if sale is None and not availability:raise PipelineError('FPT Shop: bot chưa đọc được giá hoặc trạng thái SKU')
    if shown is not None and sale is not None and shown != sale and not any(int(p['finalPrice']) == shown for p in online):
        raise PipelineError('FPT Shop: giá hiển thị của biến thể không khớp giá chi tiết; cần kiểm tra')
    listed = vnd(str(info['price'])) if info.get('price') else None
    if listed is not None and sale is not None and listed < sale:
        raise PipelineError('FPT Shop: giá niêm yết thấp hơn giá bán')
    return {'chain_name': CHAIN, 'product_name': variant.get('name') or variant.get('displayName'),
            'source_url': str(response.url), 'variant_id': code, 'color': variant_color(state,code),
            'promo_price': sale, 'original_price': listed if listed and sale is not None and listed > sale else None,
            'promo_text': annotate('\n'.join(promotion_notes(promotion, online[0] if online else None)),availability),
            'promotion_complete': True,
            'price_scope': 'Giá bán thường của SKU (finalPrice); giá online giới hạn suất, thu cũ, HSSV, thanh toán chỉ ghi chú'}
