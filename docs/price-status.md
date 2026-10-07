# Giá hiển thị và trạng thái sản phẩm

Theo yêu cầu vận hành, khả năng mua hàng không quyết định việc thu thập dữ liệu:

- Có giá hiển thị: giữ giá đó, kể cả hết hàng/đặt trước; ghi trạng thái riêng trong ghi chú.
- Chỉ có trạng thái đã xác minh của đúng SKU: vẫn lưu snapshot, giá bằng NULL, không phải 0.
- Không đọc được giá hoặc trạng thái: ghi lỗi đọc dữ liệu, không suy diễn là hết hàng.
- ‘Ngừng kinh doanh’ chỉ ghi khi website trả nhãn đó; không suy diễn từ tồn kho 0.
- Link review được đọc lại hằng ngày; link chưa khóa được SKU hoặc trùng SKU vẫn cần kiểm tra.
- Danh mục, SKU và các biến thể vẫn được giữ; lựa chọn theo dõi cá nhân không thay đổi bot.

Các adapter dùng API/JSON công khai của website, khu vực mặc định được ghi trong chú thích. Trạng thái được lưu dưới dòng đầu `[Tình trạng] …` của promo_text, cùng giá và CTKM trong snapshot bất biến. Nhãn từ trường trạng thái website được ưu tiên; cờ không cho đặt mua chỉ được diễn đạt đúng mức đó, không khẳng định ngừng kinh doanh.

## Supabase

Chạy **007_price_and_status.sql sau 001–006** trước khi đưa bot mới lên môi trường thật. Migration cho phép NULL có nhãn trạng thái; giá 0 và NULL không có trạng thái vẫn bị từ chối. Không cần đổi RPC hiện có. Đã kiểm tra 31 trường hợp SQL trên PostgreSQL cục bộ; chưa chạy Supabase thật.

## Dashboard / Excel / Telegram

Bảng ngày và 7 ngày phân biệt ‘chưa có dữ liệu’ với ‘có trạng thái, không có giá’. Snapshot NULL không tham gia phép trừ/so sánh mức giảm. Excel có cột trạng thái và sheet trạng thái theo từng ngày; tiền NULL là ô trống. Telegram có mục trạng thái đã ghi nhận, không tính các bản ghi đó thành lỗi cào. Danh sách theo dõi nhóm vẫn tách khỏi lựa chọn cá nhân.

## Đọc lại kết quả cũ

`tools/repair_statuses.py` đọc bổ sung các link chưa có kết quả từ lượt full-refresh, ghi `artifacts/status-repair/<kênh>/`, giữ thời điểm riêng của giá cũ và cập nhật demo. Script đợi worker TGDD đang chạy kết thúc rồi mới bổ sung kênh đó; không dừng hoặc chạy chồng worker TGDD. Không gửi Telegram và không ghi Supabase trong lượt thử này.

Đối chiếu kết quả tại `artifacts/status-repair.log` và summary từng kênh. Độ đầy đủ nguồn danh mục hiện là **85/86**, TGDD Garmin còn thiếu; khôi phục kết quả giá không đồng nghĩa khám phá đủ nguồn.

## Kết quả thử thực tế ngày 06/10/2026

Đã đọc bổ sung bằng adapter mới:

| Kênh | Bản ghi giá/trạng thái | Chỉ có trạng thái | Link còn lỗi |
|---|---:|---:|---:|
| CellphoneS | 1.010/1.010 | 176 | 0 |
| Phong Vũ | 572/572 | 89 | 0 |
| FPT Shop | 766/766 | 2 | 0 |
| Viettel Store | 278/297 | 1 | 19 |

Các số trên đối chiếu catalog đã khám phá, không chứng minh toàn bộ model trên mọi website đã đủ. TGDD đang cào toàn catalog bằng worker khởi chạy trước bản sửa; bước bổ sung sẽ chạy sau khi worker đó kết thúc. Dashboard còn dùng mẫu 120 SKU TGDD trong thời gian chờ, có nhãn rõ ràng.

Đã đạt 80 test Python, 13 test logic Web, 31 kiểm tra SQL cục bộ, TypeScript và production build. Kiểm tra UI trạng thái trên dữ liệu CellphoneS thật đạt cho desktop/mobile/Excel. Kiểm tra lưu lựa chọn theo dõi, lọc ngày và xuất Excel vẫn đạt. Telegram được dựng và kiểm tra cục bộ, chưa gửi vào nhóm thật.
