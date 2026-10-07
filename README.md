# Weekly Price CS — trạng thái và triển khai hiện tại

Bản local đã có dashboard và bot 5 kênh. Luồng cloud dùng Supabase Auth, phân quyền admin/CS và GitHub Actions.
Xem [hướng dẫn production](docs/production-runbook.md), [nghiệm thu](docs/acceptance-2026-10-07.md) và [bản bàn giao](docs/release-2026-10-07.md).
Các phần phía dưới ghi lại triển khai ban đầu; số liệu và trạng thái mới lấy từ các tài liệu trên.

# Weekly Price CS

Hệ thống tra cứu/so sánh giá & CTKM cho Quản lý vùng / Community Specialist.
Đầu vào là `inputs/data.xlsx` (86 trang danh mục của 5 đại lý). Không cần nhập link từng sản phẩm.

- Chủ nhật 06:00 (giờ VN): `discover_products.py` đọc Excel → tìm link → đọc thử giá/CTKM → catalog ready/review.
- Hằng ngày 10:00: `scraper.py` cào lại toàn bộ catalog → `daily_prices` + `scrape_issues` → `telegram_reporter.py`.
- Mỗi kênh (TGDD, CellphoneS, Viettel Store, FPT Shop, Phong Vũ) là một worker riêng: `--chain <kênh>`.
  **Lệnh chạy, chạy lại kênh lỗi, lịch UTC, đọc log: [docs/channels.md](docs/channels.md).**
- Dashboard: `web/` (Next.js). Xem [web/README.md](web/README.md) và [docs/discovery.md](docs/discovery.md).

## Trạng thái thực tế (cập nhật 06/10/2026)

| Thành phần | Trạng thái |
|---|---|
| Adapter 5 đại lý (TGDD, CellphoneS, FPT Shop, Viettel Store, Phong Vũ) | Đã viết và chạy thật (dry-run) trên toàn bộ 86 nguồn — kết quả ở `docs/discovery.md` |
| Định danh mọi nhóm hàng | `identity.py`: SKU khóa theo mã biến thể gốc của đại lý; model cho điện thoại/tablet/laptop/đồng hồ/AirPods |
| Sản phẩm thiếu giá | Ghi vào `scrape_issues` kèm lý do; dashboard có tab "Cần kiểm tra" |
| Supabase | Migration 001→004 **chưa chạy** trên dự án thật; RLS/RPC chưa xác minh với dịch vụ thật |
| Telegram | **Chưa gửi thật**; chỉ có bản xem trước |
| GitHub Actions / Vercel | **Chưa push, chưa bật lịch, chưa deploy** |

Nguyên tắc dữ liệu: không tạo giá/lịch sử giả; ngày thiếu để trống; giá bán = giá bán thường của biến thể đã khóa;
quà, thu cũ, HSSV, ưu đãi thanh toán, giá giờ vàng/online giới hạn suất chỉ ghi trong CTKM, không trừ vào giá.
Các phần bên dưới là hướng dẫn cài đặt và lịch sử các bước trước; nơi nào mâu thuẫn với bảng trên thì bảng trên là đúng.

## Cấu trúc

```text
weekly-price-cs/
├── supabase/001_weekly_prices.sql
├── config/products.json
├── common.py
├── scraper.py
├── telegram_reporter.py
├── requirements.in
├── requirements.txt             # lock có hash toàn bộ dependency
├── tests/test_logic.py
├── .env.example
└── .github/workflows/daily_prices.yml   # + discover_sunday.yml (matrix 5 kênh)
```

## Quy ước dữ liệu

