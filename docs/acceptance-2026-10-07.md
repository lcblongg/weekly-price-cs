> Cập nhật cuối lượt: xem [bản bàn giao](release-2026-10-07.md). MW còn 23 lỗi giá; Viettel đã đọc 297/297 link dưới dạng giá hoặc trạng thái; dashboard 3.232 bản ghi. Số liệu phía dưới mô tả lượt nghiệm thu trước khi sửa review.

# Nghiệm thu local ngày 07/10/2026

Snapshot local; chỉ job CPS đã cào thật ngày 07/10 và Garmin được thử lại riêng. Không xác nhận 86 nguồn mới ở thời điểm báo cáo.

Job CPS `20261007T150533-ae63f4`: thành công 4 SKU iPhone 17 Pro Max màu Cam vũ trụ lúc 15:06. Model CPS khác và bốn kênh còn lại giữ nguyên khi nghiệm thu job. Không gửi Telegram. Sau bước đối chiếu này, MW được bổ sung riêng 43 bản ghi Garmin đã kiểm tra.

| Kênh | Nguồn đọc được | Link catalog | SKU khóa catalog | Model nhận diện | SKU có giá | Chỉ trạng thái | Lỗi/chưa khóa SKU | Model chưa có giá trên dashboard |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TGDD | 19/19 | 737 | 657 | 301 | 657 | 0 | 80 | 5 |
| CellphoneS | 19/19 | 1010 | 610 | 478 | 834 | 176 | 0 | 0 |
| Viettel Store | 14/14 | 297 | 235 | 141 | 277 | 1 | 19 | 6 |
| FPT Shop | 19/19 | 766 | 668 | 306 | 764 | 2 | 0 | 0 |
| Phong Vũ | 15/15 | 572 | 492 | 156 | 483 | 89 | 0 | 0 |

**Đọc được 86/86 nguồn trong các snapshot hợp nhất không có nghĩa đủ toàn bộ model/SKU trên website.** Chỉ CPS một model và TGDD Garmin được kiểm tra thật mới trong lượt nghiệm thu này. Phần lớn dữ liệu còn lại từ 06/10; không gọi lại 86 nguồn. SKU khóa catalog là metadata discovery; số giá/trạng thái có thể lớn hơn do adapter đã đọc bổ sung các link review. Model được đếm theo tên chuẩn/metadata; catalog thiếu tên vẫn có link cần kiểm tra riêng.

## Garmin TGDD

Lượt mới đọc đủ 38/38 model trang công bố, tạo 44 link. Đã đọc 43/44 giá/trạng thái; 1 link Garmin Descent MK2i 52mm trả HTTP 404 và chưa khóa được SKU. Trước đây trang công bố 65 model, nên vẫn giữ cảnh báo không chứng minh đủ mọi sản phẩm Garmin. Không hạ ngưỡng 80%. Đã thêm 43 kết quả vào dashboard local.

## Model có trong catalog nhưng chưa có dữ liệu hiển thị

### TGDD

- AirPods Max: Chưa có giá/SKU đúng màu đã xác minh
- AirPods Max 2: Chưa có giá/SKU đúng màu đã xác minh
- Apple Watch S12: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra
- Apple Watch Ultra 4: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra
- Galaxy Tab S12 Ultra: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra

Khoảng dữ liệu: 2026-10-06T16:34:44.154399+07:00 → 2026-10-07T15:15:55.395751+07:00
Trạng thái màu catalog: {"other_color": 54, "selected": 15, "unconfigured": 45, "other": 618, "unknown_color": 5}. Đây là so tên màu nguồn, **không phải** chứng cứ màu giá. Bản ghi worker chọn màu: 91; mục cần kiểm tra: 10.

### CellphoneS

Không thấy model thiếu sau khi đối chiếu tên chuẩn và SKU đang hiển thị.

