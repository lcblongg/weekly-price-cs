import {test} from 'node:test';
import assert from 'node:assert/strict';
import {comparisonPage} from '../lib/comparison-page';
import {loadComparison} from '../lib/load-comparison';
test('phân trang theo byte giữ CTKM nguyên vẹn, không mất SKU',()=>{
 const data={rows:Array.from({length:30},(_,i)=>({sku:'sku-'+i,promo_text:'Khuyến mãi '.repeat(400)})),models:['A']};let offset=0;const rows:unknown[]=[];
 while(true){const page=comparisonPage(data,offset,12000);assert.ok(Buffer.byteLength(JSON.stringify(page))<12000);rows.push(...page.rows);if(page.next_offset===null)break;offset=page.next_offset;}
 assert.deepEqual(rows,data.rows);
});
test('client bỏ lượt dở dang khi snapshot đổi, thử lại bằng generation mới',async()=>{
 const bodies=[{rows:[1],generation:'old',next_offset:1},{error:'changed'},{rows:[2],generation:'new',next_offset:1},{rows:[3],generation:'new',next_offset:null}];let calls=0;
 const fetcher=(async()=>{const body=bodies[calls++];return Response.json(body,{status:body.error?409:200});}) as typeof fetch;
 const result=await loadComparison<{rows:number[]}>('2026-10-05',new AbortController().signal,fetcher);assert.deepEqual(result.rows,[2,3]);
});
test('phân trang lặp hoặc một bản ghi quá lớn phải báo lỗi, không âm thầm thiếu',async()=>{
 assert.throws(()=>comparisonPage({rows:[{text:'X'.repeat(20000)}]},0,1000));
 await assert.rejects(loadComparison('2026-10-05',new AbortController().signal,(async()=>Response.json({rows:[1],generation:'x',next_offset:0})) as typeof fetch));
});

test('dashboard yêu cầu phạm vi tracked trên mọi trang, vẫn giữ tuần trước và generation',async()=>{
 const urls:string[]=[];
 const fetcher=async(url:string)=>{urls.push(url);return Response.json({rows:[{sku:String(urls.length)}],generation:'same',next_offset:urls.length===1?1:null});};
 const result=await loadComparison('2026-10-05',new AbortController().signal,fetcher,'tracked');
 assert.equal(result.rows.length,2);
 for(const url of urls){const q=new URL(url,'https://test').searchParams;assert.equal(q.get('scope'),'tracked');assert.equal(q.get('start'),'2026-10-05');}
 assert.equal(new URL(urls[1],'https://test').searchParams.get('generation'),'same');
});
