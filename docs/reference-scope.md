# Phạm vi dashboard theo website mẫu

Tham chiếu: https://weekly-price-cs.vercel.app/ — kiểm tra ngày 05/10/2026.
Người dùng yêu cầu lấy website này làm chuẩn, giao diện chỉ điều chỉnh nhẹ.
Không tự đổi sang dashboard khác hoặc yêu cầu người dùng mô tả lại chức năng đã có trong mẫu.

## Bằng chứng và giới hạn

Trang trong trình duyệt đang dừng ở “Đang tải dữ liệu…”. Đã đọc bundle frontend công khai
/assets/index-D-IQfVRl.js để xác định các thành phần và hành vi bên dưới.
Đây là kiểm tra mã frontend, chưa chứng minh chức năng backend của website mẫu hoạt động.
Không sử dụng lại mã bundle, khóa, tài khoản, dữ liệu hoặc backend của mẫu trong dự án mới.
Triển khai độc lập theo yêu cầu và kiến trúc Next.js 15 đã chọn.

## Chức năng xác định từ frontend mẫu

1. Chuyển chế độ theo tuần / theo ngày; lựa chọn tuần hoặc ngày.
2. Lọc Category, Model và Partner (chuỗi bán lẻ).
3. Price flash: thông tin tăng/giảm giá, chuyển hết hàng và có hàng trở lại.
4. Bốn chỉ số: số model, partner có giá, số thay đổi giá, chênh lệch lớn nhất.
5. Bảng ma trận: model theo hàng, partner theo cột; đánh dấu giá thấp nhất,
   thay đổi so với kỳ trước, OOS và ngày quan sát gần nhất khi dữ liệu cũ.
6. Chọn một model: biểu đồ giá từng partner (13 tuần hoặc 7 ngày), tooltip;
   chuyển từ tuần sang dữ liệu ngày khi dữ liệu ngày có sẵn.
7. Bảng xếp hạng partner cho model: giá, chênh so với thấp nhất, chênh kỳ trước.
8. Liên kết Bản tin CS ở header; không tự xây thêm website bản tin trong phạm vi này.
9. Công cụ quản trị được bảo vệ bằng đăng nhập:
   - Duyệt observation: sửa giá/tồn kho, xác nhận/pending/loại kết quả, bắt buộc ghi lý do.
   - Quản lý model, partner, URL sản phẩm, override giá crawler; bật/tắt từng mục.
   - Lịch sử điều chỉnh, giữ nguyên dữ liệu crawler gốc.
   - Xuất Excel Daily từ trang quản trị.
10. Đăng nhập được nhớ, đăng xuất; nhận thay đổi realtime và trạng thái dữ liệu dự phòng.

## Yêu cầu gốc vẫn giữ

- Python + Playwright, Supabase, Next.js 15 App Router + Tailwind + shadcn/ui.
- Khám phá link 06:00 Chủ nhật; cào giá/CTKM và gửi Telegram 10:00 hằng ngày, cả 7 ngày/tuần (giờ Việt Nam).
- Theo dõi CTKM, giá gốc/giá KM, tìm kiếm sản phẩm và xuất XLSX dữ liệu đang lọc.
  Những yêu cầu này vẫn phải triển khai dù không thấy ở giao diện mẫu đã phân tích.
- Giao diện responsive; bố cục ma trận và trang chi tiết model như mẫu;
  chỉ chỉnh nhẹ màu sắc, khoảng cách và chữ, không coi đề xuất trắng/navy trước đó là bắt buộc.

## Ảnh hưởng đến thiết kế hiện tại

weekly_prices hiện có chỉ đủ lưu snapshot theo tuần. Để đạt phạm vi mẫu cần bổ sung migration
cho catalog (products, retailers, product_links), observations theo thời điểm/giá/tồn kho,
review corrections có audit, overrides và quyền admin riêng. Không dùng một tài khoản admin
hardcode hoặc cấp quyền ghi cho mọi authenticated user.

Đã cập nhật lịch cào và gửi Telegram 10:00 hằng ngày. Không còn lịch gửi Telegram tuần riêng.
Cần bổ sung bảng observations để lưu lịch sử mỗi ngày; schema weekly_prices hiện vẫn ghi đè
trong cùng tuần và reporter hiện so với tuần trước. Không suy diễn dữ liệu tuần thành giá từng ngày.
Chỉ carry-forward khi đánh dấu stale, ngày quan sát và phạm vi cho phép; không vẽ dữ liệu cũ
như quan sát mới hoặc nối biểu đồ xuyên khoảng thiếu một cách gây hiểu nhầm.

## Trạng thái triển khai

Hiện đã có SQL/bot/report tuần ở thư mục gốc. Dashboard, observations ngày, quản trị, audit,
realtime và deploy chưa được triển khai. File này chốt phạm vi để bước tiếp theo không bỏ sót
các chức năng của mẫu; không phải thông báo đã hoàn thành các chức năng đó.
