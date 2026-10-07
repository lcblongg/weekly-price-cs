"""Danh mục Viettel: dùng HTTP và widget công khai mà trang danh mục tự gọi.
Không đổi IP/proxy, không spoof browser, không dùng cookie chống bot hay thực thi JS nguồn.
"""
import asyncio
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs

from common import PipelineError, vnd
from catalog import clean_url
from scraper import robots_allowed, validate_url

ENDPOINT = '/Site/_Sys/GetUserControlAsync.aspx'
PARAMETERS = {'path','PaginationVisiable','CatID','ManID','Tags','PageSize','CurrentPage',
              'SpecOrder','SpecFilter','FeatureFilter','PriceFrom','PriceTo','isHot'}
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


def literal(value):
    value = value.strip()
    if re.fullmatch(r'-?\d+', value):
        return value
    if len(value) >= 2 and value[0] in "'\"" and value[-1] == value[0]:
        body = value[1:-1]
        # Tham số filter của nguồn không cần JS escapes; không thực thi biểu thức.
        if '\\' not in body and value[0] not in body:
            return body
    raise PipelineError('Viettel đổi cấu trúc tham số widget; cần kiểm tra adapter')


def catalog_request(markup, seed=None):
    """Đọc đúng object .load() trong GenProductList; không tự đoán CatID/ManID."""
    match = re.search(r'function\s+GenProductList\s*\([^)]*\)\s*\{.*?\.load\(\s*[\'\"]'
                      + re.escape(ENDPOINT) + r'[\'\"]\s*,\s*\{(.*?)\}\s*,', markup, re.S)
    if not match:
        raise PipelineError('Viettel: không thấy widget danh mục công khai trong trang nguồn')
    script_start = markup.rfind('<script', 0, match.start())
    declarations = markup[script_start:match.start()]
    entries = re.findall(r'[\'\"]([A-Za-z]+)[\'\"]\s*:\s*([^,\n\r]+)', match[1])
    search = bool(seed and urlsplit(seed).path == "/ket-qua-tim-kiem.html")
    allowed = PARAMETERS | ({"KeyWord"} if search else set())
    data = {}
    for key, expression in entries:
        if key not in allowed or key in data:
            raise PipelineError('Viettel đổi contract widget')
        expression = expression.strip()
        if key == 'CurrentPage':
            data[key] = '1'
        elif key == 'SpecOrder' and expression == 'SpecOrder':
            data[key] = 'SearchResult' if search else 'DangHot'  # Giá trị mặc định được công bố ngay trong GenProductList.
        elif search and key == 'isHot' and expression == 'HotId':
            data[key] = ''
        elif re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', expression):
            assignments = re.findall(r'\bvar\s+' + re.escape(expression) + r'\s*=\s*([^;\n\r]+);', declarations)
            if len(assignments) != 1:
                raise PipelineError('Viettel: tham số widget không xác định duy nhất')
            data[key] = literal(assignments[0])
        else:
            data[key] = literal(expression)
    if set(data) != allowed or not re.fullmatch(r'ProductList[A-Za-z0-9_-]+', data['path']):
        raise PipelineError('Viettel: widget không thuộc danh mục sản phẩm đã hỗ trợ')
    if not re.fullmatch(r'\d*' if search else r'\d+', data['CatID']) or not re.fullmatch(r'\d+(?:,\d+)*', data['ManID']):
        raise PipelineError('Viettel: thiếu mã danh mục hoặc hãng')
    if not data['PageSize'].isdigit() or not 1 <= int(data['PageSize']) <= 100:
        raise PipelineError('Viettel: PageSize không hợp lệ')
    if search and (data['KeyWord'] != parse_qs(urlsplit(seed).query).get('keyword', [None])[0] or not data['KeyWord']):
        raise PipelineError('Viettel: từ khóa widget không khớp URL nguồn')
    return data


