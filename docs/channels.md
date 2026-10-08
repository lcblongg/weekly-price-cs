# Năm bot theo kênh — vận hành, chạy lại, đọc log

Mỗi kênh là một **worker độc lập**, dùng chung: chuẩn hóa (`identity.py`), chính sách truy cập (`http_policy.py`,
`robots.py`), phân loại lỗi (`errors.py`), lưu Supabase (RPC `commit_discovery_chain`, `commit_chain_price_run`),
lịch tài chính (`business_calendar.py`) và báo cáo Telegram (`telegram_reporter.py`). Một kênh lỗi không làm
mất kết quả kênh khác.

| Slug CLI | Kênh | Adapter | Nguồn dữ liệu chính |
|---|---|---|---|
| `tgdd` (`mw`) | TGDD / MWG | `adapters/tgdd.py` | Danh mục: trình duyệt bấm "Xem thêm" (A/B 2 giao diện); chi tiết: JSON server-render, khóa màu `?code=` |
| `cellphones` (`cps`) | CellphoneS | `adapters/cellphones.py` | GraphQL công khai `api.cellphones.com.vn` (danh mục + giá theo mã màu, đọc 50 mã/request) |
| `viettel` (`vt`) | Viettel Store | `adapters/viettel_store.py` → `viettel.py`, `viettel_detail.py` | Widget danh mục + AJAX chi tiết chỉ đọc; HTML phân tích với JS tắt |
| `fpt` | FPT Shop | `adapters/fptshop.py` | API `papi.fptshop.com.vn/.../category`; chi tiết server-render `?sku=` |
| `phongvu` (`pv`) | Phong Vũ | `adapters/phongvu.py` | API tìm kiếm Teko; chi tiết `__NEXT_DATA__` |

**Phạm vi hãng** — `config/scope.json` (`scope.py`): hiện chỉ **Apple** (iPhone, iPad, MacBook, Apple Watch, AirPods).
Discovery chỉ dùng 24/86 nguồn Excel có Hãng = Apple (Viettel không có nguồn MacBook); worker giá bỏ link ngoài phạm vi
kể cả khi catalog cũ còn hãng khác. `inputs/data.xlsx` giữ nguyên; đặt `"brands": []` để cào lại mọi hãng.
Kiểm thử dữ liệu mẫu nhiều hãng dùng `WPCS_SCOPE=all`.

**Nơi chạy** — FPT Shop và Phong Vũ trả HTTP 403 với IP máy chủ GitHub (Azure) ngay từ `robots.txt`; MW không đọc được
bản ghi Apple đúng màu. Chỉ CellphoneS/Viettel đọc được từ GitHub-hosted runner (lượt 07/10/2026). Bot cần chạy
trên máy/mạng được các website chấp nhận (máy Mac vận hành), không đổi User-Agent hay né chặn.

## Lệnh chạy

```bash
cd /Users/lcblongg/weekly-price-cs
# Discovery (Chủ nhật) — một kênh, chạy thử không ghi DB:
.venv/bin/python discover_products.py --chain fpt --out artifacts/discovery --dry-run
# Nhiều kênh trong một tiến trình (chạy song song theo host):
.venv/bin/python discover_products.py --chain tgdd,cellphones --out artifacts/discovery --dry-run
# Thử nhanh có giới hạn: 2 nguồn đầu mỗi kênh
.venv/bin/python discover_products.py --chain all --limit-sources 2 --out /tmp/disc-test --dry-run

# Bot giá (hằng ngày) từ catalog Supabase của kênh:
.venv/bin/python scraper.py --chain phongvu --catalog discovery --out artifacts/prices
# Chạy thử từ catalog.json của discovery, giới hạn 20 link:
.venv/bin/python scraper.py --chain phongvu --catalog file --config artifacts/discovery/phongvu/catalog.json --limit 20 --dry-run

# Báo cáo chung (đọc summary.json của các worker):
.venv/bin/python telegram_reporter.py --summaries artifacts/prices --out artifacts/report --dry-run
# Không cần Supabase (đọc prices.json cục bộ):
.venv/bin/python telegram_reporter.py --summaries artifacts/prices --out artifacts/report --local
.venv/bin/python discovery_status.py --summaries artifacts/discovery
```

`--chain` nhận `tgdd|cellphones|viettel|fpt|phongvu|all`, lặp lại được hoặc ngăn cách dấu phẩy.
`--limit-sources`/`--limit` chỉ dùng với `--dry-run` (không bao giờ công bố dữ liệu bị cắt).

## Đầu ra (mỗi kênh một thư mục, chạy song song không ghi đè nhau)

```text
<out>/<slug>/
  catalog.json        # discovery: link ready/review kèm lý do
  sources.json        # discovery: từng nguồn Excel, số link, lỗi + error_kind
  product_links.xlsx  # discovery: file link cho người dùng
  prices.json         # bot giá: giá đọc được
  issues.json         # bot giá: link chưa có giá + reason + error_kind
  summary.json        # luôn được ghi, kể cả khi worker lỗi
  worker.log          # log riêng của kênh
```

