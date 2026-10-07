"""Runner cloud: GitHub Actions cào dữ liệu, Vercel chỉ gửi job và đọc Supabase.
Không ghi secret ra log. Chỉ scheduled daily/discovery được gửi Telegram; job thủ công không gửi.
"""
import argparse,json,os,subprocess,sys,threading,uuid
from pathlib import Path
from datetime import datetime,timedelta
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from common import database,TZ,weeks,PipelineError
from chains import CHAINS,resolve,slug as channel_slug
LABELS={'tgdd':'MW','cellphones':'CPS','fpt':'FPT','viettel':'VIETTEL','phongvu':'PV'}
FOLDERS={'tgdd':'mw-apple-selected','cellphones':'cps-apple-selected','fpt':'fpt-apple-selected','viettel':'viettel-apple-selected','phongvu':'phongvu-apple-selected'}
COMMANDS={'tgdd':['tools/scrape_mw_apple.py'],'cellphones':['tools/scrape_cps_apple.py'],'fpt':['tools/scrape_remaining_apple.py','fpt'],'viettel':['tools/scrape_remaining_apple.py','viettel'],'phongvu':['tools/scrape_remaining_apple.py','phongvu']}

def read(path,default):return json.loads(path.read_text()) if path.exists() else default

def configure(db):
 (ROOT/'artifacts').mkdir(parents=True,exist_ok=True)
 settings={r['key']:r for r in db.table('app_settings').select('*').execute().data}
 if 'apple_colors' not in settings or 'apple_models' not in settings:raise PipelineError('Chưa khởi tạo quy chuẩn trên Supabase')
 for key in ('apple_colors','apple_models'):(ROOT/f'config/{key}.json').write_text(json.dumps(settings[key]['value'],ensure_ascii=False))
 if 'telegram_watchlist' in settings:(ROOT/'config/telegram-watchlist.json').write_text(json.dumps(settings['telegram_watchlist']['value'],ensure_ascii=False))
 return settings

def materialize_catalog(db,slug):
 from catalog import fetch_discovered
 ready,meta=fetch_discovered(db,chain=CHAINS[slug])
 rows=[{'chain_name':CHAINS[slug],'source_url':r['url'],'status':'ready','reason':'','config':r} for r in ready]
 rows +=[{**r,'status':'review'} for r in meta['review_rows']]
 folder=ROOT/f'artifacts/full/merged/{slug}';folder.mkdir(parents=True,exist_ok=True)
 for name,value in [('catalog.json',rows),('summary.json',{'sources':None,'sources_ok':None,'links':len(rows),'discovery_run_id':meta['run_id']})]:(folder/name).write_text(json.dumps(value,ensure_ascii=False))
 return meta

def latest_payload(db,slug):
 rows=db.table('dashboard_snapshots').select('payload').eq('chain_name',CHAINS[slug]).order('business_date',desc=True).limit(1).execute().data
 return rows[0]['payload'] if rows else {'rows':[],'issues':[]}

def quotes(raw,slug,prefs):
 from apple_preferences import presentation
 from identity import storage_of
 out=[]
 for row in raw:
  p=presentation(row,prefs)
  if p['apple_selection'] not in ('selected','other','unconfigured'):continue
  p['apple_model']=p.get('apple_model') or p.get('model_name') or p['display_name']
  p['storage']=p.get('storage') or storage_of(p['product_name']);p['observed_at']=p.get('observed_at') or datetime.now(TZ).isoformat()
  keys=['sku','product_name','display_name','display_variant','brand','category','apple_model','storage','color','promo_price','promo_text','source_url','observed_at','promotion_complete','apple_selection','source_color','color_evidence','variant_id','stale_since','stale_reason']
  out.append({k:p.get(k) for k in keys}|{'chain':LABELS[slug],'slug':slug})
 return out

def run(args,env=None,input_text=None):
 result=subprocess.run([sys.executable,*args],cwd=ROOT,env=env,capture_output=True,text=True,input=input_text,timeout=5*3600)
 # Lưu log trong artifact GitHub, không chứa cấu hình/khóa.
 folder=ROOT/'out/cloud';folder.mkdir(parents=True,exist_ok=True)
 (folder/(Path(args[0]).stem+'-'+__import__('hashlib').sha256(json.dumps(args).encode()).hexdigest()[:8]+'.log')).write_text(result.stdout+'\n'+result.stderr)
 return result

def publish(db,job,slug,payload,revision):
 result=db.rpc('publish_dashboard_snapshot',{'p_job':job['id'],'p_chain':CHAINS[slug],'p_payload':payload,'p_date':datetime.now(TZ).date().isoformat(),'p_revision':revision}).execute()
 return result.data

