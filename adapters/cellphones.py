"""CellphoneS: danh mục và giá/CTKM qua GraphQL công khai `api.cellphones.com.vn` mà chính website gọi.
Trang danh mục chỉ dùng để đọc mã danh mục (cate-id) và số sản phẩm hiển thị để đối chiếu đủ/thiếu.
Mỗi sản phẩm cha có các sản phẩm con theo màu; giá được đọc theo đúng mã sản phẩm con đã khóa.
"""
import html
from price_availability import annotate
import json
import re
from urllib.parse import urlsplit, parse_qsl

from common import PipelineError, vnd
from http_policy import fetch
from scraper import validate_url

CHAIN = 'CellphoneS'
API = 'https://api.cellphones.com.vn/v2/graphql/query'
PROVINCE = 30          # tỉnh mặc định website trả khi chưa chọn khu vực (Hà Nội)
STOCK_IDS = '[46, 56, 152, 4920]'
PAGE = 100   # GraphQL cho phép trang lớn; sắp xếp theo mã để phân trang ổn định


def _string(value):
    if not re.fullmatch(r'[a-z0-9-]{1,80}', value):
        raise PipelineError('CellphoneS: tham số lọc chứa ký tự ngoài phạm vi cho phép')
    return json.dumps(value)


async def graphql(http, query):
    response = await fetch(http, 'POST', API, label='CellphoneS GraphQL', json={'query': query, 'variables': {}})
    try:
        data = response.json()
    except ValueError:
        raise PipelineError('CellphoneS: GraphQL không trả JSON') from None
    if data.get('errors') or 'data' not in data:
        raise PipelineError('CellphoneS: GraphQL báo lỗi hoặc đổi contract')
    return data['data']


def _filters(cate, seed):
    dynamic = []
    for key, value in parse_qsl(urlsplit(seed).query):
        if not re.fullmatch(r'[a-z_]{2,40}', key):
            raise PipelineError('CellphoneS: tham số lọc không hợp lệ')
        dynamic.append(f'{key}: {{in: [{_string(value)}]}}')
    if dynamic:
        dynamic.append('use_nice_uri: true')
    static = (f'categories: [{json.dumps(str(cate))}], province_id: {PROVINCE}, stock: {{from: 0}}, '
              f'company_stock_id: {STOCK_IDS}')
    return f'static: {{ {static} }} dynamic: {{ {" ".join(dynamic)} }}'


def category_id(markup, seed):
    """Mã danh mục: giao diện cũ có thuộc tính cate-id; giao diện mới có pageData.category_id."""
    old = set(re.findall(r'<div cate-id="(\d+)"', markup))
    if len(old) == 1:
        return old.pop(), True
    if 'self.__next_f' in markup:
        from adapters.nextflight import flight, object_after
        data = object_after(flight(markup), '"pageData":', 0)
        path = urlsplit(seed).path.lstrip('/')
        if data.get('type') == 'category' and str(data.get('request_path')) == path and str(data.get('category_id', '')).isdigit():
            return str(data['category_id']), False
    raise PipelineError('CellphoneS: không xác định duy nhất mã danh mục trên trang')


def page_counts(markup):
    """Số card đã render + 'Xem thêm N sản phẩm' trên trang danh mục, dùng để kiểm tra GraphQL đủ."""
    shown = len(re.findall(r'class="product-info-container product-item"', markup))
    more = re.search(r'btn-show-more[^>]*>\s*Xem thêm\s*(\d+)\s*sản phẩm', markup)
    return shown + (int(more[1]) if more else 0)


