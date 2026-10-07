import {test} from 'node:test';
import assert from 'node:assert/strict';
import {matrix,cellPrice,type Quote} from '../lib/comparison';
const q={sku:'a',apple_model:'iPhone 18 Pro Max',storage:'256GB',product_name:'iPhone 18 Pro Max 256GB',chain:'MW',display_variant:'',promo_price:41990000} as Quote;
test('so sánh cùng cấu hình qua kênh, giữ mọi SKU và không đổi thiếu dữ liệu thành OOS',()=>{const rows=matrix([q,{...q,chain:'CPS',sku:'b',promo_price:41000000},{...q,sku:'c',promo_price:42000000}]);assert.equal(rows.length,1);assert.equal(rows[0].cells.MW.length,2);assert.deepEqual(cellPrice(rows[0].cells.MW),{min:41990000,max:42000000});assert.equal(cellPrice(rows[0].cells.FPT??[]),null);});
test('tách cấu hình mạng và đúng thứ tự model/dung lượng',()=>{const rows=matrix([{...q,storage:'1TB'},{...q,storage:'512GB'},q,{...q,apple_model:'iPhone 18 Pro'}, {...q,apple_model:'iPad Air M4 11',display_variant:'WiFi'},{...q,apple_model:'iPad Air M4 11',display_variant:'5G / Cellular'}]);assert.equal(rows.length,6);assert.deepEqual(rows.slice(0,3).map(r=>r.name),['iPhone 18 Pro Max 256GB','iPhone 18 Pro Max 512GB','iPhone 18 Pro Max 1TB']);});

test('không bỏ iPhone Duo và hãng khác; giữ riêng dung lượng',()=>{const rows=matrix([{...q,apple_model:'iPhone Duo',storage:'256GB',brand:'Apple'},{...q,apple_model:'iPhone Duo',storage:'512GB',brand:'Apple'},{...q,apple_model:'Samsung Galaxy S26',brand:'Samsung'}]);assert.equal(rows.length,3);assert.equal(rows.filter(r=>r.model==='iPhone Duo').length,2);assert.ok(rows.some(r=>r.model==='Samsung Galaxy S26'));});
