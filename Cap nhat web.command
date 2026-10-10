#!/bin/zsh
# Cào trên máy này, tự ghi Supabase để web nhận giá mới. Không gửi Telegram.
cd "$(dirname "$0")"
[ -d Data ] && cd Data
if [ ! -x .venv/bin/python ]; then
  echo "Chưa tìm thấy môi trường Python trong Data/.venv."
  read "?Bấm Enter để đóng…"
  exit 1
fi
.venv/bin/python -m playwright install chromium || exit 1
caffeinate -i .venv/bin/python tools/env_runner.py --env-file .env tools/update_web_local.py "$@"
code=$?
echo
if [ $code -eq 0 ]; then
  echo "Đã hoàn tất. Xem web: https://weekly-price-cs-ochre.vercel.app"
elif [ $code -eq 2 ]; then
  echo "Đã cập nhật một phần; có kênh/SKU cần kiểm tra. Xem kết quả phía trên."
else
  echo "Chưa hoàn tất; dữ liệu thành công trước đó vẫn được giữ. Xem thông báo phía trên."
fi
read "?Bấm Enter để đóng…"
exit $code
