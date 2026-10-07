# Bảng so sánh gọn cho 5 kênh

Trang chính `/` hiển thị bảng model/dung lượng/cấu hình × MW/CPS/FPT/VIETTEL/PV. Bấm từng ô mở khung chi tiết SKU, màu, giá bán, trạng thái/CTKM, thời gian và link đại lý. Giữ từng SKU trong dữ liệu và Excel; ô nhiều SKU có giá khác nhau hiển thị khoảng giá. Ô thiếu bản ghi hiện “—”, không suy diễn hết hàng. Bản ghi NULL giá hiện “Không hiện giá”, vẫn có trạng thái chi tiết.

Dữ liệu hiện lấy từ các lượt nghiệm thu màu đã xác minh tại `artifacts/*-apple-selected`, tổng hợp bằng `tools/build_comparison.py` thành `web/data/comparison.json`. Mỗi lần dựng trang nghiệm thu kênh cũng dựng lại bảng chung. Chỉ các màu đúng cấu hình được đưa vào bảng. Dung lượng CPS được đối chiếu product_id cha nếu tên sản phẩm con không ghi dung lượng; không lấy tên model trống để so với phiên bản 256GB.

Theo tuần: chọn ngày thực sự có snapshot trong tuần Mon–Sun, ngày thiếu được ghi rõ và không tạo giá giả. Dashboard lịch sử đầy đủ ở `/history` vẫn giữ chế độ Supabase/demo, lọc hãng, ngày/tuần và chức năng cũ. Bảng mới hiện dùng dữ liệu nghiệm thu local; chưa phải nguồn live Supabase.

Sản phẩm theo dõi dùng cùng kho lựa chọn cá nhân với dashboard cũ (`weekly-price-cs:watchlist:v1`), không thay đổi catalog hoặc Telegram nhóm. Xuất Excel gồm bảng tổng và trang chi tiết SKU, theo đúng bộ lọc/lựa chọn đang hiển thị. Chưa có tài khoản trong chế độ local này.
