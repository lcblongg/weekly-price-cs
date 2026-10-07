# Quản lý sản phẩm Apple trên máy local

Mở `/apple-products` từ dashboard. Chọn model để sửa, hoặc **Thêm model mới**. Nhập tên model chuẩn và một màu cần theo dõi. Màu để trống nghĩa là không lọc màu. Tên màu tương đương chỉ được thêm sau khi người quản lý xác nhận cùng màu.

**Kiểm tra dữ liệu hiện có** chỉ đọc snapshot local của 5 kênh, không gọi website. Số bản ghi đúng màu chỉ tính khi có chứng cứ model, mã biến thể, ID màu website và thời điểm xác minh; model thiếu trả về 0, không tạo giá. Đây không bảo đảm website hiện tại còn cùng giá.

**Lưu và áp dụng** lưu `config/apple_colors.json` và dựng lại bảng giá/trang nghiệm thu. Nút lên/xuống thay đổi thứ tự chung, cần lưu để áp dụng. Model mới được thêm quy tắc nhận diện tên literal khi worker Python khởi động. Không nhận iPhone 19 thành iPhone 19 Pro/Pro Max. Tên marketing khác, cách viết kích thước/chip khác cần quy tắc adapter riêng; không dùng tìm chuỗi mơ hồ.

Lưu không tự chạy bot, không khởi động lại tiến trình đang chạy. Bot chọn màu đọc cấu hình khi khởi động lần kế tiếp. Nếu chưa có sản phẩm trong catalog, cần chạy discovery trước. Sau đó chạy worker chọn màu tương ứng (`tools/scrape_mw_apple.py`, `tools/scrape_cps_apple.py`, `tools/scrape_remaining_apple.py`) theo quy trình local hiện có. Không thay đổi lịch Actions và không gửi Telegram từ trang này.

Đây là bản thử chạy local. API chỉnh sửa và kiểm tra bị khóa ngoài development; muốn dùng quản trị trên Vercel cần Auth, quyền quản trị và cấu hình lưu vào Supabase. Chưa có form URL thủ công và chưa có nút khởi chạy cào từ trình duyệt.

## Sửa và xóa

Danh sách có ô tìm kiếm và nút **Sửa**, **Xóa** cho từng model. Sửa điền dữ liệu vào form; **Lưu chỉnh sửa** áp dụng cấu hình mới. Xóa yêu cầu xác nhận tên model, lưu danh sách mới và dựng lại dashboard; **Hủy** không thay đổi cấu hình. Xóa chỉ bỏ quy tắc màu chung, không xóa catalog, SKU hoặc lịch sử giá. Model chưa cấu hình màu có thể vẫn xuất hiện trên bảng; danh sách theo dõi cá nhân quản lý việc ẩn model.

## Một nguồn quy chuẩn cho bot, discovery và web (cập nhật 07/10/2026)

- Lưu và Kiểm tra trên trang đều gọi Python (`tools/apply_apple_rules.py`, `tools/preview_apple_rule.py`), dùng
  `apple_rules.py` — cùng bộ nhận diện với 5 bot và discovery (`identity.describe` → `product_standard`).
- Model thêm mới được ghi hẳn quy tắc literal vào `config/apple_models.json` (`"generated": true`), nên TypeScript
  (thứ tự/hiển thị dashboard) đọc đúng quy tắc như Python. Test `tests/test_apple_rules.py` chạy cả hai ngôn ngữ và so kết quả.
- Trước khi ghi, mọi tên model chuẩn phải khớp đúng một quy tắc (chính nó). Ví dụ thêm "Apple Watch" bị từ chối vì
  nuốt "Apple Watch S11". Cấu hình lỗi không được ghi; hai file cấu hình ghi kiểu tạm-rồi-thay.
- **Sửa tên**: model có quy tắc viết tay giữ nguyên pattern (cùng tập sản phẩm) và ghi tên cũ vào `previous_names`,
  nên giá đã xác minh màu vẫn hiển thị. Model tự sinh thì sinh lại quy tắc từ tên mới; bằng chứng cũ không được dùng,
  cần bot xác minh lại.
- **Đổi màu**: bằng chứng xác minh cho màu cũ không bao giờ được tính là đúng màu mới; Kiểm tra báo
  "xác minh cũ cho model/màu khác (không dùng)" và ô giá trống cho tới khi bot xác minh màu mới.
- **Xóa**: bỏ quy chuẩn màu và quy tắc tự sinh; quy tắc viết tay giữ lại. Catalog/giá không bị xóa; model vẫn hiện
  với nhãn "Chưa cấu hình màu".
- **Kiểm tra** báo theo kênh: số link trong catalog discovery (0 = cần chạy discovery trước), số bản ghi giá cùng model,
  số bản ghi đúng màu có bằng chứng, màu nguồn đang thấy. Chỉ đọc file local, không gọi website.

Đã kiểm thử đầu-cuối qua API local (thêm → kiểm tra → đổi màu nháp → đổi tên tự sinh → đổi tên viết tay → đổi thứ tự →
xóa → khôi phục): cấu hình và `web/data/comparison.json` trở lại y nguyên sau khi khôi phục.