Khoảng dữ liệu: 2026-10-06T14:08:29.934771+07:00 → 2026-10-07T15:06:08.489485+07:00
Trạng thái màu catalog: {"selected": 41, "unconfigured": 95, "other_color": 70, "other": 804}. Đây là so tên màu nguồn, **không phải** chứng cứ màu giá. Bản ghi worker chọn màu: 96; mục cần kiểm tra: 21.

### Viettel Store

- AirPods 3: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra
- AirPods Max 2: Chưa có giá/SKU đúng màu đã xác minh
- Garmin Forerunner 955 Solar: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra
- OPPO Find X10: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra
- Poco C95 Pro: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra
- iPhone Duo: Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra

Khoảng dữ liệu: 2026-10-06T14:16:22.520066+07:00 → 2026-10-06T21:55:57.989422+07:00
Trạng thái màu catalog: {"selected": 30, "other_color": 55, "unconfigured": 45, "unknown_color": 9, "other": 158}. Đây là so tên màu nguồn, **không phải** chứng cứ màu giá. Bản ghi worker chọn màu: 82; mục cần kiểm tra: 12.

### FPT Shop

Không thấy model thiếu sau khi đối chiếu tên chuẩn và SKU đang hiển thị.

Khoảng dữ liệu: 2026-10-06T14:30:22.023655+07:00 → 2026-10-06T21:59:39.981206+07:00
Trạng thái màu catalog: {"unconfigured": 91, "other_color": 120, "selected": 53, "other": 502}. Đây là so tên màu nguồn, **không phải** chứng cứ màu giá. Bản ghi worker chọn màu: 154; mục cần kiểm tra: 3.

### Phong Vũ

Không thấy model thiếu sau khi đối chiếu tên chuẩn và SKU đang hiển thị.

Khoảng dữ liệu: 2026-10-06T14:24:32.088177+07:00 → 2026-10-06T22:03:14.895376+07:00
Trạng thái màu catalog: {"selected": 14, "other_color": 90, "unknown_color": 94, "unconfigured": 81, "other": 293}. Đây là so tên màu nguồn, **không phải** chứng cứ màu giá. Bản ghi worker chọn màu: 126; mục cần kiểm tra: 30.

## Nguyên nhân và phần cần tiếp tục

- MW: 80 link chưa có kết quả an toàn, chủ yếu thiếu mã biến thể trong discovery (79 cũ + 1 Garmin 404). Không chuyển lỗi này thành hết hàng/ngừng kinh doanh. Các model Apple thiếu có thể chưa có màu yêu cầu hoặc adapter chưa xác minh được màu.
- Viettel: 19 link lỗi contract/model/biến thể hoặc chưa đọc được giá/trạng thái. Cần kiểm tra lại parser từng link, không tự chuyển sang màu mặc định.
- CPS/FPT/PV: snapshot giá/trạng thái bao phủ catalog hiện có; vẫn chưa bảo đảm discovery đủ mọi SKU/dung lượng/màu.
- Nhiều SKU khác màu Apple bị loại có chủ đích khỏi bảng đúng màu; không xóa dữ liệu nguồn.
- Khóa dùng chung trên một máy đã nối job Apple, worker Apple, scraper toàn catalog và discovery. Runner giữ khóa qua cả bước cào và công bố; tạo job/dựng dashboard cũng tuần tự hóa.
- Chưa chuyển sang Supabase/Auth/deploy; khóa local không thay khóa phân tán/GitHub concurrency.

## Kiểm chứng

- Job thật CPS và đối chiếu hash + bản ghi theo SKU: `artifacts/acceptance/20261007-150533/cps-acceptance.json`.
- Snapshot dự phòng: `artifacts/acceptance/20261007-150533/`; có thêm bản sao trước hợp nhất Garmin.
- Job cô lập dùng cơ chế FD khóa mới: `20261007T151121-04c960`, thành công 4 SKU CPS, không ghi dashboard thật.
- Kiểm tra browser thấy CPS 256GB = 34.990.000đ, màu Cam vũ trụ, thời điểm cập nhật 07/10 15:06:08.
- Bộ test Python 143 test; TypeScript 16 test, typecheck và build.
