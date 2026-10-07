# Lọc hãng và độ đầy đủ model

Dashboard có **Chọn hãng**, kết hợp đại lý, Category, model, từ khóa, ngày/tuần và lựa chọn theo dõi cá nhân. Bộ lọc áp dụng bảng giá, CTKM, mục cần kiểm tra và tất cả sheet Excel. Hãng lấy từ metadata nguồn, chuẩn hóa Apple/Samsung/Xiaomi/OPPO/Asus/HP/Dell/Lenovo/Huawei/Garmin…; chỉ suy ra khi tên có token hãng rõ ràng. Không đoán từ tên đại lý.

## Vì sao trước đây thiếu nhiều model

Lượt thử trước giới hạn **120 link ready/kênh**, không phải toàn bộ catalog. Catalog hợp nhất có **3.338 link: 2.619 ready + 719 review**, trong 85/86 nguồn thành công. Link khác biến thể/dung lượng không đồng nghĩa model khác nhau. Một nguồn TGDD Garmin vẫn chưa đạt kiểm tra phân trang; không được đánh dấu đầy đủ.

Demo giờ mang cả metadata catalog. Dropdown model và danh sách theo dõi lấy từ cả giá, issue và catalog, nên model chưa có giá vẫn tìm/chọn được. Khối **Sản phẩm đã tìm thấy nhưng chưa có kết quả giá** cho biết những link chưa có giá/issue cho kỳ đang chọn, xuất thành sheet riêng **Chưa có kết quả giá**. Không đưa các link này vào bảng giá bằng giá 0, không tạo snapshot hay lịch sử giả. Nguồn review chưa đọc được giá phải xem lý do riêng.

Catalog chỉ phản ánh lượt khám phá gần nhất, không chứng minh có giá trong quá khứ. Ngày trước discovery không hiển thị các link đó như đã quét giá. Hiện metadata toàn catalog được nối vào demo; chế độ live sử dụng giá/issues từ Supabase, và sẽ có các model giá khi worker đầy đủ chạy. Không mở quyền đọc cấu hình bot cho trình duyệt.

## Lượt cào không giới hạn mẫu đang triển khai

Lệnh `.venv/bin/python tools/refresh_full_demo.py` chạy 5 worker độc lập từ catalog đã xác minh, **không dùng --limit**, chỉ dry-run; không gửi Telegram/ghi Supabase. Đầu ra riêng `artifacts/full-refresh/prices/<kênh>/`, log riêng; `status.json` ghi trạng thái. Không chạy trùng khi lượt này còn hoạt động. Sau khi từng kênh hoàn tất, chương trình cập nhật `display/` và dựng demo nguyên tử để trình duyệt có thể tải lại dữ liệu mới. Kênh chưa xong giữ kết quả mẫu trước, scope ghi rõ giới hạn của từng kênh.

TGDD phải giãn cách theo nguồn nên có thể chạy lâu. Chỉ sau khi cả 5 summary đã kết thúc mới báo độ đầy đủ giá toàn catalog; thành công trong mẫu không chứng minh toàn bộ SKU đã đọc được giá. Garmin vẫn giữ cảnh báo dù bot giá đọc được tất cả link còn lại.
