# Hai bot: tự tìm link Chủ nhật, cào giá/CTKM hằng ngày

> Cập nhật 06/10/2026: cả hai bot đã tách thành 5 worker theo kênh. Lệnh hiện hành và lịch: [channels.md](channels.md).
> Các mục lịch sử bên dưới (pilot iPhone Viettel, selector placeholder) đã được thay bằng adapter 5 kênh.

Đầu vào hiện tại là `inputs/data.xlsx` bạn đã gửi: 5 đơn vị, 86 nguồn.
Xem mục “Cập nhật đầu vào Excel của bạn” và kết quả thử quét ở cuối trang.

Không cần gửi danh sách URL từng sản phẩm. Mỗi đại lý chỉ cấu hình trang danh mục,
quy tắc URL và adapter DOM một lần. Sau đó bot tự tìm các link mới trong phạm vi đã cấu hình.

## Luồng đã bổ sung

```text
Chủ nhật 06:00 giờ Việt Nam (thời điểm mặc định, có thể đổi)
  Trang danh mục các đại lý
    → Playwright scroll / phân trang href nếu cấu hình
    → lọc URL sản phẩm + bỏ tracking + loại link trùng
    → đọc tên trên trang sản phẩm, nhận diện SKU
    → kiểm tra selector giá/CTKM
    → Supabase discovery_runs + discovered_products
      • ready: đủ điều kiện bot giá sử dụng
      • review: ghi rõ lý do; không coi là dữ liệu giá

Mỗi ngày 10:00 giờ Việt Nam, cả 7 ngày/tuần
  scraper.py --catalog discovery
    → catalog mới nhất trong Supabase, tuổi không quá 8 ngày
    → chỉ link ready, kiểm tra lại biến thể/giá/CTKM
    → transaction weekly_prices
    → telegram_reporter.py, bao gồm số link review không được báo cáo giá
```

Workflow Chủ nhật lưu catalog riêng, không cần push JSON tự động vào GitHub hoặc tải artifact
của workflow khác. Các snapshot danh mục bất biến để biết bot hằng ngày sử dụng đợt nào.
Khi một trang danh mục lỗi, bot không commit catalog một phần. Bot giá chỉ dùng catalog đã
commit đầy đủ; nếu Chủ nhật lỗi vẫn có thể dùng lần thành công trong 8 ngày, không bảo đảm
mọi tuần có catalog mới. Meta tuổi catalog được lưu artifacts/catalog-used.json.

Một nguồn có link review vẫn nằm trong catalog, kèm lý do. Điều đó không có nghĩa crawler
đã theo dõi được toàn bộ sản phẩm nguồn đó. Telegram nêu số link đủ điều kiện và số cần kiểm tra.
Nếu không có ready link, workflow khám phá báo Failed sau khi lưu danh sách review để xử lý.
Bot giá cũng từ chối catalog không có ready hoặc dữ liệu quá cũ.

## File mới / thay đổi

- `discover_products.py`: khám phá và kiểm chứng URL.
- `catalog.py`: chuẩn hóa URL, nhận diện SKU và đọc catalog Supabase có phân trang.
- `config/discovery_sources.json`: cấu hình theo đại lý, không theo từng sản phẩm.
- `supabase/002_discovery.sql`: schema + RPC nguyên tử + RLS cho bot.
- `.github/workflows/discover_sunday.yml`: lịch khám phá Chủ nhật.
- `scraper.py`: mặc định đọc catalog tự động; `--catalog file` giữ cách nhập thủ công dự phòng.
- Workflow hằng ngày chuyển sang `--catalog discovery`.
- Reporter hiển thị phạm vi catalog, không âm thầm báo cáo link ready như toàn bộ link tìm được.

## Phạm vi mẫu hiện tại

Trang ngành hàng iPhone tại TGDD, FPT Shop và CellphoneS đã có trong cấu hình. Các URL
được đối chiếu với nguồn công khai của đại lý; điều đó chưa chứng minh DOM có thể cào bằng
adapter đã cấu hình. Viettel Store/Phong Vũ và các ngành iPad/MacBook/Watch chưa có adapter mẫu.

