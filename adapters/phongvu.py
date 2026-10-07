"""Phong Vũ: danh mục qua API tìm kiếm công khai mà trang /c/... tự gọi (Teko discovery),
giá/CTKM từ JSON server-render (__NEXT_DATA__) của trang chi tiết. Mỗi SKU Phong Vũ là một màu/cấu hình.
"""
import html
from price_availability import annotate, explicit_status
import json
import re
from urllib.parse import urlsplit

from common import PipelineError, vnd
from http_policy import fetch, ensure_allowed
from scraper import validate_url

CHAIN = 'Phong Vũ'
API = 'https://discovery.tekoapis.com/api/v2/search-skus-v2'
PAGE_SIZE = 40


def next_data(markup):
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', markup, re.S)
    if not match:
        raise PipelineError('Phong Vũ: trang không có dữ liệu __NEXT_DATA__')
    try:
        return json.loads(match[1])
    except ValueError:
        raise PipelineError('Phong Vũ: __NEXT_DATA__ không phải JSON hợp lệ') from None


def text_of(markup):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', markup or '')).split())


async def listing(source, http, browser=None):
    found = {}
    for seed in source['seeds']:
        validate_url(CHAIN, seed)
        await ensure_allowed(http, seed, CHAIN)
        slug = urlsplit(seed).path
        if not re.fullmatch(r'/c/[a-z0-9-]+', slug) or urlsplit(seed).query:
            raise PipelineError('Phong Vũ: link danh mục phải có dạng /c/<slug> không kèm bộ lọc')
        total, seen = None, set()
        for page in range(1, source.get('max_pages', 20) + 1):
            body = {'terminalId': 4, 'page': page, 'pageSize': PAGE_SIZE, 'slug': slug, 'filter': {},
                    'sorting': {'sort': 'SORT_BY_CREATED_AT', 'order': 'ORDER_BY_DESCENDING'},
                    'returnFilterable': [], 'isNeedFeaturedProducts': False}
            response = await fetch(http, 'POST', API, label='Phong Vũ API danh mục', json=body)
            try:
                data = response.json()['data']
                products, page_total = data['products'], int(data['total'])
            except (ValueError, KeyError, TypeError):
                raise PipelineError('Phong Vũ: API danh mục đổi cấu trúc') from None
            if total is not None and page_total != total:
                raise PipelineError('Phong Vũ: tổng sản phẩm đổi trong lúc phân trang; chạy lại')
            total = page_total
            if total > source.get('max_candidates', 500):
                raise PipelineError('Phong Vũ: danh mục vượt max_candidates; không cắt bớt âm thầm')
            for product in products:
                sku, canonical = str(product.get('sku', '')), product.get('canonical', '')
                if not sku.isdigit() or not canonical or sku in seen:
                    raise PipelineError('Phong Vũ: sản phẩm thiếu SKU/đường dẫn hoặc lặp giữa các trang')
                seen.add(sku)
                url = 'https://phongvu.vn/' + canonical.lstrip('/')
                validate_url(CHAIN, url)
                if re.search(r'--p\d+$', url):
                    # Trang nhóm nhiều SKU: khóa đúng SKU bằng tham số mà chính Phong Vũ dùng trong link.
                    url += '?sku=' + sku
                elif not url.endswith('--s' + sku):
                    raise PipelineError('Phong Vũ: đường dẫn không khớp SKU')
                found[url] = {'name': product.get('name', ''), 'variant_id': sku, 'url': url,
                              'group': str(product.get('productId') or sku),
                              'listing_price': product.get('latestPrice'),
                              'stock': 1 if product.get('sellable') else 0}
            if len(seen) >= total:
                break
            if not products:
                raise PipelineError('Phong Vũ: API trả trang rỗng trước khi đủ tổng sản phẩm')
        else:
            raise PipelineError('Phong Vũ: max_pages chưa đủ để đọc hết danh mục')
        if len(seen) != total:
            raise PipelineError('Phong Vũ: số sản phẩm đọc được khác tổng API báo')
    return found


