"""Phạm vi hãng bot cào (config/scope.json). Excel giữ nguyên; bộ lọc áp dụng khi discovery và khi đọc catalog."""
import json
import os
from pathlib import Path

DEFAULT = Path(__file__).parent / 'config/scope.json'


def brands(path=None):
    """Tập hãng được cào (casefold). Rỗng = mọi hãng. WPCS_SCOPE=all: bỏ lọc (kiểm thử dữ liệu mẫu nhiều hãng)."""
    override = os.environ.get('WPCS_SCOPE')
    if path is None and override == 'all':
        return set()
    file = Path(path or override or DEFAULT)
    if not file.exists():
        return set()
    data = json.loads(file.read_text(encoding='utf-8'))
    if data.get('version') != 1 or not isinstance(data.get('brands'), list):
        raise ValueError('config/scope.json không hợp lệ')
    return {str(b).strip().casefold() for b in data['brands'] if str(b).strip()}


def in_scope(brand, allowed=None):
    allowed = brands() if allowed is None else allowed
    return not allowed or str(brand or '').strip().casefold() in allowed
