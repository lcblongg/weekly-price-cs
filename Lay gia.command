#!/bin/zsh
# Bot 2: lấy giá đúng các link trong inputs/chon-link.xlsx → cập nhật web + gửi Telegram nhóm.
cd "$(dirname "$0")"
.venv/bin/python -m playwright install chromium >/dev/null 2>&1
.venv/bin/python tools/env_runner.py --env-file .env tools/lay_gia_link.py "$@"
code=$?
echo; [ $code -eq 0 ] && echo "XONG. Web đã cập nhật: https://weekly-price-cs-ochre.vercel.app" || echo "Có kênh lỗi hoặc dừng (mã $code) — xem thông báo phía trên; dữ liệu cũ được giữ."
read "?Bấm Enter để đóng…"
