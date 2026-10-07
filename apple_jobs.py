"""Job "Xác minh và cập nhật giá" cho một model Apple (local/development).

- Khóa theo kênh dùng chung với worker chạy từ CLI (`channel_lock`), cộng quét tiến trình để phát hiện worker
  khởi chạy trước khi có khóa.
- Mỗi job có thư mục riêng: cấu hình chụp lại (chỉ model được chọn), đầu ra từng kênh, state.json.
- Công bố chỉ thay bản ghi của đúng model ở đúng kênh; cấu hình model đổi trong lúc chạy → không công bố.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

from apple_rules import COLORS, MODELS, key
from common import TZ

ROOT = Path(__file__).parent
# WPCS_JOB_ARTIFACTS: kiểm thử cô lập (job + dữ liệu công bố ở thư mục tạm). Khóa kênh luôn dùng chung thật.
ARTIFACTS = Path(os.environ.get('WPCS_JOB_ARTIFACTS') or ROOT / 'artifacts')
ISOLATED = ARTIFACTS != ROOT / 'artifacts'
JOBS = ARTIFACTS / 'apple-jobs'
LOCKS = ROOT / 'artifacts/locks'
CHANNELS = {  # slug → (nhãn, thư mục dữ liệu đã công bố, lệnh worker)
    'tgdd': ('MW', 'mw-apple-selected', ['tools/scrape_mw_apple.py', '{model}']),
    'cellphones': ('CPS', 'cps-apple-selected', ['tools/scrape_cps_apple.py']),
    'fpt': ('FPT', 'fpt-apple-selected', ['tools/scrape_remaining_apple.py', 'fpt']),
    'viettel': ('Viettel', 'viettel-apple-selected', ['tools/scrape_remaining_apple.py', 'viettel']),
    'phongvu': ('Phong Vũ', 'phongvu-apple-selected', ['tools/scrape_remaining_apple.py', 'phongvu']),
}
WORKER_SCRIPTS = {'tgdd': 'scrape_mw_apple.py', 'cellphones': 'scrape_cps_apple.py'}
STATES = ('pending', 'running', 'success', 'partial', 'error')


class Busy(RuntimeError):
    """Kênh/job đang được tiến trình khác dùng."""


def now():
    return datetime.now(TZ).isoformat(timespec='seconds')


@contextlib.contextmanager
def channel_lock(slug, wait=False):
    """Khóa ghi một kênh. Worker CLI, job và bước công bố đều phải giữ khóa này."""
    LOCKS.mkdir(parents=True, exist_ok=True)
    path = LOCKS / f'apple-{slug}.lock'
    inherited = os.environ.get('WPCS_CHANNEL_LOCK_FD')
    if inherited and os.environ.get('WPCS_CHANNEL_LOCK_SLUG') == slug:
        # FD truyền từ runner giữ cùng khóa suốt cào → công bố; con không mở khóa của cha.
        fd = int(inherited)
        stat = os.fstat(fd)
        expected = path.stat()
        if (stat.st_dev, stat.st_ino) != (expected.st_dev, expected.st_ino):
            raise Busy('FD khóa kênh không hợp lệ')
        yield fd
        return
    handle = open(path, 'a+')
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError:
            raise Busy(f'Đang có worker khác chạy kênh {CHANNELS[slug][0]}') from None
        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        yield handle.fileno()
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def running_workers(exclude=()):
    """Worker Apple đang chạy (kể cả khởi chạy từ CLI trước khi có khóa). Trả về {slug: [pid,...]}.
    Chỉ tính tiến trình có chương trình là python và đối số script đúng là file worker (không khớp nhầm shell/grep)."""
    try:
        output = subprocess.run(['ps', '-axo', 'pid=,command='], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    found = {}
    for line in output.splitlines():
        pid, _, command = line.strip().partition(' ')
        parts = command.split()
        if not pid.isdigit() or int(pid) in exclude or not parts or 'python' not in Path(parts[0]).name.lower():
            continue
        names = set(WORKER_SCRIPTS.values()) | {'scrape_remaining_apple.py', 'scraper.py', 'discover_products.py'}
        script = next((i for i, part in enumerate(parts[1:], 1) if Path(part).name in names), None)
        if script is None:
            continue
        name = Path(parts[script]).name
        for slug, worker in WORKER_SCRIPTS.items():
            if name == worker:
                found.setdefault(slug, []).append(int(pid))
        if name in ('scraper.py', 'discover_products.py'):
            from chains import resolve, slug as chain_slug
            args = parts[script + 1:]
            values = [args[i+1] for i, v in enumerate(args[:-1]) if v == '--chain']
            try:
                for chain in resolve(values):found.setdefault(chain_slug(chain), []).append(int(pid))
            except ValueError:
                pass
        if name == 'scrape_remaining_apple.py':
            args = parts[script + 1:]
            for slug in ([a for a in args if a in ('fpt', 'viettel', 'phongvu')] or ['fpt', 'viettel', 'phongvu']):
                found.setdefault(slug, []).append(int(pid))
    return found


def rule_fingerprint(model):
    """Dấu của cấu hình ảnh hưởng tới kết quả: quy tắc màu/URL của model + toàn bộ quy tắc nhận diện."""
    colors = json.loads(COLORS.read_text(encoding='utf-8'))
    rule = next((r for r in colors['products'] if key(r['model']) == key(model)), None)
    payload = json.dumps({'rule': rule, 'models': json.loads(MODELS.read_text(encoding='utf-8'))}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest(), rule


def job_dir(job_id):
    if not job_id or not all(c.isalnum() or c == '-' for c in job_id):
        raise ValueError('Mã job không hợp lệ')
    return JOBS / job_id


def read_state(job_id):
    path = job_dir(job_id) / 'state.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def write_state(job_id, state):
    path = job_dir(job_id) / 'state.json'
    temporary = path.with_suffix(f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding='utf-8')
    temporary.replace(path)


def list_jobs(model=None, limit=10):
    if not JOBS.exists():
        return []
    states = []
    for folder in JOBS.iterdir():
        state_file = folder / 'state.json'
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding='utf-8'))
            if model is None or key(state.get('model')) == key(model):
                states.append(state)
    return sorted(states, key=lambda s: s.get('created_at', ''), reverse=True)[:limit]


def active_job():
    """Job đang chạy thật (tiến trình runner còn sống). Job mồ côi được đánh dấu lỗi, không chặn mãi."""
    for state in list_jobs(limit=50):
        if state.get('status') in ('pending', 'running'):
            pid = state.get('runner_pid')
            alive = False
            if pid:
                try:
                    os.kill(pid, 0)
                    alive = True
                except OSError:
                    alive = False
            if alive or (state.get('status') == 'pending' and not pid):
                return state
            state['status'] = 'error'
            state['error'] = 'Tiến trình chạy nền đã dừng bất thường'
            for channel in state.get('channels', {}).values():
                if channel['status'] in ('pending', 'running'):
                    channel.update(status='error', reason='Tiến trình chạy nền đã dừng bất thường', finished_at=now())
            write_state(state['id'], state)
    return None