`sku` là mã nội bộ chung giữa đại lý, không lấy mã hàng khác nhau của từng chuỗi để so sánh.
Ví dụ `apple-iphone-16-128gb-vn-new`: model, bộ nhớ, thị trường, hàng mới.
Nếu màu ảnh hưởng giá, bổ sung màu vào SKU và xác minh màu trong `verify_tokens`.
Không gộp bản 128GB/256GB, hàng cũ/mới, VN/A/xách tay. Khi mở trang, phải cố định đúng
biến thể và khu vực; cấu hình hiện tại chỉ lấy trạng thái mặc định của URL, chưa có bước bấm chọn.
Nếu nguồn cần bấm chọn, thêm thao tác Playwright riêng trước `extract` đọc giá và test thao tác đó.

`promo_price` = giá bán trực tiếp công khai, trước giảm có điều kiện (VNPAY, thu cũ,
trả góp, thành viên). Các điều kiện này nằm trong `promo_text`. `original_price` là giá gốc
trang công bố; nếu không có thì NULL, không tạo một giá gốc giả.

`year` là **ISO week-year**, không phải luôn là năm dương lịch. Đầu tháng 1 có thể thuộc
năm ISO trước. Python `isocalendar()` cùng múi giờ Asia/Ho_Chi_Minh xử lý quy tắc này.

Mỗi chuỗi + SKU + năm ISO + tuần chỉ có một dòng. Chạy lại trong tuần sẽ cập nhật snapshot
của tuần đó, không giữ mọi lần quan sát. Nếu cần lịch sử hàng ngày, cần một bảng observations khác.
`updated_at` do DB cập nhật; `source_url` và `run_id` bổ sung để truy nguồn và kiểm tra độ đầy đủ.

## BƯỚC 1 — Supabase PostgreSQL

1. Tạo dự án Supabase. Chọn khu vực gần Việt Nam và lưu mật khẩu DB trong nơi quản lý secret.
2. Mở SQL Editor → New query.
3. Dán toàn bộ `supabase/001_weekly_prices.sql` và Run. Script dành cho dự án mới,
   chỉ chạy một lần; muốn sửa schema sau đó thì thêm migration mới, không chạy lại script này.
4. Kiểm tra Table Editor có `weekly_prices` và `scrape_runs`.
5. Trong phần API của Project Settings, lấy Project URL và service role key cho bot.
   Có thể giao diện dùng tên API Keys; dùng khóa đặc quyền phía server, không publish vào Web.

### Tại sao schema này

- BIGINT lưu VND nguyên, tránh sai số float.
- UNIQUE `(chain_name, sku, year, week_number)` làm khóa UPSERT.
- B-tree tuần/chuỗi phục vụ dropdown tuần và chuỗi; SKU/tuần phục vụ lịch sử sản phẩm.
- GIN trigram tối ưu tìm tên với `ILIKE '%iphone%'`. Bộ lọc vẫn cần phân trang ở Bước 3.
- `commit_weekly_prices` dùng INSERT ON CONFLICT DO UPDATE trong một transaction Postgres.
  Vẫn dùng supabase-py, nhưng gọi RPC thay vì nhiều request `.upsert()` riêng lẻ để tránh
  ghi thành công một nửa catalog khi một dòng khác lỗi.
- `scrape_runs` chỉ xuất hiện khi commit thành công; reporter kiểm tra số dòng và run_id.

### Bảo mật ngay từ đầu

RLS bật ở cả hai bảng. `anon` không được đọc/ghi. `authenticated` chỉ được SELECT bảng
`weekly_prices`; Bước 3 cần đăng nhập Supabase Auth, tắt tự đăng ký nếu chỉ dùng nội bộ và
quản lý tài khoản CS. Policy hiện tại cho mọi tài khoản đã đăng nhập đọc toàn bộ giá; nếu cần
phân quyền từng vùng, thêm bảng thành viên và policy tương ứng ở Bước 3.

Bot dùng service role để ghi và đọc hai bảng. RPC chỉ cấp EXECUTE cho service role;
`SECURITY INVOKER` không tạo một hàm vượt quyền dành cho người dùng Web.
Không đặt service role trong biến `NEXT_PUBLIC_*`, mã frontend, file cấu hình hoặc Git.

