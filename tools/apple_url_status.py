"""Trạng thái hiện tại của mọi URL nhập tay (đọc cấu hình đã lưu + artifacts/apple-url-checks.json). Chỉ đọc."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import apple_sources  # noqa: E402
from apple_preferences import load  # noqa: E402
from apple_rules import URL_CHANNELS, manual_urls  # noqa: E402

checks = apple_sources.load_checks()
out = {}
for rule in load()['products']:
    for channel in URL_CHANNELS:
        for url in manual_urls(rule, channel):
            entry = apple_sources.status_for(rule, channel, url, checks)
            out.setdefault(rule['model'], []).append({'channel': channel, 'url': url, 'status': entry['status'],
                                                     'label': apple_sources.LABELS[entry['status']], 'detail': entry.get('detail', ''),
                                                     'checked_at': entry.get('checked_at'), 'source': entry.get('source')})
print(json.dumps({'ok': True, 'statuses': out}, ensure_ascii=False))
