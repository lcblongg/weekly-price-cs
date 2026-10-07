"""Tổng hợp snapshot đã nghiệm thu; không tạo giá hoặc trạng thái giả cho ô trống."""
import json,sys,uuid,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
# Tuần tự hóa các lần dựng từ job/worker khác kênh; lần sau luôn đọc dữ liệu mới nhất.
(ROOT/'artifacts/locks').mkdir(parents=True,exist_ok=True)
_build_lock=open(ROOT/'artifacts/locks/comparison-build.lock','a+')
fcntl.flock(_build_lock,fcntl.LOCK_EX)
from apple_preferences import load,presentation
from product_standard import MODELS
from identity import storage_of
model_meta={}
prefs=load();rows=[];issues=[];sources=[]
for slug,folder,label in [('tgdd','mw-apple-selected','MW'),('cellphones','cps-apple-selected','CPS'),('fpt','fpt-apple-selected','FPT'),('viettel','viettel-apple-selected','VIETTEL'),('phongvu','phongvu-apple-selected','PV')]:
 selected=ROOT/'artifacts'/folder
 if not (selected/'summary.json').exists():continue
 summary=json.loads((selected/'summary.json').read_text());discovery=json.loads((ROOT/f'artifacts/full/merged/{slug}/summary.json').read_text())
 sources.append({'slug':slug,'label':label,'warning':discovery.get('garmin_warning') if slug=='tgdd' else None,'updated':summary.get('last_partial_update',{}).get('at') or summary['finished_at'],'issues':summary['issues'],'models':summary['models'],'discovery':f"{discovery['sources_ok']}/{discovery['sources']}"})
 base=ROOT/f'artifacts/{slug}-review-full/{slug}'
 if not (base/'prices.json').exists():base=ROOT/('artifacts/status-repair/tgdd' if slug=='tgdd' else f'artifacts/full-refresh/display/{slug}')
 catalog=json.loads((ROOT/f'artifacts/full/merged/{slug}/catalog.json').read_text())
 by_url={r['source_url']:r['config'] for r in catalog}
 candidates=[]
 # Giữ sản phẩm ngoài quy chuẩn màu; không đưa giá Apple chưa xác minh màu vào các model đã có quy tắc.
 for row in json.loads((base/'prices.json').read_text()):
  enriched={**by_url.get(row['source_url'],{}),**row}
  if presentation(enriched,prefs)['apple_selection'] in ('other','unconfigured'):candidates.append(enriched)
 candidates+=json.loads((selected/'prices.json').read_text())
 seen=set()
 for row in candidates:
  p=presentation(row,prefs)
  if p['apple_selection'] not in ('selected','other','unconfigured'):continue
  if p['sku'] in seen:continue
  seen.add(p['sku'])
  model=p.get('apple_model') or p.get('model_name') or p['display_name']
  p['apple_model']=model
  p['storage']=p.get('storage') or storage_of(p['product_name'])
  model_meta[model]={'brand':p.get('brand') or 'Khác','category':p.get('category') or 'Khác'}
  failed=next((m.get('last_failed_update') for m in summary.get('models',[]) if m.get('model')==model),None)
  if failed:
   p['stale_since']=failed['at'];p['stale_reason']=failed['reason']
  rows.append({k:p.get(k) for k in ['sku','product_name','display_name','display_variant','brand','category','apple_model','storage','color','promo_price','promo_text','source_url','observed_at','promotion_complete','apple_selection','source_color','color_evidence','variant_id','stale_since','stale_reason']}|{'chain':label,'slug':slug})
 channel_issues=list({(r.get('source_url'),r.get('sku'),r.get('reason')):r for r in json.loads((base/'issues.json').read_text())+json.loads((selected/'issues.json').read_text())}.values())
 issues += [r|{'chain':label,'slug':slug} for r in channel_issues]
 sources[-1]['issues']=len(channel_issues)
 base_summary=json.loads((base/'summary.json').read_text())
 if base_summary.get('review_update'):sources[-1]['updated']=max(sources[-1]['updated'],base_summary['review_update']['at'])
for m in MODELS:
 model_meta.setdefault(m,{'brand':'Apple','category':'Điện thoại' if m.startswith('iPhone') else 'Máy tính bảng' if m.startswith('iPad') else 'Đồng hồ thông minh' if m.startswith('Apple Watch') else 'AirPods' if m.startswith('AirPods') else 'Máy tính xách tay'})
models=list(MODELS)+sorted(set(model_meta)-set(MODELS),key=str.casefold)
payload={'model_meta':model_meta,'rows':rows,'issues':issues,'sources':sources,'models':models,'preferences':prefs}
target=ROOT/'web/data/comparison.json'
if target.exists():
 from daily_publication import merge_history
 previous=json.loads(target.read_text())
 # Giữ ngày lịch sử; quy tắc màu đổi thì dữ liệu màu cũ không lọt vào cấu hình mới.
 history=[r for r in previous['rows'] if r.get('apple_selection')!='selected' or previous.get('preferences')==prefs]
 payload['rows']=merge_history(history,rows)

temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')));temp.replace(target)
print(len(rows),'bản ghi so sánh')
