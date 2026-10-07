import {test} from 'node:test';
import assert from 'node:assert/strict';
import {priceMovements,dailySeries} from '../lib/price-movement';
import type {Quote} from '../lib/comparison';
const q={chain:'MW',sku:'a',apple_model:'iPhone 16',storage:'128GB',display_variant:'',color:'Đen',promo_price:20000000,observed_at:'2026-10-06T10:00:00+07:00'} as Quote;
test('thông báo tăng/giảm đúng SKU; không lấy giá gốc hoặc SKU khác',()=>{
 const fresh={...q,promo_price:19000000,observed_at:'2026-10-07T10:00:00+07:00'};
 const changes=priceMovements([q,fresh,{...fresh,sku:'b',promo_price:1000000}], '2026-10-07');
 assert.equal(changes.length,1);assert.equal(changes[0].delta,-1000000);assert.equal(changes[0].percent,-5);assert.equal(changes[0].shock,true);
 assert.equal(priceMovements([q,{...fresh,color:'Hồng'}],'2026-10-07').length,0);
});
test('không tạo biến động cho NULL, ngày thiếu hoặc cùng một ngày; chọn lần cào cuối',()=>{
 const status={...q,promo_price:null,observed_at:'2026-10-07T10:00:00+07:00'};
 assert.equal(priceMovements([q,status],'2026-10-07').length,0);
 assert.equal(priceMovements([q],'2026-10-07').length,0);
 assert.equal(priceMovements([q,{...q,promo_price:1}],'2026-10-06').length,0);
 const fresh={...q,promo_price:21000000,observed_at:'2026-10-07T11:00:00+07:00'};
 assert.equal(priceMovements([q,fresh,status],'2026-10-07')[0].delta,1000000);
});
test('tuần giữ ngày trống và so tuần này với tuần trước; không gộp dung lượng hoặc kênh',()=>{
 const days=['2026-10-05','2026-10-06','2026-10-07','2026-10-08','2026-10-09','2026-10-10','2026-10-11'];
 const fresh={...q,promo_price:19000000,observed_at:'2026-10-07T10:00:00+07:00'};
 const rows=[q,fresh,{...fresh,chain:'CPS'},{...fresh,storage:'256GB'}];
 assert.equal(dailySeries(rows).size,3);
 assert.equal([...dailySeries(rows).values()][0].has('2026-10-05'),false);
 assert.equal(priceMovements(rows,'2026-10-11',days).length,0);
 const previous={...q,observed_at:'2026-10-01T10:00:00+07:00'};
 const changes=priceMovements([...rows,previous],'2026-10-11',days);assert.equal(changes.length,1);assert.equal(changes[0].delta,-1000000);
});

test('ngày không lùi qua hôm qua bị thiếu; tuần không lấy giá số cũ đè trạng thái cuối tuần',()=>{
 const fresh={...q,promo_price:19000000,observed_at:'2026-10-08T10:00:00+07:00'};
 assert.equal(priceMovements([q,fresh],'2026-10-08').length,0);
 const previous={...q,observed_at:'2026-10-04T10:00:00+07:00'},status={...fresh,promo_price:null};
 const days=['2026-10-05','2026-10-06','2026-10-07','2026-10-08','2026-10-09','2026-10-10','2026-10-11'];
 assert.equal(priceMovements([previous,q,status],'2026-10-11',days).length,0);
});