def update(db,job,status=None,result=None):
 changes={'heartbeat_at':datetime.now(TZ).isoformat()}
 if status:changes['status']=status
 if result is not None:changes['result']=result
 if status in ('success','partial','error'):changes['finished_at']=datetime.now(TZ).isoformat()
 db.table('automation_jobs').update(changes).eq('id',job['id']).eq('status','running').execute()

def work(db,job,settings):
 payload=job['payload'];kind=job['kind'];revision=settings['apple_colors']['revision'];prefs=settings['apple_colors']['value']
 if payload.get('expected_revision',revision)!=revision:raise PipelineError('Quy chuẩn đã đổi; tạo lại yêu cầu')
 if kind=='config_update':
  from apple_rules import plan
  colors,models=plan(payload.get('products'),settings['apple_models']['value'],payload.get('renames') or [],prefs['products'])
  db.rpc('set_app_configuration',{'p_colors':colors,'p_models':models,'p_revision':revision}).execute()
  return {'message':'Đã áp dụng quy chuẩn được Python xác thực','channels':{},'dashboard_rebuilt':False},'success'
 if kind=='check_urls':
  result=run(['tools/check_apple_urls.py'],input_text=json.dumps(payload));data=json.loads(result.stdout.strip().splitlines()[-1])
  if not data.get('ok'):raise PipelineError(data.get('error','Không kiểm tra được URL'))
  result=run(['tools/apple_url_status.py']);statuses=json.loads(result.stdout.strip().splitlines()[-1])
  db.table('app_settings').upsert({'key':'apple_url_checks','value':statuses.get('statuses',{})}).execute()
  return {'url_results':data.get('results',[]),'channels':{},'message':'Đã kiểm tra link; chưa công bố giá'},'success'
 channels=[channel_slug(name) for name in resolve(payload.get('channels') or ['all'])];results={};lock=threading.Lock()
 def one(slug):
  try:
   if kind=='discovery':
    result=run(['discover_products.py','--chain',slug,'--out','out/discovery','--json-only']);summary=read(ROOT/f'out/discovery/{slug}/summary.json',{})
    return {'label':LABELS[slug],'status':'success' if result.returncode==0 and summary.get('published') else 'error','reason':summary.get('message',''),'sources':summary.get('sources'),'sources_ok':summary.get('sources_ok')}
   meta=materialize_catalog(db,slug);old=latest_payload(db,slug)
   chosen=prefs
   if kind=='verify_prices':
    rule=next((r for r in prefs['products'] if r['model']==payload['model']),None)
    if not rule:raise PipelineError('Model không còn trong quy chuẩn')
    chosen={**prefs,'products':[rule]}
   conf=ROOT/f'out/config/{slug}.json';conf.parent.mkdir(parents=True,exist_ok=True);conf.write_text(json.dumps(chosen,ensure_ascii=False))
   out=ROOT/f'out/apple/{slug}';env={**os.environ,'WPCS_APPLE_COLORS':str(conf),'WPCS_APPLE_OUT_DIR':str(out)}
   command=COMMANDS[slug]+([payload['model']] if slug=='tgdd' and kind=='verify_prices' else [])
   result=run(command,env);selected=out/FOLDERS[slug];raw=read(selected/'prices.json',[]);issues=read(selected/'issues.json',[]);summary=read(selected/'summary.json',{})
   for state in summary.get('models',[]):
    if state.get('status')=='missing_catalog':issues.append({'stage':'catalog','chain_name':CHAINS[slug],'product_name':state['model'],'model_name':state['model'],'source_url':'https://'+{'tgdd':'www.thegioididong.com','cellphones':'cellphones.com.vn','fpt':'fptshop.com.vn','viettel':'viettelstore.vn','phongvu':'phongvu.vn'}[slug],'reason':'Model theo quy chuẩn chưa có link trong catalog; chưa xác minh giá/màu.'})
   if result.returncode!=0:issues.append({'stage':'price','chain_name':CHAINS[slug],'sku':'','product_name':payload.get('model',''),'source_url':'https://'+{'tgdd':'www.thegioididong.com','cellphones':'cellphones.com.vn','fpt':'fptshop.com.vn','viettel':'viettelstore.vn','phongvu':'phongvu.vn'}[slug],'reason':'Worker chọn màu lỗi; chưa bảo đảm đọc đủ model Apple'})
   catalog_raw=[]
   if kind=='daily_prices':
    # Thu thập toàn catalog ở chế độ dry-run, rồi một transaction lưu giá đã chọn + lỗi đầy đủ.
    base=run(['scraper.py','--chain',slug,'--catalog','discovery','--out','out/prices','--dry-run'])
    directory=ROOT/f'out/prices/{slug}';generic=read(directory/'prices.json',[]);catalog_raw=list(generic);issues+=read(directory/'issues.json',[])
    from apple_preferences import presentation
    generic=[r for r in generic if presentation(r,prefs)['apple_selection'] in ('other','unconfigured')]
    raw=generic+raw
   from tools.apple_job import valid_row
   rules={r['model']:r for r in chosen['products']}
   raw=[r for r in raw if r.get('brand')!='Apple' or r.get('model_name') not in rules or valid_row(r,rules[r['model_name']])]
   raw=list({r['sku']:r for r in raw}.values())
   # Lưu cả màu/SKU ngoài quy chuẩn vào lịch sử nguồn; chỉ dashboard chọn màu theo cấu hình.
   stored=list({r['sku']:r for r in catalog_raw+raw}.values())
   issues=list({(i.get('source_url'),i.get('sku') or ''):{**i,'sku':i.get('sku') or '','chain_name':CHAINS[slug],'stage':i.get('stage') or 'price'} for i in issues}.values())
   fresh=quotes(raw,slug,prefs)
   keys={r['sku'] for r in fresh};target=payload.get('model')
   retained=[]
   for r in old.get('rows',[]):
    if r['sku'] in keys:continue
    if kind=='verify_prices' and r['apple_model']!=target:retained.append(r)
    else:retained.append({**r,'stale_since':datetime.now(TZ).isoformat(),'stale_reason':'Lượt mới chưa xác minh lại được SKU; giữ giá và thời điểm cũ.'})
   if not fresh and not stored:
    why='Không có giá/trạng thái nào xác minh thành công; giữ dữ liệu cũ'
    if retained:publish(db,job,slug,{**old,'rows':retained},revision)
    return {'label':LABELS[slug],'status':'error','reason':why,'priced':0,'status_only':0,'needs_check':len(issues),'published':False}
   if not fresh:issues.append({'chain_name':CHAINS[slug],'stage':'price','source_url':stored[0]['source_url'],'reason':'Đã lưu giá nguồn nhưng chưa xác minh lại được giá theo màu cấu hình; dashboard giữ dữ liệu cũ.'})
   issues=list({(i.get('source_url'),i.get('sku') or ''):i for i in issues}.values())
   source={'slug':slug,'label':LABELS[slug],'updated':max(r['observed_at'] for r in (fresh or stored)),'issues':len(issues),'models':summary.get('models',[]),'discovery':f"{meta['ready']}/{meta['total']} link khóa SKU",'warning':f"{meta['review']} link catalog cần kiểm tra" if meta['review'] else None}
   # Reporter hiện có đọc bảng daily_prices/summary. Không trộn SKU cũ vào lượt mới.
   year,week=weeks()[0];run_id=db.rpc('commit_dashboard_run',{'p_job':job['id'],'p_chain':CHAINS[slug],'p_payload':{'rows':fresh+retained,'issues':[{**i,'slug':slug,'chain':LABELS[slug]} for i in issues],'source':source},'p_date':datetime.now(TZ).date().isoformat(),'p_revision':revision,'p_year':year,'p_week':week,'p_rows':stored,'p_issues':issues,'p_catalog_run':meta['run_id']}).execute().data
   report_dir=ROOT/f'out/report-prices/{slug}';report_dir.mkdir(parents=True,exist_ok=True)
   (report_dir/'summary.json').write_text(json.dumps({'chain_name':CHAINS[slug],'status':'degraded' if issues else 'ok','run_id':run_id,'year':year,'week':week,'prices':len(stored),'issues':len(issues),'expected':len(stored)+len(issues),'report_skus':[r['sku'] for r in fresh]}))
   return {'label':LABELS[slug],'status':'partial' if issues else 'success','priced':sum(r['promo_price'] is not None for r in fresh),'status_only':sum(r['promo_price'] is None for r in fresh),'needs_check':len(issues),'published':True}
  except Exception as exc:return {'label':LABELS[slug],'status':'error','reason':str(exc) if isinstance(exc,PipelineError) else type(exc).__name__,'published':False}
 def thread(slug):
  with lock:results[slug]={'label':LABELS[slug],'status':'running'};update(db,job,result={'channels':results})
  result=one(slug)
  with lock:results[slug]=result;update(db,job,result={'channels':results})
 threads=[threading.Thread(target=thread,args=(s,)) for s in channels]
 for t in threads:t.start()
 for t in threads:t.join()
 if kind=='daily_prices' and payload.get('send_report'):
  report=run(['telegram_reporter.py','--summaries','out/report-prices','--out','out/report','--chains',','.join(channels)])
  if report.returncode:raise PipelineError('Thu thập kết thúc nhưng Telegram lỗi; xem artifact báo cáo')
 if kind=='discovery' and payload.get('send_report'):
  report=run(['discovery_status.py','--summaries','out/discovery','--chains',','.join(channels),'--send'])
  if report.returncode:raise PipelineError('Discovery kết thúc nhưng Telegram lỗi')
 overall='success' if all(r['status']=='success' for r in results.values()) else 'error' if all(r['status']=='error' for r in results.values()) else 'partial'
 return {'channels':results,'dashboard_rebuilt':any(r.get('published') for r in results.values())},overall

