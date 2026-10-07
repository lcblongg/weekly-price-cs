"""Chạy script Python với file .env; không source shell, không in khóa ra log."""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def read_environment(path):
    values = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        key, separator, value = line.partition('=')
        key = key.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError(f'Dòng {number} trong file cấu hình không hợp lệ')
        try:
            # Giữ $ và # như ký tự thông thường; không chạy lệnh hoặc nội suy biến.
            parts = shlex.split(value.strip(), comments=False)
        except ValueError:
            raise ValueError(f'Giá trị {key} cần kiểm tra dấu nháy') from None
        if len(parts) > 1:
            raise ValueError(f'Giá trị {key} có khoảng trắng; cần đặt trong dấu nháy')
        values[key] = parts[0] if parts else ''
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', required=True)
    parser.add_argument('script')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        config = read_environment(args.env_file)
    except (OSError, ValueError) as exc:
        parser.exit(2, f'Không đọc được cấu hình: {exc}\n')
    return subprocess.run([sys.executable, args.script, *args.arguments],
                          env={**os.environ, **config}).returncode


if __name__ == '__main__':
    sys.exit(main())
