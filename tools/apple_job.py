"""Chạy nền một job "Xác minh và cập nhật giá": python tools/apple_job.py <job_id>
Dùng nguyên worker chọn màu hiện có ở chế độ cô lập (cấu hình chỉ gồm model được chọn, đầu ra trong thư mục job).
Mỗi kênh độc lập: kênh lỗi không ảnh hưởng kênh khác. Chỉ công bố khi cấu hình model không đổi trong lúc chạy;
chỉ thay bản ghi của đúng model/kênh; SKU không xác minh lại được giữ dữ liệu cũ kèm cảnh báo thời điểm.
Không ghi Supabase, không gửi Telegram."""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import apple_jobs as jobs  # noqa: E402
from apple_rules import key  # noqa: E402

TIMEOUTS = {'tgdd': 3600, 'cellphones': 1200, 'fpt': 1800, 'viettel': 1800, 'phongvu': 1800}
LOCK = threading.Lock()


def update(job_id, slug=None, **fields):
    with LOCK:
        state = jobs.read_state(job_id)
        target = state['channels'][slug] if slug else state
        target.update(fields)
        jobs.write_state(job_id, state)
        return state


def load(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def valid_row(row, rule):
    """Chỉ công bố bản ghi có đủ chứng cứ đúng model/SKU/màu và giá hợp lệ (số > 0 hoặc NULL kèm trạng thái)."""
    proof = row.get('color_evidence') or {}
    if row.get('model_name') != rule['model'] or not row.get('sku'):
        return False
    if proof.get('model') != rule['model'] or str(proof.get('product_code')) != str(row.get('variant_id')) or not proof.get('verified_at'):
        return False
    if rule.get('color') and (proof.get('website_color_id') is None or key(proof.get('canonical_color')) != key(rule['color'])):
        return False
    price = row.get('promo_price')
    if price is None:
        return '[Tình trạng]' in str(row.get('promo_text') or '')  # NULL chỉ hợp lệ khi website trả trạng thái
    return isinstance(price, int) and not isinstance(price, bool) and price > 0


def same_model(record, model):
    return key(record.get('model_name') or record.get('product_name')) == key(model)


def publish(slug, folder, rule, rows, issues, job_id, finished):
    """Thay dữ liệu của đúng model ở một kênh. Trả về số bản ghi cũ được giữ (không xác minh lại được)."""
    target = jobs.ARTIFACTS / folder
    target.mkdir(parents=True, exist_ok=True)
    prices = load(target / 'prices.json', [])
    old = [r for r in prices if same_model(r, rule['model'])]
    others = [r for r in prices if not same_model(r, rule['model'])]
    fresh = {r['sku'] for r in rows}
    kept = []
    for row in old:
        if row['sku'] in fresh:
            continue
        # Giữ kết quả thành công trước đó nhưng ghi rõ là dữ liệu cũ.
        kept.append({**row, 'stale_since': finished, 'stale_reason': f'Lượt xác minh {finished} không đọc lại được SKU này; dữ liệu lúc {row.get("observed_at")}'})
    all_issues = [i for i in load(target / 'issues.json', []) if not same_model(i, rule['model'])] + issues
    summary = load(target / 'summary.json', {'stage': folder, 'status': 'complete', 'models': []})
    models = [m for m in summary.get('models', []) if key(m.get('model')) != key(rule['model'])]
    models.append({'model': rule['model'], 'color': rule.get('color'), 'status': 'partial' if (issues or kept) else 'ok',
                   'records': len(rows) + len(kept), 'verified_records': len(rows), 'stale_records': len(kept),
                   'problems': [i.get('reason') for i in issues][:20], 'updated_at': finished, 'job': job_id})
    summary.update(models=models, prices=len(others) + len(rows) + len(kept), issues=len(all_issues),
                   last_partial_update={'model': rule['model'], 'job': job_id, 'at': finished})
    for name, data in (('prices.json', others + rows + kept), ('issues.json', all_issues), ('summary.json', summary)):
        temporary = target / f'{name}.{os.getpid()}.tmp'
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
        temporary.replace(target / name)
    return len(kept)


def mark_stale(folder, rule, finished, reason, job_id):
    """Kênh lỗi: không đổi giá cũ; ghi cảnh báo vào summary để dashboard/trang biết dữ liệu đang cũ."""
    target = jobs.ARTIFACTS / folder
    if not (target / 'summary.json').exists():
        return 0, None
    old = [r for r in load(target / 'prices.json', []) if same_model(r, rule['model'])]
    summary = load(target / 'summary.json', {})
    for model in summary.get('models', []):
        if key(model.get('model')) == key(rule['model']):
            model.update(last_failed_update={'at': finished, 'job': job_id, 'reason': reason})
    temporary = target / f'summary.json.{os.getpid()}.tmp'
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    temporary.replace(target / 'summary.json')
    return len(old), max((r.get('observed_at') or '' for r in old), default=None)


def run_channel(job_id, slug, rule, fingerprint, folder_root):
    try:
        with jobs.channel_lock(slug) as lock_fd:
            return _run_channel(job_id, slug, rule, fingerprint, folder_root, lock_fd)
    except jobs.Busy as exc:
        update(job_id, slug, status='error', finished_at=jobs.now(), reason=str(exc))
        return None
    except Exception as exc:
        update(job_id, slug, status='error', finished_at=jobs.now(), reason=f'Lỗi runner: {type(exc).__name__}: {exc}')
        return None


def _run_channel(job_id, slug, rule, fingerprint, folder_root, lock_fd):
    label, folder, command = jobs.CHANNELS[slug]
    busy = jobs.running_workers(exclude={os.getpid()}).get(slug)
    if busy:
        update(job_id, slug, status='error', finished_at=jobs.now(),
               reason=f'Đang có worker {label} khác chạy (PID {", ".join(map(str, busy))}); không chạy chồng')
        return None
    update(job_id, slug, status='running', started_at=jobs.now())
    out = folder_root / slug
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'WPCS_APPLE_COLORS': str(folder_root.parent / 'apple_colors.json'), 'WPCS_APPLE_OUT_DIR': str(out), 'WPCS_CHANNEL_LOCK_FD': str(lock_fd), 'WPCS_CHANNEL_LOCK_SLUG': slug}
    args = [sys.executable] + [a.replace('{model}', rule['model']) for a in command]
    with open(folder_root.parent / f'{slug}.log', 'w', encoding='utf-8') as log:
        try:
            code = subprocess.run(args, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=TIMEOUTS[slug], pass_fds=(lock_fd,)).returncode
        except subprocess.TimeoutExpired:
            code = 'timeout'
    finished = jobs.now()
    rows = [r for r in load(out / folder / 'prices.json', []) if same_model(r, rule['model'])]
    issues = [i for i in load(out / folder / 'issues.json', []) if same_model(i, rule['model'])]
    good = [r for r in rows if valid_row(r, rule)]
    rejected = len(rows) - len(good)
    issues += [{'chain_name': r.get('chain_name'), 'product_name': rule['model'], 'model_name': rule['model'], 'source_url': r.get('source_url'),
                'reason': 'Bản ghi thiếu chứng cứ model/SKU/màu hoặc giá không hợp lệ; không công bố'} for r in rows if not valid_row(r, rule)]
    counts = {'priced': sum(r.get('promo_price') is not None for r in good), 'status_only': sum(r.get('promo_price') is None for r in good),
              'needs_check': len(issues)}
    reasons = list(dict.fromkeys(str(i.get('reason')) for i in issues))[:3]
    if code == 3:
        update(job_id, slug, status='error', finished_at=finished, reason=f'Đang có worker {label} khác giữ khóa kênh; không chạy chồng', **counts)
        return None
    if code != 0 or not good:
        worker_state = next((m for m in load(out / folder / 'summary.json', {}).get('models', []) if key(m.get('model')) == key(rule['model'])), {})
        why = ('Worker hết thời gian' if code == 'timeout' else f'Worker thoát mã {code}' if code != 0
               else 'Chưa có link của model ở kênh này (cần discovery hoặc thêm URL nhập tay)' if worker_state.get('status') == 'missing_catalog'
               else 'Không có SKU nào xác minh được đúng model/màu')
        if reasons:
            why += ': ' + ' | '.join(reasons)
        with __import__('contextlib').nullcontext():
            kept, at = mark_stale(folder, rule, finished, why, job_id)
        warning = f'Giữ {kept} bản ghi cũ (mới nhất lúc {at}) — dữ liệu cũ, chưa cập nhật được' if kept else 'Chưa có dữ liệu cũ để giữ'
        update(job_id, slug, status='error', finished_at=finished, reason=why, stale_warning=warning, **counts)
        return None
    current, _ = jobs.rule_fingerprint(rule['model'])
    if current != fingerprint:
        update(job_id, slug, status='error', finished_at=finished, **counts,
               reason='Cấu hình model/màu/URL hoặc quy tắc nhận diện đã đổi trong lúc chạy; không công bố kết quả theo cấu hình cũ')
        return None
    with __import__('contextlib').nullcontext():
        if jobs.rule_fingerprint(rule['model'])[0] != fingerprint:
            update(job_id, slug, status='error', finished_at=finished, reason='Cấu hình đổi ngay trước khi công bố; không công bố', **counts)
            return None
        kept = publish(slug, folder, rule, good, issues, job_id, finished)
    partial = bool(issues or kept or rejected)
    update(job_id, slug, status='partial' if partial else 'success', finished_at=finished, published=True, kept_stale=kept, **counts,
           reason=(' | '.join(reasons) if reasons else '') + (f' · Giữ {kept} SKU cũ không đọc lại được (đánh dấu dữ liệu cũ)' if kept else ''))
    return slug


