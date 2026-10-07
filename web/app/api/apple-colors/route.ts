import {cloudEnabled} from '@/lib/cloud-admin';
import {getCloudColors,queueCloud} from '@/lib/cloud-management';
// Trình chỉnh cấu hình dự án trên máy local. Khi deploy phải dùng Auth/quyền quản trị + Supabase.
// Toàn bộ kiểm tra/ghi quy chuẩn do tools/apply_apple_rules.py (Python, dùng chung với bot) đảm nhiệm.
import {readFile} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {runPython} from '@/lib/local-python';
const root=resolve(process.cwd(),'..');
const path=process.env.WPCS_APPLE_COLORS||join(root,'config/apple_colors.json'); // biến cô lập dùng chung với Python khi kiểm thử
export const runtime='nodejs';
export const dynamic='force-dynamic';
function local(request:Request){const url=new URL(request.url);return process.env.NODE_ENV==='development'&&['localhost','127.0.0.1','[::1]'].includes(url.hostname)&&request.headers.get('origin')===url.origin;}
export async function GET(request:Request){
 if(cloudEnabled())return getCloudColors(request);if(process.env.NODE_ENV!=='development')return Response.json({error:'Cấu hình local chỉ dùng khi phát triển.'},{status:403});return Response.json(JSON.parse(await readFile(path,'utf8')),{headers:{'Cache-Control':'no-store'}});}
let queue:Promise<unknown>=Promise.resolve();
export async function POST(request:Request){
 if(cloudEnabled())return queueCloud(request,'config_update');
 if(!local(request)||!request.headers.get('content-type')?.startsWith('application/json'))return Response.json({error:'Chỉnh cấu hình chỉ được bật trên máy local.'},{status:403});
 const text=await request.text();if(text.length>60000)return Response.json({error:'Danh sách quá lớn.'},{status:413});
 let value:{version?:number;products?:unknown;renames?:unknown};try{value=JSON.parse(text);}catch{return Response.json({error:'JSON không hợp lệ.'},{status:400});}
 if(value?.version!==1)return Response.json({error:'Danh sách không hợp lệ.'},{status:400});
 const input=JSON.stringify({products:value.products,renames:value.renames??[]});
 // Xếp hàng: hai lần lưu không ghi chồng nhau.
 const save=queue.then(()=>runPython('tools/apply_apple_rules.py',[],input));queue=save.catch(()=>undefined);
 const {code,body}=await save;
 if(body.ok===false)return Response.json({error:body.error??'Không áp dụng được cấu hình.'},{status:400});
 if(code!==0)return Response.json({error:'Đã lưu quy chuẩn nhưng chưa dựng lại được trang: '+((body.rebuild_failed as string[]|undefined)?.join(', ')??'không rõ')},{status:500});
 return Response.json({saved:true,...body});
}
