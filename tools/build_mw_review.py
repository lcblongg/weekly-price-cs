"""Trang nghiệm thu riêng MW, chỉ dùng kết quả bot thật và ghi rõ phạm vi lượt chạy."""
import json,html,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from apple_preferences import load,presentation
from product_standard import MODELS,model_order
preferences=load()
preferences["products"].sort(key=lambda r:model_order(r["model"]))
slug=sys.argv[sys.argv.index('--chain')+1] if '--chain' in sys.argv else 'cellphones' if '--cps' in sys.argv else 'tgdd'
CPS=slug!='tgdd'
labels={'tgdd':'MW / Thế Giới Di Động','cellphones':'CPS / CellphoneS','fpt':'FPT Shop','viettel':'Viettel Store','phongvu':'Phong Vũ'}
short={'tgdd':'MW','cellphones':'CPS','fpt':'FPT','viettel':'VT','phongvu':'PV'}
selected_directory=ROOT/f'artifacts/{slug}-apple-selected' if slug not in ('tgdd','cellphones') else ROOT/('artifacts/cps-apple-selected' if CPS else 'artifacts/mw-apple-selected')
ready=ROOT/'artifacts/status-repair/tgdd/summary.json'
folder=(ROOT/f'artifacts/{slug}-review-full/{slug}' if (ROOT/f'artifacts/{slug}-review-full/{slug}/summary.json').exists() else ROOT/f'artifacts/full-refresh/display/{slug}') if CPS else (ready.parent if ready.exists() else ROOT/'artifacts/full-refresh/display/tgdd')
summary=json.loads((folder/'summary.json').read_text())
rows=json.loads((folder/'prices.json').read_text());issues=json.loads((folder/'issues.json').read_text())
catalog=json.loads((ROOT/f'artifacts/full/merged/{slug}/catalog.json').read_text())
discovery=json.loads((ROOT/f'artifacts/full/merged/{slug}/summary.json').read_text())

selected_summary=None
if (selected_directory/'summary.json').exists():
    selected_summary=json.loads((selected_directory/'summary.json').read_text())
    selected_rows=json.loads((selected_directory/'prices.json').read_text())
    # Loại snapshot Apple mặc định khỏi bảng nghiệm thu màu; giữ nguyên dữ liệu gốc trên đĩa.
    rows=[r for r in rows if presentation(r,preferences)['apple_selection'] in ('other','unconfigured')]+selected_rows
    issues=[r for r in issues if r.get('brand')!='Apple']
    issues+=[{**r,'apple_selection':'needs_verified_color','display_name':r['product_name']} for r in json.loads((selected_directory/'issues.json').read_text())]
