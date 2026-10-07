# Nghiệm thu bot CellphoneS

Mở `http://localhost:3000/cps-review.html`. Trang độc lập với MW, chỉ có giá bán hiển thị, giữ riêng SKU/dung lượng/mạng/dây/vỏ. Mặc định lọc Apple; có thể chọn tất cả hãng. Catalog đạt 19/19 nguồn Excel không đồng nghĩa đủ mọi model website.

## Chạy lại

```sh
.venv/bin/python tools/scrape_cps_apple.py
.venv/bin/python scraper.py --chain cellphones --catalog file --config artifacts/full/merged/cellphones/catalog.json --out artifacts/cps-review-full --dry-run
.venv/bin/python tools/build_mw_review.py --cps
```

Lệnh đầu mở toàn bộ child_product từ các parent_id Apple trong catalog rồi đọc lại GraphQL website đang dùng. Kiểm tra model cha/con, parent_id, mã con và tên màu trước khi công bố giá. Giá/màu trong catalog cũ không được dùng thay bằng chứng hiện tại. Bằng chứng nằm ở `artifacts/cps-apple-selected/{parents,children,prices,issues,summary}.json`. `--cached` chỉ dựng lại từ dữ liệu đã đọc, dùng khi phát triển, không dùng lịch cào hằng ngày.

Mỗi màu phải khớp nguyên tên sau chuẩn hóa chữ hoa/thường. Hai quy tắc giới hạn theo model: iPhone 17 giữ tên người dùng Xanh Lá Xô Thôm, đối chiếu lựa chọn Xanh Lá Xô Thơm; Watch Ultra 3 Đen đối chiếu Titan Đen. Không tự đổi Xám thành Xám Không Gian, Đen thành Đen Không Gian hoặc suy đoán màu khi tên thế hệ con/cha không nhất quán. Các trường hợp này ở mục cần kiểm tra.

Giá được đọc theo province_id=30 (Hà Nội) như adapter hiện tại; không trừ ưu đãi thành viên, HSSV, thu cũ hoặc thanh toán. Nếu stock API bằng 0 nhưng có giá, vẫn giữ giá. Nếu không có giá và API ghi stock=0, giữ bản ghi không giá và ghi rõ khu vực API; đây không phải xác nhận ngừng kinh doanh toàn quốc. Không thay giá thiếu bằng 0. Giá mẫu iPhone 17 Pro 512GB Cam Vũ Trụ, mã 112604, đã đối chiếu HTML trang mã màu: 38.490.000đ, trùng bot.

Đây là lượt nghiệm thu local, không ghi Supabase hoặc gửi Telegram. Cấu hình màu chung có thể sửa tại nút quản lý, lưu sẽ dựng lại cả trang MW và CPS; đổi màu cần chạy lại bot để có giá màu mới. Không ảnh hưởng danh mục hoặc dữ liệu nguồn đầy đủ.
