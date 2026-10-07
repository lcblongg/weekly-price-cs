-- Chạy một lần trong Supabase SQL Editor trên dự án mới.
begin;
create extension if not exists pg_trgm with schema extensions;

create table public.scrape_runs (
  id uuid primary key default gen_random_uuid(),
  year integer not null,
  week_number integer not null check (week_number between 1 and 53),
  product_count integer not null check (product_count > 0),
  completed_at timestamptz not null default now()
);
create table public.weekly_prices (
  id bigint generated always as identity primary key,
  chain_name text not null check (length(trim(chain_name)) > 0),
  product_name text not null check (length(trim(product_name)) > 0),
  -- SKU nội bộ chung cho các chuỗi: model + dung lượng + phiên bản.
  sku text not null check (length(trim(sku)) > 0),
  original_price bigint check (original_price > 0),
  promo_price bigint not null check (promo_price > 0),
  promo_text text not null default '',
  week_number integer not null check (week_number between 1 and 53),
  year integer not null check (year between 2020 and 2100),
  updated_at timestamptz not null default now(),
  source_url text not null check (source_url ~ '^https://'),
  run_id uuid not null references public.scrape_runs(id),
  constraint weekly_prices_identity unique (chain_name, sku, year, week_number)
);
-- Giá gốc có thể NULL khi trang không công bố. Không suy diễn giá gốc từ giá KM.
create index weekly_prices_week_chain on public.weekly_prices(year desc, week_number desc, chain_name);
create index weekly_prices_sku_week on public.weekly_prices(sku, year desc, week_number desc);
create index weekly_prices_name_search on public.weekly_prices using gin(product_name extensions.gin_trgm_ops);
create index weekly_prices_run on public.weekly_prices(run_id);
create index scrape_runs_week on public.scrape_runs(year, week_number, completed_at desc);

create function public.touch_weekly_price() returns trigger
language plpgsql set search_path = '' as $$
begin new.updated_at := now(); return new; end;
$$;
create trigger weekly_prices_updated_at before update on public.weekly_prices
for each row execute function public.touch_weekly_price();

-- Một RPC = một transaction. Nếu bất kỳ dòng nào lỗi, toàn bộ đợt UPSERT rollback.
create function public.commit_weekly_prices(p_year integer, p_week integer, p_rows jsonb)
returns uuid language plpgsql security invoker set search_path = '' as $$
declare v_run uuid;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 then
    raise exception 'Danh sách dữ liệu phải là array không rỗng';
  end if;
  -- Tuần ISO 53 chỉ tồn tại ở một số năm.
  if p_year not between 2020 and 2100 or p_week < 1 or
     p_week > extract(week from make_date(p_year, 12, 28)) then
    raise exception 'Năm/tuần ISO không hợp lệ';
  end if;
  insert into public.scrape_runs(year, week_number, product_count)
  values(p_year, p_week, jsonb_array_length(p_rows)) returning id into v_run;
  insert into public.weekly_prices(chain_name, product_name, sku, original_price,
    promo_price, promo_text, week_number, year, source_url, run_id)
  select chain_name, product_name, sku, original_price, promo_price,
    coalesce(promo_text, ''), p_week, p_year, source_url, v_run
  from jsonb_to_recordset(p_rows) as x(chain_name text, product_name text,
    sku text, original_price bigint, promo_price bigint, promo_text text, source_url text)
  on conflict (chain_name, sku, year, week_number) do update set
    product_name = excluded.product_name, original_price = excluded.original_price,
    promo_price = excluded.promo_price, promo_text = excluded.promo_text,
    source_url = excluded.source_url, run_id = excluded.run_id;
  return v_run;
end;
$$;

alter table public.weekly_prices enable row level security;
alter table public.scrape_runs enable row level security;
-- Dashboard CS cần đăng nhập Supabase Auth ở Bước 3. Không mở dữ liệu cho anon.
revoke all on public.weekly_prices, public.scrape_runs from anon, authenticated;
grant select on public.weekly_prices to authenticated;
create policy cs_read on public.weekly_prices for select to authenticated using (true);
grant all on public.weekly_prices, public.scrape_runs to service_role;
grant usage, select on sequence public.weekly_prices_id_seq to service_role;
revoke all on function public.commit_weekly_prices(integer, integer, jsonb) from public, anon, authenticated;
grant execute on function public.commit_weekly_prices(integer, integer, jsonb) to service_role;
commit;