## URL sản phẩm tùy chọn theo kênh (cập nhật 07/10/2026)

Trong form model có mục **URL sản phẩm tùy chọn theo kênh** cho MW, CPS, FPT, Viettel, Phong Vũ: mỗi dòng một URL trang
chi tiết; thêm nhiều dòng để đủ dung lượng/cấu hình, xóa dòng để bỏ. Lưu cùng model trong `config/apple_colors.json`
(trường `urls`). Kiểm tra định dạng nằm trong `apple_rules.normalize_url` (dùng chung):

| Kênh | Domain | Trang chi tiết hợp lệ | Tham số giữ lại |
|---|---|---|---|
| MW | thegioididong.com | `/dtdd|may-tinh-bang|laptop|dong-ho-thong-minh|tai-nghe/<slug>` | `code` |
| CPS | cellphones.com.vn | `/<slug>.html` | `product_id` |
| FPT | fptshop.com.vn | `/<nhóm>/<slug>` | `sku` |
| Viettel | viettelstore.vn | `…-pid<số>.html` | — |
| Phong Vũ | phongvu.vn | `/<slug>--s<số>` hoặc `--p<số>` | `sku` |

Chỉ nhận https, đúng domain, không thông tin đăng nhập; tracking/fragment bị bỏ; tối đa 20 URL/kênh/model.
Một URL sai làm cả lần lưu bị từ chối (cấu hình không đổi). FPT dùng chung dạng đường dẫn cho trang danh mục và
trang chi tiết — trang danh mục sẽ bị đánh dấu ở bước kiểm tra.

**URL chỉ là nguồn đầu vào.** Ba worker (`tools/scrape_mw_apple.py`, `tools/scrape_cps_apple.py`,
`tools/scrape_remaining_apple.py`) đọc URL nhập tay cùng link discovery và đưa qua đúng bước xác minh cũ:
đọc trang → model chuẩn phải khớp (`product_standard`) → chọn đúng biến thể màu (màu chuẩn, tên tương đương đã xác nhận,
bảng tên đã đối chiếu của adapter) → đọc giá → đối chiếu lại SKU/model/màu. Không có giá hay trạng thái nào được tạo từ URL.

**CPS:** URL không được coi là SKU. Bot đọc các mã màu trong khối chọn màu của trang, tra GraphQL lấy `parent_id`,
kiểm tra đường dẫn của sản phẩm cha trùng URL và mã màu thuộc cha (`apple_sources.cps_resolve`). `product_id` trong URL
phải thuộc danh sách màu của trang.

**Trạng thái từng URL** (`artifacts/apple-url-checks.json`): Chưa kiểm tra · Hợp lệ · Sai model · Chưa tìm thấy màu ·
Lỗi truy cập · URL không hợp lệ. Kết quả cũ hết hiệu lực khi đổi màu yêu cầu. Nút **Kiểm tra URL đã lưu**
(`tools/check_apple_urls.py`) đọc trang thật của các URL đã lưu (robots.txt, giãn cách theo host, khóa chống chạy trùng),
không đọc/ghi giá, không gửi Telegram. Worker cũng cập nhật trạng thái khi dùng URL ở lượt chạy.

Chạy thử cô lập (không đụng cấu hình/dữ liệu thật):
`WPCS_APPLE_COLORS=/tmp/x/apple_colors.json WPCS_URL_CHECKS=/tmp/x/checks.json WPCS_APPLE_OUT_DIR=/tmp/x/out .venv/bin/python tools/scrape_remaining_apple.py fpt`

Kiểm chứng 07/10/2026 trên trang thật (cấu hình tạm): iPhone 17 Pro Max — URL đúng hợp lệ ở cả 5 kênh; URL iPhone 17
bị đánh "Sai model" ở MW/CPS/FPT/Phong Vũ; URL MW không tồn tại → "Lỗi truy cập" (HTTP 404); iPhone 17 với màu Cam vũ trụ
→ "Chưa tìm thấy màu". Worker cô lập ghi giá đúng màu: MW 4, CPS 4, FPT 4, Viettel 4, Phong Vũ 2 (đúng số dung lượng
Phong Vũ đang có trong catalog), 0 giá ≤ 0.

## Xác minh và cập nhật giá cho một model (cập nhật 07/10/2026)

Trong form model đã lưu có khối **Xác minh và cập nhật giá**: chọn một hoặc nhiều kênh rồi bấm chạy. Chỉ bật trên máy
local (development) như các API quản lý khác.

- **Chỉ cấu hình đã lưu:** nút khóa khi form còn thay đổi chưa lưu hoặc đang có job khác.
- **Dùng nguyên worker hiện có** (`scrape_mw_apple.py`, `scrape_cps_apple.py`, `scrape_remaining_apple.py`) ở chế độ cô lập:
  cấu hình chụp lại chỉ gồm model được chọn, đầu ra riêng `artifacts/apple-jobs/<id>/out/<kênh>/`, log `<kênh>.log`.
  Không viết lại logic nhận diện model/màu.
