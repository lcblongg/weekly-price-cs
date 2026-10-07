# Kết quả kiểm tra ngày 06/10/2026

Dữ liệu dry-run thực tế, chưa ghi Supabase và chưa gửi Telegram.

| Kênh | Nguồn OK/tổng | Link ready | Link review | Giá đọc được/mẫu ready | Mục cần kiểm tra trong mẫu |
|---|---:|---:|---:|---:|---:|
| Viettel Store | 14/14 | 235 | 62 | 120/120 | 24 |
| CellphoneS | 19/19 | 610 | 400 | 120/120 | 24 |
| TGDD | 18/19 | 614 | 79 | 120/120 | 24 |
| Phong Vũ | 15/15 | 492 | 80 | 113/120 | 31 |
| FPT Shop | 19/19 | 668 | 98 | 119/120 | 25 |

Tổng 85/86 nguồn, 3.338 link (2.619 ready, 719 review). Mẫu giá gồm 600 link ready: 592 đọc được giá, 8 lỗi/hết hàng. 128 mục cần kiểm tra = 120 mẫu catalog review + 8 lỗi khi đọc ready. Không phải đã kiểm tra giá toàn bộ 2.619 link.

TGDD Garmin còn thiếu dữ liệu phân trang: lượt cuối 51/65 model. Nguồn chưa đạt kiểm tra độ đầy đủ, không lấy dòng của nguồn thất bại vào catalog hợp nhất. Dòng 19 Excel cần kiểm tra; không coi 85/86 là toàn bộ nguồn thành công.

Demo chỉ có ngày 06/10/2026, thời điểm riêng theo từng worker. Sáu ngày khác để trống.

Kiểm chứng sau tính năng theo dõi model: 74 test Python, 10 test logic Web, build Next.js và 28 kiểm tra SQL cục bộ đạt. Test Playwright đầy đủ 5 kênh và test theo dõi (lưu/reload, lọc kết hợp, CTKM, Excel ngày/tuần, nhãn Mới, mobile) đạt; không có page error JavaScript. Lưu lựa chọn theo tài khoản trên Supabase thật chưa xác minh vì chưa có credentials.
