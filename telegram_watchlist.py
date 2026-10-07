"""Phạm vi Telegram nhóm độc lập với lựa chọn cá nhân trên Web. Không ảnh hưởng bot cào."""
import json
import unicodedata
from pathlib import Path
from common import PipelineError


def key(category, model):
    return tuple(' '.join(unicodedata.normalize('NFC', str(s)).strip().lower().split()) for s in (category, model))


def filter_report_rows(current, previous, config):
    if not config:
        return current, previous
    try:
        value = json.loads(Path(config).read_text(encoding='utf-8'))
        if value.get('version') != 1 or not isinstance(value.get('hidden_models'), list):
            raise ValueError()
        hidden = set()
        for item in value['hidden_models']:
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ('category', 'model_name')):
                raise ValueError()
            hidden.add(key(item['category'], item['model_name']))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise PipelineError('Cấu hình danh sách theo dõi Telegram nhóm không hợp lệ') from exc
    # Không đoán tên khi thiếu metadata: giữ sản phẩm để tránh bỏ nhầm.
    def watched(row):
        return key(row.get('category', ''), row.get('model_name') or '') not in hidden
    return [r for r in current if watched(r)], [r for r in previous if watched(r)]
