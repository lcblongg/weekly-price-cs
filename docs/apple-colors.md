# Một màu theo dõi cho mỗi model Apple

Danh sách người dùng gồm 36 model, lưu trong `config/apple_colors.json`. Các màu để trống (Mac Mini và một số AirPods) có nghĩa không lọc màu; không tự điền màu mặc định. Tên/màu do người dùng cung cấp được giữ nguyên, không tự sửa theo tên thương mại khác.

Hiện áp dụng vào trang nghiệm thu riêng MW: `http://localhost:3000/mw-review.html`. Bấm **Quản lý model / màu Apple** để thêm/sửa model, màu và các tên màu tương ứng tại đại lý, rồi lưu. Cấu hình được ghi vào file chung của dự án và dựng lại trang, không phụ thuộc localStorage. Trình sửa chỉ bật trên máy local ở chế độ development; chưa lưu vào Supabase/Auth. Khi triển khai sản xuất cần thay bằng bảng cấu hình chung và quyền quản trị.

Tên rút gọn là tên model chuẩn + dung lượng, ví dụ `Điện thoại iPhone 18 Pro Max 256GB` → `iPhone 18 Pro Max 256GB`. Tên nguồn còn nguyên trong chi tiết, SKU vẫn riêng theo màu/dung lượng/phiên bản. RAM, kích thước Watch và WiFi/Cellular không bị gộp trong dữ liệu giá; tên nguồn/SKU được giữ để đối chiếu. Model ngoài danh sách (ví dụ MacBook Pro 14 M5 Pro) không được ghép với model gần giống (MacBook Pro 14 M5).

Tên màu hiển thị giữ nguyên danh sách người dùng. Bot đối chiếu lựa chọn màu của đúng model trên MW, chọn mã SKU trước khi đọc giá; không nhận snapshot màu mặc định rồi đổi tên. Các tên thương mại tương ứng được khai báo giới hạn theo model trong `mw_apple_colors.py` và lưu bằng chứng màu/SKU trong từng bản ghi.

Tab **Đối chiếu màu Apple** giữ toàn bộ link Apple, kể cả chưa khớp màu/chưa cấu hình/chưa biết màu. Phần **Độ đầy đủ danh sách Apple** trình bày cả 36 model, gồm những model chưa xác định link trong catalog hiện tại. Điều này không khẳng định website không có sản phẩm/màu đó; discovery có thể đang thiếu.

Đây là lớp hiển thị nghiệm thu MW, chưa áp dụng vào dashboard tổng hay Telegram nhóm. Bot vẫn cào và lưu đầy đủ dữ liệu gốc. Xây lại trang sau lượt bot mới bằng `.venv/bin/python tools/build_mw_review.py`.


## Sửa cách lấy màu theo yêu cầu mới

Không chỉ lọc snapshot của màu mặc định. `tools/scrape_mw_apple.py` đọc bộ lựa chọn trên MW, chọn màu cần theo dõi, lấy giao của mã màu và từng phiên bản, rồi đọc lại giá bằng `?code=<mã biến thể>`. Model, mã biến thể và nhãn màu trả về phải khớp lựa chọn. Mỗi bản ghi giữ `color_evidence` với mã màu website, mã sản phẩm, URL lựa chọn và thời điểm xác minh. Nếu không xác minh được thì không công bố giá.

Bảng nghiệm thu chỉ dùng snapshot Apple của lượt này, không dùng các snapshot Apple mặc định trước đó. Kết quả được cập nhật theo từng model vào `artifacts/mw-apple-selected/`; dữ liệu đầy đủ trước đó vẫn được giữ.

Một số tên thương mại được đối chiếu theo **đúng model** với tên lựa chọn của MW, ví dụ Xanh Da Trời trên MacBook Air M5 và Ánh Sao trên Watch SE 3. Quy tắc nằm trong `mw_apple_colors.py`; không dùng alias người dùng tự điền, không phân loại bằng suy đoán RGB, không áp dụng tên màu của model này sang model khác. Trình quản lý chỉ cần model và màu yêu cầu.

Nguồn tên màu: [MacBook Air M5 – Apple](https://www.apple.com/vn/newsroom/2026/03/apple-introduces-the-new-macbook-air-with-m5/), [iPad Air M4 – Apple](https://www.apple.com/vn/newsroom/2026/03/apple-introduces-the-new-ipad-air-powered-by-m4/), [Watch SE 3 – Apple](https://www.apple.com/vn/apple-watch-se-3/). Palette/mã SKU MW được ghi ở `artifacts/mw-color-*.json` và trong từng `color_evidence`.


Nguồn đối chiếu thêm: [iPad Pro M5](https://www.apple.com/vn/newsroom/2025/10/apple-introduces-the-powerful-new-ipad-pro-with-the-m5-chip/), [MacBook Neo](https://www.apple.com/vn/newsroom/2026/03/say-hello-to-macbook-neo/), [AirPods Max 2](https://support.apple.com/vi-vn/126620). Bot luôn yêu cầu mã màu/SKU trả về khớp palette của đúng model, không chỉ dựa vào tên thương mại.


Tên `Xanh Lá Xô Thôm` được giữ nguyên theo danh sách người dùng, đối chiếu với mã màu 116 / `Xanh Lá Xô Thơm` của MW. [Tên Apple là Xanh Lá Xô Thơm](https://www.apple.com/vn/iphone-17/specs/). Tương tự, Hồng của iPhone 15 được đối chiếu với lựa chọn Hồng nhạt, mã màu 61, trên palette của đúng model; [Apple gọi màu này là Hồng](https://support.apple.com/vi-vn/111831). Không sửa màu người dùng thành màu khác.

### MW có hai giao diện chi tiết

`adapters/tgdd_legacy.py` đọc giao diện cũ trực tiếp từ HTML, khóa `document.productCode` và thẻ màu `act[data-code]`, rồi lấy giá trong vùng `.box_right .box04 .box-price-present`. Trạng thái hết hàng/ngừng kinh doanh của vùng sản phẩm được lưu cùng giá, không làm bản ghi bị loại. Không lấy giá schema/giá GTM hoặc đổi nhãn của snapshot màu mặc định. Giao diện Next.js vẫn đọc PRODUCT_DETAIL như trước.

Ví dụ thực tế: iPad Air M4 11 WiFi 512GB, SKU 2440931001230, giao diện cũ hiện 29.390.000đ và “Hết hàng tạm thời”; bot vẫn lưu giá với màu Xám Không Gian sau khi đối chiếu đúng mã màu/SKU. Bản HTML đối chiếu nằm ở `artifacts/mw-color-read-failure.html`.

Chạy tiếp từ kết quả đã lưu bằng `.venv/bin/python tools/scrape_mw_apple.py --resume`; bản ghi đã đọc đúng được giữ nguyên, lỗi từng SKU không làm bỏ các dung lượng còn lại. Kết thúc lượt đọc không đồng nghĩa đủ tất cả model: xem trạng thái từng model và nguồn danh mục còn thiếu.

Giá online giao diện cũ được lấy từ `.box_saving .bs_price strong`, bỏ giá gốc trong `em`. Nếu vùng giá hoặc mã màu không duy nhất, bot giữ mục cần kiểm tra thay vì đoán.
