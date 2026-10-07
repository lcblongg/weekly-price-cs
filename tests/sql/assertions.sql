insert into public.app_members(user_id,role) values ('00000000-0000-0000-0000-000000000001','admin'),('00000000-0000-0000-0000-000000000002','cs');
insert into public.app_settings(key,value) values ('apple_colors','{"products":[]}'),('apple_models','{"models":[]}');
insert into public.automation_jobs(id,kind,status,payload,lease_until) values ('10000000-0000-0000-0000-000000000001','verify_prices','running','{}',now()+interval '5 minutes');
set role service_role;
select public.commit_dashboard_run('10000000-0000-0000-0000-000000000001','CellphoneS','{"rows":[],"marker":"before"}',current_date,1,2026,41,
 '[{"chain_name":"CellphoneS","sku":"cps-1","product_name":"iPhone 17 Pro Max 256GB","promo_price":34990000,"source_url":"https://cellphones.com.vn/iphone-17-pro-max.html"}]',
 '[{"chain_name":"CellphoneS","stage":"price","reason":"HTTP 403","source_url":"https://cellphones.com.vn/other.html"}]',null);
do $$ begin
 if (select count(*) from public.daily_prices)<>1 or (select count(*) from public.scrape_issues)<>1 then raise exception 'Không lưu đủ giá/lỗi/lịch sử';end if;
 begin
  perform public.commit_dashboard_run('10000000-0000-0000-0000-000000000001','CellphoneS','{"rows":[],"marker":"bad"}',current_date,1,2026,41,
    '[{"chain_name":"CellphoneS","sku":"cps-2","product_name":"Sai","promo_price":0,"source_url":"https://cellphones.com.vn/bad.html"}]','[]',null);
  raise exception 'Giá 0 phải bị từ chối';
 exception when check_violation then null;end;
 if (select payload->>'marker' from public.dashboard_snapshots) <> 'before' then raise exception 'Snapshot không rollback khi lưu giá lỗi';end if;
 begin
  perform public.publish_dashboard_snapshot('10000000-0000-0000-0000-000000000001','CellphoneS','{"rows":[]}',current_date,99);
  raise exception 'Revision cũ phải bị từ chối';
 exception when others then if sqlerrm='Revision cũ phải bị từ chối' then raise;end if;end;
 update public.automation_jobs set status='error' where id='10000000-0000-0000-0000-000000000001';
 begin
  perform public.publish_dashboard_snapshot('10000000-0000-0000-0000-000000000001','CellphoneS','{"rows":[]}',current_date,1);
  raise exception 'Runner mất quyền vẫn công bố';
 exception when others then if sqlerrm='Runner mất quyền vẫn công bố' then raise;end if;end;
 begin
  perform public.set_app_configuration('{}','{}',1);
  raise exception 'Thiếu products/models phải bị từ chối';
 exception when others then if sqlerrm='Thiếu products/models phải bị từ chối' then raise;end if;end;
end $$;
reset role;
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',false);
do $$ begin
 if not public.is_app_member() or public.is_app_admin() then raise exception 'Quyền CS sai';end if;
 if (select count(*) from public.dashboard_snapshots)<>1 then raise exception 'CS không đọc được dashboard';end if;
 if (select count(*) from public.automation_jobs)<>0 then raise exception 'CS đọc được job quản trị';end if;
 if (select count(*) from public.app_members)<>1 then raise exception 'Đọc được thành viên khác';end if;
 if has_function_privilege('authenticated','public.set_app_configuration(jsonb,jsonb,bigint)','EXECUTE') then raise exception 'Client được sửa cấu hình trực tiếp';end if;
end $$;
insert into public.personal_watchlists(user_id) values ('00000000-0000-0000-0000-000000000002');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',false);
do $$ begin
 if (select count(*) from public.personal_watchlists)<>0 then raise exception 'Đọc được watchlist tài khoản khác';end if;
 if (select count(*) from public.automation_jobs)<>1 then raise exception 'Admin không đọc được job';end if;
end $$;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',false);
do $$ begin
 if (select count(*) from public.dashboard_snapshots)<>0 or (select count(*) from public.daily_prices)<>0 then raise exception 'Tài khoản chưa cấp quyền đọc được giá';end if;
end $$;
reset role;
set role service_role;
select public.seed_dashboard_history('FPT Shop',current_date-1,'{"rows":[]}',
 jsonb_build_array(jsonb_build_object('chain_name','FPT Shop','sku','fpt-old','product_name','Đã nghiệm thu','promo_price',2000000,'source_url','https://fptshop.com.vn/old','observed_at',(current_date-1)::text||'T10:00:00+07:00')));
select public.seed_discovery_catalog('FPT Shop','[{"chain_name":"FPT Shop","source_url":"https://fptshop.com.vn/old","status":"ready","config":{}}]',((current_date-1)::text||'T09:00:00+07:00')::timestamptz);
do $$ begin
 if (select business_date from public.daily_prices where sku='fpt-old')<>current_date-1 then raise exception 'Import làm giả ngày cào';end if;
 if (select captured_at from public.daily_prices where sku='fpt-old')<>((current_date-1)::text||'T10:00:00+07:00')::timestamptz then raise exception 'Import mất thời điểm SKU';end if;
 if (select completed_at from public.discovery_runs where chain_name='FPT Shop')<>((current_date-1)::text||'T09:00:00+07:00')::timestamptz then raise exception 'Import làm mới timestamp catalog';end if;
end $$;
reset role;
select 'PASS: 8 migrations, atomic rollback, revision/lease, RLS roles/watchlist, historical import timestamps' as result;
