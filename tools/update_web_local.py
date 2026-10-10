"""Chạy trên Mac theo quy chuẩn Apple đã lưu; tự công bố lên Supabase, không Telegram."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from apple_jobs import running_workers
from chains import resolve, slug
from common import database, TZ, PipelineError
from tools.cloud_worker import expire_jobs


def active_jobs(db):
    return db.table('automation_jobs').select('id,kind,status').in_('status', ['pending', 'running']).execute().data


def wait_for_idle(db, channels, seconds, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + seconds
    last = None
    while True:
        expire_jobs(db)
        jobs = active_jobs(db)
        workers = running_workers(exclude=[os.getpid()])
        workers = {c: pids for c, pids in workers.items() if c in channels}
        if not jobs and not workers:
            return
        message = 'Đang chờ lượt bot hiện tại kết thúc; không dừng hoặc chạy chồng. Giữ cửa sổ này mở.'
        if last != message:
            print(message, flush=True)
            last = message
        if clock() >= deadline:
            raise PipelineError('Hết thời gian chờ. Bot hiện tại không bị dừng; chạy lại sau khi hoàn tất.')
        sleep(10)


def create_job(db, kind, channels, payload=None):
    # Unique index trong DB là khóa cuối cùng nếu runner khác khởi chạy đúng lúc này.
    job_id = str(uuid.uuid4())
    db.table('automation_jobs').insert({
        'id': job_id, 'kind': kind,
        'payload': {**(payload or {}), 'channels': channels, 'send_report': False, 'source': 'local_mac'},
        'lease_until': (datetime.now(TZ) + timedelta(hours=6)).isoformat(),
    }).execute()
    return job_id


def run_job(db, kind, channels, wait_seconds, payload=None):
    wait_for_idle(db, channels, wait_seconds)
    try:
        job_id = create_job(db, kind, channels) if payload is None else create_job(db, kind, channels, payload)
    except Exception:
        raise PipelineError('Một runner khác vừa nhận hàng đợi hoặc DB từ chối yêu cầu; chưa chạy bot. Thử lại sau.') from None
    folder = ROOT / 'out/local-web' / job_id
    folder.mkdir(parents=True, exist_ok=True)
    print(f'Bắt đầu {kind} trên máy này. Job: {job_id}', flush=True)
    with (folder / 'run.log').open('w') as log:
        process = subprocess.Popen([sys.executable, 'tools/cloud_worker.py', '--job-id', job_id],
                                   cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
        process.wait()
    job = db.table('automation_jobs').select('status,result').eq('id', job_id).single().execute().data
    if process.returncode and job['status'] in ('pending', 'running'):
        result = {**job.get('result', {}), 'error': 'Tiến trình local đã kết thúc có lỗi; giữ dữ liệu thành công trước.'}
        db.table('automation_jobs').update({'status': 'error', 'finished_at': datetime.now(TZ).isoformat(), 'result': result}).eq('id', job_id).in_('status', ['pending', 'running']).execute()
        job = {**job, 'status': 'error', 'result': result}
    (folder / 'summary.json').write_text(json.dumps(job, ensure_ascii=False, indent=2))
    for channel, result in job.get('result', {}).get('channels', {}).items():
        print(f"{channel}: {result.get('status')} · {result.get('priced', 0)} SKU có giá · "
              f"{result.get('status_only', 0)} chỉ trạng thái · {result.get('needs_check', 0)} cần kiểm tra", flush=True)
        if result.get('reason'):
            print(result['reason'], flush=True)
    print('Log và kết quả:', folder, flush=True)
    if process.returncode or job['status'] == 'error':
        raise PipelineError('Lượt có lỗi; xem summary. Các kênh đã công bố thành công vẫn được giữ.')
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channels', default='all')
    parser.add_argument('--discover', action='store_true', help='Tìm link trước rồi cập nhật giá')
    parser.add_argument('--check', action='store_true', help='Chỉ kiểm tra kết nối, không cào/ghi dữ liệu')
    parser.add_argument('--wait-seconds', type=int, default=21600)
    args = parser.parse_args()
    channels = [slug(c) for c in resolve([args.channels])]
    if args.wait_seconds < 0:
        parser.error('Thời gian chờ không được âm')
    db = database()
    prefs = db.table('app_settings').select('value').eq('key', 'apple_colors').single().execute().data
    print(f"Kết nối Supabase: OK · {len(prefs['value']['products'])} model Apple đã lưu", flush=True)
    if args.check:
        print('Job đang hoạt động:', len(active_jobs(db)))
        return 0
    path = ROOT / 'artifacts/locks/update-web-local.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PipelineError('Nút Cập nhật web đã chạy ở một cửa sổ khác; không khởi chạy trùng.') from None
        if args.discover:
            run_job(db, 'discovery', channels, args.wait_seconds)
        job = run_job(db, 'daily_prices', channels, args.wait_seconds)
        print('Đã kết thúc. Web tự làm mới khoảng một phút; giữ đúng thời điểm từng SKU.', flush=True)
        if job['status'] == 'partial':
            print('Có kênh/SKU cần kiểm tra; không xác nhận tất cả giá đều mới.', flush=True)
            return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except PipelineError as exc:
        print(str(exc), flush=True)
        sys.exit(1)
    except Exception as exc:
        print('Chưa hoàn tất:', type(exc).__name__, '— kiểm tra cấu hình/kết nối; không xác nhận đã cập nhật web.', flush=True)
        sys.exit(1)
