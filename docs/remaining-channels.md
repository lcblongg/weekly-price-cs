# Nghiệm thu FPT Shop, Viettel Store, Phong Vũ

Ba trang độc lập: `/fpt-review.html`, `/viettel-review.html`, `/phongvu-review.html`. Cùng danh sách chuẩn 36 model và cấu hình một màu/model với MW và CPS. Dung lượng, màu, RAM, mạng, dây/vỏ vẫn tách riêng theo mã SKU; chỉ hiển thị giá bán. Header có thời gian của dữ liệu nền và lượt đọc màu riêng.

## Chạy bot màu

```sh
.venv/bin/python tools/scrape_remaining_apple.py
# Chạy lại kênh cần sửa, giữ bản ghi đã xác minh
.venv/bin/python tools/scrape_remaining_apple.py fpt --resume
.venv/bin/python tools/scrape_remaining_apple.py viettel --resume
.venv/bin/python tools/scrape_remaining_apple.py phongvu --resume
```

Đầu ra riêng `artifacts/<slug>-apple-selected/`: prices, issues, summary và palettes có thời gian/mã nguồn. Kết thúc lượt không đồng nghĩa đủ mọi model: xem từng trạng thái missing_catalog/partial, nguồn Excel và lỗi thực tế. Đây là dry-run local, không ghi Supabase/Telegram.

- FPT: đọc `variants.skuSlugs.attributes` của đúng SKU để lấy màu; không lấy màu catalog cũ hoặc hậu tố tên chứa mã hàng. Chọn `?sku=`, yêu cầu productAdvanceInfo.sku và biến thể khớp trước khi nhận giá.
- Viettel: rule_id là mã màu dùng lại giữa nhiều sản phẩm, không phải SKU toàn cục. Mở palette theo product URL, chọn rule, kiểm tra mã ERP. Khóa lịch sử bằng mã ERP. Lỗi CTKM sau khi xác minh giá giữ giá và ghi `CTKM chưa xác minh đầy đủ`, promotion_complete=false; sai ERP vẫn bị từ chối.
- Phong Vũ: chọn options của màu từ productOptions, khóa `?sku=` và đối chiếu productInfo.sku cùng lựa chọn màu selected. Giữ màu đã xác minh cả khi không có giá và SKU có trạng thái rõ ràng.

Tên thương mại được đối chiếu giới hạn theo model, ví dụ Space Gray với Xám Không Gian trên iPad Air M4, Jet Black với Đen Bóng trên Watch S11. Lưu nhãn thực tế và mã lựa chọn trong color_evidence; UI hiển thị màu người dùng. Không dùng màu gần giống, không tự quy mọi màu Đen thành Đen Không Gian.

Discovery giữ tất cả mã màu của các model Apple thuộc danh sách chuẩn, kể cả cùng giá/hết hàng. Cấu hình màu chỉ chọn dữ liệu nghiệm thu hiển thị, không xóa catalog hay dữ liệu nguồn. Giá và CTKM dùng khu vực mặc định của từng website, ưu đãi thanh toán/thu cũ ghi chú riêng.

Apple Watch Phong Vũ có thể chỉ cho chọn màu dây. Khi thiếu nhóm màu vỏ, đọc thuộc tính Màu sắc của productDetail thuộc SKU đã khóa; không lấy Band color làm màu vỏ. Chỉ đối chiếu nhãn cụ thể như Đen / Jet Black với Đen Bóng; Đen / Black không tự được gộp.

FPT statusOnWeb=ngung_kinh_doanh khi productAdvanceInfo=null: kiểm tra variants.sku và mã con trước khi lưu trạng thái NULL giá. Không dùng variant.price trong trường hợp này vì có thể là giá lịch sử.
