# Triển khai và vận hành Weekly Price CS

## Trạng thái thực tế

Bản local đã có dashboard 5 kênh, quản lý model/màu Apple, lọc hãng/category/model/ngày/tuần,
watchlist, PRICE FLASH và so sánh tăng/giảm theo ngày/tuần. Mã cloud đã nối Supabase Auth, phân quyền admin/CS, job GitHub,
snapshot ngày và công bố giá/lỗi/snapshot trong cùng transaction. Chưa xác nhận vận hành
trên Supabase/Vercel thật nếu chưa có cấu hình tài khoản. Test PostgreSQL local không thay cho nghiệm thu dịch vụ thật.

Đọc `docs/acceptance-2026-10-07.md` và `docs/release-2026-10-07.md` để xem số liệu nguồn và lỗi còn lại.

## 1. Supabase

Tạo dự án Supabase; giữ mật khẩu database và service key trong file `.env` riêng.
Chạy SQL **001 → 008** trong `supabase/`, mỗi file một lần. Nếu dự án đã có 001–007 thì chỉ chạy 008.
Không chạy lại migration trên dữ liệu đang dùng. SQL có RLS: chỉ thành viên được cấp quyền mới đọc giá;
admin mới được thao tác cấu hình/job. Public anon key không cho phép đọc giá khi chưa đăng nhập.

File `.env` tại thư mục gốc (không commit):

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_KEY
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_CHAT_ID=YOUR_GROUP_ID
WEB_APP_URL=https://YOUR_ACTUAL_DOMAIN.vercel.app
```

Trong Supabase → Authentication → Users, tạo người dùng với email/mật khẩu; không bật đăng ký tự do.
Cấp quyền bằng SQL (thay UUID bằng ID thực của user):

```sql
insert into public.app_members(user_id,role)
values ('USER_UUID','admin')
on conflict(user_id) do update set role=excluded.role;
-- Người dùng CS: thay admin bằng cs.
```

Chuyển dữ liệu đã nghiệm thu từ máy hiện tại lên dự án **mới**, không ghi đè dữ liệu đã có:

```bash
.venv/bin/python tools/env_runner.py --env-file .env tools/cloud_worker.py --bootstrap --import-catalog --import-snapshot
```

Lệnh trên nạp file `.env` vào môi trường tiến trình; chỉ tạo file `.env` không tự truyền khóa vào Python. Không dùng shell `source` cho file tải từ nguồn khác.

Bootstrap giữ `observed_at` của từng SKU và ngày khám phá gốc, chia ngày theo múi giờ Việt Nam; không tạo lịch sử giả.
Catalog local nằm trong `artifacts/`, không đưa lên GitHub. Nếu máy khác không có catalog này,
chạy workflow discovery trước. Catalog quá 8 ngày sẽ bị từ chối để tránh cào trên danh sách quá cũ.
Nếu import dừng giữa chừng, chạy lại sẽ bỏ qua cấu hình/catalog/snapshot đã có.

## 2. GitHub và runner

Repository nên để private. Secrets trong Settings → Secrets and variables → Actions:
`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
Variables: `WEB_APP_URL`, `PRODUCTION_ENABLED=true` **chỉ sau khi nghiệm thu cloud thành công**.
Mặc định workflow theo lịch tắt khi thiếu biến này. Chạy thủ công vẫn được để nghiệm thu.

Lịch theo giờ Việt Nam:

- Discovery: Chủ nhật 06:00 (cron UTC `0 23 * * 6`).
- Giá/CTKM: mỗi ngày 10:00 (cron UTC `0 3 * * *`).
- Job trên Web: workflow `cloud_job.yml`; không gửi Telegram.

Các workflow công bố dùng chung concurrency group và hàng đợi Supabase. Job giữ lease/heartbeat;
transaction từ chối runner đã dừng/hết lease hoặc cấu hình đã đổi. Các worker local dùng khóa file
chung; không chạy một bản local công bố vào DB sản xuất ngoài hàng đợi cloud cùng lúc.

