"""Nguồn sự thật duy nhất cho quy chuẩn model Apple (Python bot, discovery và web cùng đọc).

- config/apple_colors.json: danh sách model người dùng quản lý (thứ tự hiển thị, màu, alias).
- config/apple_models.json: quy tắc nhận diện tên nguồn → model chuẩn. Quy tắc viết tay (curated) giữ nguyên;
  model thêm từ trang quản lý được sinh quy tắc literal và ghi hẳn vào file (generated=true), để TypeScript
  đọc đúng cùng quy tắc với Python thay vì mỗi bên tự suy diễn.
Mọi thay đổi đi qua `plan()`; cấu hình chỉ được ghi khi kiểm tra không có tên nào khớp 0 hoặc nhiều quy tắc.
"""
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).parent
# Biến môi trường chỉ dùng cho kiểm thử/chạy thử cô lập; mặc định là cấu hình thật của dự án.
COLORS = Path(os.environ.get('WPCS_APPLE_COLORS') or ROOT / 'config/apple_colors.json')
MODELS = Path(os.environ.get('WPCS_APPLE_MODELS') or ROOT / 'config/apple_models.json')
SUFFIXES = r'(?!\s+(?:pro|max|plus|mini|ultra|air|neo)\b)'


# URL sản phẩm nhập tay theo kênh: chỉ là NGUỒN ĐẦU VÀO; worker vẫn xác minh model/SKU/màu trước khi công bố giá.
URL_CHANNELS = {
    'tgdd': {'label': 'MW', 'hosts': ('www.thegioididong.com', 'thegioididong.com'),
             'path': r'/(?:dtdd|may-tinh-bang|laptop|dong-ho-thong-minh|tai-nghe)/[a-z0-9-]+', 'query': ('code',)},
    'cellphones': {'label': 'CPS', 'hosts': ('cellphones.com.vn',), 'path': r'/[a-z0-9-]+\.html', 'query': ('product_id',)},
    'fpt': {'label': 'FPT', 'hosts': ('fptshop.com.vn',), 'path': r'/[a-z0-9-]+/[a-z0-9-]+', 'query': ('sku',)},
    'viettel': {'label': 'Viettel', 'hosts': ('viettelstore.vn',), 'path': r'/[a-z0-9/-]*-pid\d+\.html', 'query': ()},
    'phongvu': {'label': 'Phong Vũ', 'hosts': ('phongvu.vn',), 'path': r'/[a-z0-9-]+--[sp]\d+', 'query': ('sku',)},
}
MAX_URLS_PER_CHANNEL = 20


def normalize_url(channel, url):
    """Chuẩn hóa một URL nhập tay; sai kênh/domain/định dạng → RuleError (không lưu)."""
    spec = URL_CHANNELS.get(channel)
    if spec is None:
        raise RuleError(f'Kênh không hợp lệ: {channel}')
    if not isinstance(url, str) or len(url) > 500:
        raise RuleError(f'{spec["label"]}: URL không hợp lệ')
    parts = urlsplit(url.strip())
    if parts.scheme != 'https' or parts.username or parts.password or parts.port:
        raise RuleError(f'{spec["label"]}: URL phải là https và không chứa thông tin đăng nhập ({url})')
    host = (parts.hostname or '').lower()
    if host not in spec['hosts']:
        raise RuleError(f'{spec["label"]}: URL phải thuộc {spec["hosts"][0]}, không nhận {host or "domain trống"}')
    path = parts.path.rstrip('/') or '/'
    if not re.fullmatch(spec['path'], path):
        raise RuleError(f'{spec["label"]}: đường dẫn không phải trang chi tiết sản phẩm ({path})')
    # Chỉ giữ tham số chọn biến thể của chính website; bỏ tracking/fragment.
    query = [(k, v) for k, v in parse_qsl(parts.query) if k in spec['query']]
    if any(not re.fullmatch(r'\d{1,20}', v) for _, v in query):
        raise RuleError(f'{spec["label"]}: mã biến thể trong URL phải là số')
    return urlunsplit(('https', spec['hosts'][0], path, urlencode(query), ''))


