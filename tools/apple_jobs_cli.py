"""Tạo/xem job xác minh giá (dùng bởi API local). create: stdin {model, channels, fingerprint}; list: stdin {model}."""
import json
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import apple_jobs as jobs  # noqa: E402


def create(payload):
    import fcntl
    jobs.LOCKS.mkdir(parents=True,exist_ok=True)
    with open(jobs.LOCKS/'apple-job-create.lock','a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        return _create(payload)


def _create(payload):
    model, channels = payload.get('model'), payload.get('channels') or []
    if not isinstance(channels, list) or not channels or any(c not in jobs.CHANNELS for c in channels):
        return {'ok': False, 'error': 'Chọn ít nhất một kênh hợp lệ'}
    fingerprint, rule = jobs.rule_fingerprint(model or '')
    if rule is None:
        return {'ok': False, 'error': 'Model chưa được lưu; lưu cấu hình trước khi chạy'}
    if payload.get('fingerprint') and payload['fingerprint'] != fingerprint:
        return {'ok': False, 'error': 'Cấu hình trên trang khác cấu hình đã lưu; tải lại trang'}
    active = jobs.active_job()
    if active:
        return {'ok': False, 'busy': True, 'error': f'Đang chạy job cho {active["model"]}; chờ job đó xong'}
    busy = {s: pids for s, pids in jobs.running_workers().items() if s in channels}
    if busy:
        names = ', '.join(f'{jobs.CHANNELS[s][0]} (PID {", ".join(map(str, p))})' for s, p in busy.items())
        return {'ok': False, 'busy': True, 'error': f'Đang có worker chạy từ CLI: {names}; không chạy chồng'}
    job_id = jobs.now()[:19].replace(':', '').replace('-', '') + '-' + uuid.uuid4().hex[:6]
    folder = jobs.job_dir(job_id)
    folder.mkdir(parents=True)
    state = {'id': job_id, 'model': rule['model'], 'color': rule.get('color'), 'fingerprint': fingerprint,
             'created_at': jobs.now(), 'status': 'pending', 'telegram': False,
             'channels': {s: {'label': jobs.CHANNELS[s][0], 'status': 'pending'} for s in channels}}
    jobs.write_state(job_id, state)
    log = open(folder / 'runner.log', 'w')
    # Tiến trình tách riêng: tải lại trang/khởi động lại dev server không dừng job.
    subprocess.Popen([sys.executable, str(ROOT / 'tools/apple_job.py'), job_id], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                     stdin=subprocess.DEVNULL, start_new_session=True)
    return {'ok': True, 'job': state}


def main():
    payload = json.loads(sys.stdin.read() or '{}')
    if sys.argv[1] == 'create':
        result = create(payload)
    else:
        fingerprint, rule = jobs.rule_fingerprint(payload.get('model') or '') if payload.get('model') else (None, None)
        active = jobs.active_job()
        result = {'ok': True, 'jobs': jobs.list_jobs(payload.get('model')), 'active': active, 'fingerprint': fingerprint,
                  'cli_workers': {jobs.CHANNELS[s][0]: p for s, p in jobs.running_workers().items()}}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
