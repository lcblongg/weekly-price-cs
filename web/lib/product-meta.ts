import {canonicalAppleModel} from './product-standard';
import type {DailyPrice,ProductMetadata} from './types';
export const CATEGORIES=['Điện thoại','Máy tính bảng','Máy tính xách tay','Đồng hồ thông minh','AirPods'];
export function categoryOf(row:ProductMetadata):string {
  if(row.category?.trim())return /^airpods$/i.test(row.category)?'AirPods':row.category.trim();
  // Dữ liệu cũ chưa có category: chỉ nhận các dòng tên rõ ràng, còn lại giữ chưa phân loại.
  const name=row.product_name;
  if(/\bairpods\b/i.test(name))return 'AirPods';
  if(/\b(ipad|tablet|galaxy tab|xiaomi pad|oppo pad)\b/i.test(name))return 'Máy tính bảng';
  if(/\b(apple watch|galaxy watch|smartwatch|đồng hồ)\b/i.test(name))return 'Đồng hồ thông minh';
  if(/\b(macbook|laptop|máy tính xách tay)\b/i.test(name))return 'Máy tính xách tay';
  if(/\b(iphone|điện thoại|smartphone)\b/i.test(name))return 'Điện thoại';
  return 'Chưa phân loại';
}
export function modelOf(row:ProductMetadata):string {
  if(row.model_name?.trim())return canonicalAppleModel(row.model_name)??row.model_name.trim();
  const canonical=canonicalAppleModel(row.product_name);
  if(canonical)return canonical;
  if(row.model_name?.trim())return row.model_name.trim();
  const name=row.product_name.split(' · ')[0].trim();
  const iphone=name.match(/\biphone\s+(\d{1,2}e?|air|duo)(?:\s+(pro\s+max|pro|plus|mini))?\b/i);
  if(iphone){const number=iphone[1].replace(/^air$/i,'Air').replace(/^duo$/i,'Duo').toLowerCase().replace(/^air$/,'Air').replace(/^duo$/,'Duo');const suffix=iphone[2]?.toLowerCase().replace(/\b\w/g,c=>c.toUpperCase());return `iPhone ${number}${suffix?' '+suffix:''}`;}
  // Không suy đoán tên model cho laptop/watch chưa có metadata; giữ tên nguồn.
  return name;
}

const BRAND_ALIASES:Record<string,string>={apple:'Apple',iphone:'Apple',ipad:'Apple',macbook:'Apple',airpods:'Apple',samsung:'Samsung',xiaomi:'Xiaomi',redmi:'Xiaomi',poco:'Xiaomi',oppo:'OPPO',asus:'Asus',hp:'HP',dell:'Dell',lenovo:'Lenovo',huawei:'Huawei',garmin:'Garmin',acer:'Acer',msi:'MSI'};
export function brandOf(row:Pick<DailyPrice,'brand'|'product_name'>):string {
 const explicit=row.brand?.trim();
 if(explicit)return BRAND_ALIASES[explicit.toLowerCase()]??explicit;
 // Chỉ nhận hãng khi tên có token rõ ràng; không dùng tên đại lý làm hãng.
 const name=row.product_name??'';
 if(/\b(apple|iphone|ipad|macbook|airpods)\b/i.test(name))return 'Apple';
 if(/\b(samsung|galaxy)\b/i.test(name))return 'Samsung';
 if(/\b(xiaomi|redmi|poco)\b/i.test(name))return 'Xiaomi';
 const match=name.match(/\b(oppo|asus|hp|dell|lenovo|huawei|garmin|acer|msi)\b/i);
 return match?BRAND_ALIASES[match[1].toLowerCase()]:'Chưa xác định';
}

export function statusOf(row:Pick<DailyPrice,'promo_text'>):string {return row.promo_text.startsWith('[Tình trạng] ')?row.promo_text.split('\n')[0].slice('[Tình trạng] '.length):'';}
