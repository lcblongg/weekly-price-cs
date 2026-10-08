#!/bin/zsh
# Bot 1: thu thập link Apple 5 kênh từ inputs/data.xlsx → outputs/Tong hop link.xlsx (không ghi web, không gửi Telegram).
cd "$(dirname "$0")"
[ -d Data ] && cd Data  # mã nguồn + dữ liệu nằm trong thư mục con Data
.venv/bin/python -m playwright install chromium >/dev/null 2>&1
.venv/bin/python tools/env_runner.py --env-file .env tools/thu_thap_link.py
code=$?
[ -f "outputs/Tong hop link.xlsx" ] && open "outputs/Tong hop link.xlsx"
[ -f "inputs/chon-link.xlsx" ] && open "inputs/chon-link.xlsx"
echo; [ $code -eq 0 ] && echo "XONG. Chép Model / Màu / Link cần lấy sang inputs/chon-link.xlsx rồi bấm 'Lay gia.command'." || echo "Có lỗi (mã $code) — xem thông báo phía trên."
read "?Bấm Enter để đóng…"
