"""Định danh sản phẩm cho mọi nhóm hàng trong Excel.

Hai tầng tách biệt:
- `sku`: khóa lịch sử giá = mã đại lý + mã biến thể gốc của nguồn (màu/dung lượng đã chọn).
  Không phụ thuộc phân tích tên, nên không thể gộp nhầm hai biến thể khác nhau.
- `model_name`/`storage`: nhãn để lọc và đối chiếu giữa các chuỗi. Chỉ nhận khi tên khớp mẫu rõ ràng;
  không khớp thì để None ("Chưa phân loại"), không đoán.
"""
import re
import unicodedata

from common import PipelineError

class OutOfScope(PipelineError):
    """Sản phẩm nằm trong trang danh mục nhưng không thuộc phạm vi theo dõi (hàng cũ, phụ kiện, máy bàn...)."""


CHAIN_CODES = {'TGDD': 'tgdd', 'CellphoneS': 'cps', 'FPT Shop': 'fpt', 'Viettel Store': 'vt', 'Phong Vũ': 'pv'}
CATEGORIES = {'điện thoại': 'Điện thoại', 'máy tính bảng': 'Máy tính bảng', 'máy tính xách tay': 'Máy tính xách tay',
              'đồng hồ thông minh': 'Đồng hồ thông minh', 'airpods': 'AirPods'}
# Không theo dõi hàng cũ/trưng bày/khác thị trường: giá không so sánh được với máy mới chính hãng.
NOT_NEW = re.compile(r'(?<![a-zà-ỹ])(cũ|đã kích hoạt|đã qua sử dụng|like\s*new|refurbished|renew|trưng bày|'
                     r'xách tay|quốc tế|lock|99%|98%|open\s*box|demo)(?![a-zà-ỹ])', re.I)
NOISE = re.compile(r'\b(điện thoại|máy tính bảng|máy tính xách tay|laptop|đồng hồ thông minh|đồng hồ|'
                   r'tai nghe(?: bluetooth| không dây| chụp tai| true wireless| chống ồn)*|chính hãng(?: apple việt nam| vn/a)?|'
                   r'vn/a|wifi|wi-fi)\b', re.I)


def chain_sku(chain, variant_id):
    code = CHAIN_CODES[chain]
    value = re.sub(r'[^a-z0-9]+', '-', str(variant_id).lower()).strip('-')
    if not value or len(value) > 80:
        raise PipelineError('Thiếu mã biến thể gốc của nguồn; không thể khóa SKU')
    return f'{code}-{value}'


def category_name(value):
    key = ' '.join(str(value).split()).casefold()
    if key not in CATEGORIES:
        raise PipelineError(f'Danh mục ngoài phạm vi: {value}')
    return CATEGORIES[key]


def _clean(name):
    text = unicodedata.normalize('NFC', ' '.join(str(name).split()))
    text = re.sub(r'[|·]', ' ', text)
    return ' '.join(text.split())


def _title(words):
    keep = {'ipad', 'iphone', 'macbook', 'airpods', 'fe', 'se', 'gt', 'lte', 'gps', 'ai', 'oled', 'tuf', 'rog', 'xps', 'loq', 'omen'}
    out = []
    for word in words.split():
        low = word.lower()
        if low in ('ipad', 'iphone', 'macbook', 'airpods'):
            out.append({'ipad': 'iPad', 'iphone': 'iPhone', 'macbook': 'MacBook', 'airpods': 'AirPods'}[low])
        elif low in keep:
            out.append(low.upper())
        elif re.fullmatch(r'[a-z]\d+[a-z]*', low) or re.fullmatch(r'\d+[a-z]+', low):
            out.append(low.upper() if len(low) <= 5 else low.capitalize())
        else:
            out.append(word[:1].upper() + word[1:].lower())
    return ' '.join(out)


def storage_of(text):
    """Dung lượng lưu trữ (ROM/SSD) nếu tên ghi rõ; RAM nhỏ hơn bị bỏ qua."""
    t = text.replace('+', ' ').replace('/', ' ')
    values = []
    for number, unit in re.findall(r'(?<![\d.])(\d{1,4})\s*(GB|G|TB|T)\b', t, re.I):
        n = int(number)
        gb = n * 1024 if unit.upper().startswith('T') else n
        if unit.upper() in ('G', 'T') and not re.search(r'\d\s*(G|T)\s*[+/)]|\(\s*\d+\s*G', text, re.I):
            continue
        values.append(gb)
    big = [v for v in values if v >= 32]
    if not big:
        return None
    gb = max(big)
    return f'{gb // 1024}TB' if gb >= 1024 and gb % 1024 == 0 else f'{gb}GB'


