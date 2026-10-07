"""Đối chiếu 86 nguồn Excel với catalog/snapshot; không gọi mạng, không công bố dữ liệu."""
import json,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from import_sources import read_sources
from chains import CHAINS
from apple_preferences import load,presentation
from identity import describe
from common import TZ
from coverage_metrics import dashboard_metrics
from datetime import datetime
prefs=load();inputs=read_sources(ROOT/'inputs/data.xlsx');dashboard=json.loads((ROOT/'web/data/comparison.json').read_text())
def read(p,default):return json.loads(p.read_text()) if p.exists() else default
def model(config):
 p=presentation(config,prefs)
 if p.get('apple_model'):return p['apple_model']
 if p.get('model_name'):return p['model_name']
 name=config.get('source_product_name') or config.get('product_name') or config.get('discovered_name') or ''
 try:return describe(name,config.get('category',''),config.get('brand','')).get('model_name') or p.get('display_name')
 except ValueError:return None
today=datetime.now(TZ).date().isoformat()
report={'at':datetime.now(TZ).isoformat(),'scope':'Catalog hợp nhất 86 nguồn; đây không phải lượt discovery mới. Giá/trạng thái lấy file đang công bố, thống kê dashboard tách lịch sử và SKU xác minh hôm nay. Không xác nhận đủ mọi model/SKU.','input_sources':len(inputs),'chains':[]}
latest_pointer=ROOT/'artifacts/daily-local/latest.txt'
run_state=read(ROOT/latest_pointer.read_text().strip()/'status.json',{}) if latest_pointer.exists() else {}
for slug,label in CHAINS.items():
 d=ROOT/f'artifacts/full/merged/{slug}';catalog=read(d/'catalog.json',[]);diagnostics=read(d/'sources.json',[])
 expected=[r for r in inputs if r['chain_name']==label];diag={(r.get('input_row'),r.get('url')):r for r in diagnostics}
 source_results=[]
 for source in expected:
  result=diag.get((source['input_row'],source['url']),{})
  source_results.append({**source,'status':result.get('status','Thiếu kết quả'),'error':result.get('error',''),'notes':result.get('notes',[])})
 base=ROOT/f'artifacts/{slug}-review-full/{slug}'
 if not (base/'prices.json').exists():base=ROOT/('artifacts/status-repair/tgdd' if slug=='tgdd' else f'artifacts/full-refresh/display/{slug}')
 prices=read(base/'prices.json',[]);issues=read(base/'issues.json',[])
 selected=ROOT/'artifacts'/({'tgdd':'mw','cellphones':'cps'}.get(slug,slug)+'-apple-selected');chosen=read(selected/'prices.json',[]);summary=read(selected/'summary.json',{})
 by_url={r['source_url']:r for r in prices};by_sku={r['sku']:r for r in prices}
 catalog_models={model(by_sku.get(r['config'].get('sku')) or by_url.get(r['source_url']) or r['config']) for r in catalog}-{None,''};shown={r['apple_model'] for r in dashboard['rows'] if r['slug']==slug}
 represented={model(by_sku.get(r['config'].get('sku')) or by_url.get(r['source_url']) or r['config']) for r in catalog if (by_sku.get(r['config'].get('sku')) or by_url.get(r['source_url']) or {}).get('sku') in {x['sku'] for x in dashboard['rows'] if x['slug']==slug}}
 selection=Counter(presentation({**r['config'],'product_name':r['config'].get('source_product_name') or r['config'].get('discovered_name','')},prefs)['apple_selection'] for r in catalog)
 missing=[]
 for name in sorted(catalog_models-shown-represented):
  rule=next((r for r in prefs['products'] if r['model']==name),None)
  reason='Chưa có giá/SKU đúng màu đã xác minh' if rule and rule.get('color') else 'Thiếu giá/trạng thái hoặc lệch chuẩn hóa tên; cần kiểm tra'
  missing.append({'model':name,'reason':reason})
 report['chains'].append({'slug':slug,'chain':label,'sources_total':len(expected),'sources_ok':sum(s['status']=='Đã tìm link' for s in source_results),'source_details':source_results,'catalog_links':len(catalog),'unique_urls':len({r['source_url'] for r in catalog}),'unique_skus':len({r['config'].get('sku') for r in catalog if r['config'].get('sku')}),'catalog_models':len(catalog_models),'price_unique_skus':len({r['sku'] for r in prices}),'catalog_unknown_models':sum(not model(r['config']) for r in catalog),'priced':sum(r['promo_price'] is not None for r in prices),'status_only':sum(r['promo_price'] is None for r in prices),'price_issues':len(issues),'access_error_issues':sum(r.get('error_kind') in ('blocked','rate_limited','robots','http_error','network') for r in issues),'issue_kinds':dict(Counter(r.get('error_kind') or r.get('reason','') for r in issues)),'apple_color_selection':dict(selection),'verified_apple_rows':len(chosen),'apple_issues':summary.get('issues',0),'missing_dashboard_models':missing,'dashboard_rows':sum(r['slug']==slug for r in dashboard['rows']),'observations_from':min((r.get('observed_at','') for r in prices+chosen),default=''),'observations_to':max((r.get('observed_at','') for r in prices+chosen),default='')})
for channel in report['chains']:
 slug=channel['slug']
 channel['dashboard_current']=dashboard_metrics([r for r in dashboard['rows'] if r['slug']==slug],today)
 channel['daily_run']=run_state.get('channels',{}).get(slug,{})
 channel['discovery_warning']=read(ROOT/f'artifacts/full/merged/{slug}/summary.json',{}).get('garmin_warning')
output=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'artifacts/coverage-audit.json');output.write_text(json.dumps(report,ensure_ascii=False,indent=2));print('Kênh | Nguồn OK | Link | SKU khóa | Model | Có giá | Chỉ trạng thái | Lỗi giá | Model chưa có trên dashboard')
for c in report['chains']:print(c['chain'],f"{c['sources_ok']}/{c['sources_total']}",c['catalog_links'],c['unique_skus'],c['catalog_models'],c['priced'],c['status_only'],c['price_issues'],len(c['missing_dashboard_models']),sep=' | ')