Quy tắc định danh ban đầu hỗ trợ iPhone số đời, e, Air, Pro, Pro Max, Plus, Mini + dung lượng.
Tên thiếu bộ nhớ, chứa nhiều model/bộ nhớ, hàng cũ/xách tay hoặc chưa nhận diện được → review.
Không dùng tên chuẩn hóa tùy tiện làm SKU chung giữa chuỗi.
Mở rộng iPad/MacBook/Watch cần thêm parser cho generation, chip, bộ nhớ, kích thước, kết nối,
RAM, cấu hình và tình trạng; không tự đoán các thuộc tính này bằng AI từ tên thiếu thông tin.

`identity_scope` là suffix SKU áp dụng cho nguồn đã nghiệm thu (ví dụ `vn-new`). Nếu màu hoặc
khu vực quyết định giá, adapter phải chọn/kiểm tra đúng biến thể đó và thêm scope tương ứng.
Phiên bản này chưa tự liệt kê toàn bộ dung lượng/màu nằm trong một trang sản phẩm.
Không đồng nghĩa một URL sản phẩm sẽ cung cấp mọi biến thể. Nhiều URL cùng SKU đều được
đưa vào review, không tự chọn URL đầu tiên hoặc giá rẻ nhất rồi bỏ qua khác biệt.

## Làm một lần để bật hệ thống

1. Tạo Supabase project nếu chưa có.
2. Chạy `001_weekly_prices.sql` một lần trên dự án mới.
3. Chạy `002_discovery.sql` một lần sau đó. Không chạy lại 001 nếu đã chạy thành công.
4. Điền SUPABASE_URL và SUPABASE_SERVICE_ROLE_KEY vào `.env` local / GitHub Secrets.
5. Nghiệm thu adapter từng đại lý trong `config/retailer_adapters.json`:
   - Trang ngành hàng lấy từ cột Link trong Excel; không nhập lại `seeds` thủ công.
   - `category_url_patterns`: regex theo danh mục, phân biệt URL sản phẩm với ngành hàng/tin tức/phụ kiện.
   - `link_selector`: tốt nhất chọn link trong product card, thay vì mọi a[href].
   - `next_selector`: nếu nguồn phân trang bằng link href, chọn link trang tiếp theo duy nhất;
     trang cuối phải không còn phần tử khớp.
   - `scroll_rounds`: scroll lazy load có giới hạn.
   - `selectors`: tên gồm biến thể đang chọn, giá bán trực tiếp, giá gốc tùy chọn, vùng CTKM.
   - `adapter_verified`: chỉ đổi true khi đã đối chiếu DOM nguồn thật.
   - `variant_scope_verified`: chỉ true khi biến thể/thị trường/tình trạng mặc định của nguồn
     đã được xác minh và phù hợp identity_scope.
6. Chạy preview discovery:

```bash
cd /Users/lcblongg/weekly-price-cs
source .venv/bin/activate
python -m pip install --require-hashes -r requirements.txt
python -m playwright install chromium
python discover_products.py --chain all --out artifacts/discovery --dry-run
```

`--dry-run` không ghi Supabase và không cần credential. Xem artifacts/discovery.json.
Mẫu có adapter_verified=false, vì vậy có thể tìm link nhưng sẽ không tự nhận ready.
Không đổi cờ sang true chỉ để vượt chặn cấu hình: các selector hiện vẫn là placeholder.

7. Khi preview đúng, dùng launcher `.env` trong README, thay lệnh scraper bằng:

```python
subprocess.run(['python', 'discover_products.py', '--chain', 'all', '--out', 'artifacts/discovery'], check=True)
subprocess.run(['python', 'scraper.py', '--chain', 'all', '--catalog', 'discovery', '--out', 'artifacts/prices'], check=True)
subprocess.run(['python', 'telegram_reporter.py', '--summaries', 'artifacts/prices', '--dry-run'], check=True)
```

8. Push code lên GitHub. Chạy manual `Sunday product discovery` với dry_run=true;
   kiểm tra artifact rồi bỏ chọn để publish catalog vào Supabase.