PATTERNS = [
    # Điện thoại
    ('iPhone', r'\biphone\s+(\d{1,2}e?|air|se)(?:\s+(pro\s+max|pro|plus|mini))?\b'),
    ('Samsung', r'\bgalaxy\s+(z\s*(?:fold|flip)\s*\d+(?:\s*(?:fe|ultra|special edition))?|z\s*tri\s*fold|'
                r'[asm]\d{2,3}[a-z]?(?:\s*(?:fe|ultra|plus|edge|\+))?|s\d{2}(?:\s*(?:fe|ultra|plus|edge|\+))?|xcover\s*\d+(?:\s*pro)?)\b'),
    ('Xiaomi', r'\b(xiaomi\s+\d{2}[a-z]?(?:\s*(?:t\s*pro|t|pro|ultra|lite))?|redmi\s+(?:note\s+)?\d{1,2}[a-z]?(?:\s*(?:pro\s*\+|pro\+|pro|plus|s|c|x|r))?|'
               r'poco\s+[a-z]\d+[a-z]?(?:\s*(?:pro|ultra|gt))?)\b'),
    ('OPPO', r'\b(reno\s*\d{1,2}(?:\s*(?:f|pro\s*\+|pro|z|5g))?|find\s+[nx]\d+(?:\s*(?:pro|ultra|flip|fold))?|a\d{1,2}[a-z]?(?:\s*(?:pro|s|x|k))?)\b'),
]
TABLET = [
    ('iPad', r'\bipad\s*(pro|air|mini)?\b'),
    ('Samsung', r'\bgalaxy\s+tab\s+([as]\d{1,2}(?:\s*(?:fe|ultra|plus|lite|\+))*)'),
    ('Xiaomi', r'\b(xiaomi\s+pad\s+\d+[a-z]?(?:\s*(?:s\s*pro|pro|mini))?|redmi\s+pad\s*(?:\d+|se|pro)?(?:\s*(?:pro|se|8\.7))*)'),
    ('OPPO', r'\boppo\s+pad\s*(\d+|air\s*\d*|neo|se|mini)?'),
]
WATCH = [
    ('Apple Watch', r'\bapple\s+watch\s+(series\s*\d+|se\s*\d*|ultra\s*\d*)'),
    ('Galaxy Watch', r'\bgalaxy\s+watch\s*(ultra\s*\d(?!\d)|ultra|fe|\d+)?(?:\s*(classic|pro))?'),
    ('Xiaomi', r'\b((?:xiaomi|redmi)\s+(?:smart\s+)?(?:watch|band)\s*[\w.]*(?:\s*(?:pro|active|lite|nfc))?)'),
    ('Huawei', r'\bhuawei\s+((?:watch\s+(?:gt\s*\d+|fit\s*\d*|ultimate|d\d|\d+)(?:\s*(?:pro|new|se|mini))?)|band\s*\d+(?:\s*pro)?)'),
    ('Garmin', r'\bgarmin\s+((?:forerunner|venu|fenix|vivoactive|instinct|epix|enduro|lily|vivomove|approach|bounce|vivofit)\s*[\w]*(?:\s*(?:pro|plus|solar|sapphire|x|s|2))?)'),
]
AIRPODS = r'\bairpods\s*(pro\s*\d(?!\d)|pro|max\s*\d(?!\d)|max|\d(?!\d))?'


def _laptop(text, brand):
    low = text.lower()
    mac = re.search(r'\bmacbook\s+(air|pro)\b', low)
    if mac:
        size = re.search(r'\b(1[3-6](?:\.\d)?)\s*(?:inch|in|")', low) or re.search(r'macbook\s+(?:air|pro)\s+(1[3-6])\b', low)
        chip = re.search(r'\b(m\d)(?:\s*(pro|max))?\b', low)
        parts = ['MacBook', mac[1].title()]
        if size: parts.append(size[1])
        if chip: parts.append(chip[1].upper() + (' ' + chip[2].title() if chip[2] else ''))
        return ' '.join(parts)
    series = re.search(r'\b(vivobook(?:\s+(?:go|pro|s|flip))?\s*\d{0,2}|zenbook(?:\s+(?:duo|s|a))?\s*\d{0,2}|expertbook\s*\w*|'
                       r'tuf\s+gaming\s*\w*|rog\s+\w+(?:\s+\w+)?|inspiron\s*\d{0,4}|vostro\s*\d{0,4}|latitude\s*\d{0,4}|xps\s*\d{0,2}|'
                       r'alienware\s*\w*|dell\s+(?:pro|plus)\s*\w*|pavilion\s*(?:x360|plus|aero)?\s*\d{0,2}|victus\s*\d{0,2}|envy\s*(?:x360)?\s*\d{0,2}|'
                       r'probook\s*\d{0,4}|elitebook\s*\d{0,4}|omnibook\s*\w*|omen\s*\w*|hp\s+(?:14|15|240|250|245|255)\w*|'
                       r'ideapad\s*(?:slim|gaming|pro|flex)?\s*\d{0,2}|thinkpad\s*\w*|thinkbook\s*\d{0,2}\w*|legion\s*\w*(?:\s*\d)?|'
                       r'yoga\s*(?:slim|pro)?\s*\d{0,2}\w*|loq\s*\d{0,2}\w*)\b', low)
    if not series:
        return None
    label = _title(series[1])
    brands = {'asus': 'Asus', 'dell': 'Dell', 'hp': 'HP', 'lenovo': 'Lenovo', 'acer': 'Acer', 'msi': 'MSI'}
    named = re.search(r'\b(asus|dell|hp|lenovo|acer|msi)\b', text)
    prefix = brands.get(brand.lower(), '') or (brands[named[1]] if named else '')
    if prefix and not label.lower().startswith(prefix.lower()):
        label = prefix + ' ' + label
    return label.replace('Hp ', 'HP ')


