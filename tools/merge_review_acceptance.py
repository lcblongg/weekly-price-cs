"""Hợp nhất kết quả kiểm tra link review, có backup và chỉ thay các URL vừa kiểm tra.
Không công bố Supabase, không gửi Telegram, không sửa dữ liệu của ba kênh khác.
"""
import json,sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apple_jobs import channel_lock
from scraper import write_json
b=ROOT/Path((ROOT/'artifacts/production-readiness/latest.txt').read_text().strip())
for slug in (['viettel'] if any(x in sys.argv for x in ['--vt-final','--vt-verified']) else ['tgdd','viettel']):
 fresh=b/('vt-verified' if '--vt-verified' in sys.argv else 'vt-final' if '--vt-final' in sys.argv else 'review-repair')/slug
 summary=json.loads((fresh/'summary.json').read_text())
 assert summary['status']=='ok' and summary['dry_run']
 rows=json.loads((fresh/'prices.json').read_text());issues=json.loads((fresh/'issues.json').read_text())
 assert len(rows)+len(issues)==summary['expected']
 base=ROOT/f'artifacts/{slug}-review-full/{slug}'
 if not(base/'prices.json').exists():base=ROOT/('artifacts/status-repair/tgdd' if slug=='tgdd' else f'artifacts/full-refresh/display/{slug}')
 checked={r['source_url'] for r in rows+issues}
 with channel_lock(slug):
  for f in ['prices.json','issues.json','summary.json']:
   p=base/f;target=b/('before-vt-verified-merge' if '--vt-verified' in sys.argv else 'before-vt-final-merge' if '--vt-final' in sys.argv else 'before-review-merge')/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True)
   # Không ghi đè backup nếu chạy lại script.
   if not target.exists():shutil.copy2(p,target)
  old=json.loads((base/'prices.json').read_text());old_issues=json.loads((base/'issues.json').read_text())
  merged=list({r['sku']:r for r in old+rows}.values())
  merged_issues=[i for i in old_issues if i['source_url'] not in checked]+issues
  for name,value in [('prices.json',merged),('issues.json',merged_issues)]:write_json(base/name,value)
  current=json.loads((base/'summary.json').read_text());current.update(prices=len(merged),numeric_prices=sum(r['promo_price'] is not None for r in merged),status_only=sum(r['promo_price'] is None for r in merged),issues=len(merged_issues),review_update={'at':summary['finished_at'],'prices':len(rows),'issues':len(issues),'scope':'Chỉ link review; giữ dữ liệu và thời điểm các SKU khác.'});write_json(base/'summary.json',current)
 print(slug,len(rows),'link đọc được;',len(issues),'còn cần kiểm tra')