def _validate_urls(model, value):
    if value in (None, {}):
        return {}
    if not isinstance(value, dict):
        raise RuleError(f'URL của {model} không hợp lệ')
    clean = {}
    for channel, urls in value.items():
        if not isinstance(urls, list):
            raise RuleError(f'URL {channel} của {model} phải là danh sách')
        normalized = list(dict.fromkeys(normalize_url(channel, u) for u in urls if str(u).strip()))
        if len(normalized) > MAX_URLS_PER_CHANNEL:
            raise RuleError(f'{URL_CHANNELS[channel]["label"]}: tối đa {MAX_URLS_PER_CHANNEL} URL mỗi model')
        if normalized:
            clean[channel] = normalized
    return clean


class RuleError(ValueError):
    """Cấu hình không áp dụng được; thông điệp hiển thị nguyên văn cho người quản lý."""


def key(value):
    return ' '.join(unicodedata.normalize('NFC', str(value or '')).casefold().split())


def literal_pattern(model):
    """'iPhone 19' khớp 'Điện thoại iPhone 19 256GB' nhưng không khớp 'iPhone 19 Pro'/'iPhone 19e'."""
    words = model.split()
    if not words:
        raise RuleError('Tên model trống')
    return r'\b' + r'\s+'.join(re.escape(w) for w in words) + SUFFIXES + r'(?![\w])'


def _validate_products(products):
    if not isinstance(products, list) or len(products) > 200:
        raise RuleError('Danh sách model không hợp lệ')
    seen = set()
    clean = []
    for row in products:
        if not isinstance(row, dict) or not isinstance(row.get('model'), str):
            raise RuleError('Model không hợp lệ')
        model = ' '.join(unicodedata.normalize('NFC', row['model']).split())
        color = row.get('color')
        aliases = row.get('aliases', [])
        if not model or len(model) > 120:
            raise RuleError('Tên model trống hoặc quá dài')
        if color is not None and (not isinstance(color, str) or not color.strip() or len(color) > 120):
            raise RuleError(f'Màu của {model} không hợp lệ')
        if not isinstance(aliases, list) or len(aliases) > 30 or any(not isinstance(a, str) or not a.strip() for a in aliases):
            raise RuleError(f'Tên màu tương đương của {model} không hợp lệ')
        if key(model) in seen:
            raise RuleError(f'Model bị trùng: {model}')
        seen.add(key(model))
        color = color.strip() if color else None
        aliases = list(dict.fromkeys(a.strip() for a in aliases))
        if color and key(color) in {key(a) for a in aliases}:
            aliases = [a for a in aliases if key(a) != key(color)]
        row_clean = {'model': model, 'color': color, 'aliases': aliases}
        urls = _validate_urls(model, row.get('urls'))
        if urls:
            row_clean['urls'] = urls
        previous = row.get('previous_names') or []
        if not isinstance(previous, list) or any(not isinstance(p, str) for p in previous):
            raise RuleError(f'Tên cũ của {model} không hợp lệ')
        if previous:
            row_clean['previous_names'] = previous
        clean.append(row_clean)
    return clean


def validate_products(products):
    """Xác thực đầu vào Excel/API; chưa thay đổi quy tắc nhận diện model."""
    return _validate_products(products)


