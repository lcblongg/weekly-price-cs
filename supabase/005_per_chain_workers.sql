-- Chạy SAU 001 → 004. Mỗi kênh có catalog và lượt cào riêng:
--  * discovery lỗi ở một kênh không công bố catalog kênh đó; bản thành công trước vẫn được dùng;
--  * lượt cào giá của một kênh lỗi không làm mất lượt cào của kênh khác.
begin;

alter table public.discovery_runs add column chain_name text
  check (chain_name is null or chain_name in ('TGDD','CellphoneS','FPT Shop','Viettel Store','Phong Vũ'));
create index discovery_runs_chain_latest on public.discovery_runs(chain_name, completed_at desc);

alter table public.scrape_runs add column chain_name text
  check (chain_name is null or chain_name in ('TGDD','CellphoneS','FPT Shop','Viettel Store','Phong Vũ'));
create index scrape_runs_chain_week on public.scrape_runs(chain_name, year, week_number, completed_at desc);

alter table public.scrape_issues add column error_kind text not null default '';

create function public.commit_discovery_chain(p_chain text, p_rows jsonb) returns uuid
language plpgsql security invoker set search_path = '' as $$
declare v_run uuid; v_total integer; v_ready integer;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 then
    raise exception 'Catalog kênh không được rỗng';
  end if;
  if exists (select 1 from jsonb_array_elements(p_rows) r where r->>'chain_name' is distinct from p_chain) then
    raise exception 'Catalog chứa dòng của kênh khác';
  end if;
  v_total := jsonb_array_length(p_rows);
  select count(*) into v_ready from jsonb_array_elements(p_rows) r where r->>'status' = 'ready';
  if v_ready = 0 then
    raise exception 'Catalog không có link ready';
  end if;
  insert into public.discovery_runs(candidate_count, ready_count, chain_name)
  values(v_total, v_ready, p_chain) returning id into v_run;
  insert into public.discovered_products(run_id, chain_name, source_url, status, reason, config)
  select v_run, chain_name, source_url, status, coalesce(reason, ''), config
  from jsonb_to_recordset(p_rows) as x(chain_name text, source_url text, status text, reason text, config jsonb);
  return v_run;
end;
$$;
revoke all on function public.commit_discovery_chain(text, jsonb) from public, anon, authenticated;
grant execute on function public.commit_discovery_chain(text, jsonb) to service_role;

-- Lượt cào giá một kênh: giá thành công + mục cần kiểm tra, cùng commit hoặc cùng rollback.
-- Chỉ INSERT (không UPDATE) để service_role chỉ cần quyền select/insert đã cấp ở 004.
create function public.commit_chain_price_run(p_chain text, p_year integer, p_week integer, p_rows jsonb,
                                              p_issues jsonb, p_expected integer, p_catalog_run uuid)
returns uuid language plpgsql security invoker set search_path = '' as $$
declare v_run uuid; v_captured timestamptz; v_rows integer; v_issues integer;
begin
  if jsonb_typeof(p_rows) <> 'array' or jsonb_array_length(p_rows) = 0 then
    raise exception 'Không có giá nào thành công; không ghi lượt cào';
  end if;
  if jsonb_typeof(p_issues) <> 'array' then
    raise exception 'Danh sách lỗi phải là array';
  end if;
  if exists (select 1 from jsonb_array_elements(p_rows) r where r->>'chain_name' is distinct from p_chain)
     or exists (select 1 from jsonb_array_elements(p_issues) r where r->>'chain_name' is distinct from p_chain) then
    raise exception 'Lượt cào chứa dòng của kênh khác';
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
  insert into public.scrape_runs(year, week_number, product_count, expected_count, issue_count, catalog_run_id, chain_name)
  values(p_year, p_week, v_rows, p_expected, v_issues, p_catalog_run, p_chain)
  returning id, completed_at into v_run, v_captured;
  -- weekly_prices: 1 dòng/kênh/SKU/tuần (giá mới nhất); trigger 003/004 chép mỗi lượt vào daily_prices (không ghi đè ngày).
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
    product_name, category, brand, model_name, source_url, reason, error_kind)
  select v_run, v_captured, (v_captured at time zone 'Asia/Ho_Chi_Minh')::date,
    date_trunc('week', v_captured at time zone 'Asia/Ho_Chi_Minh')::date,
    stage, chain_name, coalesce(sku, ''), coalesce(product_name, ''), coalesce(category, ''), coalesce(brand, ''),
    model_name, source_url, reason, coalesce(error_kind, '')
  from jsonb_to_recordset(p_issues) as x(stage text, chain_name text, sku text, product_name text,
    category text, brand text, model_name text, source_url text, reason text, error_kind text);
  return v_run;
end;
$$;
revoke all on function public.commit_chain_price_run(text, integer, integer, jsonb, jsonb, integer, uuid) from public, anon, authenticated;
grant execute on function public.commit_chain_price_run(text, integer, integer, jsonb, jsonb, integer, uuid) to service_role;

commit;
