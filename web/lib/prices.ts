import {canonicalAppleModel,compareModels} from './product-standard';
import {modelOf} from './product-meta';
import {datesForWeek} from './calendar';
import {CHAINS,type DailyPrice,type ProductWeek,type CatalogProduct} from './types';
// Không để dữ liệu sai cấu trúc/khác miền biến thành giá trên dashboard.
const domains:Record<string,string>={'TGDD':'thegioididong.com','FPT Shop':'fptshop.com.vn','CellphoneS':'cellphones.com.vn','Viettel Store':'viettelstore.vn','Phong Vũ':'phongvu.vn'};
export function validateRows(input:unknown):DailyPrice[] {
  if(!Array.isArray(input)) throw new Error('Dữ liệu không hợp lệ');
  return input.map(raw=>{
    const row=raw as DailyPrice;
    if(!CHAINS.includes(row.chain_name as typeof CHAINS[number])||!row.sku||!row.product_name||!/^\d{4}-\d{2}-\d{2}$/.test(row.business_date)||!Number.isFinite(Date.parse(row.captured_at))||(row.promo_price!==null&&(!Number.isSafeInteger(row.promo_price)||row.promo_price<=0))||typeof row.promo_text!=='string') throw new Error('Dữ liệu không hợp lệ');
    if(row.promo_price===null&&(row.original_price!==null||!row.promo_text.startsWith('[Tình trạng] ')))throw new Error('Thiếu giá và trạng thái đã xác minh');
    if(row.original_price!==null&&(!Number.isSafeInteger(row.original_price)||(row.promo_price!==null&&row.original_price<row.promo_price))) throw new Error('Giá gốc không hợp lệ');
    const url=new URL(row.source_url);const domain=domains[row.chain_name];
    if(url.protocol!=='https:'||url.username||url.password||![domain,'www.'+domain].includes(url.hostname)) throw new Error('Nguồn không hợp lệ');
    return row;
  });
}
export function groupWeek(rows:DailyPrice[],start:string):ProductWeek[] {
  const dates=datesForWeek(start);const groups=new Map<string,ProductWeek>();
  for(const row of rows) {
    const index=dates.indexOf(row.business_date);if(index<0) continue;
    const key=JSON.stringify([row.chain_name,row.sku]);
    if(!groups.has(key)) groups.set(key,{key,chain:row.chain_name,sku:row.sku,name:row.product_name,days:Array(7).fill(null),latest:row,change:null});
    const item=groups.get(key)!;const old=item.days[index];
    if(!old||Date.parse(row.captured_at)>Date.parse(old.captured_at)) item.days[index]=row;
  }
  for(const item of groups.values()) {
    const observations=item.days.filter((r):r is DailyPrice=>r!==null);
    item.latest=observations.at(-1)!;item.name=item.latest.product_name;
    const canonical=canonicalAppleModel(item.name);
    if(canonical){const storage=item.name.match(/\b(\d+)\s*(GB|TB)\b/gi)?.at(-1);item.name=canonical+(storage?' '+storage.toUpperCase().replace(/\s/g,''):'');}
    // Hai ngày thực sự có dữ liệu mới có thể tính biến động; không forward-fill ngày thiếu.
    item.change=observations.length>=2&&item.latest.promo_price!==null&&observations[0].promo_price!==null?item.latest.promo_price-observations[0].promo_price:null;
  }
  return [...groups.values()].sort((a,b)=>compareModels(modelOf(a.latest),modelOf(b.latest))||a.name.localeCompare(b.name,'vi',{numeric:true}));
}
export function searchKey(text:string) {return text.normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase();}

// Theo ngày chỉ lấy snapshot đúng ngày; đối chiếu đúng ngày trước đó, không lấy ngày gần nhất.
export function groupDay(rows:DailyPrice[],day:string):ProductWeek[] {
  const priorDay=new Date(Date.parse(day+'T00:00:00Z')-86400000).toISOString().slice(0,10);
  const monday=new Date(day+'T00:00:00Z');const weekday=monday.getUTCDay();
  monday.setUTCDate(monday.getUTCDate()-((weekday+6)%7));
  const products=groupWeek(rows.filter(row=>row.business_date===day),monday.toISOString().slice(0,10));
  const previous=new Map<string,DailyPrice>();
  for(const row of rows.filter(row=>row.business_date===priorDay)) {
    const key=JSON.stringify([row.chain_name,row.sku]);const old=previous.get(key);
    if(!old||Date.parse(row.captured_at)>Date.parse(old.captured_at))previous.set(key,row);
  }
  for(const product of products){const before=previous.get(product.key);product.change=before&&product.latest.promo_price!==null&&before.promo_price!==null?product.latest.promo_price-before.promo_price:null;}
  return products;
}

// Catalog chỉ chứa định danh và trạng thái, không chuyển thành giá/snapshot.
export function validateCatalog(input:unknown):CatalogProduct[] {
 if(!Array.isArray(input))throw new Error('Catalog không hợp lệ');
 return input.map(raw=>{
  const item=raw as CatalogProduct;
  if(!CHAINS.includes(item.chain_name as typeof CHAINS[number])||(item.status==='ready'&&!item.sku)||typeof item.sku!=='string'||!item.product_name||!['ready','review'].includes(item.status)||!Number.isFinite(Date.parse(item.discovered_at))||typeof item.reason!=='string')throw new Error('Catalog không hợp lệ');
  const url=new URL(item.source_url),domain=domains[item.chain_name];
  if(url.protocol!=='https:'||url.username||url.password||![domain,'www.'+domain].includes(url.hostname))throw new Error('Nguồn catalog không hợp lệ');
  return item;
 });
}
