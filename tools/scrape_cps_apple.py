"""Nghiệm thu CPS độc lập: mở tất cả màu con, đọc giá đúng SKU; không ghi Supabase/Telegram."""
import asyncio,json,sys,subprocess
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from adapters import cellphones as cps
from apple_preferences import load,model_of
from cps_apple_colors import selected_quote
from apple_rules import manual_urls
import apple_sources
from http_policy import client
from common import TZ
from identity import chain_sku,storage_of
from scraper import write_json
import os
# WPCS_APPLE_OUT_DIR: chạy thử cô lập (không ghi đè dữ liệu thật, không dựng lại dashboard).
ISOLATED=bool(os.environ.get('WPCS_APPLE_OUT_DIR'))
OUT=Path(os.environ['WPCS_APPLE_OUT_DIR'])/'cps-apple-selected' if ISOLATED else ROOT/'artifacts/cps-apple-selected'
async def main():
 OUT.mkdir(exist_ok=True,parents=True);catalog=json.loads((ROOT/'artifacts/full/merged/cellphones/catalog.json').read_text());config=load()
 ids=list(dict.fromkeys(str(r['config'].get('parent_id') or r['config'].get('variant_id')) for r in catalog if r['config'].get('brand')=='Apple' and (r['config'].get('parent_id') or r['config'].get('variant_id'))))
 async with client() as http:
  if '--cached' in sys.argv:
   parents=json.loads((OUT/'parents.json').read_text());children=json.loads((OUT/'children.json').read_text())
  else:
   parents={}
   for start in range(0,len(ids),50):
    chunk=ids[start:start+50];d=await cps.graphql(http,f'query{{products(filter:{{static:{{province_id:{cps.PROVINCE},product_id:{json.dumps(chunk)},stock:{{from:0}}}}}},size:{len(chunk)}){{general{{product_id name url_path child_product}} filterable{{is_parent parent_id price special_price stock}}}}}}');parents.update({str(p['general']['product_id']):p for p in d['products']})
   variants=list(dict.fromkeys(str(i) for p in parents.values() for i in (p['general'].get('child_product') or [p['general']['product_id']])))
   children=await cps.products_by_id(http,variants);write_json(OUT/'parents.json',parents);write_json(OUT/'children.json',children)
  # URL nhập tay: đọc mã màu trên trang → parent_id qua GraphQL → kiểm tra đường dẫn cha. Không coi URL là SKU.
  manual={}
  for rule in config['products']:
   for url in manual_urls(rule,'cellphones'):
    try:
     parent,kids=await apple_sources.cps_resolve(http,url);manual[(rule['model'],url)]=str(parent['general']['product_id'])
     parents.setdefault(str(parent['general']['product_id']),parent);children.update({k:v for k,v in kids.items() if v})
    except Exception as exc:
     manual[(rule['model'],url)]=exc;apple_sources.record(rule['model'],'cellphones',url,apple_sources.classify(exc),str(exc),rule['color'],'worker')
 now=datetime.now(TZ).isoformat();rows=[];issues=[];states=[];seen=set()
 for rule in config['products']:
  candidates=[p for p in parents.values() if model_of(p['general']['name'])==rule['model']];before=len(rows);problems=[]
  manual_parents={pid for (m,u),pid in manual.items() if m==rule['model'] and isinstance(pid,str)}
  # Sản phẩm cha từ URL nhập tay vẫn đi qua selected_quote: sai model → lỗi, không bị lọc âm thầm.
  candidates+=[parents[pid] for pid in manual_parents if parents[pid] not in candidates];selected_by_parent={}
  for parent in candidates:
   pg=parent['general'];url='https://cellphones.com.vn/'+pg['url_path'].lstrip('/');selected=0
   for rawid in pg.get('child_product') or [pg['product_id']]:
    pid=str(rawid)
    try:
     child=children.get(pid)
     if not child:raise ValueError('CPS: mã màu con không trả dữ liệu')
     result=selected_quote(parent,child,rule,url)
     if result is None:continue
     selected+=1
     if pid in seen:continue
     seen.add(pid);meta=next((r['config'] for r in catalog if str(r['config'].get('parent_id'))==str(pg['product_id'])),{})
     rows.append({**result,'sku':chain_sku('CellphoneS',pid),'source_product_name':result['product_name'],'model_name':rule['model'],'brand':'Apple','category':meta.get('category',''),'storage':storage_of(result['product_name']) or storage_of(pg['name']),'source_parent_name':pg['name'],'observed_at':now,'color_evidence':{**result['color_evidence'],'verified_at':now}})
    except Exception as exc:problems.append(str(exc));issues.append({'chain_name':'CellphoneS','product_name':rule['model'],'model_name':rule['model'],'brand':'Apple','category':'','source_url':url+'?product_id='+pid,'requested_color':rule['color'],'reason':str(exc)})
   selected_by_parent[str(pg['product_id'])]=(selected,problems[-1] if problems else None)
   if not selected:
    reason='Chưa xác minh được màu yêu cầu trong các mã con CPS: '+str(rule['color'] or 'Không lọc');problems.append(reason);issues.append({'chain_name':'CellphoneS','product_name':rule['model'],'model_name':rule['model'],'brand':'Apple','category':'','source_url':url,'requested_color':rule['color'],'reason':reason})
  for (m,url),pid in manual.items():
   if m!=rule['model'] or not isinstance(pid,str):continue
   count,problem=selected_by_parent.get(pid,(0,None))
   status='valid' if count else apple_sources.classify(apple_sources.WrongModel(problem) if problem and 'model' in problem else apple_sources.ColorNotFound(problem or 'CPS: không có mã màu con đúng màu yêu cầu'))
   apple_sources.record(rule['model'],'cellphones',url,status,f'Worker: cha {pid}, {count} mã màu đúng yêu cầu' if count else (problem or 'Không có mã màu con đúng màu yêu cầu'),rule['color'],'worker')
  states.append({'model':rule['model'],'color':rule['color'],'status':'missing_catalog' if not candidates else 'partial' if problems else 'ok','records':len(rows)-before,'problems':problems})
 summary={'stage':'cps-apple-selected','status':'complete','finished_at':now,'models':states,'prices':len(rows),'issues':len(issues),'config':config,'parents_requested':len(ids),'parents_found':len(parents),'children_found':sum(x is not None for x in children.values())}
 for name,data in [('prices.json',rows),('issues.json',issues),('summary.json',summary)]:write_json(OUT/name,data)
 ISOLATED or subprocess.run([sys.executable,'tools/build_mw_review.py','--cps'],cwd=ROOT,check=True)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':
 from apple_jobs import channel_lock,Busy
 try:
  with channel_lock('cellphones'):asyncio.run(main())  # khóa chung với job dashboard: không chạy chồng một kênh
 except Busy as exc:print(exc,flush=True);raise SystemExit(3)