## BƯỚC 2A — Cài Python và cấu hình

Chạy tại terminal:

```bash
cd /Users/lcblongg/weekly-price-cs
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
python -m playwright install chromium
cp .env.example .env
```

Dùng Python 3.12 trong CI. Bot tương thích Python 3.11+. Sửa `.env` bằng editor;
không dán token vào lệnh shell có thể lưu history.

| Biến | Ý nghĩa | Nơi dùng |
|---|---|---|
| SUPABASE_URL | Project URL HTTPS | Python / Repository Secret |
| SUPABASE_SERVICE_ROLE_KEY | Khóa đặc quyền server | Python / Repository Secret |
| TELEGRAM_BOT_TOKEN | Token BotFather cấp | Python / Repository Secret |
| TELEGRAM_CHAT_ID | ID nhóm Telegram, thường số âm | Python / Repository Secret |
| WEB_APP_URL | URL dashboard được deploy thực tế | Python / Repository Variable |

Các script không tự đọc `.env`. Để không thực thi nội dung `.env` như mã shell, có thể dùng
launcher Python sau với file `.env` chỉ chứa `KEY=value` một dòng, không dùng dấu quote:

```bash
python - <<'PY'
import os
import subprocess
from pathlib import Path
for raw in Path('.env').read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith('#'):
        continue
    key, value = line.split('=', 1)
    os.environ[key.strip()] = value.strip()
subprocess.run(['python', 'scraper.py', '--chain', 'all', '--catalog', 'discovery', '--out', 'artifacts/prices'], check=True)
subprocess.run(['python', 'telegram_reporter.py', '--summaries', 'artifacts/prices', '--dry-run'], check=True)
PY
```

Sau khi xem preview, bỏ `--dry-run` ở dòng cuối để gửi thật.
Chạy scraper trước khi gửi để manifest và snapshot khớp nhau. URL Vercel ở `.env.example`
chỉ là giá trị mong muốn; tên miền có thể đã được người khác dùng và chưa được cấp cho dự án này.

## Adapter Viettel đã kiểm tra trên nguồn thật

Adapter native HTTP đã chạy thử 30 link iPhone Viettel: 24 ready, 6 review; bot giá cào lại 24 ready thành công. Giá được khóa theo mã màu/ERP và CTKM được đọc từ trang chi tiết. Xem `docs/discovery.md` cho phạm vi, trạng thái review và lệnh dry-run. Đây là pilot 1/86 nguồn; các đại lý khác vẫn cần nghiệm thu. Chưa ghi Supabase/gửi Telegram thật.

## BƯỚC 2B — Nghiệm thu selector từng đại lý

1. Chọn sản phẩm và phạm vi giá (khu vực, bộ nhớ, màu, loại hàng).
2. Mở URL sản phẩm, xác nhận biến thể mặc định đúng; nếu không đúng, sử dụng URL biến thể
   riêng hoặc bổ sung thao tác chọn biến thể trước khi đọc giá.
3. Dùng DevTools → Inspect hoặc Playwright codegen để lấy selector:

```bash
python -m playwright codegen https://cellphones.com.vn/iphone-16.html
```

4. Điền `selectors.name`, `selectors.promo_price`, `selectors.original_price` và
   `selectors.promotions`. `original_price=null` chỉ khi trang thật sự không có giá gốc.
   Mỗi selector phải khớp đúng một vùng đang hiển thị, không chứa nhiều mức giá.
   `promotions` là danh sách vùng CTKM bao gồm quà, thanh toán, thu cũ; khi không có KM,
   vẫn chọn vùng thông báo không có KM trên trang. Vùng thiếu không được ngầm hiểu là không có KM.
5. `verify_tokens` phải chứa model + dung lượng và các đặc tính quyết định SKU.
   Nếu `h1` không có dung lượng, chọn selector khác bao trùm tên và biến thể đang chọn,
   hoặc mở rộng xác minh trong adapter. Không bỏ token dung lượng chỉ để làm bot chạy được.
