-- Sau 001 → 007. Cấu hình, quyền quản trị, job GitHub và snapshot dashboard theo ngày.
begin;
create table public.app_members (
 user_id uuid primary key references auth.users(id) on delete cascade,
 role text not null check(role in ('admin','cs')),
 created_at timestamptz not null default now()
);
create function public.is_app_member() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.app_members where user_id=auth.uid())
$$;
create function public.is_app_admin() returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.app_members where user_id=auth.uid() and role='admin')
$$;
revoke all on function public.is_app_member(),public.is_app_admin() from public,anon;
grant execute on function public.is_app_member(),public.is_app_admin() to authenticated;
alter table public.app_members enable row level security;
grant select on public.app_members to authenticated;
create policy member_self on public.app_members for select to authenticated using(user_id=auth.uid());
grant all on public.app_members to service_role;
create table public.app_settings (
 key text primary key,
 value jsonb not null,
 revision bigint not null default 1,
 updated_at timestamptz not null default now()
);
alter table public.app_settings enable row level security;
grant select on public.app_settings to authenticated;
create policy settings_member_read on public.app_settings for select to authenticated using(public.is_app_member());
grant all on public.app_settings to service_role;
create table public.automation_jobs (
 id uuid primary key default gen_random_uuid(),
 requested_by uuid references auth.users(id),
 kind text not null check(kind in ('verify_prices','config_update','check_urls','daily_prices','discovery')),
 status text not null default 'pending' check(status in ('pending','running','success','partial','error')),
 payload jsonb not null,
 result jsonb not null default '{}',
 created_at timestamptz not null default now(),
 started_at timestamptz,
 finished_at timestamptz,
 heartbeat_at timestamptz,
 lease_until timestamptz
);
create index automation_jobs_created on public.automation_jobs(created_at desc);
create unique index automation_one_active on public.automation_jobs((true)) where status in ('pending','running');
alter table public.automation_jobs enable row level security;
grant select on public.automation_jobs to authenticated;
create policy jobs_admin_read on public.automation_jobs for select to authenticated using(public.is_app_admin());
grant all on public.automation_jobs to service_role;
create table public.dashboard_snapshots (
 id uuid primary key default gen_random_uuid(),
 chain_name text not null check(chain_name in ('TGDD','CellphoneS','FPT Shop','Viettel Store','Phong Vũ')),
 business_date date not null,
 completed_at timestamptz not null default now(),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 unique(chain_name,business_date)
);
create index dashboard_snapshots_date on public.dashboard_snapshots(business_date desc,chain_name);
alter table public.dashboard_snapshots enable row level security;
grant select on public.dashboard_snapshots to authenticated;
create policy dashboard_member_read on public.dashboard_snapshots for select to authenticated using(public.is_app_member());
grant all on public.dashboard_snapshots to service_role;
-- Các bảng dữ liệu cũ cũng chỉ dành cho tài khoản đã được quản trị cấp quyền.
do $$ declare t text; p record; begin
 foreach t in array array['weekly_prices','daily_prices','scrape_issues','discovered_products','discovery_runs'] loop
  for p in select policyname from pg_policies where schemaname='public' and tablename=t and cmd='SELECT' loop
   execute format('drop policy %I on public.%I',p.policyname,t);
  end loop;
  execute format('create policy member_read on public.%I for select to authenticated using(public.is_app_member())',t);
 end loop;
end $$;

create function public.claim_automation_job(p_id uuid) returns jsonb language plpgsql security invoker set search_path='' as $$
declare j public.automation_jobs; begin
 update public.automation_jobs set status='running',started_at=now(),heartbeat_at=now(),lease_until=now()+interval '6 hours'
 where id=p_id and status='pending' returning * into j;
 if j.id is null then raise exception 'Job không ở trạng thái chờ'; end if;
 return to_jsonb(j);
