import {test} from 'node:test';
import assert from 'node:assert/strict';
import {trackedComparison} from '../lib/tracked-comparison';
test('rút gọn tracked giữ SKU, ngày thiếu và trạng thái; không lấy model/màu ngoài danh sách',()=>{
 const selected={sku:'a',apple_model:'iPhone 17',apple_selection:'selected',promo_price:null,observed_at:'2026-10-07T10:00:00+07:00'};
 const previous={...selected,sku:'b',promo_price:20000000,observed_at:'2026-10-04T10:00:00+07:00'};
 const data={rows:[selected,previous,{...selected,apple_selection:'other'},{...selected,apple_model:'iPhone 17 Pro'}],issues:[{model_name:'iPhone 17',reason:'403'},{model_name:'iPhone 17 Pro',reason:'403'},{reason:'Kênh lỗi'}],models:['iPhone 17','iPhone 17 Pro'],model_meta:{'iPhone 17':{brand:'Apple',category:'phone'},'iPhone 17 Pro':{brand:'Apple',category:'phone'}},preferences:{products:[{model:'iPhone 17'},{model:'iPhone mới chưa có dữ liệu'}]},sources:[{slug:'fpt',warning:'HTTP 403'}]};
 const result=trackedComparison(data);
 assert.deepEqual(result.rows,[selected,previous]);assert.deepEqual(result.models,['iPhone 17','iPhone mới chưa có dữ liệu']);assert.equal(result.issues.length,2);assert.equal(result.sources,data.sources);
 assert.equal(data.rows.length,4);assert.equal(result.rows[0].promo_price,null);
});