9. Chạy workflow hằng ngày bằng manual và không bật Send report để kiểm tra DB/report.
10. Sau khi nghiệm thu, workflow lịch sẽ chạy tự động. Chưa deploy/tạo lịch thật từ máy này.

## Giới hạn và cách vận hành

- Bot khám phá không tự hiểu mọi website: cần adapter ổn định theo chuỗi, cấu hình một lần
  rồi bảo trì khi DOM đổi. Người dùng không cần nhập URL của từng model.
- Nguồn dùng nút “Xem thêm”/AJAX không có href cần adapter load-more riêng trước khi
  coi kết quả là toàn bộ catalog. Scroll có giới hạn chỉ lấy link đã render, không chứng minh
  catalog đã hết. Bản này hỗ trợ phân trang href; không tự bấm nút không được cấu hình.
- Regex có thể bỏ sót pattern mới. Có thể mở rộng nguồn bằng sitemap/feed/API được cho phép;
  bản hiện tại sử dụng trang danh mục. Không đi theo link tùy ý khắp website.
- Có giới hạn số trang/link để tránh crawl vô hạn; chạm giới hạn thì dừng thay vì truncate im lặng.
- Discovery không cập nhật/xóa catalog cũ trực tiếp: commit run mới và bot giá dùng run mới nhất.
  Link không xuất hiện lần này không được cào lần này; lịch sử giá tuần cũ vẫn giữ nguyên.
- Tôn trọng robots.txt, không vượt CAPTCHA. Giới hạn 2 giây giữa sản phẩm.
- Chủ nhật cũng cào giá và gửi Telegram lúc 10:00; bot luôn lấy lại giá/CTKM ở thời điểm chạy.
- GitHub schedule có thể trễ; đặt workflow trên default branch và bật thông báo failure.
- Snapshot discovery tích lũy; cần chính sách retention sau khi biết quy mô thực tế.
- Cron giá/Telegram là `0 3 * * *` (10:00 Việt Nam). Không có một lịch gửi Telegram thứ Hai riêng.
- Chạy hằng ngày nhưng schema hiện tại vẫn UPSERT snapshot tuần; các ngày trong cùng tuần
  ghi đè nhau và reporter vẫn so với tuần trước. Bảng lịch sử ngày và so sánh ngày liền trước
  sẽ được bổ sung trong bước triển khai tiếp theo, không được coi là đã hoàn thành.

## Kiểm chứng đã thực hiện

22 unittest đạt, gồm loại tracking/giữ query biến thể, SKU khác nhau theo model/dung lượng,
model không xác định/hàng cũ phải review, nhiều URL cùng SKU phải review, catalog quá cũ,
catalog thiếu dòng và các kiểm thử báo cáo giá trước đó. Python compileall đạt.
Chưa chạy migration lên Supabase, chưa thử nguồn thật, chưa deploy GitHub Actions.

## Cập nhật đầu vào Excel của bạn

File `inputs/data.xlsx` đã được sao chép từ file bạn gửi, không thay đổi bản gốc.
Workbook có 86 nguồn: MWG 19, CPS 19, FPT 19, VT 14, PV 15.
Tên sheet ánh xạ lần lượt tới TGDD, CellphoneS, FPT Shop, Viettel Store và Phong Vũ.
Cột bắt buộc là Danh mục, Hãng, Link; dòng trống được bỏ qua, hyperlink Excel được đọc đúng.
Bot giữ query lọc hãng/tìm kiếm, không chỉ lấy phần URL trước dấu hỏi.

- `import_sources.py`: đọc workbook và tạo artifacts/sources.json + input-summary.json.
- `config/retailer_adapters.json`: adapter theo đại lý, quy tắc URL theo danh mục.
- `discover_products.py`: mặc định đọc inputs/data.xlsx, không còn danh sách 3 nguồn iPhone cứng.
- `excel_export.py`: xuất artifacts/product_links.xlsx trên GitHub runner. Runner không có
  Artifact Tool nội bộ của Codex; exporter dùng openpyxl portable, dependency đã khóa hash.
- File đầu ra gồm Link sản phẩm và Nguồn quét. Metadata hãng/danh mục là phạm vi nguồn quét,
  không tự khẳng định hãng/danh mục của từng sản phẩm đã xác minh.