def main(args):
 db=database()
 if args.bootstrap:
  for key in ['apple_colors','apple_models','telegram_watchlist']:
   existing=db.table('app_settings').select('key').eq('key',key).execute().data
   file=ROOT/('config/telegram-watchlist.json' if key=='telegram_watchlist' else f'config/{key}.json')
   if not existing:db.table('app_settings').insert({'key':key,'value':read(file,{})}).execute()
  if args.import_catalog:
   for slug,chain in CHAINS.items():
    existing=db.table('discovery_runs').select('id').eq('chain_name',chain).limit(1).execute().data
    if existing:continue
    catalog=read(ROOT/f'artifacts/full/merged/{slug}/catalog.json',[])
    if not catalog:raise PipelineError('Không có catalog local đã nghiệm thu cho '+chain)
    completed=min(r['config']['discovered_at'] for r in catalog)
    db.rpc('seed_discovery_catalog',{'p_chain':chain,'p_rows':catalog,'p_completed':completed}).execute()
  if args.import_snapshot:
   data=read(ROOT/'web/data/comparison.json',{})
   for slug,chain in CHAINS.items():
    rows=[r for r in data.get('rows',[]) if r['slug']==slug]
    for day in sorted({r['observed_at'][:10] for r in rows}):
     payload={'rows':[r for r in rows if r['observed_at'][:10]==day],'issues':[i for i in data.get('issues',[]) if i.get('slug')==slug],'source':next((s for s in data.get('sources',[]) if s['slug']==slug),{})}
     exists=db.table('dashboard_snapshots').select('id').eq('chain_name',chain).eq('business_date',day).execute().data
     if not exists:db.table('dashboard_snapshots').insert({'chain_name':chain,'business_date':day,'payload':payload}).execute()
  print('Khởi tạo cấu hình hoàn tất; không ghi đè cấu hình/snapshot đã có.');return
 if args.job_id:uuid.UUID(args.job_id);job_id=args.job_id
 else:
  job_id=str(uuid.uuid4());db.table('automation_jobs').insert({'id':job_id,'kind':args.kind,'payload':{'channels':args.chains.split(',') if args.chains!='all' else list(CHAINS),'send_report':args.send_report},'lease_until':(datetime.now(TZ)+timedelta(hours=6)).isoformat()}).execute()
 job=db.rpc('claim_automation_job',{'p_id':job_id}).execute().data
 stop=threading.Event()
 def heartbeat():
  while not stop.wait(30):
   try:db.table('automation_jobs').update({'heartbeat_at':datetime.now(TZ).isoformat(),'lease_until':(datetime.now(TZ)+timedelta(hours=6)).isoformat()}).eq('id',job_id).eq('status','running').execute()
   except Exception:pass
 beat=threading.Thread(target=heartbeat,daemon=True);beat.start()
 try:settings=configure(db);result,status=work(db,job,settings);update(db,job,status,result);print(json.dumps({'id':job_id,'status':status,'result':result},ensure_ascii=False));return 1 if status=='error' else 0
 except Exception as exc:update(db,job,'error',{'error':str(exc) if isinstance(exc,PipelineError) else type(exc).__name__});raise
 finally:stop.set();beat.join(timeout=2)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--job-id');parser.add_argument('--kind',choices=['daily_prices','discovery']);parser.add_argument('--chains',default='all');parser.add_argument('--send-report',action='store_true');parser.add_argument('--bootstrap',action='store_true');parser.add_argument('--import-snapshot',action='store_true');parser.add_argument('--import-catalog',action='store_true');args=parser.parse_args()
 if not(args.job_id or args.kind or args.bootstrap):parser.error('Cần job ID, kind hoặc bootstrap')
 raise SystemExit(main(args) or 0)
