// Giới hạn theo byte để CTKM dài không làm phản hồi vượt giới hạn hosting.
export function comparisonPage<T extends {rows:unknown[]}>(data:T,offset:number,budget=3_500_000){
 if(!Number.isSafeInteger(offset)||offset<0||offset>data.rows.length)throw Error('Offset không hợp lệ.');
 const metadata={...data,rows:[],next_offset:null};let size=Buffer.byteLength(JSON.stringify(metadata))+128;
 if(size>=budget)throw Error('Metadata quá lớn.');
 const rows:unknown[]=[];
 for(let i=offset;i<data.rows.length&&rows.length<1500;i++){
  const bytes=Buffer.byteLength(JSON.stringify(data.rows[i]))+1;
  if(size+bytes>budget){if(!rows.length)throw Error('Một bản ghi quá lớn.');break;}
  rows.push(data.rows[i]);size+=bytes;
 }
 return {...data,rows,next_offset:offset+rows.length<data.rows.length?offset+rows.length:null};
}
