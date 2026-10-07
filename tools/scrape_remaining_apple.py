"""Nghiệm thu 3 kênh còn lại: mở palette thật, chọn đúng màu/SKU, giữ giá và trạng thái."""
import asyncio,json,os,sys,subprocess,re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apple_preferences import load,key
from apple_rules import accepted_colors
import apple_rules
import apple_sources
from product_standard import canonical_model
from adapters.registry import ADAPTERS
from adapters.fptshop import variant_color
from adapters.nextflight import flight,object_after
from adapters.phongvu import next_data,color_rows,selected_color
from adapters.viettel_detail import read_product as vt_detail
from common import TZ,PipelineError
from http_policy import client,fetch,wait_turn
from identity import chain_sku,storage_of
from scraper import write_json
from playwright.async_api import async_playwright
CHAINS={'fpt':'FPT Shop','viettel':'Viettel Store','phongvu':'Phong Vũ'}
LABELS={
 'iPhone 17':{'Xanh Lá Xô Thôm':['Xanh Lá Xô Thơm','Sage']},
 'Apple Watch Ultra 3':{'Đen':['Titan Đen','Black Titanium','Titan Đen / Black Titanium']},
 'Apple Watch S11':{'Đen Bóng':['Jet Black','Đen / Jet Black']},
 'Apple Watch SE 3':{'Ánh Sao':['Starlight','Trắng / Starlight']},
 'iPad A16':{'Bạc':['Silver']},
 'iPad Air M4 11':{'Xám Không Gian':['Space Gray','Xám']},
 'iPad Air M4 13':{'Xám Không Gian':['Space Gray','Xám']},
 'iPad Pro M5 11':{'Đen Không Gian':['Space Black','Đen']},
 'iPad Pro M5 13':{'Đen Không Gian':['Space Black','Đen']},
 'iPad Mini 7':{'Xám':['Space Gray','Space Grey','Xám không gian']},
 'MacBook Neo':{'Vàng Citrus':['Citrus']},
 'MacBook Air 13 M5':{'Xanh Da Trời':['Sky Blue']},
 'MacBook Air 15 M5':{'Xanh Da Trời':['Sky Blue']},
 'MacBook Pro 14 M5':{'Đen Không Gian':['Space Black','Đen']},
 'MacBook Pro 16 M5 Pro':{'Đen Không Gian':['Space Black','Đen']},
 'AirPods Max':{'Đêm Xanh Thẳm':['Midnight']},
 'AirPods Max 2':{'Đêm Xanh Thẳm':['Midnight']},
}

def matches(rule,color):
 accepted=accepted_colors(rule,LABELS.get(rule['model'],{}).get(rule['color'],[]))  # gồm tên tương đương người dùng xác nhận
 return accepted is None or key(color) in accepted
def sku_url(url,sku):
 p=urlsplit(url);params=dict(parse_qsl(p.query));params['sku']=str(sku);return urlunsplit((p.scheme,p.netloc,p.path,urlencode(params),''))
async def palette(slug,http,browser,item):
 if slug=='viettel':
  await wait_turn(http,item['url']);d=await vt_detail(item['url'],http,browser,rules_only=True)
  return [{'url':item['url'],'variant_id':v['rule_id'],'variant_erp_id':v['erp_id'],'color':v['color'],'name':d['product_name']} for v in d['variants']],d
 response=await fetch(http,'GET',item['url'],label=CHAINS[slug]+' lựa chọn màu')
 if slug=='fpt':
  d=object_after(flight(response.text),'"initialState":');skus=d['variants']['variantResult']['skus'];items=[]
  for v in skus:
   name=v.get('name') or '';base=v.get('displayName') or '';color=variant_color(d,str(v['code']))
   items.append({'url':sku_url('https://fptshop.com.vn/'+v['slug'].lstrip('/'),v['code']),'variant_id':str(v['code']),'color':color,'name':name})
  return items,d
 d=next_data(response.text)['props']['pageProps']['serverProduct'];product=d['product'];name=product['productInfo']['name'];rows=color_rows(product);items=[]
 for row in rows:
  if True:
   for v in row.get('options') or []:
    if not v.get('sku') or not v.get('url'):continue
    items.append({'url':sku_url('https://phongvu.vn/'+v['url'].lstrip('/'),v['sku']),'variant_id':str(v['sku']),'color':v['label'],'name':name})
 if not items:items=[{'url':item['url'],'variant_id':str(product['productInfo']['sku']),'color':selected_color(product),'name':name}]
 return items,d
