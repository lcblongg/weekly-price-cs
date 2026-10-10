# Chạy bot 5 kênh từ một file trên Mac

File đầu vào: `../data.xlsx` (ở cạnh thư mục `Data`). Bấm **Chay bot.command** cùng thư mục để đọc link, xác minh và cập nhật Supabase/web. Không chụp ảnh, không cập nhật Numbers, không gửi Telegram và không chạy discovery.

Sheet đầu tiên có các cột `Tên sản phẩm`, `Màu`, `MW`, `CPS`, `FPT`, `Viettel`, `Phong Vũ`. Mẫu giữ danh sách tên/màu từ file Hoàng Hà; các cột link để trống cho người dùng nhập. Bot và file Hoàng Hà không thay đổi.

1. Điền link trang chi tiết đúng kênh vào từng cột. Chỉ nhận HTTPS, không nhận link danh mục hoặc link Hoàng Hà.
2. Nhiều dung lượng/cấu hình: xuống dòng giữa các URL trong một ô, hoặc thêm dòng cùng tên model/màu. Link trùng được loại bỏ, mã biến thể trong query được giữ. Tối đa 20 URL/model/kênh, 200 model.
3. Lưu rồi đóng file trước khi bấm nút chạy. File thay đổi trong lúc chờ sẽ khiến lượt dừng để tránh dùng nhầm bản.
4. Để cửa sổ Terminal mở và máy có mạng. `caffeinate` giữ máy thức trong lượt chạy. Nếu bot khác đang hoạt động, lượt mới chờ; không dừng bot cũ.
5. Đọc số SKU có giá, chỉ trạng thái và cần kiểm tra từng kênh. Web nhận dữ liệu mới qua Supabase; không cần deploy lại để cập nhật giá. Cache có thể cần khoảng 30 giây.

Ô URL trống không tạo giá và không khởi chạy kênh đó. Nếu toàn file chưa có URL, bot dừng trước khi thay đổi cấu hình/DB. Model không có link vẫn nằm trong quy chuẩn; dữ liệu đã có không bị xóa, thời điểm cũ vẫn giữ. Lỗi truy cập hoặc sai màu/model không được đổi thành hết hàng hay giá 0.

File điều khiển danh sách model/màu/URL chung trên web: mỗi lượt có link sẽ áp dụng danh sách trong file, với kiểm tra revision. Xóa một dòng sẽ bỏ model khỏi danh sách theo dõi chung, không xóa lịch sử. Tên màu tương đương chỉ được giữ nếu đã xác nhận trong cấu hình và màu yêu cầu không đổi; file không tự suy luận màu tương đương. CPS vẫn giải parent/child ID bằng worker hiện có, không coi URL là SKU.

```bash
cd /Users/lcblongg/weekly-price-cs/Data
.venv/bin/python tools/run_data.py --check
.venv/bin/python tools/env_runner.py --env-file .env tools/run_data.py
# File khác:
.venv/bin/python tools/env_runner.py --env-file .env tools/run_data.py --file /duong-dan/data.xlsx
```

`--check` chỉ kiểm tra file, không truy cập Supabase/cào/lưu cấu hình. `.env` ở `Data/.env`, không commit hoặc gửi khóa qua chat. Backup cấu hình trước lượt: `out/data-runs/<timestamp>/`; log và summary từng job: `out/local-web/<job-id>/`; giá/issues riêng: `out/jobs/<job-id>/apple/<kênh>/`. Kênh lỗi không làm mất kết quả kênh thành công. Lượt chạy lỗi giữ dữ liệu cũ với cảnh báo; ngày chưa có snapshot vẫn thiếu, không bù từ ngày khác.

Lịch GitHub hiện có vẫn là luồng riêng; nút này chỉ chạy khi bạn bật trên máy. Không tự thay đổi lịch/Telegram nhóm. Cần điền link thật trước khi nghiệm thu luồng file → giá → web; kiểm thử mock không chứng minh website từng kênh truy cập được.