def main(job_id):
    state = jobs.read_state(job_id)
    folder = jobs.job_dir(job_id)
    update(job_id, status='running', runner_pid=os.getpid(), started_at=jobs.now())
    fingerprint, rule = jobs.rule_fingerprint(state['model'])
    if rule is None or fingerprint != state['fingerprint']:
        for slug in state['channels']:
            update(job_id, slug, status='error', finished_at=jobs.now(), reason='Cấu hình đã đổi từ lúc tạo job; tạo lại job')
        update(job_id, status='error', finished_at=jobs.now(), error='Cấu hình đã đổi từ lúc tạo job')
        return 1
    (folder / 'apple_colors.json').write_text(json.dumps({'version': 1, 'products': [rule]}, ensure_ascii=False, indent=1), encoding='utf-8')
    published = []
    threads = [threading.Thread(target=lambda s=s: published.append(run_channel(job_id, s, rule, fingerprint, folder / 'out')))
               for s in state['channels']]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    published = [p for p in published if p]
    rebuild_error = None
    for slug in ([] if jobs.ISOLATED else published):  # cô lập: không dựng lại dashboard thật
        result = subprocess.run([sys.executable, 'tools/build_mw_review.py', '--chain', slug], cwd=ROOT, capture_output=True, text=True, timeout=300)
        if result.returncode:
            rebuild_error = f'Chưa dựng lại được dashboard kênh {slug}'
    statuses = [c['status'] for c in jobs.read_state(job_id)['channels'].values()]
    overall = 'success' if all(s == 'success' for s in statuses) else 'error' if all(s == 'error' for s in statuses) else 'partial'
    update(job_id, status=overall, finished_at=jobs.now(), dashboard_rebuilt=bool(published) and not jobs.ISOLATED and not rebuild_error, error=rebuild_error)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
