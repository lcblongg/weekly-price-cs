import {cloudEnabled} from '@/lib/cloud-admin';
import {previewCloud} from '@/lib/cloud-management';
// Kiểm tra quy chuẩn nháp trên snapshot đã có, bằng chính bộ nhận diện của bot (Python). Chỉ đọc.
import {runPython} from '@/lib/local-python';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export async function POST(request:Request){
 if(cloudEnabled())return previewCloud(request);
 const u=new URL(request.url);if(process.env.NODE_ENV!=='development'||!['localhost','127.0.0.1','[::1]'].includes(u.hostname)||request.headers.get('origin')!==u.origin)return Response.json({error:'Chỉ kiểm tra trên máy local.'},{status:403});
 const text=await request.text();if(text.length>10000)return Response.json({error:'Dữ liệu quá lớn.'},{status:413});
 let payload:{rule?:{model?:unknown;color?:unknown;aliases?:unknown};rename_from?:unknown};try{payload=JSON.parse(text);}catch{return Response.json({error:'JSON không hợp lệ.'},{status:400});}
 const rule=payload.rule;if(!rule||typeof rule.model!=='string'||!rule.model.trim()||!(rule.color===null||typeof rule.color==='string')||!Array.isArray(rule.aliases)||rule.aliases.some(a=>typeof a!=='string'))return Response.json({error:'Model/màu không hợp lệ.'},{status:400});
 const {body}=await runPython('tools/preview_apple_rule.py',[],JSON.stringify({rule,rename_from:typeof payload.rename_from==='string'?payload.rename_from:null}),60000);
 if(body.ok===false)return Response.json({error:body.error??'Không kiểm tra được.'},{status:400});
 return Response.json({checks:body.checks},{headers:{'Cache-Control':'no-store'}});
}
