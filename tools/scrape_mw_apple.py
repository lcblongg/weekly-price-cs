"""Lượt nghiệm thu MW Apple: chọn màu yêu cầu trên website rồi mới lấy giá đúng SKU.
Đầu ra riêng, giữ nguyên catalog và dữ liệu đầy đủ trước đó. Không gửi Telegram/Supabase.
"""
import asyncio,json,sys,subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apple_preferences import load,model_of
from apple_rules import manual_urls
import apple_sources
from mw_apple_colors import selected_variants,verify_quote
from adapters import tgdd
from common import TZ
from http_policy import client
from identity import chain_sku,storage_of
from scraper import write_json
import os
# WPCS_APPLE_OUT_DIR: chạy thử cô lập (không ghi đè dữ liệu thật, không dựng lại dashboard).
ISOLATED=bool(os.environ.get('WPCS_APPLE_OUT_DIR'))
OUT=Path(os.environ['WPCS_APPLE_OUT_DIR'])/'mw-apple-selected' if ISOLATED else ROOT/'artifacts/mw-apple-selected'
async def main():
 OUT.mkdir(parents=True,exist_ok=True);config=load();selected_models=sys.argv[1:];retry=any(v in selected_models for v in ('--retry','--resume'))
 if retry:
  completed={r['model'] for r in json.loads((OUT/'summary.json').read_text())['models'] if r['status']=='ok'}
  selected_models=[r['model'] for r in config['products'] if r['model'] not in completed]
 catalog=json.loads((ROOT/'artifacts/full/merged/tgdd/catalog.json').read_text());rows=[];issues=[];states=[];seen=set()
 if selected_models and (OUT/'summary.json').exists():
  rows=[r for r in json.loads((OUT/'prices.json').read_text()) if retry or r.get('model_name') not in selected_models]
  issues=[r for r in json.loads((OUT/'issues.json').read_text()) if r.get('model_name') not in selected_models]
  states=[r for r in json.loads((OUT/'summary.json').read_text())['models'] if r['model'] not in selected_models]
  seen={r['variant_id'] for r in rows}
 # Duyệt URL từng cấu hình mạng/GPS/vỏ; bộ phiên bản website mở rộng các dung lượng cùng nhóm.
 groups={}
 for record in catalog:
  item=record['config'];model=model_of(item.get('source_product_name') or item.get('product_name') or item.get('discovered_name') or record['source_url'].split('?',1)[0].replace('-',' '))
  if item.get('brand')=='Apple' and model:groups.setdefault(model,[]).append(record['source_url'])
 def publish(status):
  now=datetime.now(TZ).isoformat();summary={'stage':'mw-apple-selected','status':status,'finished_at':now,'models':states,'prices':len(rows),'issues':len(issues),'config':config}
  for name,value in [('prices.json',rows),('issues.json',issues),('summary.json',summary)]:write_json(OUT/name,value)
  ISOLATED or subprocess.run([sys.executable,'tools/build_mw_review.py'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 publish('running')
 async with client(timeout=35) as http:
  for rule in config['products']:
   if selected_models and rule['model'] not in selected_models:continue
   manual=manual_urls(rule,'tgdd')  # URL nhập tay: nguồn đầu vào, vẫn xác minh model/màu như link discovery
   urls=list(dict.fromkeys(groups.get(rule['model'],[])+manual));count_before=len(rows);problems=[]
   if not urls:states.append({'model':rule['model'],'color':rule['color'],'status':'missing_catalog','records':0});publish('running');continue
   visited=set()
   for url in urls:
    if url in visited and url not in manual:continue
    url_before=len(rows);url_problem=None;url_variants=0
    try:
     _,queries=await tgdd.detail(http,url);data=(queries.get('PRODUCT_DETAIL') or {}).get('data') or {}
     proofdir=OUT/'palettes';proofdir.mkdir(exist_ok=True)
     import hashlib
     write_json(proofdir/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json'),{'url':url,'observed_at':datetime.now(TZ).isoformat(),'model_name':data.get('name'),'filter':data.get('filter'),'productCode':data.get('productCode')})
     variants=selected_variants(data,url,rule);url_variants=len(variants)
     for item in variants:
      visited.add(item['url'])
      if item['variant_id'] in seen:continue
      try:
       quote=await tgdd.read_product(item,http);evidence=verify_quote(quote,item,rule);now=datetime.now(TZ).isoformat()
       seen.add(item['variant_id']);rows.append({'chain_name':'TGDD','sku':chain_sku('TGDD',item['variant_id']),'variant_id':item['variant_id'],'product_name':quote['product_name'],'source_product_name':quote['product_name'],'brand':'Apple','category':next((r['config'].get('category') for r in catalog if r['source_url']==url),''),'model_name':rule['model'],'storage':storage_of(quote['product_name']),'color':rule['color'],'promo_price':quote['promo_price'],'original_price':None,'promo_text':quote['promo_text'],'source_url':item['url']+'?'+urlencode({'code':item['variant_id']}),'color_evidence':{**evidence,'verified_at':now},'observed_at':now})
      except Exception as exc:
       url_problem=exc;reason=str(exc);problems.append(reason);issues.append({'chain_name':'TGDD','product_name':rule['model'],'model_name':rule['model'],'brand':'Apple','category':'','source_url':item['url']+'?'+urlencode({'code':item['variant_id']}),'variant_id':item['variant_id'],'requested_color':rule['color'],'reason':reason})
    except Exception as exc:
     url_problem=exc;reason=str(exc);problems.append(reason);issues.append({'chain_name':'TGDD','product_name':rule['model'],'model_name':rule['model'],'brand':'Apple','category':'','source_url':url,'requested_color':rule['color'],'reason':reason})
    if url in manual:
     added=len(rows)-url_before;ok=url_variants and (added or not url_problem)
     apple_sources.record(rule['model'],'tgdd',url,'valid' if ok else apple_sources.classify(url_problem),f'Worker: {url_variants} biến thể đúng model/màu, {added} giá ghi mới' if ok else str(url_problem),rule['color'],'worker')
   states.append({'model':rule['model'],'color':rule['color'],'status':'partial' if problems else 'ok','records':sum(r['model_name']==rule['model'] for r in rows),'problems':problems})
   publish('running');print(rule['model'],len(rows)-count_before,'bản ghi đúng màu;',len(problems),'mục cần kiểm tra',flush=True)
 publish('complete');print('Hoàn tất MW Apple; xem summary.json để đánh giá nguồn còn thiếu.',flush=True)
if __name__=='__main__':
 from apple_jobs import channel_lock,Busy
 try:
  with channel_lock('tgdd'):asyncio.run(main())  # khóa chung với job dashboard: không chạy chồng một kênh
 except Busy as exc:print(exc,flush=True);raise SystemExit(3)
