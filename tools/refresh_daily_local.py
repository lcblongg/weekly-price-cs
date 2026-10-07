"""Cập nhật thật toàn catalog và màu Apple, từng kênh độc lập, không Telegram/DB.
Đầu ra/backup riêng mỗi lượt; khóa được giữ suốt cào và công bố. Lịch sử giữ ngày nguồn.
"""
import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, threading
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from apple_jobs import CHANNELS, channel_lock
from apple_preferences import load
from common import TZ
from scraper import write_json
OUT=ROOT/'artifacts/daily-local'/datetime.now(TZ).strftime('%Y%m%d-%H%M%S')
MUTEX=threading.Lock()
STATE={'started_at':datetime.now(TZ).isoformat(),'channels':{s:{'status':'pending'} for s in CHANNELS},'telegram_sent':False}

def signature():
 return hashlib.sha256((ROOT/'config/apple_colors.json').read_bytes()+(ROOT/'config/apple_models.json').read_bytes()).hexdigest()

def checkpoint(slug,**values):
 with MUTEX:
  STATE['channels'][slug].update(values);write_json(OUT/'status.json',STATE)
 print(slug,values,flush=True)

def read(path):return json.loads(path.read_text())

def base_folder(slug):
 path=ROOT/f'artifacts/{slug}-review-full/{slug}'
 return path if (path/'prices.json').exists() else ROOT/('artifacts/status-repair/tgdd' if slug=='tgdd' else f'artifacts/full-refresh/display/{slug}')

def publish(slug,folder,target,fingerprint,apple=False):
 if signature()!=fingerprint:raise RuntimeError('Cấu hình màu đã đổi; không công bố kết quả của quy tắc cũ')
 summary=read(folder/'summary.json')
 if summary.get('status') not in ('complete','ok','degraded'):raise RuntimeError('Worker chưa hoàn tất thành công: '+str(summary.get('message') or summary.get('status')))
 fresh=[r for r in read(folder/'prices.json') if not r.get('stale_since')];issues=read(folder/'issues.json')
 if not fresh:raise RuntimeError('Không có giá/trạng thái mới; giữ dữ liệu cũ')
 previous=read(target/'prices.json');ids={r['sku'] for r in fresh};now=datetime.now(TZ).isoformat()
 # SKU lỗi không bị xóa, nhưng vẫn giữ giờ cào cũ và đánh dấu lần cập nhật thất bại.
 old=[{**r,'stale_since':now,'stale_reason':'Lượt cập nhật ngày hôm nay chưa xác minh lại được SKU này; xem lỗi nguồn.'} for r in previous if r['sku'] not in ids]
 rows=fresh+old
 summary.update(prices=len(fresh),retained_stale=len(old),last_partial_update={'at':now},review_update={'at':now,'scope':'Cào thật toàn catalog; giữ giờ nguồn của SKU lỗi.'})
 if apple:
  by_model={m['model']:m for m in summary.get('models',[])}
  for row in old:
   m=by_model.get(row.get('model_name'))
   if m:m['last_failed_update']={'at':now,'reason':row['stale_reason']}
 for name,value in [('prices.json',rows),('issues.json',issues),('summary.json',summary)]:write_json(target/name,value)
 # Build được khóa chung; không công bố lại toàn bộ snapshot cũ và không thay ngày giá.
 subprocess.run([sys.executable,'tools/build_comparison.py','--preserve-history'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
 return {'fresh':len(fresh),'numeric':sum(r.get('promo_price') is not None for r in fresh),'status_only':sum(r.get('promo_price') is None for r in fresh),'issues':len(issues),'retained':len(old)}

def worker(slug):
 try:
  with channel_lock(slug) as fd:
   fingerprint=signature();env=os.environ.copy();env.update(WPCS_CHANNEL_LOCK_FD=str(fd),WPCS_CHANNEL_LOCK_SLUG=slug,WPCS_APPLE_OUT_DIR=str(OUT/'apple'))
   target=ROOT/'artifacts'/CHANNELS[slug][1];folder=OUT/'apple'/CHANNELS[slug][1]
   command=[sys.executable,*CHANNELS[slug][2]]
   command=[c for c in command if c!='{model}']
   checkpoint(slug,status='running',phase='apple')
   with (OUT/f'{slug}-apple.log').open('w') as log:
    result=subprocess.run(command,cwd=ROOT,env=env,pass_fds=(fd,),stdout=log,stderr=subprocess.STDOUT)
   if result.returncode==0:
    stats=publish(slug,folder,target,fingerprint,apple=True);checkpoint(slug,apple=stats)
   else:checkpoint(slug,apple_error=f'Worker Apple exit {result.returncode}; giữ dữ liệu cũ')
   checkpoint(slug,phase='catalog')
   generic=OUT/'prices'/slug;generic.mkdir(parents=True,exist_ok=True)
   # Seed để worker giữ lại các SKU lỗi, không ảnh hưởng dữ liệu đã công bố.
   shutil.copy2(base_folder(slug)/'prices.json',generic/'prices.json')
   with (OUT/f'{slug}-catalog.log').open('w') as log:
    result=subprocess.run([sys.executable,'scraper.py','--chain',slug,'--catalog','file','--config',str(ROOT/f'artifacts/full/merged/{slug}/catalog.json'),'--dry-run','--out',str(OUT/'prices')],cwd=ROOT,env=env,pass_fds=(fd,),stdout=log,stderr=subprocess.STDOUT)
   stats=publish(slug,generic,base_folder(slug),fingerprint)
   checkpoint(slug,status='partial' if stats['issues'] or STATE['channels'][slug].get('apple_error') or STATE['channels'][slug].get('apple',{}).get('issues') else 'success',phase='finished',catalog=stats,finished_at=datetime.now(TZ).isoformat())
 except Exception as exc:checkpoint(slug,status='error',reason=str(exc),finished_at=datetime.now(TZ).isoformat())

def main():
 OUT.mkdir(parents=True);load()
 # Backup bất biến trước khi chạy bất kỳ worker nào.
 targets=[ROOT/'web/data/comparison.json']+[ROOT/'artifacts'/x[1] for x in CHANNELS.values()]+[base_folder(s) for s in CHANNELS]
 for path in targets:
  dest=OUT/'backup'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
  if path.is_dir():shutil.copytree(path,dest)
  else:shutil.copy2(path,dest)
 write_json(OUT/'status.json',STATE)
 (ROOT/'artifacts/daily-local/latest.txt').write_text(str(OUT.relative_to(ROOT)))
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(worker,CHANNELS))
 STATE['finished_at']=datetime.now(TZ).isoformat();write_json(OUT/'status.json',STATE)
 print('FINISHED',str(OUT),flush=True)
if __name__=='__main__':main()