- **Chạy nền** (`tools/apple_job.py`, tách khỏi tiến trình web): tải lại trang hoặc dev server khởi động lại vẫn xem được
  tiến độ (`state.json`). Trạng thái mỗi kênh: Chờ · Đang chạy · Thành công · Thành công một phần · Lỗi, kèm giờ bắt đầu/xong,
  lý do, số SKU có giá / chỉ có trạng thái / cần kiểm tra.
- **Chống chạy trùng:** một job tại một thời điểm; khóa theo kênh `artifacts/locks/apple-<kênh>.lock` dùng chung với worker
  chạy từ CLI (worker CLI giờ cũng giữ khóa; kênh bận thì thoát mã 3); thêm quét tiến trình để phát hiện worker khởi chạy
  trước khi có khóa. Job mồ côi (tiến trình chết) được đánh dấu lỗi, không chặn mãi.
- **Công bố:** từng bản ghi phải có chứng cứ đúng model, mã SKU = mã biến thể đã chọn, đúng màu yêu cầu, thời điểm xác minh;
  giá là số > 0 hoặc NULL kèm nhãn trạng thái website. Giá 0/NULL không trạng thái không bao giờ được công bố.
  Chỉ thay bản ghi của đúng model ở đúng kênh trong `artifacts/<kênh>-apple-selected/`; model và kênh khác giữ nguyên.
- **Cấu hình đổi trong lúc chạy** (màu, tên tương đương, URL, quy tắc nhận diện): không công bố, ghi rõ lý do.
- **Khi lỗi:** giữ giá thành công trước đó, ghi `last_failed_update` vào summary kênh và cảnh báo "giữ N bản ghi cũ (mới nhất lúc …)".
  SKU không đọc lại được trong lượt thành công một phần vẫn giữ nhưng gắn `stale_since`; dashboard hiện "Dữ liệu cũ — …" trong chi tiết SKU.
- Sau khi công bố, dashboard được dựng lại (`build_mw_review.py` → `comparison.json`). Không ghi Supabase, không gửi Telegram.

Kiểm thử cô lập (không đụng dữ liệu thật): đặt `WPCS_JOB_ARTIFACTS`, `WPCS_APPLE_COLORS`, `WPCS_URL_CHECKS`; dev server thứ hai:
`WPCS_NEXT_DIST=.next-test <các biến trên> npx next dev --port 3005`.

Đã kiểm chứng 07/10/2026 bằng dữ liệu thật trong môi trường cô lập: CPS iPhone 17 Pro Max 4 SKU có giá, 92 bản ghi model khác
và 4 kênh còn lại không đổi; MacBook Neo FPT thành công + Viettel lỗi (chưa có link) không ảnh hưởng nhau; job thứ hai bị chặn;
worker CLI MW/Viettel bị phát hiện, kênh FPT không liên quan vẫn chạy; khóa kênh bị giữ → kênh lỗi; đổi tên màu tương đương giữa
lượt MW → đọc được 4 giá nhưng không công bố; giao diện: khóa khi chưa lưu, tải lại thấy tiến độ, mobile không tràn ngang.

Giới hạn: chưa có hàng đợi (job thứ hai phải chờ); chưa có nút hủy job đang chạy; quét tiến trình chỉ nhận đúng 3 script worker
Apple (bot giá/discovery toàn catalog dùng dữ liệu khác, không bị chặn); trên Vercel chưa có Auth/quyền quản trị nên chức năng bị khóa.

## Khóa phối hợp các luồng (07/10/2026)

Job Apple, worker Apple chạy CLI, `scraper.py` toàn catalog và `discover_products.py` dùng chung khóa theo kênh trong `artifacts/locks/apple-<slug>.lock`. Job giữ khóa từ trước khi khởi chạy worker đến khi công bố, truyền FD khóa cho worker con; worker con không mở khóa của runner. Kênh đang bận từ chối chạy, không ghi đè snapshot; kênh khác vẫn độc lập. Bộ quét tiến trình nhận cả discovery và bot giá cũ chưa giữ khóa.

Tạo job được tuần tự hóa bằng khóa riêng. Dựng comparison cũng có khóa chung để các lần dựng khác kênh không công bố ngược thứ tự. Khóa là trên một máy; không thay thế kiểm soát giao dịch trên Supabase hoặc khóa giữa nhiều máy chạy Actions.

Bot giá giữ file giá thành công trước khi một lượt không đọc được giá/trạng thái nào. Khi có lỗi một phần, SKU lỗi có bản cũ được giữ kèm `stale_since`/`stale_reason`. Lượt lỗi ghi `last_failed_update` trong summary. Discovery gặp nguồn lỗi giữ catalog cũ và lưu thử nghiệm vào `catalog.failed.json`; summary và diagnostics ghi rõ lượt mới lỗi. Không đánh dấu catalog giữ lại là dữ liệu đầy đủ mới.