catalog_by_url={r['source_url']:r['config'] for r in catalog}
catalog_by_sku={r['config']['sku']:r['config'] for r in catalog if r['config'].get('sku')}
rows=[presentation({**catalog_by_sku.get(r.get('sku'),catalog_by_url.get(r['source_url'],{})),**r},preferences) for r in rows]
issues=[presentation({**catalog_by_sku.get(r.get('sku'),catalog_by_url.get(r['source_url'],{})),**r},preferences) for r in issues]
catalog=[{**r,'config':presentation(r['config'],preferences)} for r in catalog]
rows.sort(key=lambda r:(model_order(r.get('apple_model')),r.get('display_name',''),r.get('sku','')))
issues.sort(key=lambda r:(model_order(r.get('apple_model')),r.get('display_name','')))
catalog.sort(key=lambda r:model_order(r['config'].get('apple_model')))
payload=json.dumps(dict(selected_summary=selected_summary,preferences=preferences,summary=summary,rows=rows,issues=issues,catalog=catalog,discovery=discovery),ensure_ascii=False).replace('<','\\u003c')
editor_script=r"""
function selectionReason(r){return ({needs_verified_color:'Chưa xác minh màu bằng mã biến thể.',selected:'Khớp cấu hình màu / không lọc màu.',other_color:'Tên màu nguồn chưa khớp màu theo dõi.',unknown_color:'Chưa xác minh được màu nguồn.',unconfigured:'Chưa có model chính xác trong danh sách.'}[r.apple_selection]||'')+' Màu cần: '+(r.selected_color||'Không lọc');}
let preferences=d.preferences;
function editorRows(){ $('rules').innerHTML=preferences.products.map((r,i)=>'<tr><td><input aria-label="Model '+i+'" data-field="model" value="'+esc(r.model)+'"></td><td><input aria-label="Màu '+i+'" data-field="color" value="'+esc(r.color||'')+'"></td></tr>').join('');}
function collect(){return {version:1,products:[...$('rules').children].map(tr=>({model:tr.querySelector('[data-field=model]').value.trim(),color:tr.querySelector('[data-field=color]').value.trim()||null,aliases:[]}))};}
$('manage').onclick=async()=>{try{const response=await fetch('/api/apple-colors',{cache:'no-store'});if(!response.ok)throw Error('Không tải được cấu hình');preferences=await response.json();editorRows();$('save-status').textContent='';$('editor').showModal();}catch(e){alert(e.message);}};
$('add-rule').onclick=()=>{preferences=collect();preferences.products.push({model:'',color:null,aliases:[]});editorRows();};
$('close-editor').onclick=()=>$('editor').close();
$('save-rules').onclick=async()=>{const button=$('save-rules');button.disabled=true;$('save-status').textContent='Đang lưu…';try{const response=await fetch('/api/apple-colors',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});const result=await response.json();if(!response.ok)throw Error(result.error||'Không lưu được');location.reload();}catch(e){$('save-status').textContent=e.message;button.disabled=false;}};
"""
page='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MW · Kết quả bot</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f4;color:#183f34;font:15px system-ui,sans-serif}main{max-width:1400px;margin:auto;padding:24px}h1{font-size:32px;margin:8px 0}p{line-height:1.6}.note{background:#fff6df;border-left:4px solid #b77d09;padding:15px;border-radius:8px}.metrics{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}.metrics>div{background:white;border:1px solid #dbe4de;border-radius:12px;padding:16px;flex:1;min-width:160px}.metrics strong{font-size:28px;display:block}.controls{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}select,input,button{padding:12px;border:1px solid #cbd9d1;border-radius:8px;background:white;font:inherit;color:inherit}input{flex:1;min-width:180px}button{cursor:pointer}.active{background:#087d73;color:white}.table{overflow:auto;background:white;border-radius:12px;border:1px solid #dbe4de}table{border-collapse:collapse;width:100%;min-width:900px}th,td{padding:14px;text-align:left;border-bottom:1px solid #e4ebe6;vertical-align:top}th{background:#183f34;color:white}td:first-child{min-width:250px}small{display:block;color:#64766b;margin-top:5px}.price{white-space:nowrap;font-weight:700}a{color:#007e75}details{max-width:440px;white-space:pre-wrap;line-height:1.6}summary{cursor:pointer}dialog{width: min(1000px,95vw);max-height:90vh;border:1px solid #cbd9d1;border-radius:12px;color:inherit}dialog input{min-width:150px;width:100%}dialog::backdrop{background:#183f3480}footer{margin-top:20px;color:#65756e}@media(max-width:600px){main{padding:16px}h1{font-size:26px}.controls>*{max-width:100%}}
</style><main><small>NGHIỆM THU TỪNG KÊNH · W2Q1FY27</small><h1>MW / Thế Giới Di Động</h1><p id="time"></p><div class="note" id="scope"></div><div class="metrics" id="metrics"></div><details><summary>Độ đầy đủ danh sách Apple theo màu đã chọn</summary><div class="table"><table><thead><tr><th>Model theo dõi</th><th>Màu cần</th><th>Bản ghi giá đúng cấu hình</th><th>Đối chiếu catalog</th></tr></thead><tbody id="coverage"></tbody></table></div></details><p>Apple chỉ hiển thị màu bạn đã chọn. Dòng không khớp màu được giữ trong danh mục và mục xác minh, không lấy màu khác thay thế.</p><button id="manage">Quản lý model / màu Apple</button><dialog id="editor"><h2>Danh sách Apple theo dõi</h2><p>Cấu hình lưu vào dự án trên máy local, chưa đồng bộ Supabase. Mỗi model một màu. Để trống = không lọc màu. Bot phải chọn mã biến thể trên website trước khi đọc giá.</p><div class="table"><table><thead><tr><th>Model</th><th>Màu theo dõi</th></tr></thead><tbody id="rules"></tbody></table></div><p id="save-status"></p><button id="add-rule">Thêm model</button> <button id="save-rules">Lưu cấu hình</button> <button id="close-editor">Đóng</button></dialog><div class="controls" id="tabs"><button class="active" data-tab="prices">Giá đã ghi nhận</button><button data-tab="issues">Mục cần kiểm tra</button><button data-tab="catalog">Danh mục đã tìm</button><button data-tab="apple">Đối chiếu màu Apple</button></div><div class="controls"><input id="search" aria-label="Tìm sản phẩm" placeholder="Tìm tên sản phẩm, model hoặc SKU…"><select id="brand" aria-label="Chọn hãng"></select><select id="category" aria-label="Chọn danh mục"></select></div><p id="count"></p><div class="table"><table><thead id="head"></thead><tbody id="body"></tbody></table></div><footer>Giá được giữ riêng theo SKU/màu/dung lượng. Ưu đãi thanh toán và thu cũ được ghi chú, không tự trừ vào giá bán. Đây là dữ liệu chạy thử cục bộ, chưa ghi Supabase.</footer></main><script id="data" type="application/json">PAYLOAD</script><script>
const d=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id);let tab='prices';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const cash=v=>v===null||v===undefined?'Không hiện giá':new Intl.NumberFormat('vi-VN').format(v)+' đ';
$('time').textContent='Dữ liệu nền MW hoàn tất lúc '+new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',dateStyle:'short',timeStyle:'short'}).format(new Date(d.summary.finished_at));
const limited=d.summary.catalog?.limited_to;
$('scope').textContent=(limited?'Đây là lượt lấy mẫu '+limited+' SKU, chưa phải kết quả cào toàn bộ. Các mục cần kiểm tra thuộc logic bot cũ, chưa được xác nhận lại bằng bản sửa giá/trạng thái. ':'Đây là kết quả sau khi đọc bổ sung giá/trạng thái. ')+ 'Danh mục đạt '+d.discovery.sources_ok+'/'+d.discovery.sources+' nguồn; TGDD Garmin (Excel dòng 19) còn thiếu và chưa được tính là hoàn tất.';
if(d.selected_summary){$('time').textContent+=' · Bot màu Apple cập nhật '+new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',dateStyle:'short',timeStyle:'short'}).format(new Date(d.selected_summary.finished_at));$('scope').textContent+=' Bot chọn màu Apple '+(d.selected_summary.status==='running'?'đang chạy, kết quả cập nhật theo từng model.':'đã kết thúc lượt đọc; các mục chưa xác minh vẫn được ghi rõ.');}
$('metrics').innerHTML=[[d.catalog.length,'Link đã tìm'],[d.rows.length,'Bản ghi trong bảng nghiệm thu'],[d.issues.length,'Mục cần kiểm tra đang giữ'],[d.discovery.sources_ok+'/'+d.discovery.sources,'Nguồn danh mục thành công'],[d.rows.filter(r=>r.apple_selection==='selected').length,'Apple theo đúng cấu hình']].map(([n,t])=>'<div><strong>'+esc(n)+'</strong>'+esc(t)+'</div>').join('');
$('coverage').innerHTML=d.preferences.products.map(rule=>{const matches=d.catalog.filter(r=>r.config.apple_model===rule.model);const selected=matches.filter(r=>r.config.apple_selection==='selected');const prices=d.rows.filter(r=>r.apple_model===rule.model&&r.apple_selection==='selected');const note=!matches.length&&!prices.length?'Chưa xác định được link model trong catalog hiện tại.':!selected.length&&!prices.length?'Có model nhưng chưa xác minh được màu đã chọn.':!prices.length?'Có link đúng cấu hình; chưa có kết quả giá/trạng thái.':selected.length+' link catalog đúng cấu hình; dữ liệu vẫn tách riêng theo SKU.';return '<tr><td>'+esc(rule.model)+'</td><td>'+esc(rule.color||'Không lọc màu')+'</td><td>'+prices.length+'</td><td>'+esc(note)+'</td></tr>';}).join('');
for(const [id,key,label] of [['brand','brand','Tất cả hãng'],['category','category','Tất cả danh mục']]){$(id).innerHTML='<option value="">'+label+'</option>'+[...new Set(d.catalog.map(r=>r.config[key]).filter(Boolean))].sort().map(v=>'<option>'+esc(v)+'</option>').join('');$(id).onchange=render;}$('search').oninput=render;
$('tabs').onclick=e=>{if(!e.target.dataset.tab)return;tab=e.target.dataset.tab;for(const b of $('tabs').children)b.classList.toggle('active',b.dataset.tab===tab);render();};
function render(){let entries=tab==='prices'?d.rows.filter(r=>['other','selected','unconfigured'].includes(r.apple_selection)):tab==='issues'?d.issues:tab==='apple'?d.catalog.filter(r=>r.config.apple_selection!=='other').map(r=>({...r.config,source_url:r.source_url,reason:selectionReason(r.config)})):d.catalog.map(r=>({...r.config,source_url:r.source_url,catalog_status:r.status,reason:r.reason}));const q=$('search').value.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase();entries=entries.filter(r=>(!$('brand').value||r.brand===$('brand').value)&&(!$('category').value||r.category===$('category').value)&&(!q||[r.display_name,r.product_name,r.discovered_name,r.model_name,r.sku].join(' ').normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().includes(q)));$('count').textContent=entries.length+' bản ghi đang hiển thị';$('head').innerHTML='<tr>'+ (tab==='prices'?['Sản phẩm / SKU','Hãng / nhóm hàng','Màu','Giá bán hiển thị','Trạng thái & CTKM','Nguồn']:['Sản phẩm / SKU','Hãng / nhóm hàng','Thông tin','Nguồn']).map(t=>'<th>'+t+'</th>').join('')+'</tr>';$('body').innerHTML=entries.map(r=>'<tr><td><b>'+esc(r.display_name||r.product_name||r.discovered_name||'Chưa xác định tên')+'</b>'+(r.display_variant?'<small>'+esc(r.display_variant)+'</small>':'')+'<small>'+esc(r.sku||r.variant_id||'Chưa khóa SKU')+'</small></td><td>'+esc(r.brand)+'<small>'+esc(r.category)+'</small></td>'+ (tab==='prices'?'<td>'+esc(r.selected_color||r.source_color||'Không lọc màu')+'</td><td class="price">'+cash(r.promo_price)+'</td><td><details><summary>Xem chi tiết</summary>'+esc('Tên nguồn: '+(r.product_name||r.discovered_name||'')+'\\nMàu yêu cầu: '+(r.selected_color||'Không lọc màu')+'\\nMã biến thể: '+(r.variant_id||r.sku||'Chưa xác định')+'\\n\\n'+(r.promo_text||'Không có ghi chú'))+'</details></td>':'<td>'+ (tab==='apple'?'':tab==='catalog'?(r.catalog_status==='ready'?'Đã khóa SKU; kết quả giá xem ở tab giá.':'Catalog cần xác minh. '):'Cần đọc lại / kiểm tra: ')+esc(r.reason||'')+'</td>')+'<td><a target="_blank" rel="noopener noreferrer" href="'+esc(r.source_url||r.url)+'">Mở trang đại lý ↗</a></td></tr>').join('');}$('brand').value='Apple';render();
EDITOR_SCRIPT
</script></html>'''.replace('PAYLOAD',payload).replace('EDITOR_SCRIPT',editor_script)
if CPS:
 page=page.replace('MW · Kết quả bot',short[slug]+' · Kết quả bot').replace('MW / Thế Giới Di Động',labels[slug]).replace('Dữ liệu nền MW','Dữ liệu nền '+short[slug])
 page=page.replace('TGDD Garmin (Excel dòng 19) còn thiếu và chưa được tính là hoàn tất.','Độ đầy đủ dựa trên các nguồn '+short[slug]+' trong Excel; không khẳng định đủ toàn bộ model trên website.')
 page=page.replace('mã biến thể trên website trước khi đọc giá','mã màu con trên website trước khi đọc giá')
 target=ROOT/('web/public/'+('cps' if slug=='cellphones' else slug)+'-review.html')
else:target=ROOT/'web/public/mw-review.html'
nav='<p>'+ ' · '.join('<a href="/'+filename+'-review.html">'+label+'</a>' for filename,label in [('mw','MW'),('cps','CPS'),('fpt','FPT'),('viettel','VT'),('phongvu','PV')])+'</p>'
page=page.replace('<p id="time">',nav+'<p id="time">')
target.write_text(page)
import subprocess
subprocess.run([sys.executable,'tools/build_comparison.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
print(target)
