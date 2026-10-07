# Sản phẩm theo dõi

Mở **Sản phẩm theo dõi** ở trên bộ lọc dashboard. Tìm tên model và bật/tắt checkbox theo Category. Chọn tất cả, bỏ chọn tất cả áp dụng cho toàn danh sách, kể cả các model không khớp ô tìm kiếm. Khôi phục mặc định bật lại mọi model và bỏ nhãn mới. Model mới xuất hiện sau lần tải đầu được bật sẵn, có nhãn **Mới**; chọn **Đã xem model mới** để xác nhận.

Định danh là cặp Category + tên model chuẩn hóa Unicode/khoảng trắng/hoa thường, khớp chính xác. iPhone 16 khác iPhone 16 Pro/Pro Max. Một lựa chọn áp dụng mọi đại lý nhưng không thay đổi SKU, biến thể, giá hoặc lịch sử gốc. Tên model do adapter cung cấp cần nhất quán giữa các kênh; tên khác thật sự không tự ghép bằng tìm chuỗi.

Danh sách model tích lũy từ các kỳ đã tải, gồm cả mục cần kiểm tra. Khi chưa tải catalog toàn bộ, đây không phải danh sách mọi model đang có trên tất cả website. Lựa chọn áp dụng bảng giá, CTKM, mục cần kiểm tra và cả hai sheet Excel. Số liệu tổng quan vẫn thể hiện dữ liệu nguồn trước bộ lọc, giống các bộ lọc khác.

## Lưu lựa chọn

- Demo: localStorage `weekly-price-cs:watchlist:v1`, riêng từng trình duyệt. Không ảnh hưởng bot hoặc Telegram. Không thể đồng bộ giữa máy ở chế độ demo.
- Live: chạy migration `supabase/006_personal_watchlists.sql` sau 001→005. Bảng `personal_watchlists` dùng UUID tài khoản Supabase Auth, RLS chỉ cho tài khoản đọc/ghi hàng của mình. Anon không có quyền. Đăng xuất xóa dữ liệu lựa chọn khỏi state; đăng nhập lại tải từ DB.
- Nếu tải hoặc ghi lỗi, giao diện báo rõ và có **Thử lại**; không báo đã lưu khi thất bại. Khi tải chưa thành công, bảng không hiện dữ liệu chưa áp dụng lựa chọn.
- Sau migration, kiểm tra bằng hai tài khoản rằng A không đọc/sửa hàng của B. Hiện chưa có credentials Supabase thật nên lưu theo tài khoản chưa xác minh trên dịch vụ thật.

## Telegram nhóm

`config/telegram-watchlist.json` là cấu hình CHUNG riêng, mặc định không ẩn model nào. Bot báo cáo đọc file này, không đọc localStorage hay bảng `personal_watchlists`.

```json
{"version":1,"hidden_models":[{"category":"Điện thoại","model_name":"iPhone 16"}]}
```

Chạy `telegram_reporter.py --watchlist config/telegram-watchlist.json` (cũng là mặc định CLI). Áp dụng cùng phạm vi cho dữ liệu hiện tại và tuần trước; thống kê trạng thái worker vẫn phản ánh thu thập đầy đủ. Thay file cấu hình chung phải commit để GitHub Actions nhận được. Không xóa gì khỏi catalog hoặc pipeline cào.

Cập nhật: bản demo lấy thêm model từ toàn catalog đã tìm thấy, không chỉ những dòng đã có giá. Có thể lọc hãng trong hộp theo dõi. Chọn tất cả/bỏ chọn tất cả vẫn áp dụng toàn danh sách, kể cả khi đang lọc hãng. Xem [brands-and-catalog.md](brands-and-catalog.md) để phân biệt model đã biết với kết quả giá đã cào.