def promotions(server):
    notes = []
    for group in (server.get('priceAndPromotions') or {}).get('promotions') or []:
        for promo in group.get('promotions') or []:
            title = text_of(promo.get('title') or promo.get('name'))
            if title:
                prefix = 'Chọn 1: ' if group.get('groupType') == 'GROUP_TYPE_SELECTABLE' else ''
                notes.append(prefix + title)
    for policy in server.get('salePolicies') or []:
        if policy.get('isHighlightedOnPromotionBlock'):
            value = text_of(policy.get('highlightText') or policy.get('displayText'))
            if value:
                notes.append(value)
    return list(dict.fromkeys(notes))


def color_rows(product):
    return [row for row in (product.get('productOptions') or {}).get('rows') or [] if 'mausac' in str(row.get('code','')).casefold() or str(row.get('title','')).casefold()=='màu sắc']


def selected_color(product):
    sku=str(product['productInfo']['sku'])
    rows=color_rows(product)
    if not rows:
        # Watch có thể chỉ cho chọn màu dây; màu vỏ nằm trong thuộc tính của đúng SKU.
        labels={' '.join(str(a.get('value')).split()) for a in (product.get('productDetail') or {}).get('attributeGroups') or [] if str(a.get('name','')).strip().casefold()=='màu sắc' and a.get('value')}
        return next(iter(labels)) if len(labels)==1 else ''
    selected=[o for row in rows for o in row.get('options') or [] if o.get('selected') and str(o.get('sku'))==sku]
    return selected[0]['label'] if len(selected)==1 else ''


async def read_product(item, http, browser=None):
    url = item['url']
    validate_url(CHAIN, url)
    response = await fetch(http, 'GET', url, label='Phong Vũ chi tiết')
    validate_url(CHAIN, str(response.url))
    try:
        server = next_data(response.text)['props']['pageProps']['serverProduct']
        product = server['product']
        info = product['productInfo']
    except (KeyError, TypeError):
        raise PipelineError('Phong Vũ: trang chi tiết đổi cấu trúc') from None
    if str(info.get('sku')) != str(item['variant_id']):
        raise PipelineError('Phong Vũ: trang chuyển sang SKU khác; cần khám phá lại')
    color = selected_color(product)
    availability='SKU chưa cho đặt mua tại khu vực mặc định.' if (product.get('status') or {}).get('sellable') is False else None
    availability=explicit_status(product.get('status')) or availability
    if not product.get('prices'):
        if availability:
            return {'chain_name':CHAIN,'product_name':info['name'],'source_url':str(response.url),'variant_id':str(info['sku']),'color':color,'promo_price':None,'original_price':None,'promo_text':annotate('\n'.join(promotions(server)),availability+' Nguồn không hiện giá của SKU này.'),'promotion_complete':True}
        raise PipelineError('Phong Vũ: bot chưa đọc được giá hay trạng thái của đúng SKU; cần đối chiếu trang/khu vực')
    price = product['prices'][0]
    try:
        sale = vnd(str(price['latestPrice'])) if price.get('latestPrice') else None
        if sale is None and not availability:raise PipelineError('Phong Vũ: chưa đọc được giá hoặc trạng thái SKU')
        listed = vnd(str(price['supplierRetailPrice'])) if price.get('supplierRetailPrice') else None
    except (KeyError, TypeError):
        raise PipelineError('Phong Vũ: thiếu giá bán') from None
    original = listed if listed and sale is not None and listed > sale else None
    if listed and sale is not None and listed < sale:
        raise PipelineError('Phong Vũ: giá niêm yết thấp hơn giá bán')
    return {'chain_name': CHAIN, 'product_name': info['name'], 'source_url': str(response.url),
            'variant_id': str(info['sku']), 'color': color, 'promo_price': sale, 'original_price': original,
            'promo_text': annotate('\n'.join(promotions(server)),availability), 'promotion_complete': True,
            'price_scope': 'Giá bán hiển thị (đã gồm KM giảm thẳng mặc định); quà/ưu đãi thanh toán chỉ ghi chú'}
