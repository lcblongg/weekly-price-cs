"""Nguồn URL nhập tay cho các worker chọn màu Apple và trạng thái kiểm tra từng URL.

URL nhập tay chỉ là nguồn đầu vào. Worker vẫn đọc trang, xác minh đúng model chuẩn (apple_rules/product_standard)
và đúng biến thể màu trước khi công bố giá. Không có URL nào tự sinh giá hay trạng thái.

Trạng thái một URL: unchecked | valid | wrong_model | color_not_found | access_error | invalid_url.
"""
import fcntl
import json
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from apple_rules import URL_CHANNELS, key, manual_urls
from common import PipelineError, TZ

ROOT = Path(__file__).parent
CHECKS = Path(os.environ.get('WPCS_URL_CHECKS') or ROOT / 'artifacts/apple-url-checks.json')
STATUSES = ('unchecked', 'valid', 'wrong_model', 'color_not_found', 'access_error', 'invalid_url')
LABELS = {'unchecked': 'Chưa kiểm tra', 'valid': 'Hợp lệ', 'wrong_model': 'Sai model',
          'color_not_found': 'Chưa tìm thấy màu', 'access_error': 'Lỗi truy cập', 'invalid_url': 'URL không hợp lệ'}


class WrongModel(PipelineError):
    pass


class ColorNotFound(PipelineError):
    pass


def classify(exc):
    """Phân loại lỗi khi đọc một URL nhập tay. Không rõ nguyên nhân → lỗi truy cập (không bao giờ là hợp lệ)."""
    if isinstance(exc, WrongModel):
        return 'wrong_model'
    if isinstance(exc, ColorNotFound):
        return 'color_not_found'
    text = str(exc)
    if re.search(r'model (?:trên trang|con/cha) (?:khác|không đúng)|không đúng model|sai model', text, re.I):
        return 'wrong_model'
    if re.search(r'chưa xác minh được (?:một lựa chọn )?màu|màu yêu cầu', text, re.I):
        return 'color_not_found'
    return 'access_error'


def check_key(model, channel, url):
    return f'{key(model)}|{channel}|{url}'


def load_checks():
    return json.loads(CHECKS.read_text(encoding='utf-8')) if CHECKS.exists() else {}


def record(model, channel, url, status, detail, color, source):
    """Ghi trạng thái một URL (trang kiểm tra hoặc worker). Khóa file để hai tiến trình không ghi đè nhau."""
    if status not in STATUSES:
        raise ValueError(status)
    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    lock = open(str(CHECKS) + '.lock', 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        data = load_checks()
        data[check_key(model, channel, url)] = {
            'model': model, 'channel': channel, 'url': url, 'status': status, 'detail': detail,
            'color': color, 'checked_at': datetime.now(TZ).isoformat(timespec='seconds'), 'source': source}
        temporary = Path(f'{CHECKS}.{os.getpid()}.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        temporary.replace(CHECKS)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def status_for(rule, channel, url, checks=None):
    """Trạng thái hiển thị: kết quả cũ chỉ còn hiệu lực nếu cùng model và cùng màu yêu cầu."""
    entry = (checks if checks is not None else load_checks()).get(check_key(rule['model'], channel, url))
    if not entry or key(entry.get('color')) != key(rule.get('color')):
        return {'status': 'unchecked', 'detail': 'Chưa kiểm tra với cấu hình hiện tại'}
    return entry


def manual_records(rule, channel):
    """URL nhập tay ở dạng bản ghi catalog để worker dùng chung luồng xác minh với link discovery."""
    return [{'source_url': url, 'status': 'manual', 'reason': '',
             'config': {'url': url, 'brand': 'Apple', 'category': '', 'manual': True}} for url in manual_urls(rule, channel)]


# ---------- CellphoneS: URL → mã sản phẩm cha/con thật ----------

def cps_child_ids(markup):
    """Mã màu con nằm trong khối chọn màu (list-variants); bỏ qua sản phẩm liên quan ở phần khác của trang."""
    block = re.search(r'class="list-variants"(.*?)</ul>', markup, re.S)
    if not block:
        raise PipelineError('CPS: trang không có khối chọn màu/mã sản phẩm')
    ids = list(dict.fromkeys(re.findall(r'data-product-id="(\d+)"', block[1])))
    if not ids:
        raise PipelineError('CPS: không đọc được mã sản phẩm trên trang')
    return ids


async def cps_resolve(http, url):
    """Từ URL nhập tay: đọc mã con trên trang → tra GraphQL lấy parent_id → kiểm tra cha có đúng đường dẫn URL.
    Trả về (parent, {child_id: child}). URL không bao giờ được coi là SKU."""
    from adapters import cellphones as cps
    from http_policy import fetch
    path = urlsplit(url).path.lstrip('/')
    response = await fetch(http, 'GET', url, label='CPS URL nhập tay')
    ids = cps_child_ids(response.text)
    requested = parse_qs(urlsplit(url).query).get('product_id', [None])[0]
    if requested and requested not in ids:
        raise PipelineError(f'CPS: product_id={requested} trong URL không thuộc danh sách màu của trang')
    children = await cps.products_by_id(http, ids)
    parent_ids = {str((c['filterable'] or {}).get('parent_id') or c['general']['product_id']) for c in children.values() if c}
    if len(parent_ids) != 1:
        raise PipelineError('CPS: các mã màu trên trang không cùng một sản phẩm cha')
    parent_id = parent_ids.pop()
    found = await cps.graphql(http, f'''query{{products(filter:{{static:{{province_id:{cps.PROVINCE},product_id:{json.dumps([parent_id])},stock:{{from:0}}}}}},size:1){{general{{product_id name url_path child_product}} filterable{{is_parent parent_id price special_price stock}}}}}}''')
    parent = next((p for p in found.get('products') or [] if str(p['general']['product_id']) == parent_id), None)
    if not parent:
        raise PipelineError('CPS: không tra được sản phẩm cha từ GraphQL')
    if str(parent['general'].get('url_path', '')).lstrip('/') != path:
        raise PipelineError('CPS: URL không khớp đường dẫn của sản phẩm cha tra được; không dùng')
    listed = {str(i) for i in (parent['general'].get('child_product') or [parent_id])}
    if not set(ids) <= listed | {parent_id}:
        raise PipelineError('CPS: mã màu trên trang không thuộc sản phẩm cha')
    missing = [i for i in listed if i not in children]
    if missing:
        children.update(await cps.products_by_id(http, missing))
    return parent, {i: children.get(i) for i in listed}
