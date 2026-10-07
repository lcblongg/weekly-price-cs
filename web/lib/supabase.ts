'use client';
import {createClient,type SupabaseClient} from '@supabase/supabase-js';
import {addDays} from './calendar';
import {validateRows} from './prices';
import {validateIssues} from './issues';
import type {DailyPrice,ScrapeIssue} from './types';
import {quoteDay,type Quote} from './comparison';
let client:SupabaseClient|undefined;
export function supabase() {
  const url=process.env.NEXT_PUBLIC_SUPABASE_URL;const key=process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if(!url||!key) throw new Error('Chưa cấu hình kết nối Supabase.');
  return client??=createClient(url,key); // Chỉ public anon key. Tuyệt đối không dùng service_role trong Web.
}
export async function loadWeek(start:string,signal:AbortSignal):Promise<DailyPrice[]> {
  const rows:DailyPrice[]=[];
  for(let offset=0;offset<50000;offset+=500) {
    const {data,error}=await supabase().from('daily_prices').select('*').gte('business_date',start).lte('business_date',addDays(start,6)).order('id').range(offset,offset+499).abortSignal(signal);
    if(error) throw new Error('Không tải được lịch sử giá. Kiểm tra kết nối, đăng nhập và migration 003.');
    rows.push(...validateRows(data));
    if(data.length<500) {
      if(process.env.NEXT_PUBLIC_DATA_MODE!=='live')return rows;
      // Lịch sử dùng cùng phạm vi màu đã xác minh với bảng so sánh; DB vẫn giữ đủ màu nguồn.
      const {data:{session}}=await supabase().auth.getSession();
      const response=await fetch('/api/comparison?start='+start,{signal,headers:{Authorization:'Bearer '+(session?.access_token??'')}});
      if(!response.ok)throw new Error('Không tải được phạm vi màu đã xác minh cho lịch sử.');
      const snapshot=await response.json();
      const chains:Record<string,string>={MW:'TGDD',CPS:'CellphoneS',FPT:'FPT Shop',VIETTEL:'Viettel Store',PV:'Phong Vũ'};
      const allowed=new Set((snapshot.rows as Quote[]).map(r=>JSON.stringify([chains[r.chain],r.sku,quoteDay(r)])));
      return rows.filter(r=>allowed.has(JSON.stringify([r.chain_name,r.sku,r.business_date])));
    }
  }
  throw new Error('Dữ liệu vượt giới hạn hiển thị; cần giới hạn phạm vi truy vấn.');
}
export async function loadIssues(start:string,signal:AbortSignal):Promise<ScrapeIssue[]> {
  const rows:ScrapeIssue[]=[];
  for(let offset=0;offset<50000;offset+=500) {
    const {data,error}=await supabase().from('scrape_issues').select('*').gte('business_date',start).lte('business_date',addDays(start,6)).order('id').range(offset,offset+499).abortSignal(signal);
    if(error) throw new Error('Không tải được danh sách cần kiểm tra. Kiểm tra migration 004.');
    rows.push(...validateIssues(data));
    if(data.length<500) return rows;
  }
  throw new Error('Dữ liệu vượt giới hạn hiển thị; cần giới hạn phạm vi truy vấn.');
}
