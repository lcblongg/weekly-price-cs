"""Kiểm tra migration 001→007 trên Postgres nhúng (dev, không thuộc CI).
Cài riêng: python -m venv /tmp/pg && /tmp/pg/bin/pip install pgserver psycopg2-binary
Chạy: /tmp/pg/bin/python tools/check_migrations.py /tmp/pgdata  (thư mục dữ liệu mới, sẽ tự tạo)
Giả lập role anon/authenticated/service_role; bản nhúng thiếu pg_trgm nên index trigram được thay bằng index thường.
"""
import json, pgserver, sys
from pathlib import Path
import psycopg2
ROOT=Path(__file__).resolve().parents[1]/'supabase'
srv=pgserver.get_server(Path(sys.argv[1]), cleanup_mode='stop')
conn=psycopg2.connect(srv.get_uri()); conn.autocommit=True; cur=conn.cursor()
def run(q,args=None):
    cur.execute(q,args)
    try: return cur.fetchall()
    except psycopg2.ProgrammingError: return None
for r in ['anon','authenticated','service_role']:
    run(f"do $$ begin if not exists (select from pg_roles where rolname='{r}') then create role {r} nologin {'bypassrls' if r=='service_role' else ''}; end if; end $$;")
run("create schema if not exists extensions")
run("grant usage on schema public to anon, authenticated, service_role")
# Mô phỏng Supabase Auth cho migration lựa chọn cá nhân; không dùng dữ liệu thật.
run("create schema if not exists auth")
run("create table if not exists auth.users(id uuid primary key)")
run("create or replace function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$")
run("grant usage on schema auth to authenticated")
for f in sorted(ROOT.glob('00*.sql')):
    text=f.read_text()
    if f.name.startswith('001'):
        text=text.replace('using gin(product_name extensions.gin_trgm_ops)','(product_name)').replace('create extension if not exists pg_trgm with schema extensions;','')  # chỉ trong môi trường thử: thiếu pg_trgm
    run(text); print('applied', f.name)
# Quyền bảng mặc định của Supabase cho service_role (Supabase tự cấp qua default privileges).
def as_role(role, q, args=None):
    run(f"set role {role}")
    try: return run(q,args)
    finally: run("reset role")
results=[]
def check(name, fn, expect_error=None):
    try:
        out=fn(); ok = expect_error is None
        results.append((name, 'OK' if ok else 'FAIL (không lỗi như mong đợi)', str(out)[:120]))
    except Exception as e:
        msg=str(e).split('\n')[0]
        ok = expect_error is not None and expect_error in msg
        results.append((name, 'OK' if ok else 'FAIL', msg[:160]))
        conn.rollback() if not conn.autocommit else None
