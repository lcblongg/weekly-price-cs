-- Chạy SAU 001_weekly_prices.sql. Chỉ bot server được dùng dữ liệu khám phá.
begin;
create table public.discovery_runs (
  id uuid primary key default gen_random_uuid(),
  completed_at timestamptz not null default now(),
  candidate_count integer not null check(candidate_count > 0),
  ready_count integer not null check(ready_count >= 0 and ready_count <= candidate_count)
);
create table public.discovered_products (
  run_id uuid not null references public.discovery_runs(id),
  chain_name text not null,
  source_url text not null check(source_url ~ '^https://'),
  status text not null check(status in ('ready', 'review')),
  reason text not null default '',
  config jsonb not null,
  primary key(run_id, chain_name, source_url)
);
create index discovery_runs_latest on public.discovery_runs(completed_at desc);
create index discovered_products_status on public.discovered_products(run_id, status);
alter table public.discovery_runs enable row level security;
alter table public.discovered_products enable row level security;
revoke all on public.discovery_runs, public.discovered_products from anon, authenticated;
grant all on public.discovery_runs, public.discovered_products to service_role;

create function public.commit_discovery(p_rows jsonb) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare v_run uuid; v_total integer; v_ready integer;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 then
    raise exception 'Danh sách khám phá không được rỗng';
  end if;
  v_total := jsonb_array_length(p_rows);
  select count(*) into v_ready from jsonb_array_elements(p_rows) r where r->>'status' = 'ready';
  insert into public.discovery_runs(candidate_count, ready_count)
  values(v_total, v_ready) returning id into v_run;
  insert into public.discovered_products(run_id, chain_name, source_url, status, reason, config)
  select v_run, chain_name, source_url, status, coalesce(reason, ''), config
  from jsonb_to_recordset(p_rows) as x(chain_name text, source_url text, status text, reason text, config jsonb);
  return v_run;
end;
$$;
revoke all on function public.commit_discovery(jsonb) from public, anon, authenticated;
grant execute on function public.commit_discovery(jsonb) to service_role;
-- Các lần khám phá bất biến để tuần sau vẫn truy được nguồn danh mục.
-- Người vận hành có thể bổ sung chính sách lưu trữ khi catalog lớn; không xóa tự động trong bot.
commit;
