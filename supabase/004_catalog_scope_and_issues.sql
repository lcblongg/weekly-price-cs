-- Chạy SAU 001 → 002 → 003. Không chạy lại các file trước.
-- Mục tiêu:
--  1) Lưu nhóm hàng / hãng / model / biến thể cùng giá để dashboard lọc đúng mọi nhóm sản phẩm.
--  2) Lưu sản phẩm KHÔNG đọc được giá (hết hàng, đổi cấu trúc, link cần kiểm tra) kèm lý do,
--     để dashboard hiển thị thay vì làm chúng biến mất.
--  3) Một lượt cào = một transaction: giá thành công + danh sách lỗi cùng commit hoặc cùng rollback.
begin;

alter table public.weekly_prices
  add column category text not null default '',
  add column brand text not null default '',
  add column model_name text,
  add column variant_label text not null default '';
alter table public.daily_prices
  add column category text not null default '',
  add column brand text not null default '',
  add column model_name text,
  add column variant_label text not null default '';
alter table public.scrape_runs
  add column expected_count integer check (expected_count >= 0),
  add column issue_count integer not null default 0 check (issue_count >= 0),
  add column catalog_run_id uuid references public.discovery_runs(id);
create index daily_prices_category on public.daily_prices(week_start, category, chain_name);

-- Trigger lưu lịch sử ngày giờ chép thêm metadata. Không đổi dữ liệu cũ.
create or replace function public.capture_daily_price() returns trigger
language plpgsql security invoker set search_path = '' as $$
declare captured timestamptz;
begin
  select completed_at into strict captured from public.scrape_runs where id=new.run_id;
  insert into public.daily_prices(run_id,captured_at,business_date,week_start,chain_name,sku,
    product_name,original_price,promo_price,promo_text,source_url,category,brand,model_name,variant_label)
  values(new.run_id,captured,(captured at time zone 'Asia/Ho_Chi_Minh')::date,
    date_trunc('week',captured at time zone 'Asia/Ho_Chi_Minh')::date,
    new.chain_name,new.sku,new.product_name,new.original_price,new.promo_price,new.promo_text,new.source_url,
    new.category,new.brand,new.model_name,new.variant_label);
  return new;
end;
$$;

create table public.scrape_issues (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.scrape_runs(id),
  captured_at timestamptz not null,
  business_date date not null,
  week_start date not null check (extract(isodow from week_start) = 1),
  stage text not null check (stage in ('catalog', 'price')),
  chain_name text not null,
  sku text not null default '',
  product_name text not null default '',
  category text not null default '',
  brand text not null default '',
  model_name text,
  source_url text not null check (source_url ~ '^https://'),
  reason text not null check (length(trim(reason)) > 0),
  unique (run_id, chain_name, source_url, sku)
);
create index scrape_issues_week on public.scrape_issues(week_start, business_date, chain_name);
alter table public.scrape_issues enable row level security;
revoke all on public.scrape_issues from anon, authenticated;
grant select on public.scrape_issues to authenticated;
create policy cs_read_issues on public.scrape_issues for select to authenticated using (true);
grant select, insert on public.scrape_issues to service_role;
grant usage, select on sequence public.scrape_issues_id_seq to service_role;

-- Lượt cào hằng ngày: chấp nhận một phần sản phẩm lỗi (ghi vào scrape_issues) thay vì bỏ cả ngày.
-- p_expected = số link trong catalog; bắt buộc bằng số giá + số lỗi để không mất dòng âm thầm.
create function public.commit_price_run(p_year integer, p_week integer, p_rows jsonb, p_issues jsonb,
                                        p_expected integer, p_catalog_run uuid)
returns uuid language plpgsql security invoker set search_path = '' as $$
declare v_run uuid; v_captured timestamptz; v_rows integer; v_issues integer;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 then
    raise exception 'Không có giá nào thành công; không ghi lượt cào';
  end if;
  if jsonb_typeof(p_issues) <> 'array' then
    raise exception 'Danh sách lỗi phải là array';
  end if;
  v_rows := jsonb_array_length(p_rows);
  v_issues := jsonb_array_length(p_issues);
  if p_expected is null or v_rows + v_issues <> p_expected then
    raise exception 'Số giá + số lỗi không khớp số link catalog';
  end if;
  if p_year not between 2020 and 2100 or p_week < 1 or
     p_week > extract(week from make_date(p_year, 12, 28)) then
    raise exception 'Năm/tuần ISO không hợp lệ';
  end if;
  insert into public.scrape_runs(year, week_number, product_count, expected_count, issue_count, catalog_run_id)
  values(p_year, p_week, v_rows, p_expected, v_issues, p_catalog_run)
  returning id, completed_at into v_run, v_captured;
  insert into public.weekly_prices(chain_name, product_name, sku, original_price, promo_price, promo_text,
    week_number, year, source_url, run_id, category, brand, model_name, variant_label)
  select chain_name, product_name, sku, original_price, promo_price, coalesce(promo_text, ''),
    p_week, p_year, source_url, v_run, coalesce(category, ''), coalesce(brand, ''), model_name, coalesce(variant_label, '')
  from jsonb_to_recordset(p_rows) as x(chain_name text, product_name text, sku text, original_price bigint,
    promo_price bigint, promo_text text, source_url text, category text, brand text, model_name text, variant_label text)
  on conflict (chain_name, sku, year, week_number) do update set
    product_name = excluded.product_name, original_price = excluded.original_price,
    promo_price = excluded.promo_price, promo_text = excluded.promo_text, source_url = excluded.source_url,
    run_id = excluded.run_id, category = excluded.category, brand = excluded.brand,
    model_name = excluded.model_name, variant_label = excluded.variant_label;
  insert into public.scrape_issues(run_id, captured_at, business_date, week_start, stage, chain_name, sku,
    product_name, category, brand, model_name, source_url, reason)
  select v_run, v_captured, (v_captured at time zone 'Asia/Ho_Chi_Minh')::date,
    date_trunc('week', v_captured at time zone 'Asia/Ho_Chi_Minh')::date,
    stage, chain_name, coalesce(sku, ''), coalesce(product_name, ''), coalesce(category, ''), coalesce(brand, ''),
    model_name, source_url, reason
  from jsonb_to_recordset(p_issues) as x(stage text, chain_name text, sku text, product_name text,
    category text, brand text, model_name text, source_url text, reason text);
  return v_run;
end;
$$;
revoke all on function public.commit_price_run(integer, integer, jsonb, jsonb, integer, uuid) from public, anon, authenticated;
grant execute on function public.commit_price_run(integer, integer, jsonb, jsonb, integer, uuid) to service_role;

commit;
