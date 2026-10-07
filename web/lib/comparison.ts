import {compareModels} from './product-standard';
export type Quote={stale_since?:string|null;stale_reason?:string|null;apple_selection?:string;source_color?:string|null;sku:string;product_name:string;display_name:string;display_variant:string|null;brand:string;category:string;apple_model:string;storage:string|null;color:string|null;promo_price:number|null;promo_text:string;source_url:string;observed_at:string;promotion_complete:boolean|null;chain:string;slug:string};
export type MatrixRow={key:string;model:string;name:string;variant:string;cells:Record<string,Quote[]>};
const dayFormatter=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'});
export function quoteDay(r:Quote){return dayFormatter.format(new Date(r.observed_at));}
// Lấy bản ghi gần nhất cho từng SKU/kênh; giữ nguyên thời điểm và trạng thái nguồn.
// Không dùng lại giá cũ nếu bản ghi mới hơn của SKU đã chuyển thành chỉ trạng thái.
export function latestQuotes(rows:Quote[],asOf:string):Quote[]{
 const latest=new Map<string,Quote>();
 for(const row of rows){
  if(quoteDay(row)>asOf)continue;
  const key=JSON.stringify([row.chain,row.sku]),previous=latest.get(key);
  if(!previous||Date.parse(row.observed_at)>Date.parse(previous.observed_at))latest.set(key,row);
 }
 return [...latest.values()];
}
function storageValue(name:string){const m=name.match(/\b(\d+)(GB|TB)\b/);return m?Number(m[1])*(m[2]==='TB'?1024:1):0;}
export function matrix(rows:Quote[]):MatrixRow[]{
 const result=new Map<string,MatrixRow>();
 for(const q of rows){
  const model=q.apple_model,name=model+(q.storage?' '+q.storage:'');
  // Cấu hình ảnh hưởng giá được tách thành dòng riêng; các SKU còn lại vẫn giữ trong ô chi tiết.
  let variant=q.display_variant??'';
  if(model.startsWith('MacBook')){const ram=q.product_name.match(/\b(\d{1,2})\s*GB\b/i);variant=[...new Set([...variant.split(' · '),ram&&Number(ram[1])<128?`RAM ${ram[1]}GB`:''].filter(Boolean))].sort().join(' · ');}
  const key=JSON.stringify([model,q.storage??'',variant]);
  if(!result.has(key))result.set(key,{key,model,name,variant,cells:{}});
  const row=result.get(key)!;(row.cells[q.chain]??=[]).push(q);
 }
 return [...result.values()].sort((a,b)=>compareModels(a.model,b.model)||storageValue(a.name)-storageValue(b.name)||a.variant.localeCompare(b.variant,'vi',{numeric:true}));
}
export function cellPrice(rows:Quote[]){const values=rows.map(r=>r.promo_price).filter((v):v is number=>v!==null);return values.length?{min:Math.min(...values),max:Math.max(...values)}:null;}