def plan(products, models_config, renames=(), current=()):
    """Trả về (colors_config, models_config) mới. Không ghi file.

    renames: [{'from': tên cũ, 'to': tên mới}] khi người dùng sửa tên một model đang có.
    - Quy tắc viết tay: giữ pattern (vẫn nhận đúng tên nguồn), chỉ đổi nhãn.
    - Quy tắc tự sinh: sinh lại theo tên mới (tên cũ có thể là lỗi gõ, không được tiếp tục khớp).
    """
    products = _validate_products(products)
    # Giữ lịch sử tên cũ từ cấu hình hiện tại (trang quản lý không gửi lại trường này).
    history = {p['model']: list(p.get('previous_names') or []) for p in current}
    for p in products:
        merged = list(dict.fromkeys(history.get(p['model'], []) + p.get('previous_names', [])))
        if merged:
            p['previous_names'] = merged
    entries = {}
    for entry in models_config.get('models', []):
        if entry['name'] in entries:
            raise RuleError(f'apple_models.json trùng model {entry["name"]}')
        entries[entry['name']] = dict(entry)
    for rename in renames or ():
        old, new = rename.get('from'), rename.get('to')
        if not isinstance(old, str) or not isinstance(new, str):
            raise RuleError('Thông tin đổi tên không hợp lệ')
        new = ' '.join(new.split())
        if old == new or old not in entries:
            continue
        entry = entries.pop(old)
        target = next((p for p in products if p['model'] == new), None)
        if entry.get('generated'):
            # Sinh lại từ tên mới: tập sản phẩm khớp có thể khác, bằng chứng màu cũ KHÔNG còn hiệu lực.
            if target:
                target.pop('previous_names', None)
            continue
        if new in entries:
            raise RuleError(f'Không thể đổi {old} thành {new}: {new} đã có quy tắc nhận diện riêng')
        entries[new] = {**entry, 'name': new}
        if target:
            # Quy tắc viết tay giữ nguyên pattern = cùng tập sản phẩm; bằng chứng xác minh theo tên cũ vẫn hợp lệ.
            target['previous_names'] = list(dict.fromkeys(history.get(old, []) + [old] + target.get('previous_names', [])))
    wanted = {p['model'] for p in products}
    for name in list(entries):
        # Quy tắc tự sinh của model đã xóa khỏi danh sách quản lý được bỏ; quy tắc viết tay luôn giữ.
        if entries[name].get('generated') and name not in wanted:
            del entries[name]
    for product in products:
        if product['model'] not in entries:
            entries[product['model']] = {'name': product['model'], 'pattern': literal_pattern(product['model']), 'generated': True}
    for p in products:
        names = [n for n in p.get('previous_names', []) if n != p['model']]
        if names:
            p['previous_names'] = names
        else:
            p.pop('previous_names', None)
    ordered = [entries[p['model']] for p in products] + [e for n, e in entries.items() if n not in wanted]
    check(ordered)
    return {'version': 1, 'products': products}, {'version': models_config.get('version', 1), 'models': ordered}


def check(entries):
    """Mỗi tên chuẩn phải được đúng một quy tắc nhận diện (chính nó). Bắt xung đột như
    'iPhone 19' khớp cả 'iPhone 19 Pro', hoặc hai model cùng tên viết khác hoa/thường."""
    compiled = []
    for entry in entries:
        try:
            compiled.append((entry['name'], re.compile(entry['pattern'], re.I)))
        except re.error:
            raise RuleError(f'Quy tắc nhận diện của {entry["name"]} không hợp lệ') from None
    for name, _ in compiled:
        hits = [other for other, pattern in compiled if pattern.search(name)]
        if hits != [name]:
            if not hits:
                raise RuleError(f'Tên {name} không khớp quy tắc của chính nó')
            raise RuleError(f'Tên {name} khớp nhiều quy tắc ({", ".join(hits)}); cần đặt tên rõ hơn')


def _atomic_write(path, data):
    temporary = Path(f'{path}.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return temporary


def apply(products, renames=(), colors_path=COLORS, models_path=MODELS):
    models_config = json.loads(Path(models_path).read_text(encoding='utf-8'))
    current = json.loads(Path(colors_path).read_text(encoding='utf-8')).get('products', []) if Path(colors_path).exists() else []
    colors, models = plan(products, models_config, renames, current)
    temporaries = [(_atomic_write(models_path, models), models_path), (_atomic_write(colors_path, colors), colors_path)]
    for temporary, target in temporaries:
        temporary.replace(target)
    return colors, models


def manual_urls(rule, channel):
    """URL nhập tay của một model ở một kênh (đã chuẩn hóa khi lưu)."""
    return list((rule.get('urls') or {}).get(channel, []))


def accepted_colors(rule, builtin=()):
    """Tên màu được chấp nhận: màu chuẩn + tên tương đương người dùng đã xác nhận + bảng tên đã đối chiếu của adapter."""
    if not rule.get('color'):
        return None
    return {key(rule['color']), *(key(a) for a in rule.get('aliases', [])), *(key(b) for b in builtin)}
