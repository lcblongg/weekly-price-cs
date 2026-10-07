"""Đọc lại các link chưa có kết quả bằng logic giá/trạng thái mới, giữ nguyên giá đã đọc.
Không dừng worker TGDD đang chạy; đợi summary của kênh đó rồi mới đọc bổ sung.
Không ghi Supabase hoặc gửi Telegram. Dùng thư mục riêng để đối chiếu trước/sau.
"""
import asyncio,json,sys,shutil,subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import httpx
from playwright.async_api import async_playwright
from common import TZ
from scraper import recheck_review,write_json
SLUGS=['cellphones','viettel','phongvu','fpt','tgdd']
OUT=ROOT/'artifacts/status-repair'
async def worker(slug,http,browser):
    source=ROOT/'artifacts/full-refresh/prices'/slug
    while not (source/'summary.json').exists():await asyncio.sleep(15)
    summary=json.loads((source/'summary.json').read_text())
    if summary.get('status') not in ('ok','degraded'):
        print(slug,'worker gốc lỗi; không công bố bổ sung',flush=True);return
    rows=json.loads((source/'prices.json').read_text())
    for row in rows:row['observed_at']=summary['finished_at']
    known={r['source_url'] for r in rows}
    catalog=json.loads((ROOT/'artifacts/full/merged'/slug/'catalog.json').read_text())
    pending=[r for r in catalog if r['source_url'] not in known]
    issues=[];before=len(rows)
    await recheck_review(pending,http,browser,rows,issues)
    finished=datetime.now(TZ).isoformat()
    for row in rows[before:]:row['observed_at']=finished
    if len(rows)+len(issues)!=len(catalog):raise RuntimeError('Không đủ bản ghi kết quả')
    if len({r['sku'] for r in rows})!=len(rows):raise RuntimeError('Trùng SKU')
    summary.update(finished_at=finished,status='degraded' if issues else 'ok',prices=len(rows),numeric_prices=sum(r['promo_price'] is not None for r in rows),status_only=sum(r['promo_price'] is None for r in rows),issues=len(issues),price_failures=sum(i['stage']=='price' for i in issues),issues_by_kind=dict(Counter(i['error_kind'] for i in issues)),blocked=sum(i['error_kind']=='blocked' for i in issues),review_rechecked=len(pending),expected=len(catalog),repair_base=str(source))
    dest=OUT/slug;dest.mkdir(parents=True,exist_ok=True)
    for name,value in [('prices.json',rows),('issues.json',issues),('summary.json',summary)]:write_json(dest/name,value)
    display=ROOT/'artifacts/full-refresh/display'/slug
    for name in ['prices.json','issues.json','summary.json']:shutil.copy2(dest/name,display/name)
    subprocess.run([sys.executable,'build_demo.py','--prices','artifacts/full-refresh/display'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    print(slug,json.dumps({'recovered':len(rows)-before,'records':len(rows),'status_only':summary['status_only'],'issues':len(issues)},ensure_ascii=False),flush=True)
async def main():
    selected=sys.argv[1:] or SLUGS
    if any(s not in SLUGS for s in selected):raise SystemExit('Kênh không hợp lệ')
    OUT.mkdir(parents=True,exist_ok=True)
    async with httpx.AsyncClient(timeout=40,follow_redirects=True) as http:
        async with async_playwright() as pw:
            browser=await pw.chromium.launch()
            try:await asyncio.gather(*(worker(s,http,browser) for s in selected))
            finally:await browser.close()
if __name__=='__main__':asyncio.run(main())
