import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateCatalog} from '../lib/prices';
import {modelEntry} from '../lib/watchlist';
const ready={chain_name:'TGDD',sku:'tgdd-123',product_name:'iPhone 16 Pro 256GB',category:'Điện thoại',brand:'Apple',model_name:'iPhone 16 Pro',source_url:'https://www.thegioididong.com/dtdd/iphone-16-pro',status:'ready',reason:'',discovered_at:'2026-10-06T11:00:00+07:00'};
test('model trong catalog không cần snapshot/giá để theo dõi, không tạo giá giả',()=>{
 const [item]=validateCatalog([ready]);assert.equal(modelEntry(item).name,'iPhone 16 Pro');assert.equal('promo_price' in item,false);
 assert.equal(validateCatalog([{...ready,sku:'',status:'review',reason:'Hết hàng'}]).length,1);
 assert.throws(()=>validateCatalog([{...ready,sku:''}]));assert.throws(()=>validateCatalog([{...ready,source_url:'https://evil.example'}]));
});