- Khi một nguồn lỗi, bot vẫn ghi chẩn đoán và file kết quả quét được, đánh dấu nguồn lỗi;
  không xuất bản một catalog thiếu nguồn vào Supabase.

Kiểm tra workbook không cần truy cập web:

```bash
python import_sources.py --input inputs/data.xlsx
```

Chạy thử toàn bộ nguồn, không ghi DB hoặc gửi Telegram:

```bash
python discover_products.py --chain all --input inputs/data.xlsx --out artifacts/discovery --dry-run
```

Để cập nhật nguồn sau này, sửa/thay inputs/data.xlsx rồi push commit mới lên GitHub.
Workflow Chủ nhật đọc file này từ checkout; không đọc đường dẫn Downloads trên máy cá nhân.
File XLSX đầu ra tải tại Actions → run Chủ nhật → artifact product-discovery.
Hiện chưa cấu hình Supabase nên catalog chưa được publish và lịch trên GitHub chưa kích hoạt.

Phạm vi Excel gồm nhiều hãng và nhiều nhóm sản phẩm. Bot tìm link cho tất cả nguồn,
nhưng parser SKU chuẩn ban đầu vẫn mới hỗ trợ iPhone. Các nhóm khác giữ nguyên trong file
và vào review cho đến khi bổ sung rule định danh/adapter; không tự lấy tên rút gọn làm SKU.
Các regex URL của VT/PV và selector product-card cần nghiệm thu theo HTML thật, không được
coi là production chỉ vì đã đọc được URL từ Excel.

### Lần thử quét đầu vào ngày 05/10/2026

Đã kiểm tra một nguồn iPhone của mỗi đơn vị: TGDD 29 link, CellphoneS 20,
FPT Shop 12, Phong Vũ 1. Tổng 62 link ứng viên. Viettel Store trả HTTP 403.
Đây là thử 5/86 nguồn, không phải catalog đầy đủ. Tất cả link đang review do chưa
nghiệm thu selector giá/CTKM và biến thể. Không ghi Supabase và không gửi Telegram.
Input checksum giữ nguyên so với file Downloads người dùng gửi; 22 unittest đạt.


## Sửa lỗi HTTP 403 ở danh mục Viettel

Chromium tại máy thử nghiệm nhận HTTP 403 từ trang danh mục, trong khi HTTP thông thường nhận 200. Adapter `adapters/viettel.py` đọc HTML nguồn và gửi đúng tham số tới widget công khai `/Site/_Sys/GetUserControlAsync.aspx` mà trang tự gọi. Không cần proxy, cookie chống bot hoặc thay đổi IP. `discovery_transport: viettel_http` trong cấu hình tự động chọn adapter khi nhập Excel.

Adapter đọc mã danh mục/hãng/từ khóa từ trang nguồn, kiểm tra robots.txt, phân trang theo `RecordCountSP`, xác minh hãng và giới hạn số sản phẩm. Phản hồi 403, sai cấu trúc, thiếu trang hoặc lặp sản phẩm vẫn được báo lỗi; không biến chúng thành danh mục rỗng. AirPods dùng widget tìm kiếm với từ khóa khớp URL Excel.

Kiểm tra trực tiếp ngày 05/10/2026: cả 14 nguồn Viettel trong Excel thành công; kết quả lưu ở `artifacts/viettel-validation.json`. Đây là kết quả tại máy local; chưa xác minh trên runner GitHub Actions. Việc tìm link thành công không xác nhận selector giá/CTKM của trang chi tiết. Các cờ xác minh sản phẩm vẫn giữ nguyên để tránh đưa giá chưa kiểm chứng vào báo cáo.

## Quét thử giá và CTKM danh mục Viettel

Chạy từ thư mục dự án:

```bash
.venv/bin/python preview_viettel_prices.py
```

