import {test} from 'node:test';
import assert from 'node:assert/strict';
import {fiscalLabel,weekStart} from '../lib/calendar';
import {groupWeek,validateRows,searchKey} from '../lib/prices';
import type {DailyPrice} from '../lib/types';
const row:DailyPrice={run_id:'x',captured_at:'2026-10-06T03:00:00Z',business_date:'2026-10-06',week_start:'2026-10-05',chain_name:'Viettel Store',sku:'locked-color',product_name:'iPhone 16 128GB · Đen',original_price:21000000,promo_price:20000000,promo_text:'Thu cũ giảm thêm',source_url:'https://viettelstore.vn/dien-thoai/iphone-pid123.html'};
test('lịch FY đúng mốc, đổi quý và đổi năm',()=>{assert.equal(fiscalLabel('2026-10-05'),'W2Q1FY27');assert.equal(fiscalLabel('2026-12-28'),'W1Q2FY27');assert.equal(fiscalLabel('2027-09-27'),'W1Q1FY28');assert.equal(weekStart('2026-10-11'),'2026-10-05');});
test('không tạo giá giả cho ngày thiếu; một ngày không tạo biến động',()=>{const product=groupWeek([row],'2026-10-05')[0];assert.equal(product.days.length,7);assert.equal(product.days[0],null);assert.equal(product.days[1]?.promo_price,20000000);assert.equal(product.change,null);});
test('chọn snapshot mới nhất dù timezone khác; không ghép màu khác',()=>{const later={...row,captured_at:'2026-10-06T11:00:00+07:00',promo_price:19000000};const products=groupWeek([row,later,{...row,sku:'another-color'}],'2026-10-05');assert.equal(products.length,2);assert.equal(products.find(p=>p.sku===row.sku)?.latest.promo_price,19000000);});
test('chỉ tính biến động khi có hai ngày thực tế',()=>{const product=groupWeek([row,{...row,business_date:'2026-10-08',promo_price:19000000,captured_at:'2026-10-08T03:00:00Z'}],'2026-10-05')[0];assert.equal(product.change,-1000000);assert.equal(product.days[2],null);});
test('loại URL giả và giá không hợp lệ',()=>{assert.equal(validateRows([row]).length,1);for(const bad of [{...row,source_url:'https://evil.example'},{...row,promo_price:0},{...row,original_price:1}])assert.throws(()=>validateRows([bad]));});
test('tìm tiếng Việt không dấu',()=>{assert.equal(searchKey('Điện thoại Đen'),'dien thoai den');});

test('theo ngày không lấy giá ngày khác và chỉ so đúng ngày trước',async()=>{
  const {groupDay}=await import('../lib/prices');
  assert.equal(groupDay([row],'2026-10-05').length,0);
  assert.equal(groupDay([row],'2026-10-06')[0].change,null);
  const prior={...row,business_date:'2026-10-05',captured_at:'2026-10-05T03:00:00Z',promo_price:21000000};
  const product=groupDay([prior,row],'2026-10-06')[0];
  assert.equal(product.latest.promo_price,20000000);assert.equal(product.change,-1000000);
  assert.equal(groupDay([prior,{...row,business_date:'2026-10-07'}],'2026-10-07')[0].change,null);
});

test('trạng thái không có giá vẫn là dữ liệu; không biến NULL thành 0 hay mức giảm',async()=>{
  const status={...row,promo_price:null,original_price:null,promo_text:'[Tình trạng] Ngừng kinh doanh',business_date:'2026-10-08',captured_at:'2026-10-08T03:00:00Z'};
  assert.equal(validateRows([status]).length,1);
  const product=groupWeek([row,status],'2026-10-05')[0];
  assert.equal(product.days[3]?.promo_price,null);assert.equal(product.days[2],null);assert.equal(product.change,null);
  const {groupDay}=await import('../lib/prices');assert.equal(groupDay([row,status],'2026-10-08')[0].latest.promo_price,null);
  assert.throws(()=>validateRows([{...status,promo_text:''}]));
  assert.throws(()=>validateRows([{...status,promo_price:0}]));
});
