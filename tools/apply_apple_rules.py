"""Áp dụng danh sách model Apple từ trang quản lý (stdin JSON {products, renames}).
--check: chỉ kiểm tra, không ghi. Mặc định: ghi apple_colors.json + apple_models.json rồi dựng lại
trang nghiệm thu và dashboard. Không chạy bot, không gửi Telegram."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apple_rules import RuleError, apply, plan, MODELS  # noqa: E402


def main():
    try:
        payload = json.loads(sys.stdin.read() or '{}')
        products, renames = payload.get('products'), payload.get('renames') or []
        if '--check' in sys.argv:
            plan(products, json.loads(MODELS.read_text(encoding='utf-8')), renames)
            print(json.dumps({'ok': True}))
            return 0
        colors, models = apply(products, renames)
    except RuleError as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 2
    except (ValueError, TypeError, AttributeError):
        print(json.dumps({'ok': False, 'error': 'Dữ liệu gửi lên không hợp lệ'}, ensure_ascii=False))
        return 2
    failed = []
    for chain in ('tgdd', 'cellphones', 'fpt', 'viettel', 'phongvu'):
        result = subprocess.run([sys.executable, 'tools/build_mw_review.py', '--chain', chain], cwd=ROOT,
                                capture_output=True, text=True, timeout=120)
        if result.returncode:
            failed.append(chain)
    print(json.dumps({'ok': True, 'models': len(colors['products']),
                      'generated_rules': sum(1 for m in models['models'] if m.get('generated')),
                      'rebuild_failed': failed}, ensure_ascii=False))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
