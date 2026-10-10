#!/bin/zsh
cd "$(dirname "$0")"
[ -d Data ] && cd Data
if [ ! -x .venv/bin/python ]; then
  echo "Chưa tìm thấy Data/.venv."
  read "?Bấm Enter để đóng…"
  exit 1
fi
caffeinate -i .venv/bin/python tools/env_runner.py --env-file .env tools/run_data.py "$@"
code=$?
echo
if [ $code -eq 0 ]; then
  echo "Đã hoàn tất. Xem web: https://weekly-price-cs-ochre.vercel.app"
elif [ $code -eq 2 ]; then
  echo "Cập nhật một phần; xem lỗi từng kênh phía trên."
else
  echo "Chưa hoàn tất; xem thông báo phía trên."
fi
read "?Bấm Enter để đóng…"
exit $code