async def run(slug,browser):
 chain=CHAINS[slug];isolated=bool(os.environ.get('WPCS_APPLE_OUT_DIR'));out=(Path(os.environ['WPCS_APPLE_OUT_DIR']) if isolated else ROOT/'artifacts')/f'{slug}-apple-selected';out.mkdir(parents=True,exist_ok=True);(out/'palettes').mkdir(exist_ok=True)
 catalog=json.loads((ROOT/f'artifacts/full/merged/{slug}/catalog.json').read_text());config=load();rows=[];issues=[];states=[];seen=set();expanded=set()
 if '--resume' in sys.argv and (out/'summary.json').exists():
  previous=json.loads((out/'summary.json').read_text());complete={m['model'] for m in previous['models'] if m['status']=='ok'};retry={r['model'] for r in config['products'] if r['model'] not in complete}
  config={**config,'products':[r for r in config['products'] if r['model'] in retry]}
  rows=json.loads((out/'prices.json').read_text());issues=[r for r in json.loads((out/'issues.json').read_text()) if r['product_name'] not in retry];states=[m for m in previous['models'] if m['model'] not in retry];seen={str(r.get('variant_erp_id') or r['variant_id']) for r in rows}
 def publish(status):
  summary={'stage':slug+'-apple-selected','status':status,'finished_at':datetime.now(TZ).isoformat(),'prices':len(rows),'issues':len(issues),'models':states,'config':load()}
  for filename,data in [('prices.json',rows),('issues.json',issues),('summary.json',summary)]:write_json(out/filename,data)
  if not isolated:subprocess.run([sys.executable,'tools/build_mw_review.py','--chain',slug],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 publish('running')
 async with client(timeout=35) as http:
  for rule in config['products']:
   sources=[r for r in catalog if canonical_model(r['config'].get('source_product_name') or r['config'].get('product_name') or r['config'].get('discovered_name'))==rule['model']];before=len(rows);problems=[]
   # URL nhập tay đi cùng luồng palette → chọn màu → đọc giá → đối chiếu SKU/model/màu như link discovery.
   manual_set=set(apple_rules.manual_urls(rule,slug));known={r['source_url'] for r in sources};sources+=[r for r in apple_sources.manual_records(rule,slug) if r['source_url'] not in known]
   for record in sources:
    item={**record['config'],'url':record['source_url']};url=item['url'];is_manual=bool(record['config'].get('manual')) or url in manual_set;url_problem=None;url_wanted=0;url_before=len(rows)
    identity=lambda v:(urlsplit(v['url']).path+'|'+str(v['variant_id'])) if slug=='viettel' else str(v['variant_id'])
    if item.get('variant_id') and identity(item) in expanded and not is_manual:continue  # URL nhập tay luôn được xác minh
    try:
     options,evidence=await palette(slug,http,browser,item)
     import hashlib
     write_json(out/'palettes'/(hashlib.sha256(url.encode()).hexdigest()[:16]+'.json'),{'url':url,'observed_at':datetime.now(TZ).isoformat(),'data':evidence})
     same_model=[v for v in options if canonical_model(v['name'])==rule['model']]
     if not same_model:raise apple_sources.WrongModel('Trang không phải model '+rule['model']+'; không dùng màu/giá của model khác')
     wanted=[v for v in same_model if matches(rule,v['color'])]
     expanded.update(identity(v) for v in same_model)
     if not wanted:raise apple_sources.ColorNotFound('Chưa xác minh được màu yêu cầu trong palette: '+str(rule['color'] or 'Không lọc'))
     url_wanted=len(wanted)
     for v in wanted:
      if (str(v.get('variant_erp_id') or v['variant_id'])) in seen:continue
      try:
       q=await ADAPTERS[chain].read_product(v,http,browser)
       if str(q['variant_id'])!=str(v['variant_id']) or canonical_model(q['product_name'])!=rule['model'] or key(q.get('color'))!=key(v['color']):raise PipelineError('Mã SKU/model/màu trả về khác lựa chọn; không công bố giá')
       now=datetime.now(TZ).isoformat();seen.add(str(v.get('variant_erp_id') or v['variant_id']));rows.append({**q,'sku':chain_sku(chain,q.get('sku_key') or q['variant_id']),'source_product_name':q['product_name'],'brand':'Apple','category':item.get('category',''),'model_name':rule['model'],'storage':storage_of(q['product_name']),'color':rule['color'],'observed_at':now,'color_evidence':{'model':rule['model'],'canonical_color':rule['color'],'website_color_label':q.get('color'),'website_color_id':str(v['variant_id']),'product_code':str(q['variant_id']),'selected_url':v['url'],'verified_at':now}})
      except Exception as exc:
       url_problem=exc;problems.append(str(exc));issues.append({'chain_name':chain,'product_name':rule['model'],'brand':'Apple','category':item.get('category',''),'source_url':v['url'],'requested_color':rule['color'],'reason':str(exc)})
    except Exception as exc:
     url_problem=exc;problems.append(str(exc));issues.append({'chain_name':chain,'product_name':rule['model'],'brand':'Apple','category':item.get('category',''),'source_url':url,'requested_color':rule['color'],'reason':str(exc)})
    if is_manual:
     added=len(rows)-url_before;ok=url_wanted and (added or not url_problem)
     apple_sources.record(rule['model'],slug,url,'valid' if ok else apple_sources.classify(url_problem),f'Worker: {url_wanted} biến thể đúng model/màu, {added} giá ghi mới' if ok else str(url_problem),rule['color'],'worker')
   states.append({'model':rule['model'],'color':rule['color'],'status':'missing_catalog' if not sources else 'partial' if problems else 'ok','records':sum(r.get('model_name')==rule['model'] for r in rows),'problems':problems});publish('running');print(slug,rule['model'],len(rows)-before,'bản ghi;',len(problems),'cần kiểm tra',flush=True)
 publish('complete')
async def main():
 slugs=[s for s in sys.argv[1:] if s in CHAINS] or list(CHAINS)
 async with async_playwright() as p:
  browser=await p.chromium.launch()
  try:
   results=await asyncio.gather(*(run(slug,browser) for slug in slugs),return_exceptions=True)
   for slug,result in zip(slugs,results):
    if isinstance(result,Exception):raise RuntimeError(slug+': '+str(result))
  finally:await browser.close()
if __name__=='__main__':
 import contextlib
 from apple_jobs import channel_lock,Busy
 try:
  with contextlib.ExitStack() as stack:
   for slug in [s for s in sys.argv[1:] if s in CHAINS] or list(CHAINS):stack.enter_context(channel_lock(slug))
   asyncio.run(main())
 except Busy as exc:print(exc,flush=True);raise SystemExit(3)
