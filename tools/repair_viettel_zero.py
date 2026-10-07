"""Đọc bổ sung đúng các link Viettel có giá placeholder 0; không đổi giá đã thu thập."""
import asyncio,json,sys,subprocess,shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx
from playwright.async_api import async_playwright
from common import TZ
from scraper import recheck_review,write_json
async def main():
 dest=ROOT/'artifacts/status-repair/viettel'
 issues=json.loads((dest/'issues.json').read_text());urls={r['source_url'] for r in issues if r['reason']=='Giá không phải một số tiền VND duy nhất'}
 if not urls:return
 catalog=json.loads((ROOT/'artifacts/full/merged/viettel/catalog.json').read_text());pending=[r for r in catalog if r['source_url'] in urls]
 rows=json.loads((dest/'prices.json').read_text());before=len(rows);issues=[i for i in issues if i['source_url'] not in urls]
 async with httpx.AsyncClient(timeout=40,follow_redirects=True) as http:
  async with async_playwright() as pw:
   browser=await pw.chromium.launch()
   try:await recheck_review(pending,http,browser,rows,issues)
   finally:await browser.close()
 now=datetime.now(TZ).isoformat()
 for row in rows[before:]:row['observed_at']=now
 if len(rows)+len(issues)!=len(catalog):raise RuntimeError('Kết quả thiếu link')
 summary=json.loads((dest/'summary.json').read_text());summary.update(finished_at=now,prices=len(rows),numeric_prices=sum(r['promo_price'] is not None for r in rows),status_only=sum(r['promo_price'] is None for r in rows),issues=len(issues),price_failures=sum(i['stage']=='price' for i in issues),issues_by_kind=dict(Counter(i['error_kind'] for i in issues)),blocked=sum(i['error_kind']=='blocked' for i in issues))
 for name,value in [('prices.json',rows),('issues.json',issues),('summary.json',summary)]:
  write_json(dest/name,value);shutil.copy2(dest/name,ROOT/'artifacts/full-refresh/display/viettel'/name)
 subprocess.run([sys.executable,'build_demo.py','--prices','artifacts/full-refresh/display'],cwd=ROOT,check=True)
 print('Viettel recovered',len(rows)-before,'issues',len(issues),flush=True)
if __name__=='__main__':asyncio.run(main())