6. Thay URL trang chủ Viettel/Phong Vũ bằng trang sản phẩm thật. Xóa mục không thuộc phạm vi
   theo dõi khỏi JSON; không để mục chưa cấu hình nằm trong danh sách production.
7. Sau khi đã kiểm tra DOM, đổi `verified` thành `true`. Đây là xác nhận cấu hình của bạn,
   không phải cơ chế bot tự chứng nhận giá đúng.
8. Chạy dry-run, không cần Supabase/Telegram:

```bash
python scraper.py --chain viettel --catalog file --config config/products.json --dry-run
```

9. Mở `artifacts/preview.json`, đối chiếu từng dòng với giá/CTKM đang hiển thị trong trình duyệt.
   Kiểm tra thêm một sản phẩm có giá gốc, một sản phẩm không có giá gốc, một sản phẩm hết hàng.
   Nếu hết hàng vẫn hiển thị giá cũ, cần thêm selector/trạng thái còn hàng vào adapter trước production;
   phiên bản này chỉ phản ánh giá niêm yết, không cam kết có tồn kho.
10. Chạy lại sau vài ngày để phát hiện DOM đổi; chỉ bật lịch sau khi các nguồn đã nghiệm thu.

Bot kiểm tra robots.txt bằng user-agent WeeklyPriceCS và dừng khi nguồn cấm hoặc không truy cập được.
robots.txt chỉ là một tín hiệu kỹ thuật, không thay thế thỏa thuận/quyền truy cập dữ liệu của nguồn.
Bot không xử lý CAPTCHA hoặc tìm cách vượt chặn; nếu bị chặn, làm việc với nguồn hoặc dùng API/feed được cấp.
Cào tuần tự, mỗi sản phẩm cách nhau ít nhất 2 giây và retry tối đa 3 lần. Không dùng networkidle
vì các trang bán lẻ thường có analytics liên tục. Playwright chờ phần tử hiển thị và yêu cầu selector duy nhất.

## BƯỚC 2C — Báo cáo Telegram

1. Trong Telegram, dùng BotFather tạo bot và lấy token.
2. Thêm bot vào nhóm CS, cấp quyền gửi tin; không cần quyền admin nếu nhóm cho phép thành viên gửi.
3. Gửi một lệnh `/start@TEN_BOT` trong nhóm để tạo update cho bot.
4. Gọi `getUpdates` bằng công cụ API hoặc đoạn Python sau; không dán token vào URL trình duyệt.
   Đoạn này yêu cầu TELEGRAM_BOT_TOKEN đã được nạp vào môi trường theo launcher ở trên:

```python
import os
import httpx
r = httpx.get(
    'https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/getUpdates',
    timeout=20,
)
if r.status_code != 200:
    raise RuntimeError('Không đọc được Telegram updates')
for item in r.json().get('result', []):
    message = item.get('message', {})
    chat = message.get('chat', {})
    if chat.get('type') in ('group', 'supergroup'):
        print(chat.get('title'), chat.get('id'))
```

Nếu bot đang dùng webhook thì getUpdates không hoạt động; dùng bot mới dành riêng cho hệ thống
hoặc điều chỉnh tích hợp hiện tại sau khi xác minh webhook. Nhóm chuyển thành supergroup có thể đổi ID.

### Quy tắc phân tích

- Đọc snapshot đầy đủ của tuần hiện tại theo manifest scraper vừa tạo.
- Đọc lần commit gần nhất của đúng tuần liền trước, kể cả chuyển năm.
- Ghép `(chain_name, sku)`; không so tên tương tự hoặc giá giữa các chuỗi để tính biến động tuần.
- Giảm mạnh khi `(giá trước - giá hiện tại) / giá trước > 3%` **HOẶC** giảm `>500.000đ`.
- Sắp xếp giảm theo %, rồi số tiền; hiển thị top 10.
- CTKM mới/thay đổi = nội dung đã chuẩn hóa khác tuần trước và khớp từ khóa
  VNPAY/thu cũ/đổi mới/quà/tặng/voucher/hoàn tiền/giảm thêm.
