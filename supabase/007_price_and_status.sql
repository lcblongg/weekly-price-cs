-- Website có thể chỉ ghi trạng thái, không có giá. Lưu snapshot đó với NULL, không phải 0.
-- Ghi chú [Tình trạng] được lưu cùng snapshot qua RPC/trigger hiện có (không mất lịch sử).
begin;
alter table public.weekly_prices alter column promo_price drop not null;
alter table public.daily_prices alter column promo_price drop not null;
alter table public.weekly_prices add constraint weekly_price_or_status
 check (promo_price is not null or (original_price is null and promo_text like '[Tình trạng] %'));
alter table public.daily_prices add constraint daily_price_or_status
 check (promo_price is not null or (original_price is null and promo_text like '[Tình trạng] %'));
commit;