async def listing(source, http, browser=None):
    found = {}
    for seed in source['seeds']:
        validate_url(CHAIN, seed)
        page = await fetch(http, 'GET', seed, label='CellphoneS danh mục')
        cate, rendered = category_id(page.text, seed)
        filters = _filters(cate, seed)
        total = (await graphql(http, f'query{{ total(filter: {{ {filters} }}) }}'))['total']
        # Đối chiếu với số sản phẩm trang server-render khi có (giao diện cũ, không tham số lọc).
        # Giao diện mới/trang có lọc tải danh sách phía client nên chỉ kiểm tra tổng GraphQL > 0 và khớp số đọc được.
        expected = page_counts(page.text) if rendered and not urlsplit(seed).query else total
        if not isinstance(total, int) or total <= 0 or total != expected:
            raise PipelineError(f'CellphoneS: GraphQL báo {total} sản phẩm, trang hiển thị {expected}; không dùng dữ liệu lệch')
        if total > source.get('max_candidates', 500):
            raise PipelineError('CellphoneS: danh mục vượt max_candidates; không cắt bớt âm thầm')
        seen = {}
        for number in range(1, total // PAGE + 2):
            data = await graphql(http, f'''query{{ products(filter: {{ {filters} }}, page: {number}, size: {PAGE},
                sort: [{{product_id: desc}}]) {{ general{{ product_id name url_path child_product }} filterable{{ is_parent price special_price stock }} }} }}''')
            products = data.get('products') or []
            for product in products:
                general = product['general']
                pid = str(general['product_id'])
                if pid in seen:
                    raise PipelineError('CellphoneS: sản phẩm lặp giữa các trang')
                seen[pid] = product
            if len(seen) >= total or not products:
                break
        if len(seen) != total:
            raise PipelineError('CellphoneS: số sản phẩm đọc được khác tổng GraphQL báo')
        for pid, product in seen.items():
            general = product['general']
            url = 'https://cellphones.com.vn/' + str(general['url_path']).lstrip('/')
            validate_url(CHAIN, url)
            found[url] = {'url': url, 'parent_id': pid, 'name': general['name'],
                          'children': [str(c) for c in general.get('child_product') or []]}
    return found


FIELDS = 'general{ product_id name url_path } filterable{ is_parent parent_id price special_price stock promotion_information promotion_pack }'


async def products_by_id(http, ids):
    """Đọc nhiều mã trong một truy vấn `products` (GraphQL chỉ cho một root field mỗi request)."""
    result = {pid: None for pid in ids}
    for parent_flag in ('false', 'true'):
        missing = [pid for pid, value in result.items() if value is None]
        for start in range(0, len(missing), 50):
            chunk = missing[start:start + 50]
            data = await graphql(http, f'''query{{ products(filter: {{ static: {{ is_parent: ["{parent_flag}"],
                province_id: {PROVINCE}, product_id: {json.dumps(chunk)}, stock: {{from: 0}} }} }}, size: {len(chunk)},
                sort: [{{product_id: desc}}]) {{ {FIELDS} }} }}''')
            for product in data.get('products') or []:
                pid = str(product['general']['product_id'])
                if pid in result:
                    result[pid] = product
    return result


async def variants(http, candidate):
    """Mở rộng sản phẩm cha thành các biến thể màu kèm giá, dùng ở bước khám phá Chủ nhật."""
    ids = candidate['children'] or [candidate['parent_id']]
    rows = []
    for pid, product in (await products_by_id(http, ids)).items():
        if not product:
            continue
        general, filterable = product['general'], product['filterable']
        # Link màu theo đúng dạng CellphoneS dùng cho nút chọn màu; bot không tải link này (giá đọc qua GraphQL).
        url = candidate['url'] + ('?product_id=' + pid if candidate['children'] else '')
        rows.append({'url': url, 'variant_id': pid, 'parent_id': candidate['parent_id'],
                     'name': general['name'], 'parent_name': candidate['name'], 'color': color_of(general['name'], candidate['name']),
                     'listing_price': filterable.get('special_price') or filterable.get('price'),
                     'stock': filterable.get('stock')})
    return rows


def color_of(child_name, parent_name):
    """Tên con = tên cha (bỏ hậu tố) + '-<màu>'; chỉ nhận khi đúng mẫu đó."""
    if '-' not in child_name:
        return ''
    base, color = child_name.rsplit('-', 1)
    return color.strip() if base.strip() and len(color.strip()) <= 40 else ''


def _notes(filterable):
    notes = []
    info = filterable.get('promotion_information') or ''
    notes += [' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', part)).split())
              for part in re.split(r'</p>|<br\s*/?>', info, flags=re.I)]
    pack = filterable.get('promotion_pack') or {}
    for group in pack.values() if isinstance(pack, dict) else []:
        for promo in (group or {}).values() if isinstance(group, dict) else []:
            if not promo.get('is_active', True):
                continue
            for entry in promo.get('items') or []:
                if entry.get('is_active', True) and entry.get('name'):
                    notes.append(' '.join(str(entry['name']).split()))
    return [n for n in dict.fromkeys(notes) if n]


def quote(item, product):
    pid = str(item['variant_id'])
    if not product:
        raise PipelineError('CellphoneS: mã sản phẩm đã khóa không còn trên GraphQL; cần khám phá lại')
    general, filterable = product['general'], product['filterable']
    if item.get('parent_id') and str(filterable.get('parent_id') or pid) not in (str(item['parent_id']), pid):
        raise PipelineError('CellphoneS: sản phẩm con đổi sang model cha khác')
    availability='hết hàng tại khu vực mặc định Hà Nội, chưa xác nhận đặt mua.' if filterable.get('stock') is not None and int(filterable['stock'])<=0 else None
    listed = vnd(str(int(filterable['price']))) if filterable.get('price') else None
    special = int(filterable.get('special_price') or 0)
    sale = vnd(str(special)) if special else listed
    if sale is None and not availability:
        raise PipelineError('CellphoneS: bot chưa đọc được giá hoặc trạng thái SKU')
    if listed is not None and sale is not None and listed < sale:
        raise PipelineError('CellphoneS: giá gốc thấp hơn giá bán')
    url = item.get('url') or 'https://cellphones.com.vn/' + str(general['url_path']).lstrip('/')
    validate_url(CHAIN, url)
    return {'chain_name': CHAIN, 'product_name': general['name'], 'source_url': url, 'variant_id': pid,
            'color': item.get('color') or color_of(general['name'], item.get('name', '')), 'promo_price': sale,
            'original_price': listed if listed and sale is not None and listed > sale else None,
            'promo_text': annotate('\n'.join(_notes(filterable)),availability), 'promotion_complete': True,
            'price_scope': 'Giá bán thường (special_price) của mã màu, khu vực mặc định Hà Nội; giá Smember/HSSV/thanh toán không trừ'}


async def read_product(item, http, browser=None):
    pid = str(item['variant_id'])
    return quote(item, (await products_by_id(http, [pid]))[pid])


async def read_many(items, http, browser=None):
    """Đọc giá hàng loạt (50 mã/request). Trả về {variant_id: quote | PipelineError}."""
    products = await products_by_id(http, [str(item['variant_id']) for item in items])
    result = {}
    for item in items:
        try:
            result[str(item['variant_id'])] = quote(item, products.get(str(item['variant_id'])))
        except PipelineError as exc:
            result[str(item['variant_id'])] = exc
    return result
