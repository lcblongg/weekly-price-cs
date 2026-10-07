"""Chuẩn hóa link và định danh bảo thủ: không suy đoán biến thể chưa rõ."""
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from common import PipelineError
from scraper import validate_url

TRACKERS = {'fbclid', 'gclid', 'itm', 'ref', 'source'}


def clean_url(chain, base, href):
    url = urljoin(base, href)
    validate_url(chain, url)
    parsed = urlparse(url)
    # Giữ query chọn biến thể; chỉ loại tham số tracking đã biết và fragment.
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in TRACKERS]
    return urlunparse(parsed._replace(query=urlencode(query), fragment=''))


def iphone_identity(name):
    """MVP iPhone mới. Không tự gán VN/A, màu hay tình trạng từ tên thiếu thông tin."""
    text = ' '.join(name.split())
    if re.search(r'cũ|đã dùng|like\s*new|refurbished|đổi bảo hành|trưng bày|99%|lock|quốc tế|xách tay', text, re.I):
        raise PipelineError('Hàng cũ/khác thị trường: cần kiểm tra')
    matches = list(re.finditer(r'\biphone\s+(\d{1,2}(?:e)?|air)(?:\s+(pro\s+max|pro|plus|mini))?\b', text, re.I))
    if len(matches) != 1:
        raise PipelineError('Chưa nhận diện chắc chắn một model iPhone')
    capacities = re.findall(r'\b(64|128|256|512|1|2)\s*(GB|TB)\b', text, re.I)
    if len(capacities) != 1:
        raise PipelineError('Thiếu hoặc có nhiều dung lượng')
    capacity, unit = capacities[0]
    if (unit.upper() == 'TB' and capacity not in {'1', '2'}) or (unit.upper() == 'GB' and capacity in {'1', '2'}):
        raise PipelineError('Dung lượng không hợp lệ')
    model = 'iPhone ' + matches[0][1].lower()
    if matches[0][2]:
        model += ' ' + matches[0][2].title()
    size = capacity + unit.upper()
    # Suffix thị trường/tình trạng do adapter nguồn đã nghiệm thu khai báo.
    sku = 'apple-' + re.sub(r'\s+', '-', model.lower()) + '-' + size.lower()
    return {'sku': sku, 'product_name': model + ' ' + size, 'verify_tokens': [model, size]}


def fetch_discovered(db, max_age_days=8, now=None, chain=None):
    """Catalog thành công mới nhất (của một kênh nếu có `chain`). Không dùng catalog quá cũ.
    Discovery lỗi không được công bố, nên bản mới nhất ở đây luôn là bản thành công trước đó."""
    query = db.table('discovery_runs').select('*')
    if chain:
        query = query.eq('chain_name', chain)
    runs = query.order('completed_at', desc=True).limit(1).execute().data
    if not runs:
        raise PipelineError(f'Chưa có catalog khám phá{" cho " + chain if chain else ""}; chạy bot Chủ nhật trước')
    run = runs[0]
    completed = datetime.fromisoformat(run['completed_at'].replace('Z', '+00:00'))
    now = now or datetime.now(timezone.utc)
    if completed > now + timedelta(minutes=5) or now - completed > timedelta(days=max_age_days):
        raise PipelineError('Catalog khám phá quá cũ hoặc timestamp bất thường')
    all_rows, offset = [], 0
    while True:
        batch = (db.table('discovered_products').select('*').eq('run_id', run['id'])
                 .order('chain_name').order('source_url').range(offset, offset + 499).execute().data)
        all_rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    if len(all_rows) != run['candidate_count']:
        raise PipelineError('Catalog khám phá thiếu dòng')
    ready = [row['config'] for row in all_rows if row['status'] == 'ready']
    if not ready or len(ready) != run['ready_count']:
        raise PipelineError('Chưa có link được kiểm chứng để cào giá; cấu hình adapter nguồn')
    # Danh mục có review phải được thể hiện rõ; không coi đó là sản phẩm có giá.
    review_rows = [{'chain_name': row['chain_name'], 'source_url': row['source_url'], 'reason': row['reason'],
                    'config': row['config']} for row in all_rows if row['status'] != 'ready']
    return ready, {'run_id': run['id'], 'total': len(all_rows), 'ready': len(ready),
                   'review': len(all_rows) - len(ready), 'completed_at': run['completed_at'],
                   'review_rows': review_rows}
