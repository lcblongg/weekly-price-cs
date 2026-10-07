-- Danh sách cá nhân chỉ ảnh hưởng Web; bot cào và Telegram nhóm không đọc bảng này.
begin;
create table public.personal_watchlists (
 user_id uuid primary key references auth.users(id) on delete cascade,
 preferences jsonb not null default '{"version":1,"models":[],"hidden":[],"fresh":[]}'::jsonb,
 updated_at timestamptz not null default now(),
 constraint watchlist_object check (
  jsonb_typeof(preferences) = 'object' and preferences @> '{"version":1}'::jsonb
  and preferences ?& array['models','hidden','fresh']
  and jsonb_typeof(preferences->'models') = 'array'
  and jsonb_typeof(preferences->'hidden') = 'array'
  and jsonb_typeof(preferences->'fresh') = 'array'
 )
);
alter table public.personal_watchlists enable row level security;
revoke all on public.personal_watchlists from anon;
grant select, insert, update on public.personal_watchlists to authenticated;
create policy watchlist_select on public.personal_watchlists for select to authenticated using ((select auth.uid()) = user_id);
create policy watchlist_insert on public.personal_watchlists for insert to authenticated with check ((select auth.uid()) = user_id);
create policy watchlist_update on public.personal_watchlists for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
commit;
