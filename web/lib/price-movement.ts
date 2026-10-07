import {quoteDay,type Quote} from './comparison';
import {addDays} from './calendar';
export type Movement={before:Quote;after:Quote;delta:number;percent:number;shock:boolean};
// Định danh cùng SKU, model, cấu hình và màu. Không so giá thấp nhất của hai tập SKU khác nhau.
export const seriesKey=(q:Quote)=>JSON.stringify([q.chain,q.sku,q.apple_model,q.storage,q.display_variant,q.color]);
export function dailySeries(rows:Quote[]){
 const groups=new Map<string,Map<string,Quote>>();
 for(const q of rows){const key=seriesKey(q),day=quoteDay(q);if(!groups.has(key))groups.set(key,new Map());const series=groups.get(key)!,old=series.get(day);if(!old||Date.parse(q.observed_at)>Date.parse(old.observed_at))series.set(day,q);}
 return groups;
}
export function movement(before:Quote|undefined,after:Quote|undefined):Movement|null{
 if(!before||!after||seriesKey(before)!==seriesKey(after)||quoteDay(before)>=quoteDay(after)||before.promo_price===null||after.promo_price===null||!Number.isFinite(before.promo_price)||!Number.isFinite(after.promo_price)||before.promo_price<=0||after.promo_price<=0)return null;
 const delta=after.promo_price-before.promo_price,percent=delta/before.promo_price*100;
 return {before,after,delta,percent,shock:Math.abs(percent)>3||Math.abs(delta)>500000};
}
// Giá đại diện tuần là bản ghi cuối thực tế trong từng tuần, kể cả bản chỉ trạng thái.
// Tuần đang chạy so đến lần cào mới nhất; luôn hiển thị hai ngày được sử dụng.
export function weeklyPair(series:Map<string,Quote>,weekDays:string[]){
 const previousDays=weekDays.map(day=>addDays(day,-7));
 const last=(days:string[])=>days.map(day=>series.get(day)).filter((q):q is Quote=>!!q).at(-1);
 const before=last(previousDays),after=last(weekDays);
 return {before,after,change:movement(before,after)};
}
export function priceMovements(rows:Quote[],day:string,weekDays?:string[]):Movement[]{
 const changes:Movement[]=[];
 for(const series of dailySeries(rows).values()){
  const change=weekDays?weeklyPair(series,weekDays).change:movement(series.get(addDays(day,-1)),series.get(day));
  if(change&&change.delta!==0)changes.push(change);
 }
 return changes.sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta));
}
