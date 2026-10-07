"""Danh sách kênh và tên gọi dùng ở CLI/GitHub Actions. Mỗi kênh là một worker độc lập."""
from common import PipelineError

CHAINS = {'tgdd': 'TGDD', 'cellphones': 'CellphoneS', 'viettel': 'Viettel Store',
          'fpt': 'FPT Shop', 'phongvu': 'Phong Vũ'}
ALIASES = {'mw': 'tgdd', 'mwg': 'tgdd', 'thegioididong': 'tgdd', 'cps': 'cellphones', 'vt': 'viettel',
           'viettelstore': 'viettel', 'fptshop': 'fpt', 'pv': 'phongvu'}
SLUGS = {name: slug for slug, name in CHAINS.items()}


def resolve(values):
    """['tgdd','cps'] / ['all'] / tên hiển thị → danh sách tên kênh, giữ thứ tự, không trùng."""
    if not values:
        raise PipelineError('Phải chọn ít nhất một kênh (--chain tgdd|cellphones|viettel|fpt|phongvu|all)')
    out = []
    for raw in values:
        for value in str(raw).split(','):
            key = value.strip()
            if not key:
                continue
            if key.lower() == 'all':
                names = list(CHAINS.values())
            elif key in SLUGS:
                names = [key]
            else:
                slug = ALIASES.get(key.lower(), key.lower())
                if slug not in CHAINS:
                    raise PipelineError(f'Kênh không hợp lệ: {key}')
                names = [CHAINS[slug]]
            out += [n for n in names if n not in out]
    if not out:
        raise PipelineError('Phải chọn ít nhất một kênh')
    return out


def slug(name):
    return SLUGS[name]