`summary.json.status`: `ok` · `degraded` (đọc < 50% giá so với link ready; dữ liệu đọc được vẫn lưu) ·
`failed` (không lưu; xem `message`/`error_kind`). Discovery: `published=false` khi có nguồn lỗi —
**không công bố catalog thiếu**, bot giá tiếp tục dùng catalog thành công trước đó của kênh (`fetch_discovered(chain=…)`,
tối đa 8 ngày tuổi).

`error_kind`: `blocked` (HTTP 401/403 — bị chặn, không lưu giá), `rate_limited` (429), `robots`, `http_error`,
`network`, `out_of_stock`, `preorder`, `variant_changed`, `incomplete_listing`, `structure_changed`, `technical`.

## Đọc log

- `worker.log`: một dòng cho mỗi nguồn Excel (`link / ready / review / ngoài phạm vi`), cảnh báo nguồn lỗi, dòng `Kết thúc`.
- Log tiến trình chính (stdout) chỉ ghi tổng kết từng kênh; thư viện HTTP để mức WARNING, không in URL Telegram/khóa.
- Không có secret trong log: Supabase key/Telegram token chỉ đọc từ biến môi trường, không ghi ra file.

## Chạy lại một kênh lỗi

- Local: chạy lại lệnh với `--chain <slug>` và cùng `--out`; chỉ thư mục của kênh đó bị thay.
- GitHub: Actions → *Sunday product discovery* hoặc *Daily prices and Telegram report* → Run workflow →
  nhập `chains` = `tgdd` (hoặc `tgdd,fpt`). Các job kênh khác được bỏ qua; job tổng hợp vẫn chạy và nêu kênh thiếu.
  Chạy lại bot giá trong cùng ngày tạo thêm một lượt cào; dashboard lấy lượt mới nhất của ngày, lịch sử ngày trước không bị ghi đè.

## Lịch (GitHub Actions, giờ UTC)

| Workflow | Giờ Việt Nam | Cron UTC | Concurrency group |
|---|---|---|---|
| `discover_sunday.yml` | Chủ nhật 06:00 | `0 23 * * 6` (thứ Bảy 23:00 UTC) | `catalog-discovery` |
| `daily_prices.yml` | 10:00 mỗi ngày | `0 3 * * *` | `daily-prices` |

Matrix 5 kênh, `fail-fast: false`; job `summarize`/`report` chạy với `if: always()` và gửi **một** tin Telegram
nêu tình trạng từng kênh. Job cuối báo Failed nếu có kênh `failed/degraded` để người vận hành nhận email GitHub.
GitHub có thể trễ lịch khi tải cao.

## Khu vực, phiên, popup

- TGDD: không chọn tỉnh → giá theo khu vực mặc định website; không giữ cookie A/B giữa các request (mỗi lượt như khách mới);
  giao diện cũ ở trang chi tiết được hỏi lại tối đa 6 lần, vẫn giữ Crawl-delay 5s. Popup không chặn nút "Xem thêm".
- CellphoneS: `province_id=30` (Hà Nội, mặc định website). Giá Smember/HSSV không trừ.
- FPT/Phong Vũ/Viettel: giá mặc định website, không đăng nhập, không cookie phiên.
- Không vượt CAPTCHA, không giả danh trình duyệt (User-Agent tự xưng `WeeklyPriceCS/1.0`), không xoay IP.

## Biến môi trường

| Biến | Dùng ở | Ghi chú |
|---|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` | discovery, scraper, report | GitHub Secrets; không đặt vào Web |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | report, discovery_status `--send` | GitHub Secrets |
| `WEB_APP_URL` | report | GitHub Variable |
| `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_DATA_MODE` | web | Vercel |

Thứ tự migration: `001 → 002 → 003 → 004 → 005`.

## Kết quả kiểm chứng 06/10/2026 (dry-run, chưa ghi Supabase)

Discovery 86 nguồn = lượt đầy đủ + chạy lại nguồn lỗi, hợp nhất bằng `tools/merge_discovery.py`
(bản hợp nhất chỉ để thử, không công bố). Giá: mẫu 120 link ready/kênh, xoay vòng theo nguồn Excel.

| Kênh | Nguồn OK | Ready | Review | Ngoài phạm vi | Thử đọc giá | Có giá |
|---|---|---|---|---|---|---|
| TGDD | 18/19 | 614 | 79 | 2 | 120 | 120 |
| CellphoneS | 19/19 | 610 | 400 | 40 | 120 | 120 |
| Viettel Store | 14/14 | 235 | 62 | 0 | 120 | 120 |
| FPT Shop | 19/19 | 668 | 98 | 5 | 120 | 119 |
| Phong Vũ | 15/15 | 492 | 80 | 3 | 120 | 113 |

Còn lỗi: TGDD Garmin — trang công bố số sản phẩm dao động (33/65/72), 3 lượt đều chỉ đọc 51/65 model (< 80%).
Review chủ yếu là hết hàng; Viettel 35 đặt trước; TGDD 16 máy chưa mở bán (trang không có giá server-render).
Mẫu 600 link chưa chứng minh toàn bộ 2.619 link ready đọc được giá; thời gian cào toàn catalog chưa đo.
