# Kiểm tra trước triển khai thật

Thời điểm: 2026-10-07T18:32:33.480395+07:00. Chỉ đọc dữ liệu đang công bố; không chạy thêm bot và không gửi Telegram.

## Dashboard hiện tại

Các số dưới đây là SKU duy nhất đang hiển thị, sau quy chuẩn màu Apple; không phải tổng dòng lịch sử hoặc toàn bộ link nguồn. Giá/trạng thái của màu khác không được thế vào màu người dùng chọn.

| Kênh | SKU hiển thị | Có giá mới hôm nay | Trạng thái mới hôm nay | Chưa xác minh hôm nay | Mục Apple cần đối chiếu |
|---|---:|---:|---:|---:|---:|
| TGDD | 707 | 167 | 0 | 540 | 8 |
| CellphoneS | 995 | 819 | 176 | 0 | 21 |
| Viettel Store | 288 | 281 | 7 | 0 | 9 |
| FPT Shop | 747 | 732 | 10 | 5 | 3 |
| Phong Vũ | 500 | 439 | 61 | 0 | 30 |

## Phần chưa hoàn tất

- MW còn cào toàn catalog; số MW trên là thời điểm báo cáo, chưa nghiệm thu lượt cuối. Không dừng tiến trình này để deploy.
- FPT giữ 5 SKU cũ, có 5 lỗi nguồn cần kiểm tra. Không đổi thời gian của giá cũ thành hôm nay.
- Catalog hợp nhất đọc được 86/86 nguồn nhưng không phải lượt discovery mới hôm nay và không chứng minh đủ tất cả model/SKU.
- Garmin MW: lượt riêng 38/38 model so với trang từng công bố 65; 1 link HTTP 404, vẫn giữ cảnh báo.
- Các mục Apple cần đối chiếu là kết quả worker chọn màu, tách biệt với thành công của bot toàn catalog. Không gán màu suy đoán.
- Dữ liệu tuần trước chưa có nên chưa thể nghiệm thu biến động tuần thật; tính toán đã được kiểm tra bằng fixture, UI ghi thiếu kỳ trước.

## Triển khai dịch vụ

- CI commit 582558f đạt Python/web/PostgreSQL. Ba kiểm tra mới cho thống kê nghiệm thu cũng đạt (SKU khác kênh, lịch sử, timezone và trạng thái thay giá cũ).
- Repository chưa có Secrets Supabase/Telegram; PRODUCTION_ENABLED=false. Chưa có xác nhận Supabase/Auth, Vercel và Telegram thật.
- Cần đường dẫn file cấu hình bí mật trên máy và lựa chọn hosting. Không đưa khóa vào chat hoặc repository.
- Thứ tự thực hiện khi có cấu hình: backup → migration 001–008 → tạo admin/CS → import dữ liệu giữ thời gian gốc → deploy live → nghiệm thu quyền và job riêng không Telegram → nghiệm thu pipeline → cấu hình nhóm Telegram → bật lịch.
- Không công bố hoàn tất production trước khi kiểm tra các dịch vụ thật; hướng dẫn chi tiết trong [production-runbook.md](production-runbook.md).
