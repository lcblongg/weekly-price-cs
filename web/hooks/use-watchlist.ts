'use client';
import {useCallback,useEffect,useRef,useState} from 'react';
import {supabase} from '@/lib/supabase';
import {discoverModels,emptyWatchlist,parseWatchlist,type ModelEntry,type Watchlist} from '@/lib/watchlist';
const KEY='weekly-price-cs:watchlist:v1';
export function useWatchlist(mode:string,userId:string|null,entries:ModelEntry[]) {
 const [state,setState]=useState<Watchlist>(emptyWatchlist),[ready,setReady]=useState(false),[status,setStatus]=useState(''),[error,setError]=useState(''),[retry,setRetry]=useState(0);
 const generation=useRef(0),queue=useRef<Promise<void>>(Promise.resolve()),latest=useRef(state);
 useEffect(()=>{
  const token=++generation.current;let active=true;
  setReady(false);setState(emptyWatchlist());setError('');setStatus('');
  async function load(){try{
   let value:unknown=null;
   if(mode==='demo'){const raw=localStorage.getItem(KEY);if(raw)value=JSON.parse(raw);}
   else if(mode==='live'&&userId){const {data,error}=await supabase().from('personal_watchlists').select('preferences').eq('user_id',userId).maybeSingle();if(error)throw error;value=data?.preferences;}
   else return;
   if(active&&token===generation.current){const loaded=value?parseWatchlist(value):emptyWatchlist();latest.current=loaded;setState(loaded);setReady(true);setStatus(mode==='demo'?'Lưu trên trình duyệt này':'Lưu theo tài khoản');}
  }catch{if(active){setError(mode==='demo'?'Không đọc được lựa chọn trên trình duyệt.':'Không tải được lựa chọn. Kiểm tra kết nối và migration 006.');}}}
  void load();return()=>{active=false;};
 },[mode,userId,retry]);
 const change=useCallback((value:Watchlist)=>{
  if(!ready)return;latest.current=value;setState(value);setError('');setStatus('Đang lưu…');
  const token=generation.current;
  queue.current=queue.current.catch(()=>{}).then(async()=>{
   if(token!==generation.current)return;
   try{
    if(mode==='demo')localStorage.setItem(KEY,JSON.stringify(value));
    else if(mode==='live'&&userId){const {error}=await supabase().from('personal_watchlists').upsert({user_id:userId,preferences:value,updated_at:new Date().toISOString()},{onConflict:'user_id'});if(error)throw error;}
    if(token===generation.current&&latest.current===value)setStatus(mode==='demo'?'Đã lưu trên trình duyệt':'Đã lưu theo tài khoản');
   }catch{if(token===generation.current){setStatus('Chưa lưu');setError('Không lưu được lựa chọn. Hãy thử lại trước khi tải lại trang.');}}
  });
 },[mode,userId,ready]);
 useEffect(()=>{if(ready){const next=discoverModels(state,entries);if(next!==state)change(next);}},[entries,state,ready,change]);
 return {state,ready,status,error,change,onRetry:()=>{if(ready)change(latest.current);else setRetry(n=>n+1);}};
}
