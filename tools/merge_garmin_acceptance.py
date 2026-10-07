"""Hợp nhất lượt Garmin đã nghiệm thu, giữ dữ liệu kênh khác và ghi rõ link chưa đọc được."""
import json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apple_jobs import channel_lock
from discover_products import write_json
b=Path((ROOT/'artifacts/acceptance/latest.txt').read_text())
if not b.is_absolute():b=ROOT/b
fresh=b/'garmin-recheck/tgdd';prices=b/'garmin-prices/tgdd'
summary=json.loads((prices/'summary.json').read_text());assert summary['status']=='ok',summary
catalog=json.loads((fresh/'catalog.json').read_text());new_prices=json.loads((prices/'prices.json').read_text());new_issues=json.loads((prices/'issues.json').read_text())
new_prices=[{**r,'observed_at':r.get('observed_at') or summary['finished_at'],'observation_window':{'from':summary.get('started_at'),'to':summary['finished_at']}} for r in new_prices]
assert len(new_prices)+len(new_issues)==len(catalog)
with channel_lock('tgdd'):
 d=ROOT/'artifacts/full/merged/tgdd';base=ROOT/'artifacts/status-repair/tgdd'
 for folder in [d,base]:
  for file in ['catalog.json','sources.json','summary.json','prices.json','issues.json']:
   p=folder/file
   if p.exists():target=b/'before-garmin-merge'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
 old=json.loads((d/'catalog.json').read_text());combined={r['source_url']:r for r in old};combined.update({r['source_url']:r for r in catalog});all_catalog=list(combined.values());write_json(d/'catalog.json',all_catalog)
 sources=json.loads((d/'sources.json').read_text());new_sources=json.loads((fresh/'sources.json').read_text());sources=[s for s in sources if not(s['brand']=='Garmin' and s['category']=='Đồng hồ thông minh')]+new_sources;write_json(d/'sources.json',sources)
 ds=json.loads((d/'summary.json').read_text());ds.update(sources_ok=sum(s['status']=='Đã tìm link' for s in sources),sources_still_failed=[{'input_row':s['input_row']} for s in sources if s['status']!='Đã tìm link'],links=len(all_catalog),ready=sum(r['status']=='ready' for r in all_catalog),review=sum(r['status']=='review' for r in all_catalog),garmin_checked_at=summary['finished_at'],garmin_warning='Lượt mới đọc đủ 38/38 model trang công bố (trước đây 65); 1 link chi tiết trả HTTP 404. Chưa chứng minh đủ mọi model Garmin.',note='Snapshot local hợp nhất; chưa công bố Supabase. Chỉ Garmin được kiểm tra mới ngày 07/10.');write_json(d/'summary.json',ds)
 old_prices=json.loads((base/'prices.json').read_text());by_sku={r['sku']:r for r in old_prices};by_sku.update({r['sku']:r for r in new_prices});all_prices=list(by_sku.values());write_json(base/'prices.json',all_prices)
 old_issues=json.loads((base/'issues.json').read_text());all_issues=list({(r.get('source_url'),r.get('sku'),r.get('reason')):r for r in old_issues+new_issues}.values());write_json(base/'issues.json',all_issues)
 bs=json.loads((base/'summary.json').read_text());bs.update(prices=len(all_prices),numeric_prices=sum(r['promo_price'] is not None for r in all_prices),status_only=sum(r['promo_price'] is None for r in all_prices),issues=len(all_issues),expected=len(all_catalog),garmin_update={'at':summary['finished_at'],'prices':len(new_prices),'issues':len(new_issues)});write_json(base/'summary.json',bs)
print('Garmin:',len(new_prices),'giá/trạng thái;',len(new_issues),'mục cần kiểm tra')