GitHub schedule là lịch chạy dự kiến, có thể trễ. Cào toàn catalog thường tốn hàng giờ; kiểm tra
phút Actions còn lại của tài khoản trước khi bật hằng ngày. Nếu cần tiết kiệm quota repository private,
thiết lập self-hosted runner và variable `RUNNER_LABELS=["self-hosted","macOS","ARM64"]` (hoặc nhãn
thực của runner). Máy runner phải bật/online vào giờ chạy. Xem [billing GitHub Actions](https://docs.github.com/en/actions/concepts/billing-and-usage). Không cam kết toàn bộ hệ thống miễn phí
nếu giới hạn gói đang dùng không đáp ứng lượt cào.

## 3. Vercel

Import repository, chọn Root Directory **web**, preset Next.js, Node.js 22.
Thiết lập Environment Variables trước khi deploy production:

```dotenv
NEXT_PUBLIC_DATA_MODE=live
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_PUBLIC_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVER_KEY
GITHUB_REPOSITORY=lcblongg/weekly-price-cs
GITHUB_ACTIONS_TOKEN=YOUR_FINE_GRAINED_TOKEN
GITHUB_WORKFLOW_REF=main
# Tùy chọn: true = ai cũng xem bảng giá/lịch sử không cần đăng nhập (chỉ đọc).
NEXT_PUBLIC_PUBLIC_VIEW=true
```

`NEXT_PUBLIC_PUBLIC_VIEW=true`: `/api/comparison` trả snapshot đã công bố cho khách; khách lưu "Sản phẩm theo dõi"
trên trình duyệt. Quản lý Apple, job cập nhật giá và mọi API ghi vẫn bắt buộc tài khoản admin (nút "Đăng nhập quản trị").
Tắt: đặt `false` (hoặc xóa biến) rồi Redeploy — biến `NEXT_PUBLIC_*` chỉ có hiệu lực sau khi build lại.

Token GitHub chỉ cấp repository này và quyền **Actions: write**, Metadata: read;
không đưa token/service key vào biến `NEXT_PUBLIC_*`. Vercel chỉ xác thực/dispatch/đọc DB;
Python và Chromium chạy trên GitHub runner, không chạy trong Vercel Function. API bảng giá phân trang
dưới 3,5 MB/phản hồi để đáp ứng [giới hạn payload Vercel](https://vercel.com/docs/functions/limitations);
client tải đủ các trang và kiểm tra generation nhất quán trước khi hiển thị.
Dùng tên miền Vercel thực cấp, không cam kết `weekly-price-cs.vercel.app` còn khả dụng.
Trong Supabase Auth → URL Configuration đặt Site URL là domain thực. Vercel [Hobby](https://vercel.com/docs/plans/hobby) chỉ dành cho cá nhân, phi thương mại;
cần gói phù hợp cho việc dùng nội bộ doanh nghiệp hoặc lựa chọn hosting khác.

Các trang `*-review.html` là kết quả kiểm tra local, được gitignore; không đưa chúng lên deploy
vì chúng không qua Auth. Bản production không cấu hình live sẽ hiện hướng dẫn thiết lập.

## 4. Nghiệm thu cloud trước khi bật lịch

1. Đăng nhập admin; đăng xuất phải mất quyền đọc API. CS đọc được giá nhưng không lưu quy chuẩn/job.
2. Chạy job CPS riêng iPhone 17 Pro Max/Cam vũ trụ, không Telegram. So đúng model, màu,
   SKU, giá, giờ mới và bảo đảm model/kênh khác không đổi. Giá có thể thay đổi so với lượt local.
3. Sửa quy chuẩn, đợi job success rồi tải lại quản lý. Không áp dụng một bản nháp cũ khi revision đã đổi.
4. Thử check URL; trạng thái lưu trên DB. Chỉ job giá mới công bố giá.
5. Theo ngày so đúng ngày liền trước; theo tuần so giá ghi nhận cuối tuần này với cuối tuần trước, có ghi ngày và mở chi tiết 7 ngày. Thiếu kỳ trước không tạo chênh lệch. Giảm nền/chữ đỏ, tăng nền/chữ xanh; PRICE FLASH cùng kỳ đối chiếu. SKU cũ giữ giờ gốc và cảnh báo nếu đọc lại lỗi.
6. Watchlist ẩn đúng model, lưu theo tài khoản, không đổi báo cáo nhóm; bộ lọc áp dụng cả bảng và PRICE FLASH. Không có nút xuất Excel theo yêu cầu hiện tại.
7. Chạy discovery/daily thủ công `send_report=false`; xem artifact và đủ 5 trạng thái kênh.
8. Cấu hình bot vào nhóm Telegram, kiểm tra bằng lượt thủ công `send_report=true` chỉ khi đã có
   chỉ định gửi. Sau khi đạt, bật `PRODUCTION_ENABLED=true`.

## 5. Lỗi, dữ liệu cũ và phục hồi

- Không đọc được giá không đồng nghĩa hết hàng. Bản ghi trạng thái chỉ được lưu khi website hiện rõ.
- Lỗi một kênh giữ snapshot trước; từng SKU giữ `observed_at`, có `stale_since`/`stale_reason`.
- Khác màu yêu cầu không được gán thành màu chuẩn. Thay màu làm chứng cứ cũ không còn hợp lệ.
- Lỗi discovery giữ catalog thành công trước; quá 8 ngày cần discovery mới.
- Garmin MW vẫn cần đối chiếu: nguồn hiện công bố 38 model, trước đó 65; 1 link HTTP 404.
  Không coi đọc 86 trang danh mục là đã đủ mọi SKU/model.
- Job stuck: xem GitHub log trước, kiểm tra lease. Web đánh dấu job hết lease là lỗi trước khi tạo
  job khác. Không chỉnh status sang success bằng tay để che lỗi; không bật Telegram khi đang sửa.
- Trước khi đổi adapter/công bố thủ công, backup artifacts/cấu hình/Supabase; dùng dry-run/đầu ra riêng.

## Kiểm tra ở máy local

```bash
.venv/bin/python -m unittest discover -s tests -v
cd web
npm test
npm run typecheck
npm run build
cd ..
# Có PostgreSQL 17: database tạm, không TCP, không chạm Supabase.
tools/test_postgres.sh
# Dev server local đang chạy ở 3000:
.venv/bin/python web/tests/test_comparison_ui.py
.venv/bin/python tools/audit_coverage.py
```