- Đây là phát hiện dựa trên từ khóa, không phải mô hình hiểu mọi điều kiện CTKM.
  Một nội dung thay đổi có thể là ưu đãi giảm đi; báo cáo chỉ yêu cầu CS kiểm tra, không khẳng định tốt hơn.
- SKU mới không có baseline bị loại khỏi nhận định giảm sốc/CTKM mới; tuần đầu chỉ tạo baseline.
- Escape HTML dữ liệu nguồn, chia tin theo block dưới giới hạn Telegram, xử lý 429 với retry_after.
- Khi lỗi mạng/5xx, trạng thái gửi có thể không rõ; không tự gửi lại để tránh nhân đôi.
  Gửi nhiều phần không có transaction: có thể gửi thành công một phần rồi lỗi.
- Chạy lại workflow với gửi tin sẽ gửi báo cáo lại. Phiên bản này không bảo đảm exactly-once delivery;
  kiểm tra nhóm trước khi chạy lại. Thêm outbox/delivery ledger khi cần quản lý gửi lại từng phần.

`artifacts/report.html` là bản xem trước nội dung Telegram, không phải dashboard.
`load_week` chỉ chọn run_id hợp lệ và kiểm tra product_count để không trộn dữ liệu cũ cùng tuần.
Nếu sửa danh mục trong tuần, các dòng cũ vẫn còn trong bảng weekly_prices; dashboard Bước 3 cần
lọc theo snapshot run_id gần nhất hoặc đánh dấu dữ liệu cũ, không chỉ lọc year/week.

## BƯỚC 2D — GitHub Actions

Sau khi kiểm chứng nguồn, chạy test và commit một lần từ máy local:

```bash
python -m unittest discover -s tests -v
```

Tạo repo GitHub, rồi thực hiện:

```bash
cd /Users/lcblongg/weekly-price-cs
git init -b main
git add .
git commit -m 'Add weekly pricing database scraper and Telegram reporter'
# Thay URL dưới đây bằng repository của bạn.
git remote add origin https://github.com/YOUR_ACCOUNT/weekly-price-cs.git
git push -u origin main
```

Trong repository → Settings → Secrets and variables → Actions:
- Repository Secrets: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
- Repository Variables: WEB_APP_URL.

Vào Actions → Daily prices and Telegram report → Run workflow. Lần đầu bỏ chọn Send report:
workflow vẫn ghi Supabase nhưng chỉ tạo report preview. Tải artifact, đối chiếu rồi chạy lại với
Send report để gửi vào nhóm. Sau đó lịch tự động cào giá/CTKM và gửi Telegram lúc 10:00 mỗi ngày, cả 7 ngày/tuần.

Cron `0 3 * * *`: 03:00 UTC = 10:00 mỗi ngày Việt Nam. Không còn lịch Telegram thứ Hai riêng.
Schedule phải nằm trên default branch; GitHub có thể trì hoãn/bỏ qua đợt chạy lúc tải cao.
Repo public có thể bị vô hiệu lịch sau 60 ngày không hoạt động theo chính sách GitHub.
Do đó đây không phải lịch SLA chính xác đến phút. Kiểm tra trạng thái Actions khi báo cáo thiếu.
Concurrency không hủy run đang chạy; workflow dừng khi scrape/test/report lỗi và hiện Failed.
Chưa có tin Telegram riêng cho lỗi scraper: nhóm nhận báo cáo giá chỉ sau commit thành công.
Bật thông báo workflow failure của GitHub cho người vận hành.