row=lambda chain,url,status='ready': {'chain_name':chain,'source_url':url,'status':status,'reason':'' if status=='ready' else 'Hết hàng','config':{'sku':url[-3:]}}
check('commit_discovery_chain ok', lambda: as_role('service_role',"select public.commit_discovery_chain('Phong Vũ', %s::jsonb)",[json.dumps([row('Phong Vũ','https://phongvu.vn/a1'),row('Phong Vũ','https://phongvu.vn/a2','review')])]))
check('catalog chứa kênh khác bị từ chối', lambda: as_role('service_role',"select public.commit_discovery_chain('Phong Vũ', %s::jsonb)",[json.dumps([row('TGDD','https://x/1')])]), 'kênh khác')
check('catalog trùng source_url bị từ chối (PK)', lambda: as_role('service_role',"select public.commit_discovery_chain('TGDD', %s::jsonb)",[json.dumps([row('TGDD','https://x/1'),row('TGDD','https://x/1','review')])]), 'duplicate key')
check('authenticated không gọi được RPC', lambda: as_role('authenticated',"select public.commit_discovery_chain('TGDD','[]')"), 'permission denied')
price=lambda chain,sku,p: {'chain_name':chain,'sku':sku,'product_name':'A','original_price':None,'promo_price':p,'promo_text':'','source_url':'https://phongvu.vn/'+sku,'category':'Điện thoại','brand':'','model_name':'Galaxy A57','variant_label':'128GB'}
iss=lambda chain,sku: {'stage':'price','chain_name':chain,'sku':sku,'product_name':'B','category':'Điện thoại','brand':'','model_name':None,'source_url':'https://phongvu.vn/'+sku,'reason':'HTTP 403 — bị chặn','error_kind':'blocked'}
check('commit_chain_price_run ok', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,%s::jsonb,2,null)",[json.dumps([price('Phong Vũ','pv-1',1000000)]),json.dumps([iss('Phong Vũ','pv-2')])]))
check('lượt 2 cùng ngày: lịch sử không bị ghi đè', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,'[]'::jsonb,1,null)",[json.dumps([price('Phong Vũ','pv-1',900000)])]))
check('daily_prices giữ 2 snapshot pv-1', lambda: (lambda r: r if r[0][0]==2 else (_ for _ in ()).throw(Exception('expected 2, got %s'%r)))(run("select count(*) from daily_prices where sku='pv-1'")))
check('weekly_prices 1 dòng/tuần, giá mới nhất', lambda: (lambda r: r if r==[(1,900000)] else (_ for _ in ()).throw(Exception(str(r))))(run("select count(*), max(promo_price) from weekly_prices where sku='pv-1'")))
check('metadata category/model chép sang daily', lambda: (lambda r: r if r[0]==('Điện thoại','Galaxy A57','128GB') else (_ for _ in ()).throw(Exception(str(r))))(run("select category,model_name,variant_label from daily_prices where sku='pv-1' limit 1")))
check('scrape_issues có error_kind', lambda: (lambda r: r if r==[('blocked',)] else (_ for _ in ()).throw(Exception(str(r))))(run("select error_kind from scrape_issues")))
check('scrape_runs gắn chain_name', lambda: (lambda r: r if r==[('Phong Vũ',2)] else (_ for _ in ()).throw(Exception(str(r))))(run("select chain_name,count(*) from scrape_runs group by 1")))
check('số giá+lỗi lệch catalog bị từ chối', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,'[]'::jsonb,5,null)",[json.dumps([price('Phong Vũ','pv-1',1)])]), 'không khớp')
check('dòng kênh khác bị từ chối', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,'[]'::jsonb,1,null)",[json.dumps([price('TGDD','tg-1',1)])]), 'kênh khác')
check('giá 0 bị từ chối, rollback cả lượt', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,%s::jsonb,2,null)",[json.dumps([price('Phong Vũ','pv-9',0)]),json.dumps([iss('Phong Vũ','pv-8')])]), 'check constraint')
check('rollback: không còn issue pv-8', lambda: (lambda r: r if r==[(0,)] else (_ for _ in ()).throw(Exception(str(r))))(run("select count(*) from scrape_issues where sku='pv-8'")))
check('anon không đọc daily_prices', lambda: as_role('anon',"select count(*) from daily_prices"), 'permission denied')
check('authenticated đọc daily_prices', lambda: as_role('authenticated',"select count(*) from daily_prices"))
check('authenticated đọc scrape_issues', lambda: as_role('authenticated',"select count(*) from scrape_issues"))
check('authenticated không ghi daily_prices', lambda: as_role('authenticated',"insert into daily_prices(run_id) values (gen_random_uuid())"), 'permission denied')
check('authenticated không đọc catalog bot', lambda: as_role('authenticated',"select count(*) from discovered_products"), 'permission denied')
check('fetch catalog theo kênh: bản mới nhất', lambda: run("select chain_name, candidate_count, ready_count from discovery_runs order by completed_at desc"))
user_a='11111111-1111-1111-1111-111111111111'
user_b='22222222-2222-2222-2222-222222222222'
run("insert into auth.users(id) values (%s),(%s)",[user_a,user_b])
run("select set_config('request.jwt.claim.sub',%s,false)",[user_a])
check('watchlist: A ghi lựa chọn của mình', lambda: as_role('authenticated',"insert into personal_watchlists(user_id) values (%s)",[user_a]))
check('watchlist: A không ghi cho B', lambda: as_role('authenticated',"insert into personal_watchlists(user_id) values (%s)",[user_b]), 'row-level security')
check('watchlist: A đọc được hàng của mình', lambda: (lambda r: r if r==[(user_a,)] else (_ for _ in ()).throw(Exception(str(r))))(as_role('authenticated',"select user_id::text from personal_watchlists")))
run("select set_config('request.jwt.claim.sub',%s,false)",[user_b])
check('watchlist: B không thấy hàng A', lambda: (lambda r: r if r==[] else (_ for _ in ()).throw(Exception(str(r))))(as_role('authenticated',"select user_id from personal_watchlists")))
check('watchlist: B không sửa hàng A', lambda: (lambda r: r if r==[] else (_ for _ in ()).throw(Exception(str(r))))(as_role('authenticated',"update personal_watchlists set updated_at=now() where user_id=%s returning user_id",[user_a])))
check('watchlist: anon không đọc', lambda: as_role('anon',"select * from personal_watchlists"), 'permission denied')
run("select set_config('request.jwt.claim.sub',%s,false)",[user_a])
check('watchlist: A upsert được hàng mình', lambda: as_role('authenticated',"insert into personal_watchlists(user_id) values (%s) on conflict(user_id) do update set updated_at=now()",[user_a]))
status_price={**price('Phong Vũ','pv-status',None),'promo_text':'[Tình trạng] Ngừng kinh doanh'}
check('NULL với trạng thái lưu qua RPC', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,'[]'::jsonb,1,null)",[json.dumps([status_price])]))
check('trạng thái sao chép vào daily', lambda: (lambda r:r if r==[(None,'[Tình trạng] Ngừng kinh doanh')] else (_ for _ in ()).throw(Exception(str(r))))(run("select promo_price,promo_text from daily_prices where sku='pv-status'")))
check('NULL không có trạng thái bị từ chối', lambda: as_role('service_role',"select public.commit_chain_price_run('Phong Vũ',2026,41,%s::jsonb,'[]'::jsonb,1,null)",[json.dumps([price('Phong Vũ','pv-null-invalid',None)])]),'check constraint')
for r in results: print(f'{r[1]:<6} {r[0]} — {r[2]}')
failed=any(not r[1].startswith('OK') for r in results)
print('FAILED' if failed else 'ALL OK')
sys.exit(1 if failed else 0)
