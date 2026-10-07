"""Cào toàn catalog 5 kênh không giới hạn mẫu; cập nhật demo khi từng kênh hoàn tất.
Không ghi Supabase/gửi Telegram. Đầu ra riêng, giữ nguyên lượt thử trước.
Chạy từ gốc dự án: .venv/bin/python tools/refresh_full_demo.py
"""
import concurrent.futures
import json
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/full-refresh'
SLUGS=['tgdd','cellphones','viettel','fpt','phongvu']

def worker(slug):
    with (OUT/f'{slug}.log').open('w',encoding='utf-8') as log:
        result=subprocess.run([sys.executable,'scraper.py','--chain',slug,'--catalog','file','--config',f'artifacts/full/merged/{slug}/catalog.json','--dry-run','--out',str(OUT/'prices')],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    return slug,result.returncode

def update():
    subprocess.run([sys.executable,'build_demo.py','--prices',str(OUT/'display')],cwd=ROOT,check=True)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # Không ghi đè lượt full-refresh trước; mỗi lượt cần thư mục riêng.
    if any((OUT/'prices'/slug/'summary.json').exists() for slug in SLUGS):
        raise SystemExit('Đã có kết quả full-refresh; chọn thư mục lượt mới trong script trước khi chạy lại.')
    for slug in SLUGS:
        dest=OUT/'display'/slug;dest.mkdir(parents=True,exist_ok=True)
        for name in ['prices.json','issues.json','summary.json']:
            shutil.copy2(ROOT/'artifacts/full/prices'/slug/name,dest/name)
    update()
    states={slug:'running' for slug in SLUGS}
    def checkpoint():
        target=OUT/'status.json';temp=target.with_suffix('.tmp');temp.write_text(json.dumps(states,ensure_ascii=False,indent=2));temp.replace(target)
    checkpoint()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        jobs=[pool.submit(worker,slug) for slug in SLUGS]
        for future in concurrent.futures.as_completed(jobs):
            slug,code=future.result();summary_path=OUT/'prices'/slug/'summary.json'
            summary=json.loads(summary_path.read_text()) if summary_path.exists() else {}
            states[slug]={'exit_code':code,'status':summary.get('status','failed'),'prices':summary.get('prices',0),'expected':summary.get('expected',0)}
            if code==0 and summary.get('status') in ['ok','degraded']:
                for name in ['prices.json','issues.json','summary.json']:
                    shutil.copy2(OUT/'prices'/slug/name,OUT/'display'/slug/name)
                update()
            checkpoint();print(slug,states[slug],flush=True)
    print('Đã kết thúc lượt cào toàn catalog. Kiểm tra status.json; Garmin vẫn chưa đủ nguồn.',flush=True)
if __name__=='__main__':main()
