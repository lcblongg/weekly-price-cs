'use client';
import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
import {supabase} from '@/lib/supabase';
import s from './comparison.module.css';
const Auth=createContext<{userId:string;role:string}|null>(null);
export const useCloudAuth=()=>useContext(Auth);
export default function CloudGate({children,admin=false,optional=false}:{children:ReactNode;admin?:boolean;optional?:boolean}){
 const [member,setMember]=useState<{userId:string;role:string}|null>(null),[loading,setLoading]=useState(true),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState('');
 useEffect(()=>{
  let stopped=false,unsubscribe=()=>{};
  const update=async()=>{try{
   const client=supabase();const {data,error:authError}=await client.auth.getUser();
   if(authError||!data.user){if(!stopped)setMember(null);return;}
   const m=await client.from('app_members').select('role').eq('user_id',data.user.id).maybeSingle();
   if(m.error||!m.data){if(!stopped){setMember(null);setError('Tài khoản chưa được quản trị viên cấp quyền.');}return;}
   if(!stopped){setMember({userId:data.user.id,role:m.data.role});setError('');}
  }catch{if(!stopped){setMember(null);setError('Chưa kết nối được Supabase. Kiểm tra cấu hình dịch vụ.');}}finally{if(!stopped)setLoading(false);}};
  try{const {data}=supabase().auth.onAuthStateChange(()=>{setTimeout(()=>{if(!stopped)void update();},0);});unsubscribe=()=>data.subscription.unsubscribe();}catch{setError('Chưa cấu hình Supabase.');setLoading(false);}
  void update();return()=>{stopped=true;unsubscribe();};
 },[]);
 if(loading)return <main className={s.page}>Đang kiểm tra phiên đăng nhập…</main>;
 if(!member&&optional&&!admin)return <Auth.Provider value={null}>{children}</Auth.Provider>;
 if(member){if(admin&&member.role!=='admin')return <main className={s.page}><h1>Bạn chưa có quyền quản trị</h1><a href="/">Về bảng giá</a></main>;return <Auth.Provider value={member}>{children}</Auth.Provider>;}
 return <main className={s.page} style={{maxWidth:480,margin:'8vh auto'}}><section className={s.manager}><span className={s.eyebrow}>WEEKLY PRICE CS</span><h1>Đăng nhập</h1><p>Tài khoản do quản trị viên cấp cho đội ngũ CS.</p><form onSubmit={async e=>{e.preventDefault();setError('');setLoading(true);try{const r=await supabase().auth.signInWithPassword({email,password});if(r.error)setError('Email hoặc mật khẩu không đúng.');}catch{setError('Không kết nối được dịch vụ đăng nhập.');}finally{setPassword('');setLoading(false);}}}><label>Email<input autoComplete="username" type="email" required value={email} onChange={e=>setEmail(e.target.value)} style={{width:'100%',margin:'8px 0 16px'}}/></label><label>Mật khẩu<input autoComplete="current-password" type="password" required value={password} onChange={e=>setPassword(e.target.value)} style={{width:'100%',margin:'8px 0 16px'}}/></label><button className={s.primary}>Đăng nhập</button></form>{error&&<p role="alert">{error}</p>}</section></main>;
}