class ProductCards(HTMLParser):
    """Chỉ đọc <a data-id data-name> nằm trong product-item, bỏ menu/script/bài viết."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.cards = [], []
        self.card_depth, self.card = None, None
        self.total = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'input' and attrs.get('id') == 'RecordCountSP':
            value = attrs.get('value', '')
            if not value.isdigit():
                raise PipelineError('Viettel: tổng số sản phẩm không hợp lệ')
            self.total = int(value)
        if tag not in VOID:
            self.stack.append(tag)
        if 'product-item' in attrs.get('class', '').split():
            if self.card_depth is not None:
                raise PipelineError('Viettel: product card lồng nhau, cần kiểm tra HTML')
            self.card_depth = len(self.stack)
            self.card = None
        if tag == 'a' and self.card_depth is not None and attrs.get('data-id') and attrs.get('data-name'):
            card = {'id':attrs['data-id'], 'href':attrs.get('href',''),
                    'name':attrs['data-name'].strip(), 'brand':attrs.get('data-brand','')}
            if self.card and card != self.card:
                raise PipelineError('Viettel: một card chứa nhiều sản phẩm khác nhau')
            self.card = card

    def handle_endtag(self, tag):
        positions = [i for i, entry in enumerate(self.stack) if entry == tag]
        if not positions:
            return
        position = positions[-1]
        if self.card_depth is not None and position < self.card_depth:
            if not self.card or not self.card['href']:
                raise PipelineError('Viettel: product card thiếu link/tên')
            self.cards.append(self.card)
            self.card_depth, self.card = None, None
        self.stack = self.stack[:position]


class QuoteCards(ProductCards):
    """Giá bán và CTKM tóm tắt đúng trong card; không trừ ưu đãi có điều kiện."""
    def __init__(self):
        super().__init__()
        self.fields, self.capture = {}, []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        super().handle_starttag(tag, attrs)
        if 'product-item' in attributes.get('class', '').split():
            self.fields, self.capture = {}, []
        if self.card_depth is not None:
            for field in ('price', 'price-old', 'promotion-text'):
                if field in attributes.get('class', '').split():
                    if field in self.fields:
                        raise PipelineError('Viettel: nhiều vùng giá/CTKM trong một card')
                    self.fields[field] = []
                    self.capture.append((field, len(self.stack)))

    def handle_data(self, data):
        for field, depth in self.capture:
            self.fields[field].append(data)

    def handle_endtag(self, tag):
        positions = [i for i, entry in enumerate(self.stack) if entry == tag]
        if positions:
            position = positions[-1]
            if self.card_depth is not None and position < self.card_depth and self.card:
                fields = {key: ' '.join(''.join(value).split()) for key,value in self.fields.items()}
                price = fields.get('price', '')
                original = fields.get('price-old', '')
                # Không có giá rõ ràng thì giữ review, không biến thành giá 0.
                try:
                    sale = vnd(price)
                    old = vnd(original) if original else None
                    if old is not None and old < sale:
                        raise PipelineError('Giá gốc nhỏ hơn giá bán')
                    error = ''
                except PipelineError as exc:
                    sale, old, error = None, None, str(exc)
                self.card.update(promo_price=sale, original_price=old,
                                 promo_text=fields.get('promotion-text',''),
                                 price_error=error, promotion_complete=False)
            self.capture = [(field,depth) for field,depth in self.capture if position >= depth]
        super().handle_endtag(tag)


def parse_cards(markup, quotes=False):
    parser = QuoteCards() if quotes else ProductCards()
    parser.feed(markup)
    parser.close()
    if parser.card_depth is not None:
        raise PipelineError('Viettel: HTML product card chưa hoàn chỉnh')
    if parser.total is None:
        raise PipelineError('Viettel: phản hồi thiếu RecordCountSP; không coi là catalog rỗng')
    return parser.cards, parser.total


async def response_ok(client, method, url, **kwargs):
    # Endpoint POST này chỉ đọc HTML danh mục; retry tối đa một lần cho lỗi máy chủ.
    for attempt in range(2):
        response = await client.request(method, url, **kwargs)
        if response.status_code in (502,503,504) and attempt == 0:
            await asyncio.sleep(2)
            continue
        if response.status_code != 200:
            raise PipelineError(f'Viettel: HTTP {response.status_code} trên nguồn HTTP công khai')
        validate_url('Viettel Store', str(response.url))
        if 'text/html' not in response.headers.get('content-type','').lower():
            raise PipelineError('Viettel: nguồn không trả HTML danh mục')
        if len(response.content) > 5_000_000:
            raise PipelineError('Viettel: HTML vượt giới hạn an toàn')
        return response


async def listing_links(source, client, *, quotes=False):
    if source['chain_name'] != 'Viettel Store':
        raise PipelineError('Adapter Viettel không dùng cho đại lý khác')
    found = {}
    for seed in source['seeds']:
        validate_url('Viettel Store', seed)
        await robots_allowed(client, 'Viettel Store', seed)
        page = await response_ok(client, 'GET', seed)
        parameters = catalog_request(page.text, seed)
        endpoint = urljoin(str(page.url), ENDPOINT)
        await robots_allowed(client, 'Viettel Store', endpoint)
        seen_ids, expected_total = set(), None
        for page_number in range(1, source.get('max_pages',10)+1):
            response = await response_ok(client, 'POST', endpoint,
                                         data={**parameters, 'CurrentPage':str(page_number)})
            cards, total = parse_cards(response.text, quotes=quotes)
            if total > source.get('max_candidates',500):
                raise PipelineError('Viettel: catalog vượt max_candidates; không cắt bớt âm thầm')
            if expected_total is not None and total != expected_total:
                raise PipelineError('Viettel: catalog thay đổi trong khi phân trang, cần chạy lại')
            expected_total = total
            for card in cards:
                if card['id'] in seen_ids:
                    raise PipelineError('Viettel: endpoint lặp sản phẩm giữa các trang')
                if parameters['ManID'] != '0' and card['brand'] not in parameters['ManID'].split(','):
                    raise PipelineError('Viettel: sản phẩm trả về không khớp hãng của danh mục')
                url = clean_url('Viettel Store', seed, card['href'])
                if not re.search(source['product_url_pattern'],url) or url in source.get('excluded_urls',[]):
                    raise PipelineError('Viettel: URL trong product card không khớp contract')
                if url in found and (found[url]['name'] if quotes else found[url]) != card['name']:
                    raise PipelineError('Viettel: URL sản phẩm trùng nhưng tên khác')
                seen_ids.add(card['id'])
                found[url] = {**card, 'source_url': url} if quotes else card['name']
            if len(seen_ids) == total:
                break
            if len(seen_ids) > total or not cards or len(cards) < int(parameters['PageSize']):
                raise PipelineError('Viettel: phân trang thiếu/sai sản phẩm so với RecordCountSP')
            if page_number == source.get('max_pages',10):
                raise PipelineError('Viettel: max_pages chưa đủ để đọc hết catalog')
            await asyncio.sleep(2)
    return found
