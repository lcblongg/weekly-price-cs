import {createClient} from '@supabase/supabase-js';
export function cloudEnabled(){return process.env.NEXT_PUBLIC_DATA_MODE==='live';}
export function serviceDb(){const url=process.env.NEXT_PUBLIC_SUPABASE_URL,key=process.env.SUPABASE_SERVICE_ROLE_KEY;if(!url||!key)throw new Error('Chưa cấu hình dịch vụ Supabase phía server.');return createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});}
export async function authorize(request:Request,admin=false){
 const jwt=request.headers.get('authorization')?.match(/^Bearer (.+)$/)?.[1];if(!jwt)throw new Error('401: Vui lòng đăng nhập.');
 const db=serviceDb();const {data,error}=await db.auth.getUser(jwt);if(error||!data.user)throw new Error('401: Phiên đăng nhập không hợp lệ.');
 const member=await db.from('app_members').select('role').eq('user_id',data.user.id).maybeSingle();if(member.error||!member.data||admin&&member.data.role!=='admin')throw new Error('403: Tài khoản chưa được cấp quyền.');
 return {db,userId:data.user.id,role:member.data.role};
}
export function cloudError(error:unknown){const text=error instanceof Error?error.message:'Lỗi dịch vụ';const status=text.startsWith('401:')?401:text.startsWith('403:')?403:500;return Response.json({error:status===500?'Không xử lý được yêu cầu. Kiểm tra cấu hình dịch vụ hoặc thử lại.':text.slice(5)},{status});}
export async function enqueue(request:Request,kind:string,payload:unknown){
 const {db,userId}=await authorize(request,true);
 // Job hết lease không được chặn mãi; runner còn sống phải heartbeat và ngừng công bố khi mất lease.
 await db.from('automation_jobs').update({status:'error',finished_at:new Date().toISOString(),result:{error:'Job hết thời gian; không xác nhận đã cập nhật'}}).in('status',['pending','running']).lt('lease_until',new Date().toISOString());
 const {data:job,error}=await db.from('automation_jobs').insert({kind,payload,requested_by:userId,lease_until:new Date(Date.now()+6*3600000).toISOString()}).select().single();
 if(error){if(error.code==='23505')return Response.json({error:'Đang có một lượt chạy; chờ hoàn tất rồi thử lại.'},{status:409});throw error;}
 try{
  const repo=process.env.GITHUB_REPOSITORY,token=process.env.GITHUB_ACTIONS_TOKEN,ref=process.env.GITHUB_WORKFLOW_REF||'main';if(!repo||!token||!/^[-\w.]+\/[-\w.]+$/.test(repo))throw Error('Chưa cấu hình GitHub runner');
  const r=await fetch(`https://api.github.com/repos/${repo}/actions/workflows/cloud_job.yml/dispatches`,{method:'POST',signal:AbortSignal.timeout(15000),headers:{Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'},body:JSON.stringify({ref,inputs:{job_id:job.id}})});
  if(!r.ok)throw Error('Không khởi chạy được GitHub runner');
 }catch{await db.from('automation_jobs').update({status:'error',finished_at:new Date().toISOString(),result:{error:'Chưa gửi được yêu cầu tới GitHub; kiểm tra cấu hình runner'}}).eq('id',job.id);return Response.json({error:'Chưa khởi chạy được bot trên GitHub. Kiểm tra cấu hình runner.'},{status:502});}
 return Response.json({ok:true,queued:true,job,message:'Yêu cầu đã được đưa vào hàng đợi GitHub; theo dõi trạng thái bên dưới.'},{status:202});
}
