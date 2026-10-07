import type {ProductWeek,ScrapeIssue,CatalogProduct} from './types';
import {datesForWeek,fiscalLabel} from './calendar';
export async function exportExcel(products:ProductWeek[],start:string,day?:string,issues:ScrapeIssue[]=[],pending:CatalogProduct[]=[]) {
  const {Workbook}=await import('exceljs');const book=new Workbook();
  book.creator='Weekly Price CS';const sheet=book.addWorksheet(day?'Giá theo ngày':'Giá 7 ngày');
  const dates=day?[day]:datesForWeek(start);
  sheet.columns=[{header:'Tuần FY',key:'week',width:16},{header:'Chuỗi',key:'chain',width:20},{header:'Sản phẩm',key:'name',width:42},{header:'SKU / biến thể',key:'sku',width:60},...dates.map((date,i)=>({header:day?`Giá bán ${date}`:`${i===6?'CN':'T'+(i+2)} ${date}`,key:date,width:20})),{header:'Giá gốc mới nhất',key:'original',width:22},{header:'CTKM mới nhất',key:'promo',width:80},{header:'Link nguồn',key:'url',width:60},{header:'Thời điểm cập nhật',key:'time',width:28},{header:'Trạng thái sản phẩm',key:'status',width:70}];
  for(const product of products) {
    const record:Record<string,string|number|null>={week:fiscalLabel(start),chain:product.chain,name:product.name,sku:product.sku,original:product.latest.original_price,promo:product.latest.promo_text,url:product.latest.source_url,time:product.latest.captured_at,status:product.latest.promo_text.startsWith('[Tình trạng] ')?product.latest.promo_text.split('\n')[0].slice(13):''};
    dates.forEach((date,i)=>{record[date]=day?product.latest.promo_price:product.days[i]?.promo_price??null;});
    // Chuỗi luôn là cell text; không đưa dữ liệu từ đại lý vào công thức/hyperlink Excel.
    const row=sheet.addRow(record);row.alignment={vertical:'top',wrapText:true};
    for(let col=5;col<=5+dates.length;col++) row.getCell(col).numFmt='#,##0" đ"';
  }
  sheet.getRow(1).font={bold:true,color:{argb:'FFFFFFFF'}};sheet.getRow(1).height=28;
  sheet.getRow(1).eachCell(cell=>{cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FF183F34'}};});
  sheet.views=[{state:'frozen',xSplit:3,ySplit:1}];sheet.autoFilter={from:'A1',to:{row:1,column:sheet.columns.length}};
  // Sheet riêng cho link chưa có giá, cùng bộ lọc đang chọn; không trộn vào cột giá.
  const review=book.addWorksheet('Cần kiểm tra');
  review.columns=[{header:'Chuỗi',key:'chain',width:18},{header:'Danh mục',key:'category',width:20},{header:'Sản phẩm',key:'name',width:50},{header:'SKU',key:'sku',width:30},{header:'Loại',key:'stage',width:20},{header:'Lý do',key:'reason',width:70},{header:'Link nguồn',key:'url',width:60},{header:'Lượt quét',key:'time',width:28}];
  for(const issue of issues) review.addRow({chain:issue.chain_name,category:issue.category,name:issue.product_name,sku:issue.sku,stage:issue.stage==='catalog'?'Catalog cần xem':'Lỗi đọc trang',reason:issue.reason,url:issue.source_url,time:issue.captured_at}).alignment={vertical:'top',wrapText:true};
  review.getRow(1).font={bold:true,color:{argb:'FFFFFFFF'}};review.getRow(1).eachCell(cell=>{cell.fill={type:'pattern',pattern:'solid',fgColor:{argb:'FF8A5A00'}};});
  review.views=[{state:'frozen',ySplit:1}];
  const statuses=book.addWorksheet(day?'Trạng thái trong ngày':'Trạng thái 7 ngày');
  statuses.columns=[{header:'Chuỗi',key:'chain',width:20},{header:'Sản phẩm',key:'name',width:55},{header:'SKU',key:'sku',width:45},...dates.map(d=>({header:d,key:d,width:70}))];
  for(const p of products){const item:Record<string,string>={chain:p.chain,name:p.name,sku:p.sku};dates.forEach((d,i)=>{const r=day?p.latest:p.days[i];item[d]=r?(r.promo_text.startsWith('[Tình trạng] ')?r.promo_text.split('\n')[0].slice(13):'Đã ghi nhận giá hiển thị'):'Chưa có dữ liệu';});statuses.addRow(item).alignment={wrapText:true,vertical:'top'};}
  statuses.getRow(1).font={bold:true};statuses.views=[{state:'frozen',ySplit:1}];
  if(pending.length){
    const catalog=book.addWorksheet('Chưa có kết quả giá');
    catalog.columns=[{header:'Chuỗi',key:'chain',width:20},{header:'Hãng',key:'brand',width:18},{header:'Danh mục',key:'category',width:24},{header:'Model',key:'model',width:40},{header:'Sản phẩm',key:'name',width:60},{header:'SKU',key:'sku',width:40},{header:'Trạng thái',key:'status',width:80},{header:'Link nguồn',key:'url',width:60}];
    pending.forEach(p=>catalog.addRow({chain:p.chain_name,brand:p.brand??'',category:p.category??'',model:p.model_name??'',name:p.product_name,sku:p.sku,status:p.status==='review'?`Catalog cần kiểm tra: ${p.reason}`:'Chưa quét giá trong kỳ đang chọn',url:p.source_url}));
    catalog.getRow(1).font={bold:true};catalog.views=[{state:'frozen',ySplit:1}];
  }
  const buffer=await book.xlsx.writeBuffer();const blob=new Blob([buffer as BlobPart],{type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'});
  const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`weekly-price-${day??fiscalLabel(start)}.xlsx`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
