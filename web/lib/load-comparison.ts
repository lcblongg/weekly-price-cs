// Tải đủ trang, giữ một generation nhất quán; không đưa snapshot dở dang lên UI/Excel.
export async function loadComparison<T extends {rows:unknown[]}>(start:string,signal:AbortSignal,fetcher:(url:string,init?:RequestInit)=>Promise<Response>=fetch,scope?:'tracked'):Promise<T>{
 for(let attempt=0;attempt<3;attempt++){
  let offset=0,generation='',result:T|undefined;const rows:unknown[]=[];let changed=false;
  while(true){
   const q=new URLSearchParams({start,offset:String(offset)});if(scope)q.set('scope',scope);if(generation)q.set('generation',generation);
   const response=await fetcher('/api/comparison?'+q,{signal});
   if(response.status===409){changed=true;break;}
   const data=await response.json();if(!response.ok)throw Error(data.error||'Không tải được bảng giá.');
   if(!Array.isArray(data.rows)||typeof data.generation!=='string')throw Error('Phản hồi bảng giá không hợp lệ.');
   if(!result){result=data;generation=data.generation;}else if(data.generation!==generation){changed=true;break;}
   rows.push(...data.rows);if(rows.length>100000)throw Error('Phạm vi dữ liệu quá lớn. Chọn tuần khác.');
   if(data.next_offset===null)return {...result,rows} as T;
   if(!Number.isSafeInteger(data.next_offset)||data.next_offset<=offset)throw Error('Phân trang bảng giá không hợp lệ.');
   offset=data.next_offset;
  }
  if(!changed)break;
 }
 throw Error('Dữ liệu đang được cập nhật. Hãy tải lại sau khi bot hoàn tất.');
}