Artifacts giữ 7 ngày, chỉ chứa dữ liệu giá/báo cáo/manifest, không có secret. Nếu giá cần giữ nội bộ,
chọn repository private và kiểm soát quyền đọc repository/artifacts. Dung lượng và phút Actions
miễn phí phụ thuộc gói tài khoản; không giả định toàn bộ hệ thống luôn miễn phí không giới hạn.

## Cập nhật dependency có kiểm soát

CI cài đúng lock có hash trong requirements.txt. Khi muốn nâng dependency:

```bash
python -m pip install pip-tools
pip-compile --upgrade --generate-hashes --output-file=requirements.txt requirements.in
python -m pip install --require-hashes -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
```

Sau đó nghiệm thu dry-run nguồn thật và review diff lock trước khi commit. Workflow dùng
major version của action chính thức; môi trường nghiêm ngặt nên pin commit SHA và cập nhật qua Dependabot.

## Checklist nghiệm thu trước khi bật lịch

- SQL đã chạy thành công; anon không đọc/ghi, tài khoản CS chỉ đọc, service role ghi được.
- Chạy scraper 2 lần cùng tuần không tăng số dòng cho cùng chuỗi/SKU.
- Một nguồn lỗi làm toàn bộ lượt scrape dừng trước commit.
- Giá gốc/giá KM và mọi ưu đãi có điều kiện được CS đối chiếu với trang thật.
- Tất cả SKU/biến thể/khu vực nhất quán giữa đại lý và giữa các tuần.
- Report preview đúng; thử nhóm Telegram nội bộ trước nhóm CS chính thức.
- Workflow được đặt trên default branch, secrets/variable đúng, người vận hành nhận GitHub failure.
- Chưa có baseline tuần trước thì không diễn giải thiếu cảnh báo là không có giảm giá.

## Tài liệu chính thức đã đối chiếu

- Supabase Python upsert: https://supabase.com/docs/reference/python/upsert
- Supabase Row Level Security: https://supabase.com/docs/guides/database/postgres/row-level-security
- Playwright locators: https://playwright.dev/python/docs/locators
- Telegram Bot API: https://core.telegram.org/bots/api#sendmessage
- GitHub schedule: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

## Tiếp theo — Bước 3 và 4

Next.js 15 App Router + Tailwind + shadcn/ui, đăng nhập Supabase Auth, bộ lọc/phân trang,
badge chuỗi và export XLSX toàn bộ dữ liệu đã lọc. Dashboard phải thể hiện độ mới/snapshot,
không trộn dòng sót từ danh mục cũ. Vercel chỉ nhận publishable/anon key phía frontend;
service role tiếp tục ở bot. Kiểm tra quyền lợi gói Vercel phù hợp sử dụng nội bộ doanh nghiệp
trước khi chọn gói; không cam kết tên miền và điều kiện gói miễn phí ở giai đoạn này.

## Kết quả kiểm tra tại máy ngày 05/10/2026

- Python compileall: đạt.
- 10 unittest: đạt, bao gồm ngưỡng >3%/500k, tuần chuyển năm, khác SKU, CTKM,
  escape/chia HTML, phân trang, snapshot thiếu và extraction dùng Playwright mock.
- `pip check`: không có dependency bị thiếu/xung đột.
- Cấu hình verified=false: bot thoát lỗi trước truy cập nguồn/ghi DB, đúng thiết kế.
- Lock lấy phiên bản runtime đã chạy test và SHA256 từ metadata release chính thức PyPI;
  chưa kiểm tra thực thi trên runner Ubuntu/Python 3.12.
- Đã kiểm chứng adapter iPhone Viettel trên nguồn thật; các adapter đại lý khác chưa nghiệm thu. Chưa chạy migration Postgres hoặc gọi Supabase/Telegram thật.
  Unittest mock không chứng minh selector trang thật hay quyền DB đang hoạt động.

## Lịch tài chính và lịch sử 7 ngày

