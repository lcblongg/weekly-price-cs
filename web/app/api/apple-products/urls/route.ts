import {cloudEnabled} from '@/lib/cloud-admin';
import {getCloudUrls,queueCloud} from '@/lib/cloud-management';
// Trạng thái và kiểm tra URL nhập tay (chỉ local). Kiểm tra gọi tools/check_apple_urls.py: đọc trang thật,
// xác minh model/màu bằng hàm của worker; không ghi giá, không gửi Telegram.
import {runPython} from '@/lib/local-python';
export const runtime='nodejs';
export const dynamic='force-dynamic';
function local(request:Request){const u=new URL(request.url);return process.env.NODE_ENV==='development'&&['localhost','127.0.0.1','[::1]'].includes(u.hostname);}
export async function GET(request:Request){
 if(cloudEnabled())return getCloudUrls(request);
 if(!local(request))return Response.json({error:'Chỉ dùng trên máy local.'},{status:403});
 const {body}=await runPython('tools/apple_url_status.py',[],'',60000);
 return Response.json(body,{headers:{'Cache-Control':'no-store'}});
}
let running=false;
export async function POST(request:Request){
 if(cloudEnabled())return queueCloud(request,'check_urls');
 const u=new URL(request.url);
 if(!local(request)||request.headers.get('origin')!==u.origin)return Response.json({error:'Chỉ kiểm tra trên máy local.'},{status:403});
 if(running)return Response.json({error:'Đang có một lượt kiểm tra URL; vui lòng chờ.'},{status:409});
 let payload:{model?:unknown;channels?:unknown};try{payload=JSON.parse(await request.text());}catch{return Response.json({error:'JSON không hợp lệ.'},{status:400});}
 if(typeof payload.model!=='string'||!payload.model.trim())return Response.json({error:'Thiếu model.'},{status:400});
 running=true;
 try{const {body}=await runPython('tools/check_apple_urls.py',[],JSON.stringify({model:payload.model,channels:Array.isArray(payload.channels)?payload.channels:undefined}),900000);
  if(body.ok===false)return Response.json({error:body.error??'Không kiểm tra được.'},{status:400});return Response.json(body);}
 finally{running=false;}
}
