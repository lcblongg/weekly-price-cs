'use client';
import {compareModels} from '../lib/product-standard';

import {useState} from 'react';
import {Button} from './ui/button';
import {Input} from './ui/input';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from './ui/select';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription} from './ui/dialog';
import {searchKey} from '@/lib/prices';
import type {Watchlist} from '@/lib/watchlist';
export default function WatchlistPanel({state,onChange,ready,status,error,onRetry}:{state:Watchlist;onChange:(v:Watchlist)=>void;ready:boolean;status:string;error:string;onRetry:()=>void}) {
 const [open,setOpen]=useState(false),[query,setQuery]=useState(''),[brand,setBrand]=useState('all');
 const hidden=state.models.filter(m=>state.hidden.includes(m.id)).length;
 const entries=state.models.filter(m=>(brand==='all'||(m.brand??'Chưa xác định')===brand)&&searchKey(m.name).includes(searchKey(query))).sort((a,b)=>compareModels(a.name,b.name));
 const categories=[...new Set(entries.map(m=>m.category))];
 return <><div className="watchlist-bar"><Button variant="outline" onClick={()=>setOpen(true)}>Sản phẩm theo dõi</Button><span>{ready?`${state.models.length-hidden} model đang theo dõi · ${hidden} model đã ẩn`:'Đang tải lựa chọn…'}</span><small role="status">{status}</small>{error&&<span role="alert">{error} <button onClick={onRetry}>Thử lại</button></span>}</div>
 <Dialog open={open} onOpenChange={setOpen}><DialogContent className="watchlist-dialog"><DialogHeader><DialogTitle>Sản phẩm theo dõi</DialogTitle><DialogDescription>Lựa chọn cá nhân áp dụng cho tất cả đại lý, bảng giá, CTKM và Excel. Bot vẫn thu thập đầy đủ; Telegram nhóm dùng phạm vi riêng.</DialogDescription></DialogHeader>
 <Input aria-label="Tìm model theo dõi" placeholder="Tìm tên model…" value={query} onChange={e=>setQuery(e.target.value)}/>
 <Select value={brand} onValueChange={setBrand}><SelectTrigger aria-label="Lọc hãng theo dõi"><SelectValue/></SelectTrigger><SelectContent><SelectItem value="all">Tất cả hãng</SelectItem>{[...new Set(state.models.map(m=>m.brand??'Chưa xác định'))].sort().map(name=><SelectItem key={name} value={name}>{name}</SelectItem>)}</SelectContent></Select>
 <div className="watchlist-actions"><Button variant="outline" disabled={!ready} onClick={()=>onChange({...state,hidden:[]})}>Chọn tất cả</Button><Button variant="outline" disabled={!ready} onClick={()=>onChange({...state,hidden:state.models.map(m=>m.id)})}>Bỏ chọn tất cả</Button><Button variant="outline" disabled={!ready} onClick={()=>onChange({...state,hidden:[],fresh:[]})}>Khôi phục mặc định</Button>{state.fresh.length>0&&<Button variant="outline" disabled={!ready} onClick={()=>onChange({...state,fresh:[]})}>Đã xem model mới</Button>}</div>
 <p>{state.models.length-hidden} model đang theo dõi · {hidden} model đã ẩn. Chọn tất cả áp dụng cho toàn bộ danh sách.</p>
 <div className="watchlist-groups">{categories.map(category=><fieldset key={category}><legend>{category}</legend>{entries.filter(m=>m.category===category).map(m=><label key={m.id}><input type="checkbox" aria-label={m.name} disabled={!ready} checked={!state.hidden.includes(m.id)} onChange={e=>onChange({...state,hidden:e.target.checked?state.hidden.filter(id=>id!==m.id):[...new Set([...state.hidden,m.id])]})}/><span>{m.name}</span>{state.fresh.includes(m.id)&&<small className="new-model">Mới</small>}</label>)}</fieldset>)}{!entries.length&&<p>Chưa có model phù hợp. Danh sách được bổ sung khi tải dữ liệu các ngày/tuần.</p>}</div><p role="status">{status}</p>{error&&<p role="alert">{error}</p>}</DialogContent></Dialog></>;
}