Tuần là thứ Hai–Chủ nhật, theo giờ Việt Nam. Mốc đã xác nhận: 05–11/10/2026 = W2Q1FY27. Mỗi quý 13 tuần, một FY 52 tuần; FY27 bắt đầu ngày 28/09/2026. Cấu hình nằm trong `config/fiscal_calendar.json`. Tuần ISO vẫn dùng làm khóa tương thích DB; nhãn hiển thị và metadata dùng lịch FY.

Chạy thêm `supabase/003_daily_history.sql` sau migration 001 và 002 trước khi dùng reporter mới. Migration giữ mỗi snapshot trong `daily_prices`; weekly_prices vẫn là giá mới nhất trong tuần. Backfill chỉ các dòng còn tồn tại, không phục hồi những ngày đã bị ghi đè. Reporter đọc snapshot bất biến để không mất run cũ. `daily_history.weekly_grid` dựng đủ 7 ngày, để trống ngày thiếu và chọn snapshot mới nhất nếu chạy lại trong cùng ngày. Báo cáo hằng ngày vẫn so sánh với tuần trước; phần xem đủ 7 ngày sẽ dùng daily_prices trong dashboard. Lịch chạy vẫn Chủ nhật 06:00 tìm link, hằng ngày 10:00 cào giá/CTKM và Telegram. Tuần đang diễn ra chưa được coi là tuần đã kết thúc.

Migration 003 chưa thực thi trên Supabase; cần chạy SQL Editor khi cấu hình dịch vụ. Không tự tạo lịch sử giả cho các ngày chưa chạy bot.

## Dashboard Web đã triển khai local

Mã nguồn nằm trong `web/`; xem `web/README.md` cho cấu hình, chế độ demo/live và deploy Vercel. Dashboard hỗ trợ bộ lọc, lịch FY, giá mới nhất, lịch sử 7 ngày, CTKM chi tiết, xuất Excel và đăng nhập Supabase. Dataset demo là 24 sản phẩm Viettel đã cào thực tế ở một ngày; không phải catalog đủ các chuỗi hoặc lịch sử 7 ngày đã thu thập. Dữ liệu live đọc từ `daily_prices`, cần chạy migration 003 trước.

### Sản phẩm theo dõi cá nhân

Dashboard có danh sách checkbox model theo Category, lưu lựa chọn cá nhân, áp dụng bảng giá/CTKM/Excel. Xem [docs/product-watchlist.md](docs/product-watchlist.md). Chạy migration 006 sau 001–005 trước khi dùng lưu theo tài khoản. Telegram nhóm dùng riêng `config/telegram-watchlist.json`; bot cào vẫn thu thập đủ catalog.

Kết quả lượt thử mẫu ban đầu: [docs/verification-2026-10-06.md](docs/verification-2026-10-06.md). Demo đã cập nhật đủ 5 kênh (592 giá thực tế trong mẫu), giữ cảnh báo TGDD Garmin chưa đầy đủ.

### Hãng và các model chưa có giá

Bộ lọc hãng áp dụng bảng giá/CTKM/issues/Excel. Danh sách model trong demo lấy thêm từ toàn bộ catalog, có khối và sheet riêng cho link chưa có kết quả giá. Xem [docs/brands-and-catalog.md](docs/brands-and-catalog.md). Lượt cào không giới hạn mẫu đang cập nhật demo theo từng kênh; trạng thái tại `artifacts/full-refresh/status.json`. Không chạy trùng lượt này.

### Giá và trạng thái hết hàng/ngừng kinh doanh

Bot giữ giá website hiển thị dù hết hàng, đặt trước; trạng thái không có giá vẫn được lưu với NULL. Link review được đọc lại mỗi ngày. Xem [docs/price-status.md](docs/price-status.md); chạy migration `supabase/007_price_and_status.sql` sau 001–006 trước khi dùng Supabase thật.