def describe(name, category, brand=''):
    """Nhãn lọc bảo thủ. Lỗi → PipelineError (ngoài phạm vi hàng mới), không khớp mẫu → model_name None."""
    text = _clean(name)
    if NOT_NEW.search(text):
        raise OutOfScope('Hàng cũ/trưng bày/khác thị trường: ngoài phạm vi so sánh hàng mới')
    cat = category_name(category)
    low = NOISE.sub(' ', text).lower()
    low = ' '.join(low.split())
    model = None
    if cat == 'Điện thoại':
        for family, pattern in PATTERNS:
            found = list(re.finditer(pattern, low))
            if len(found) == 1:
                if family == 'iPhone':
                    model = 'iPhone ' + found[0][1].replace('air', 'Air').replace('se', 'SE') + (' ' + found[0][2].title() if found[0][2] else '')
                elif family == 'Samsung':
                    model = 'Galaxy ' + _title(found[0][1].replace('+', ' Plus'))
                else:
                    model = _title(found[0][1].replace('+', ' Plus'))
                    if family == 'OPPO' and not model.lower().startswith(('reno', 'find', 'a')):
                        model = None
                    elif family == 'OPPO':
                        model = 'OPPO ' + model
                break
    elif cat == 'Máy tính bảng':
        for family, pattern in TABLET:
            found = re.search(pattern, low)
            if found:
                if family == 'iPad':
                    tier = (found[1] or '').title()
                    chip = re.search(r'\b(m\d|a\d{2}(?:\s*pro)?)\b', low)
                    size = re.search(r'\b(1[0-3](?:\.\d)?|8\.3|7\.9)\s*(?:inch|in|")', low)
                    gen = re.search(r'\b(?:gen\s*(\d+)|(\d+)(?:th)?\s*gen)', low)
                    parts = ['iPad'] + ([tier] if tier else [])
                    if size: parts.append(size[1])
                    if chip: parts.append(chip[1].upper())
                    elif gen: parts.append('Gen ' + (gen[1] or gen[2]))
                    net = re.search(r'\b(5g|cellular|lte)\b', low)
                    parts.append('5G' if net else 'WiFi')
                    model = ' '.join(parts)
                elif family == 'Samsung':
                    model = 'Galaxy Tab ' + _title(found[1].replace('+', ' Plus'))
                elif family == 'OPPO':
                    model = 'OPPO Pad' + (' ' + _title(found[1]) if found[1] else '')
                else:
                    model = _title(found[1])
                break
    elif cat == 'Máy tính xách tay':
        if re.search(r'\b(mac\s*mini|mac\s*studio|imac|mac\s*pro|màn hình|studio display)\b', low) and 'macbook' not in low:
            raise OutOfScope('Máy bàn/màn hình Mac: ngoài phạm vi máy tính xách tay')
        model = _laptop(low, brand)
    elif cat == 'Đồng hồ thông minh':
        for family, pattern in WATCH:
            found = re.search(pattern, low)
            if found:
                if family in ('Apple Watch', 'Galaxy Watch'):
                    extra = re.sub(r'(ultra)(\d)', r'\1 \2', ' '.join(x for x in found.groups() if x))
                    model = family + (' ' + _title(extra) if extra else '')
                    size = re.search(r'\b(\d{2})\s*mm\b', low)
                    if size: model += f' {size[1]}mm'
                    if re.search(r'\b(lte|cellular|esim|4g)\b', low): model += ' LTE'
                    elif family == 'Apple Watch' and re.search(r'\bgps\b', low): model += ' GPS'
                elif family == 'Garmin':
                    model = 'Garmin ' + _title(found[1])
                elif family == 'Huawei':
                    model = 'Huawei ' + _title(found[1])
                else:
                    model = _title(found[1])
                break
    elif cat == 'AirPods':
        found = re.search(AIRPODS, low)
        if not found:
            raise OutOfScope('Không phải AirPods (phụ kiện/tai nghe khác): ngoài phạm vi nguồn AirPods')
        model = 'AirPods' + (' ' + _title(found[1]) if found[1] else '')
        if re.search(r'chống ồn|anc', low) and 'pro' not in model.lower() and 'max' not in model.lower():
            model += ' ANC'
    storage = storage_of(text) if cat in ('Điện thoại', 'Máy tính bảng', 'Máy tính xách tay') else None
    from product_standard import canonical_model
    model=canonical_model(text) or model
    return {'category': cat, 'brand': brand, 'model_name': model, 'storage': storage}