end $$;
revoke all on function public.claim_automation_job(uuid) from public,anon,authenticated;
grant execute on function public.claim_automation_job(uuid) to service_role;
create function public.set_app_configuration(p_colors jsonb,p_models jsonb,p_revision bigint) returns bigint language plpgsql security invoker set search_path='' as $$
declare r bigint; begin
 if jsonb_typeof(p_colors->'products') is distinct from 'array' or jsonb_typeof(p_models->'models') is distinct from 'array' then raise exception 'Cấu hình không hợp lệ';end if;
 update public.app_settings set value=p_colors,revision=revision+1,updated_at=now() where key='apple_colors' and revision=p_revision returning revision into r;
 if r is null then raise exception 'Cấu hình đã thay đổi; tải lại trước khi lưu';end if;
 insert into public.app_settings(key,value) values('apple_models',p_models) on conflict(key) do update set value=excluded.value,revision=app_settings.revision+1,updated_at=now();
 return r;
end $$;
revoke all on function public.set_app_configuration(jsonb,jsonb,bigint) from public,anon,authenticated;
grant execute on function public.set_app_configuration(jsonb,jsonb,bigint) to service_role;
-- Công bố snapshot chỉ khi job còn lease và cấu hình chưa đổi. Giao dịch khóa tránh runner cũ ghi đè.
create function public.publish_dashboard_snapshot(p_job uuid,p_chain text,p_payload jsonb,p_date date,p_revision bigint)
returns uuid language plpgsql security invoker set search_path='' as $$
declare j public.automation_jobs; r bigint; result uuid; begin
 select * into j from public.automation_jobs where id=p_job for update;
 if j.status is distinct from 'running' or j.lease_until is null or j.lease_until<now() then raise exception 'Job đã dừng hoặc hết lease';end if;
 select revision into r from public.app_settings where key='apple_colors' for share;
 if r is distinct from p_revision then raise exception 'Cấu hình đã thay đổi; không công bố';end if;
 if jsonb_typeof(p_payload->'rows') is distinct from 'array' then raise exception 'Snapshot không hợp lệ';end if;
 insert into public.dashboard_snapshots(chain_name,business_date,payload) values(p_chain,p_date,p_payload)
 on conflict(chain_name,business_date) do update set payload=excluded.payload,completed_at=now() returning id into result;
 return result;
end $$;
revoke all on function public.publish_dashboard_snapshot(uuid,text,jsonb,date,bigint) from public,anon,authenticated;
grant execute on function public.publish_dashboard_snapshot(uuid,text,jsonb,date,bigint) to service_role;

-- Giá, lỗi và snapshot phải cùng thành công; lỗi ở bước nào đều rollback toàn bộ.
create function public.commit_dashboard_run(p_job uuid,p_chain text,p_payload jsonb,p_date date,
 p_revision bigint,p_year integer,p_week integer,p_rows jsonb,p_issues jsonb,p_catalog_run uuid)
returns uuid language plpgsql security invoker set search_path='' as $$
declare run uuid; begin
 perform public.publish_dashboard_snapshot(p_job,p_chain,p_payload,p_date,p_revision);
 run := public.commit_chain_price_run(p_chain,p_year,p_week,p_rows,p_issues,
   jsonb_array_length(p_rows)+jsonb_array_length(p_issues),p_catalog_run);
 return run;
end $$;
revoke all on function public.commit_dashboard_run(uuid,text,jsonb,date,bigint,integer,integer,jsonb,jsonb,uuid) from public,anon,authenticated;
grant execute on function public.commit_dashboard_run(uuid,text,jsonb,date,bigint,integer,integer,jsonb,jsonb,uuid) to service_role;

-- Chuyển catalog đã nghiệm thu sang dự án mới, giữ ngày khám phá thật (không biến dữ liệu cũ thành mới).
create function public.seed_discovery_catalog(p_chain text,p_rows jsonb,p_completed timestamptz)
returns uuid language plpgsql security invoker set search_path='' as $$
declare run uuid; begin
 if p_completed is null or p_completed>now()+interval '5 minutes' then raise exception 'Thời điểm catalog không hợp lệ';end if;
 perform pg_advisory_xact_lock(hashtext('seed-catalog:'||p_chain));
 if exists(select 1 from public.discovery_runs where chain_name=p_chain) then raise exception 'Đã có catalog; không ghi đè khi khởi tạo';end if;
 run := public.commit_discovery_chain(p_chain,p_rows);
 update public.discovery_runs set completed_at=p_completed where id=run;
 return run;
end $$;
revoke all on function public.seed_discovery_catalog(text,jsonb,timestamptz) from public,anon,authenticated;
grant execute on function public.seed_discovery_catalog(text,jsonb,timestamptz) to service_role;

commit;
