import {test} from 'node:test';
import assert from 'node:assert/strict';
import {brandOf} from '../lib/product-meta';
test('chuẩn hóa hãng, ưu tiên metadata và không lấy tên đại lý làm hãng',()=>{
 assert.equal(brandOf({brand:'apple',product_name:'x'}),'Apple');
 assert.equal(brandOf({brand:'HP',product_name:'x'}),'HP');
 assert.equal(brandOf({brand:'Xiaomi',product_name:'Samsung'}),'Xiaomi');
 assert.equal(brandOf({product_name:'iPhone 16 Pro'}),'Apple');
 assert.equal(brandOf({product_name:'Galaxy Tab S10'}),'Samsung');
 assert.equal(brandOf({product_name:'Laptop Asus Vivobook'}),'Asus');
 assert.equal(brandOf({product_name:'Sản phẩm Phong Vũ'}),'Chưa xác định');
});
