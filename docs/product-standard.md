# Quy chuẩn model Apple chung

`config/apple_models.json` là nguồn chuẩn tên và thứ tự 36 model do người dùng cung cấp. Cả năm bot dùng `identity.describe` và `scraper.price_row`, web dùng cùng JSON qua `web/lib/product-standard.ts`. Các trang nghiệm thu MW/CPS dùng cùng thứ tự. Không dùng thứ tự chữ cái cho model Apple.

Tên hiển thị = model chuẩn + dung lượng lưu trữ; WiFi/5G, RAM, kích thước Watch, dây/vỏ, màu và mã SKU là thuộc tính biến thể, không gộp giá. Chuẩn hóa không làm thay đổi SKU hay giá. Tên gốc vẫn được giữ trong catalog và dữ liệu bằng chứng của các lượt nghiệm thu. Model ngoài danh sách hoặc không xác định chính xác nằm sau danh sách chuẩn; không ép thế hệ khác vào model theo dõi, không tự biến AirPods Max 2026 thành AirPods Max 2.

Lượt bot tiếp theo áp dụng chuẩn mới. Lịch sử đã lưu không bị ghi đè; dashboard đọc lịch sử và chuẩn hóa nhãn từ metadata/tên nguồn. Danh sách chuẩn và danh sách màu là hai cấu hình riêng: sửa màu không thay đổi thứ tự model. Việc thêm model chuẩn cần bổ sung quy tắc nhận diện rõ ràng ở JSON.