Bot đọc đúng 14 nguồn Viettel trong Excel, dùng adapter HTTP đã kiểm tra, lưu `artifacts/viettel-price-preview.json` và trang tra cứu cục bộ `artifacts/viettel-price-preview.html`. Không cần secret. Thao tác này không ghi Supabase và không gửi Telegram. Mỗi dòng lưu thời điểm, nguồn danh mục, link sản phẩm, giá gốc/giá bán hiển thị, ghi chú CTKM và trạng thái review. Giá liên hệ hoặc giá không hợp lệ được giữ null với `price_error`, không dùng 0. CTKM có điều kiện được giữ trong ghi chú, không khấu trừ vào giá bán.

Kiểm tra ngày 05/10/2026: 298 sản phẩm, 290 sản phẩm có giá hợp lệ, 8 sản phẩm cần kiểm tra giá; cả 14 nguồn thành công. Endpoint chi tiết `/AjaxAction.aspx` với `get-block-info-product` và `get-list-rule-by-product` trả 404 tại máy kiểm tra. Vì chưa xác minh CTKM chi tiết và màu mặc định, tất cả dòng vẫn `review`, `promotion_complete=false`, `production_ready=false`. Không bật cờ adapter_verified/variant_scope_verified chỉ từ kết quả này. Phần giá chính thức tiếp tục cần nghiệm thu trang chi tiết trước khi vào báo cáo.

## Adapter giá/CTKM chi tiết Viettel — cập nhật 05–06/10/2026

Lỗi 404 ở thử nghiệm trước đã được xác định: request AJAX thiếu header `X-Requested-With: XMLHttpRequest`. Với header và Referer đúng theo trang nguồn, các endpoint chi tiết trả 200. `adapters/viettel_detail.py` dùng các request chỉ đọc mà website công bố: thông tin sản phẩm, danh sách mã màu, API giá theo mã màu, ưu đãi ERP và ưu đãi thanh toán. Không thực thi JavaScript từ website; fragment HTML được phân tích trong context Chromium tắt JavaScript và chặn tải tài nguyên phụ.

Quét toàn bộ một danh mục iPhone Viettel (30 link): 24 ready, 6 review. Sáu link gồm 1 timeout, 1 đặt trước chưa hỗ trợ và 4 trang không khớp contract model/URL. Sau đó bot giá đã cào lại cả 24 link ready thành công ở chế độ dry-run. Dữ liệu này là pilot **1/86 nguồn**, không phải catalog toàn bộ Excel.

Cấu hình native được bật trong `config/retailer_adapters.json`; các nhóm khác iPhone vẫn review vì chưa có parser định danh. Discovery khóa `variant_rule_id`, `variant_erp_id` và `source_product_name`. SKU Viettel chứa mã màu để so sánh lịch sử đúng biến thể; chưa dùng SKU này để tự ghép so sánh cùng model giữa nhiều đại lý. Bot giá kiểm tra lại tên/ERP, không chuyển sang màu mặc định mới một cách âm thầm. Hết hàng, đặt trước, ưu đãi ERP cần lựa chọn, sai cấu trúc hoặc thiếu CTKM thanh toán đều phải kiểm tra trước khi ghi dữ liệu.

Các file pilot:
- `artifacts/viettel-detail-discovery.json`: 30 link và lý do review.
- `artifacts/viettel-ready-products.json`: cấu hình 24 sản phẩm đã khóa màu.
- `artifacts/viettel-detail-prices.json`: giá/CTKM chi tiết 24 sản phẩm.
- `artifacts/viettel-detail-preview.html`: bảng tra cứu có tìm kiếm.
- `artifacts/viettel-telegram-preview.html`: bản báo cáo thử, chưa gửi Telegram. Chưa có dữ liệu tuần trước nên không suy diễn giảm giá hay CTKM mới.

Chạy lại bot giá trên catalog pilot, không ghi DB:

```bash
.venv/bin/python scraper.py --chain viettel --catalog file --config artifacts/discovery/viettel/catalog.json --dry-run
```

Catalog pilot bị gitignore và không thay thế catalog toàn bộ từ bot Chủ nhật. Chưa chạy SQL trên Supabase hoặc gửi Telegram thật; lịch GitHub chưa triển khai. TGDD đã khảo sát trang chi tiết và đọc được giá/khuyến mãi hiển thị, nhưng adapter TGDD chưa nghiệm thu.
