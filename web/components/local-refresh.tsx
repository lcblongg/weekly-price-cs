'use client';
import {useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
type Channel={status:string;phase?:string;apple?:{fresh:number;issues:number};catalog?:{fresh:number;issues:number};reason?:string};
type State={started_at?:string;finished_at?:string;channels:Record<string,Channel>};
const labels:Record<string,string>={tgdd:'MW',cellphones:'CPS',fpt:'FPT',viettel:'Viettel',phongvu:'PV'};
export default function LocalRefresh(){
 const [state,setState]=useState<State|null>(null),router=useRouter();
 useEffect(()=>{let alive=true,last='';const poll=async()=>{try{const response=await fetch('/api/local-refresh',{cache:'no-store'});if(!response.ok)return;const data:State=await response.json();if(!alive)return;setState(data);const current=JSON.stringify(data.channels);if(last&&last!==current)router.refresh();last=current;}catch{/* Kết quả đã công bố vẫn xem được khi mất kết nối. */}};void poll();const timer=setInterval(poll,15000);return()=>{alive=false;clearInterval(timer);};},[router]);
 if(!state?.started_at)return null;
 const running=Object.values(state.channels).some(c=>c.status==='pending'||c.status==='running');
 return <aside role="status" style={{padding:'12px 16px',background:'#fff5dc',borderRadius:10,margin:'12px 0',color:'#6e5113'}}><strong>Lượt cào thật {new Date(state.started_at).toLocaleDateString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'})}: {running?'đang cập nhật':'đã kết thúc'}</strong><p style={{margin:'6px 0'}}>Giá từng kênh xuất hiện khi bước xác minh hoàn tất. Ô trống chưa được xác minh không có nghĩa hết hàng.</p><div style={{display:'flex',gap:16,flexWrap:'wrap'}}>{Object.entries(state.channels).map(([slug,c])=><span key={slug}><b>{labels[slug]||slug}</b>: {c.status==='error'?'Lỗi — giữ dữ liệu cũ':c.status==='pending'?'Chờ chạy':c.status==='running'?(c.phase==='apple'?'Đang xác minh màu Apple':'Đang cào toàn catalog'):c.status==='partial'?'Xong, còn lỗi nguồn':'Xong'}{c.apple&&` · ${c.apple.fresh} SKU Apple, ${c.apple.issues} mục Apple cần đối chiếu`}{c.catalog&&` · ${c.catalog.fresh} SKU mới, ${c.catalog.issues} lỗi`}</span>)}</div></aside>;
}
