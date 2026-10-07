import {cloudEnabled} from '@/lib/cloud-admin';
import {getCloudJobs,queueCloud} from '@/lib/cloud-management';
// Job "Xác minh và cập nhật giá" (chỉ local/development). Logic chạy/khóa/công bố nằm trong Python
// (apple_jobs.py, tools/apple_job.py) và dùng nguyên worker hiện có. Không gửi Telegram.
import {runPython} from '@/lib/local-python';
export const runtime='nodejs';
export const dynamic='force-dynamic';
function local(request:Request){const u=new URL(request.url);return process.env.NODE_ENV==='development'&&['localhost','127.0.0.1','[::1]'].includes(u.hostname);}
export async function GET(request:Request){
 if(cloudEnabled())return getCloudJobs(request);
 if(!local(request))return Response.json({error:'Chỉ dùng trên máy local.'},{status:403});
 const model=new URL(request.url).searchParams.get('model')??'';
 const {body}=await runPython('tools/apple_jobs_cli.py',['list'],JSON.stringify({model:model||null}),60000);
 return Response.json(body,{headers:{'Cache-Control':'no-store'}});
}
export async function POST(request:Request){
 if(cloudEnabled())return queueCloud(request,'verify_prices');
 const u=new URL(request.url);
 if(!local(request)||request.headers.get('origin')!==u.origin)return Response.json({error:'Chỉ chạy trên máy local.'},{status:403});
 let payload:{model?:unknown;channels?:unknown;fingerprint?:unknown};try{payload=JSON.parse(await request.text());}catch{return Response.json({error:'JSON không hợp lệ.'},{status:400});}
 if(typeof payload.model!=='string'||!Array.isArray(payload.channels))return Response.json({error:'Thiếu model hoặc kênh.'},{status:400});
 const {body}=await runPython('tools/apple_jobs_cli.py',['create'],JSON.stringify(payload),60000);
 if(body.ok===false)return Response.json({error:body.error},{status:body.busy?409:400});
 return Response.json(body);
}
