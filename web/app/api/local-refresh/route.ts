import {readFile} from 'node:fs/promises';
import path from 'node:path';
export const dynamic='force-dynamic';
export async function GET(){
 if(process.env.NODE_ENV!=='development')return new Response(null,{status:404});
 try{
  const root=path.resolve(process.cwd(),'..'),relative=(await readFile(path.join(root,'artifacts/daily-local/latest.txt'),'utf8')).trim();
  // Không nhận đường dẫn từ client; vẫn chặn file pointer thoát khỏi thư mục kết quả.
  if(!/^artifacts\/daily-local\/\d{8}-\d{6}$/.test(relative))throw new Error('Invalid run');
  const state=JSON.parse(await readFile(path.join(root,relative,'status.json'),'utf8'));
  return Response.json({started_at:state.started_at,finished_at:state.finished_at,channels:state.channels},{headers:{'Cache-Control':'no-store'}});
 }catch{return Response.json({channels:{}},{headers:{'Cache-Control':'no-store'}});}
}
