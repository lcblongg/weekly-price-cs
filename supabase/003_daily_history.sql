-- Chạy sau 001 và 002. Giữ từng snapshot bất biến để không mất giá các ngày trong tuần.
begin;
create table public.daily_prices (
  id bigint generated always as identity primary key,
  run_id uuid not null references public.scrape_runs(id),
  captured_at timestamptz not null,
  business_date date not null,
  week_start date not null check (extract(isodow from week_start) = 1),
  chain_name text not null,
  sku text not null,
  product_name text not null,
  original_price bigint check (original_price > 0),
  promo_price bigint not null check (promo_price > 0),
  promo_text text not null default '',
  source_url text not null,
  unique(run_id, chain_name, sku)
);
create index daily_prices_week_chain on public.daily_prices(week_start, chain_name, business_date);
create index daily_prices_sku_date on public.daily_prices(chain_name, sku, business_date desc, captured_at desc);
create index daily_prices_run on public.daily_prices(run_id);

-- Backfill chỉ dữ liệu còn tồn tại, không tự tạo lịch sử của các ngày đã bị ghi đè.
insert into public.daily_prices(run_id,captured_at,business_date,week_start,chain_name,sku,
 product_name,original_price,promo_price,promo_text,source_url)
select p.run_id,r.completed_at,(r.completed_at at time zone 'Asia/Ho_Chi_Minh')::date,
 date_trunc('week',r.completed_at at time zone 'Asia/Ho_Chi_Minh')::date,
 p.chain_name,p.sku,p.product_name,p.original_price,p.promo_price,p.promo_text,p.source_url
from public.weekly_prices p join public.scrape_runs r on r.id=p.run_id;

-- RPC cũ vẫn là một transaction: history và weekly_prices cùng rollback nếu có lỗi.
create function public.capture_daily_price() returns trigger
language plpgsql security invoker set search_path = '' as $$
declare captured timestamptz;
begin
  select completed_at into strict captured from public.scrape_runs where id=new.run_id;
  insert into public.daily_prices(run_id,captured_at,business_date,week_start,chain_name,sku,
    product_name,original_price,promo_price,promo_text,source_url)
  values(new.run_id,captured,(captured at time zone 'Asia/Ho_Chi_Minh')::date,
    date_trunc('week',captured at time zone 'Asia/Ho_Chi_Minh')::date,
    new.chain_name,new.sku,new.product_name,new.original_price,new.promo_price,new.promo_text,new.source_url);
  return new;
end;
$$;
create trigger weekly_price_capture_daily after insert or update on public.weekly_prices
for each row execute function public.capture_daily_price();
alter table public.daily_prices enable row level security;
revoke all on public.daily_prices from anon,authenticated;
grant select on public.daily_prices to authenticated;
create policy cs_read_daily on public.daily_prices for select to authenticated using (true);
grant select,insert on public.daily_prices to service_role;
grant usage,select on sequence public.daily_prices_id_seq to service_role;
commit;
