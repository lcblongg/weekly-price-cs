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

`NEXT_PUBLIC_PUBLIC_VIEW=true`: `/api/comparison` trả snapshot đã công bố cho khách, chỉ xem. Bảng giá live chỉ hiện các
model Apple trong danh sách **Sản phẩm theo dõi** (`app_settings.apple_colors`, trang `/apple-products`, chỉ admin): thêm model + màu,
xoá model; sau khi lưu, các job tự nối áp dụng quy chuẩn → discovery → cập nhật giá. Các lượt này không gửi Telegram. Thêm/xoá trên cloud được GitHub tự nhận qua workflow `queued_jobs.yml` mỗi 10 phút khi bật production (GitHub có thể chạy trễ). `GITHUB_ACTIONS_TOKEN` là tùy chọn để dispatch ngay.
Mọi API ghi vẫn bắt buộc admin (nút "Đăng nhập quản trị").
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


## Tự động hóa hàng đợi (10/10/2026)

- `queued_jobs.yml`: kiểm tra Supabase mỗi 10 phút, chỉ cài Python/Chromium khi có yêu cầu chờ.
- Cả hàng đợi, discovery, daily và nút xác minh dùng chung concurrency group; không hủy bot đang chạy.
- Lưu danh sách Apple tạo job cấu hình. Khi thành công, tự xếp job discovery; discovery thành công/một phần xếp job giá.
- Job hết lease được chuyển lỗi, giữ kết quả từng kênh đã ghi nhận. RPC không cho runner hết lease công bố.
- Nếu một yêu cầu khác chiếm hàng đợi ở đúng lúc nối bước, job ghi `followup_warning`; không báo đã cào thành công.
- Lịch giá 10:00 VN (03:00 UTC), discovery Chủ nhật 06:00 VN (23:00 UTC thứ Bảy).
- FPT/PV đã trả HTTP 403 từ runner GitHub trong lượt 07/10. Không vượt chặn; giá cũ giữ thời điểm cũ.
  Nếu vẫn bị chặn, cần runner hợp lệ khác và kiểm chứng lại; không thể cam kết 5 kênh đều có giá mới.
- Repo hiện public; không đưa secrets hoặc artifacts nội bộ vào Git.


## Bảng giá Apple và tốc độ tải (10/10/2026)

Bảng công khai và API công khai chỉ trả các model Apple trong danh sách theo dõi.
Giữ iPhone/iPad/MacBook/Apple Watch/AirPods; bot đọc `config/scope.json` chỉ Apple.
Dữ liệu lịch sử hãng khác giữ nguyên trong DB; chưa có thao tác xóa lịch sử.
Không hiện bộ lọc hãng khi dữ liệu chỉ có Apple.

API rút gọn trước phân trang, chuẩn bị regex một lần và tải snapshot/quy chuẩn song song.
Snapshot rút gọn được nén trong cache server, thời gian revalidate 30 giây; phản hồi vẫn giữ timestamp nguồn.
Cache Next.js có thể trả bản trước trong lúc làm mới sau TTL; không thay timestamp hoặc lấp ngày thiếu.
Generation vẫn kiểm tra mọi trang để tránh ghép hai lượt dữ liệu.
Khách xem giá không chờ Supabase Auth; trang quản trị vẫn xác thực đầy đủ.
`web/vercel.json` đặt một region Tokyo (`hnd1`), cùng vùng Supabase.
Xem [cấu hình region Vercel](https://vercel.com/docs/project-configuration/vercel-json).
Phép đo trước sửa: 23,07 giây / 5 request API trên Chromium mobile; cần đo lại production sau deploy.


## Bấm chạy trên Mac → tự cập nhật web

Mã nằm trong `weekly-price-cs/Data/`; file `.env` ở Data, không đưa khóa vào hội thoại/Git.
Nút duy nhất ở thư mục `weekly-price-cs/`: **Chay bot.command** (cũng có bản trong Data).
Đọc `weekly-price-cs/data.xlsx` với 5 cột URL → xác minh model/SKU/màu → lưu Supabase và cập nhật web.
Xem [hướng dẫn một file](data-file-bot.md). Không discovery hoặc chụp ảnh trong luồng này.
Các launcher cũ đã được bỏ để tránh chọn nhầm luồng đầu vào hoặc gửi Telegram.

Giữ Terminal mở và máy có Internet. `caffeinate -i` giữ máy không ngủ do nhàn rỗi;
không đóng nắp máy trong lượt chạy. Web tự làm mới mỗi phút; cache server có thể thêm một khoảng trễ.
Không cần deploy web sau mỗi lượt giá. Các lượt local này **không gửi Telegram**.

Nút mới dùng khóa file local, kiểm tra worker CLI và hàng đợi Supabase; chờ lượt đang chạy,
không dừng GitHub. Unique index/RPC trong DB ngăn công bố chồng, giữ timestamp nguồn, chỉ công bố SKU/màu đúng.
Nếu có lỗi, giữ giá cũ với cảnh báo; không xác nhận toàn bộ kênh thành công. HTTP 403 trên Mac vẫn là lỗi truy cập.
Log riêng: `Data/out/local-web/<job-id>/run.log` và `summary.json`.

Lệnh kiểm tra kết nối (không cào/ghi dữ liệu):

```bash
cd /Users/lcblongg/weekly-price-cs/Data
.venv/bin/python tools/env_runner.py --env-file .env tools/update_web_local.py --check
# Chạy riêng FPT/PV nếu cần:
.venv/bin/python tools/env_runner.py --env-file .env tools/update_web_local.py --channels fpt,phongvu
```

Ngày 10/10: kiểm tra kết nối thực đạt (36 model); job GitHub vẫn đang chạy khi chuẩn bị launcher.
Chưa xác nhận lượt cào trên Mac mới đã hoàn tất.
