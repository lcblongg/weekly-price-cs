import {supabase} from './supabase';
// Token Supabase dùng để xác thực các API quản trị trên cloud, không phải khóa service role.
export async function apiFetch(url:string,options:RequestInit={}){
 const headers=new Headers(options.headers);
 if(process.env.NEXT_PUBLIC_DATA_MODE==='live'){
  const {data}=await supabase().auth.getSession();if(data.session)headers.set('Authorization',`Bearer ${data.session.access_token}`);
 }
 return fetch(url,{...options,headers});
}
