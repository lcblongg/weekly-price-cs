import {authorize,cloudEnabled,cloudError,publicView,serviceDb} from '@/lib/cloud-admin';
import {parseWatchlist} from '@/lib/watchlist';
// Danh sách "Sản phẩm theo dõi" dùng chung: admin chỉnh, mọi người xem Web thấy cùng danh sách.
// Không ảnh hưởng bot cào hoặc báo cáo Telegram nhóm.
export const dynamic='force-dynamic';
const KEY='public_watchlist';
export async function GET(request:Request){try{
 if(!cloudEnabled())return Response.json({error:'Chỉ dùng ở chế độ live.'},{status:404});
 const {db}=publicView()?{db:serviceDb()}:await authorize(request);
 const {data,error}=await db.from('app_settings').select('value').eq('key',KEY).maybeSingle();if(error)throw error;
 return Response.json({value:data?.value??null},{headers:{'Cache-Control':'no-store'}});
}catch(e){return cloudError(e);}}
export async function PUT(request:Request){try{
 if(!cloudEnabled())return Response.json({error:'Chỉ dùng ở chế độ live.'},{status:404});
 const text=await request.text();if(text.length>200000)return Response.json({error:'Danh sách quá lớn.'},{status:413});
 const {db}=await authorize(request,true);
 let value;try{value=parseWatchlist(JSON.parse(text));}catch{return Response.json({error:'Danh sách theo dõi không hợp lệ.'},{status:400});}
 const {error}=await db.from('app_settings').upsert({key:KEY,value,updated_at:new Date().toISOString()},{onConflict:'key'});if(error)throw error;
 return Response.json({saved:true});
}catch(e){return cloudError(e);}}
