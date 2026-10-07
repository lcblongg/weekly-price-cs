import {test} from 'node:test';
import assert from 'node:assert/strict';
import {discoverModels,emptyWatchlist,isWatched,modelEntry,parseWatchlist} from '../lib/watchlist';
import type {DailyPrice} from '../lib/types';
const row={category:'Điện thoại',model_name:'iPhone 16',product_name:'iPhone 16 128GB',chain_name:'TGDD',sku:'a'} as DailyPrice;
test('ẩn model chính xác trên mọi kênh, không ẩn bản Pro và không gộp SKU',()=>{
 const state=discoverModels(emptyWatchlist(),[modelEntry(row)]);state.hidden=[modelEntry(row).id];
 assert.equal(isWatched(state,row),false);assert.equal(isWatched(state,{...row,chain_name:'CellphoneS',sku:'b'}),false);
 assert.equal(isWatched(state,{...row,model_name:'iPhone 16 Pro'}),true);assert.equal(isWatched(state,{...row,model_name:'iPhone 16 Pro Max'}),true);
});
test('lần đầu làm baseline; model mới mặc định theo dõi và có nhãn Mới',()=>{
 const base=discoverModels(emptyWatchlist(),[modelEntry(row),modelEntry({...row,chain_name:'FPT Shop'})]);assert.equal(base.models.length,1);assert.deepEqual(base.fresh,[]);
 base.hidden=[modelEntry(row).id];const nextRow={...row,model_name:'iPhone 17'};const next=discoverModels(base,[modelEntry(nextRow)]);
 assert.equal(isWatched(next,nextRow),true);assert.deepEqual(next.fresh,[modelEntry(nextRow).id]);assert.equal(isWatched(next,row),false);
 assert.deepEqual(parseWatchlist(JSON.parse(JSON.stringify(next))),next);
});
test('định danh chuẩn hóa hoa thường/khoảng trắng, tách danh mục; dữ liệu hỏng bị từ chối',()=>{
 assert.equal(modelEntry(row).id,modelEntry({...row,model_name:' IPHONE   16 '}).id);
 assert.notEqual(modelEntry(row).id,modelEntry({...row,category:'Máy tính bảng'}).id);
 assert.throws(()=>parseWatchlist({version:1,models:[{id:'bad',name:'x',category:'y'}],hidden:[],fresh:[]}));
});
