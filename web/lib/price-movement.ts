import {quoteDay,type Quote} from './comparison';
export type Movement={before:Quote;after:Quote;delta:number;percent:number;shock:boolean};
// Định danh cùng SKU, model, cấu hình và màu. Không so giá thấp nhất của hai tập SKU khác nhau.
export const seriesKey=(q:Quote)=>JSON.stringify([q.chain,q.sku,q.apple_model,q.storage,q.display_variant,q.color]);
export function dailySeries(rows:Quote[]){
 const groups=new Map<string,Map<string,Quote>>();
 for(const q of rows){const key=seriesKey(q),day=quoteDay(q);if(!groups.has(key))groups.set(key,new Map());const series=groups.get(key)!,old=series.get(day);if(!old||Date.parse(q.observed_at)>Date.parse(old.observed_at))series.set(day,q);}
 return groups;
}
export function movement(before:Quote|undefined,after:Quote|undefined):Movement|null{
 if(!before||!after||seriesKey(before)!==seriesKey(after)||quoteDay(before)>=quoteDay(after)||before.promo_price===null||after.promo_price===null||before.promo_price<=0||after.promo_price<=0)return null;
 const delta=after.promo_price-before.promo_price,percent=delta/before.promo_price*100;
 return {before,after,delta,percent,shock:Math.abs(percent)>3||Math.abs(delta)>500000};
}
export function priceMovements(rows:Quote[],day:string,weekDays?:string[]):Movement[]{
 const changes:Movement[]=[];
 for(const series of dailySeries(rows).values()){
  const ordered=[...series.values()].sort((a,b)=>quoteDay(a).localeCompare(quoteDay(b)));
  const scoped=weekDays?ordered.filter(q=>weekDays.includes(quoteDay(q))):ordered.filter(q=>quoteDay(q)<=day);
  const after=weekDays?scoped.at(-1):scoped.find(q=>quoteDay(q)===day);
  // NULL ở ngày trước là trạng thái, không lùi thêm để tạo biến động giá giả.
  const before=weekDays?scoped[0]:scoped.filter(q=>quoteDay(q)<day).at(-1);
  const change=movement(before,after);if(change&&change.delta!==0)changes.push(change);
 }
 return changes.sort((a,b)=>Math.abs(b.delta)-Math.abs(a.delta));
}
