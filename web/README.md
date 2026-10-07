# Weekly Price CS — Web Dashboard

Next.js 15 App Router + Tailwind CSS 4 + các component shadcn/ui. Dashboard có bố cục riêng màu xanh, dùng lịch tài chính 13 tuần/quý theo mốc đã xác nhận.

## Chạy local

```bash
cd /Users/lcblongg/weekly-price-cs/web
npm ci
cp .env.example .env.local
npm run dev
```

Mở http://localhost:3000. Không ghi đè `.env.local` nếu bạn đã cấu hình. Bản production local có thể chạy bằng `npm run build` rồi `npm run start`.

## Các chức năng đã có

- Lọc đại lý, tìm sản phẩm không dấu và chọn tuần FY.
- Bảng giá mới nhất và lịch sử 7 ngày từ thứ Hai đến Chủ nhật. Chỉ dùng giá thật ở ngày đã ghi nhận; ngày thiếu để trống.
- SKU khóa màu được giữ nguyên; chưa tự ghép cùng model giữa nhiều đại lý.
- Biến động trong tuần chỉ tính khi cùng SKU có dữ liệu ở ít nhất 2 ngày; tính từ ngày đầu tới ngày cuối có dữ liệu.
- Xem CTKM, nguồn sản phẩm và thời điểm quét; ưu đãi có điều kiện không được trừ vào giá.
- Xuất Excel đúng các sản phẩm đang lọc, kèm 7 cột ngày, giá gốc, CTKM và nguồn. Cell số tiền là số; ngày thiếu để trống.
- Mobile dùng thẻ sản phẩm; lịch sử ngày có vùng cuộn riêng.
- Chế độ live đăng nhập email/mật khẩu Supabase, tải `daily_prices` có phân trang qua RLS, làm mới bằng nút. Không dùng service role key trong Web.
- Trang lịch mô tả cấu hình; không tự bật GitHub Actions hoặc cam kết job đã chạy.

## Demo và live

`NEXT_PUBLIC_DATA_MODE=demo` hiển thị 24 giá/CTKM Viettel đã cào thật trong pilot. File demo có một ngày dữ liệu 06/10/2026, không giả lập lịch sử đủ tuần hoặc giá của các đại lý khác. Thời điểm demo là lúc hoàn thành lần quét thử; chưa phải snapshot từ Supabase.

Production thiếu cấu hình sẽ hiện màn hình thiết lập, không âm thầm chuyển sang demo. Trong chế độ live, dữ liệu pilot không được đưa vào props dashboard. Cần public Supabase URL + anon key; service role key chỉ đặt trong GitHub Secrets của bot.

```dotenv
NEXT_PUBLIC_DATA_MODE=live
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_PUBLIC_ANON_KEY
```

Chạy SQL 001 → 002 → 003 trên Supabase, cấu hình Supabase Auth email/password, tạo tài khoản cho CS và tắt đăng ký công khai vì policy hiện cho phép các tài khoản authenticated đọc dữ liệu. Web chưa có luồng đăng ký/reset mật khẩu tự phục vụ. Migration 003 và RLS chưa được thử trên tài khoản thật của bạn.

## Deploy Vercel

1. Đưa toàn bộ repo lên GitHub; giữ `.env.local`, `.env`, artifacts, node_modules và dữ liệu secret ngoài Git.
2. Import repo trong Vercel, chọn **Root Directory = web**, Framework Next.js.
3. Thêm ba biến môi trường trên vào Production/Preview theo môi trường bạn muốn. Bản production thật đặt mode live.
4. Deploy; sau khi thêm/sửa biến môi trường phải redeploy để Next.js cập nhật giá trị public.
5. Cấu hình URL ứng dụng trong Supabase Auth và `WEB_APP_URL` cho bot. Tên miền `weekly-price-cs.vercel.app` chỉ dùng được nếu còn khả dụng; chưa cấp tên miền cho dự án này.
6. Sau khi có catalog đầy đủ đã nghiệm thu, cấu hình Secrets Supabase/Telegram và bật Actions. Các adapter còn lại chưa sẵn sàng; đừng coi pilot một danh mục là catalog đủ 86 nguồn.

Tài liệu: [Next.js](https://nextjs.org/docs/app/getting-started/installation), [Supabase client](https://supabase.com/docs/reference/javascript/initializing), [shadcn/ui](https://ui.shadcn.com/docs/installation/next).

## Kiểm chứng

```bash
npm run typecheck
npm run test
npm run build
npm audit --omit=dev
```

Có 6 kiểm thử logic lịch FY, ngày thiếu, snapshot mới nhất, tách màu, validation nguồn/giá và tìm kiếm không dấu. Khi app demo chạy ở cổng 3000, chạy từ thư mục gốc:

```bash
.venv/bin/python web/tests/test_dashboard_ui.py
```

Kiểm tra UI dùng Chromium, tải Excel rồi đọc lại bằng openpyxl để xác nhận 4 sản phẩm lọc, tiền là số, ngày thiếu là ô trống và không có công thức. Bao gồm bộ lọc tuần/chuỗi, CTKM, lịch và mobile. Test này dùng dataset pilot cố định W2Q1FY27.

Khóa dependency trong package-lock.json. Overrides PostCSS/uuid dùng bản đã vá, và export Excel đã kiểm tra sau override. Kết quả audit hiện tại là kết quả lúc kiểm tra; cần chạy lại khi cập nhật dependency.

Chưa deploy Vercel, chưa kết nối Supabase thật, chưa có realtime/biểu đồ 13 tuần/trang quản trị catalog. Không tự báo cáo thành công những phần này.

## Xem theo ngày và theo tuần

Hai nút Theo tuần / Theo ngày nằm ở đầu dashboard, cạnh dropdown thời gian. Theo ngày có danh sách 91 ngày gần nhất (thêm ngày có trong pilot nếu nằm ngoài khoảng này). Chọn ngày chỉ hiển thị snapshot mới nhất đúng ngày đó, gồm giá, CTKM và thời điểm quét; không dùng giá ngày gần nhất để điền ngày thiếu. Biến động ngày so với đúng ngày liền trước của cùng đại lý/SKU. Ở ranh giới thứ Hai, Web tải thêm tuần trước để có thể đối chiếu Chủ nhật. Theo tuần giữ lịch FY và bảng 7 ngày. Excel xuất một cột giá ngày ở chế độ ngày, hoặc 7 cột ngày ở chế độ tuần. Dataset hiện vẫn là pilot Viettel, chưa có dữ liệu đủ mọi model/đại lý.

Hiện có 7 kiểm thử logic, thêm kiểm tra chế độ ngày không lấy giá ngày khác và so sánh đúng ngày trước.

## Bộ lọc Category / Model

Thêm hai dropdown Tất cả Category / Tất cả model cạnh bộ lọc đại lý. Model được lấy từ sản phẩm đang có dữ liệu trong category/đại lý đã chọn; đổi category tự xóa model cũ. Cả giá theo ngày, theo tuần, CTKM và Excel dùng cùng bộ lọc. Với dữ liệu cũ thiếu metadata, nhận diện những nhóm tên rõ ràng; tên không xác định giữ Chưa phân loại. Ưu tiên trường category/model_name nếu adapter cung cấp. Model iPhone tách riêng Pro/Pro Max/Plus/e và bỏ dung lượng/màu ở cấp lọc, nhưng mỗi SKU/giá vẫn giữ biến thể riêng. Các category chưa có giá sẽ có trạng thái trống, không tạo dữ liệu giả.
