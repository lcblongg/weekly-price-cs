# Cấu hình Supabase thật

> Trạng thái 06/10/2026: **chưa có credentials, chưa migration nào được chạy trên Supabase thật**, chưa có dữ liệu
> thật trong DB. Các bước dưới đây chưa được xác minh trên dịch vụ của bạn.
> Đã kiểm tra: chuỗi migration 001→005 chạy được trên PostgreSQL 16 nhúng (giả lập role Supabase) với 21 phép
> kiểm tra RPC/transaction/unique/RLS (`tools/check_migrations.py`). Index trigram (pg_trgm) không kiểm được ở môi trường đó.

## 1. Tạo dự án và chạy migration (một lần, đúng thứ tự)

Supabase → SQL Editor → New query, dán từng file và Run. Mỗi file tự `begin … commit`; lỗi giữa chừng sẽ rollback cả file.

1. `supabase/001_weekly_prices.sql` — bảng tuần, `scrape_runs`, RLS, RPC cũ.
2. `supabase/002_discovery.sql` — catalog bot Chủ nhật.
3. `supabase/003_daily_history.sql` — `daily_prices` + trigger lưu mỗi lượt (không ghi đè ngày).
4. `supabase/004_catalog_scope_and_issues.sql` — category/model/biến thể, `scrape_issues`, `commit_price_run`.
5. `supabase/005_per_chain_workers.sql` — catalog/lượt cào theo kênh (`commit_discovery_chain`, `commit_chain_price_run`).

Không chạy lại file đã chạy thành công (các lệnh `create`/`alter add column` sẽ báo trùng). Không có migration nào xóa dữ liệu.

## 2. Kiểm tra sau migration (SQL Editor)

```sql
-- Đủ bảng và cột mới
select table_name from information_schema.tables where table_schema='public'
  and table_name in ('weekly_prices','scrape_runs','discovery_runs','discovered_products','daily_prices','scrape_issues');
select column_name from information_schema.columns where table_name='scrape_runs' and column_name in ('chain_name','expected_count','issue_count');
-- RPC chỉ service_role được gọi
select routine_name from information_schema.routines where routine_schema='public'
  and routine_name in ('commit_discovery_chain','commit_chain_price_run','commit_price_run');
select grantee, privilege_type from information_schema.role_routine_grants
  where routine_name='commit_chain_price_run';            -- chỉ service_role (và postgres)
-- RLS bật
select relname, relrowsecurity from pg_class where relname in ('daily_prices','scrape_issues','discovered_products');
```

Phép thử ghi (không ảnh hưởng dữ liệu thật — chạy trong transaction rồi rollback):

```sql
begin;
set local role service_role;
select public.commit_chain_price_run('Phong Vũ', 2026, 41,
  '[{"chain_name":"Phong Vũ","sku":"pv-test","product_name":"Test","original_price":null,"promo_price":1000000,"promo_text":"","source_url":"https://phongvu.vn/test","category":"Điện thoại","brand":"","model_name":null,"variant_label":""}]',
  '[]', 1, null);
select count(*) from public.daily_prices where sku='pv-test';   -- 1
rollback;
```

## 3. Đăng nhập dashboard

Authentication → Providers → Email: bật; **tắt Sign-ups công khai** (policy cho mọi tài khoản đăng nhập đọc dữ liệu).
Authentication → Users → Add user cho từng CS. URL Configuration → Site URL = URL Vercel sau khi deploy.

## 4. Biến môi trường

| Nơi | Biến | Lấy ở đâu |
|---|---|---|
| GitHub → Settings → Secrets (Actions) | `SUPABASE_URL` | Project Settings → API → Project URL |
| | `SUPABASE_SERVICE_ROLE_KEY` | Project Settings → API → service_role (bí mật, chỉ cho bot) |
| | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | BotFather / getUpdates (xem README) |
| GitHub → Variables | `WEB_APP_URL` | URL Vercel |
| Vercel (Root Directory = `web`) | `NEXT_PUBLIC_DATA_MODE=live` | |
| | `NEXT_PUBLIC_SUPABASE_URL` | Project URL |
| | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | anon/public key (không dùng service_role) |
| Local (`.env`, không commit) | như GitHub Secrets | dùng launcher Python trong README, không `source .env` |

## 5. Lượt chạy đầu tiên (thủ công, theo thứ tự)

1. Actions → *Sunday product discovery* → Run workflow, `dry_run=true`, `chains=all` → tải artifact, xem `summary.json`.
2. Chạy lại với `dry_run=false` để công bố catalog. Kênh nào lỗi nguồn sẽ không công bố; chạy lại riêng kênh đó.
3. Actions → *Daily prices and Telegram report* → Run workflow, `send_report=false` → xem `report.html`.
4. Kiểm tra DB: `select chain_name, count(*) from daily_prices group by 1;` và dashboard (đăng nhập) có đủ 5 kênh.
5. Chạy lại với `send_report=true` cho nhóm Telegram nội bộ trước khi để lịch tự chạy.

## Lựa chọn model cá nhân

Sau 001→005, chạy `supabase/006_personal_watchlists.sql`. Chi tiết vận hành và cấu hình Telegram nhóm: [product-watchlist.md](product-watchlist.md). Migration 006 đã kiểm tra quyền RLS cục bộ với hai tài khoản mô phỏng; chưa xác minh trên Supabase thật.

### Snapshot chỉ có trạng thái

Sau 006, chạy `supabase/007_price_and_status.sql`. Đây là điều kiện để lưu bản ghi hết hàng/ngừng kinh doanh không có giá (NULL). Giá 0 và NULL không có trạng thái vẫn bị chặn. Chuỗi 001–007 đã qua 31 kiểm tra PostgreSQL cục bộ; chưa chạy trên Supabase thật. Xem [price-status.md](price-status.md).
