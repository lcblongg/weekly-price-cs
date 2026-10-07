"""Báo cáo theo từng chuỗi + SKU, so với đúng tuần ISO liền trước."""
import argparse
import html
import json
import logging
import re
import time
from pathlib import Path

import httpx
from common import PipelineError, database, required, weeks, https_url
from business_calendar import fiscal_period
from telegram_watchlist import filter_report_rows

LOG = logging.getLogger('reporter')
HOT = re.compile(r'vnpay|thu cũ|đổi mới|quà|tặng|voucher|hoàn tiền|giảm thêm', re.I)


def money(value):
    return f'{value:,}'.replace(',', '.') + 'đ'


def esc(value, limit=180):
    # Ngân sách sau escape: chuỗi nhiều '&' không làm một block vượt giới hạn.
    parts, size = [], 0
    for character in str(value):
        encoded = html.escape(character, quote=True)
        width = len(encoded.encode('utf-16-le')) // 2
        if size + width > limit:
            parts.append('…')
            break
        parts.append(encoded)
        size += width
    return ''.join(parts)


def normalized(value):
    return ' '.join(value.casefold().split())


def load_week(db, year, week, run_id=None):
    query = db.table('scrape_runs').select('*').eq('year', year).eq('week_number', week)
    if run_id:
        query = query.eq('id', run_id)
    runs = query.order('completed_at', desc=True).limit(1).execute().data
    if not runs:
        if run_id:
            raise PipelineError('Run ID không tồn tại trong tuần yêu cầu')
        return []
    run = runs[0]
    rows, offset = [], 0
    # Phân trang dưới giới hạn mặc định 1.000 dòng của Supabase.
    while True:
        batch = (db.table('daily_prices').select('*').eq('run_id', run['id'])
                 .order('id').range(offset, offset + 499).execute().data)
        rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    if len(rows) != run['product_count']:
        raise PipelineError('Snapshot đã bị thay thế hoặc thiếu dòng; chạy lại scraper')
    return rows


def analyze(current, previous):
    old = {(r['chain_name'], r['sku']): r for r in previous}
    drops, promotions = [], []
    unmatched = 0
    for row in current:
        before = old.get((row['chain_name'], row['sku']))
        if not before:
            unmatched += 1
            continue  # Sản phẩm mới không được tính là giảm giá/CTKM mới.
        text = row['promo_text']
        if text and normalized(text) != normalized(before['promo_text']) and HOT.search(text):
            promotions.append(row)
        if row.get('promo_price') is None or before.get('promo_price') is None:
            continue  # Trạng thái không có giá không phải giảm xuống 0.
        delta = before['promo_price'] - row['promo_price']
        # OR và dấu > đúng yêu cầu. So sánh số nguyên để không sai số ở 3%.
        if delta > 0 and (delta * 100 > before['promo_price'] * 3 or delta > 500_000):
            drops.append((row, before['promo_price'], delta, delta * 100 / before['promo_price']))
    drops.sort(key=lambda x: (-x[3], -x[2], x[0]['chain_name'], x[0]['sku']))
    promotions.sort(key=lambda x: (x['chain_name'], x['sku']))
    return drops, promotions, unmatched


def utf16_size(text):
    # Đếm cả markup bảo thủ; emoji có thể chiếm 2 UTF-16 code units.
    return len(text.encode('utf-16-le')) // 2


def pack(blocks, limit=3800):
    """Chia tại ranh giới block; không bao giờ cắt giữa tag HTML/entity."""
    chunks, chunk = [], ''
    for block in blocks:
        if utf16_size(block) > limit:
            raise PipelineError('Một block báo cáo quá dài')
        combined = chunk + ('\n\n' if chunk else '') + block
        if utf16_size(combined) > limit:
            chunks.append(chunk)
            chunk = block
        else:
            chunk = combined
    if chunk:
        chunks.append(chunk)
    return chunks


def render(current, previous, period, web_url, catalog=None, fiscal=None, summary=None):
    drops, promos, unmatched = analyze(current, previous)
    year, week = period
    chains = ', '.join(sorted({r['chain_name'] for r in current}))
    title = fiscal['label'] if fiscal else f'Tuần {week:02d}/{year}'
    date_note = f"{fiscal['week_start']} → {fiscal['week_end']} | Thứ Hai–Chủ nhật\n" if fiscal else ''
    blocks = [f'<b>📊 WEEKLY PRICE CS — {esc(title)}</b>\n'
              + date_note
              + f'{len(current)} bản ghi giá/trạng thái | {esc(chains, 300)}\n'
              'So sánh giá bán trực tiếp, cùng đại lý và SKU; ưu đãi có điều kiện ghi riêng.']
    if catalog:
        blocks.append(f'🔎 Danh mục tự động: {catalog["ready"]}/{catalog["total"]} link đã khóa SKU; '
                      f'{catalog["review"]} link cần đọc lại/xác minh. Báo cáo dùng kết quả đọc hôm nay.')
    if summary:
        lines = [f'⚠️ <b>{summary["issues"]}/{summary["expected"]} link chưa đọc được dữ liệu hôm nay</b> '
                 '(lỗi đọc trang, thay đổi cấu trúc, cần kiểm tra) — xem lý do trên dashboard.']
        for chain, (total, ok) in sorted(summary.get('by_chain', {}).items()):
            lines.append(f'• {esc(chain)}: {ok}/{total} link có giá/trạng thái')
        if summary.get('degraded_chains'):
            lines.append('❗ Đại lý còn lỗi hoặc cần kiểm tra: ' + esc(', '.join(summary['degraded_chains'])) + ' — xem số link và nguyên nhân phía trên.')
        blocks.append('\n'.join(lines))
    if not previous:
        blocks.append('ℹ️ Chưa có dữ liệu tuần liền trước; đây là tuần tạo đường cơ sở.')
    elif unmatched:
        blocks.append(f'ℹ️ {unmatched} SKU/đại lý chưa có đối chiếu tuần trước, không tính biến động.')
    blocks.append(f'<b>🔥 Top biến động giá</b>\nCó {len(drops)} sản phẩm vượt ngưỡng &gt;3% hoặc &gt;500.000đ.')
    for index, (row, old, delta, percent) in enumerate(drops[:10], 1):
        blocks.append(f'<b>{index}. {esc(row["product_name"])}</b> — {esc(row["chain_name"])}\n'
                      f'{money(old)} → <b>{money(row["promo_price"])}</b>\n'
                      f'Giảm {money(delta)} ({percent:.2f}%)\n'
                      f'CTKM: {esc(row["promo_text"] or "Không có nội dung trong vùng CTKM", 500)}')
    if previous and not drops:
        blocks.append('Không có sản phẩm giảm giá vượt ngưỡng trong phạm vi theo dõi.')
    blocks.append(f'<b>🎁 CTKM mới/thay đổi cần xem</b>\n{len(promos)} nội dung khớp từ khóa; CS cần xác minh điều kiện áp dụng.')
    for row in promos[:10]:
        blocks.append(f'<b>{esc(row["chain_name"])}</b> | {esc(row["product_name"])}\n{esc(row["promo_text"], 700)}')
    statuses=[r for r in current if r.get('promo_text','').startswith('[Tình trạng] ')]
    if statuses:
        blocks.append(f'<b>📌 Trạng thái sản phẩm đã ghi nhận</b>\n{len(statuses)} sản phẩm có trạng thái riêng; không phải lỗi cào.')
        for row in statuses[:10]:
            shown=money(row['promo_price']) if row.get('promo_price') is not None else 'Không hiện giá'
            blocks.append(f"{esc(row['chain_name'])} | {esc(row['product_name'])} — {shown}\n{esc(row['promo_text'].split(chr(10))[0],300)}")
    blocks.append(f'<a href="{html.escape(https_url(web_url), quote=True)}">🌐 Mở Dashboard Weekly Price CS</a>\n'
                  'Báo cáo giới hạn top 10 mỗi mục. Giá/quà có thể phụ thuộc khu vực, màu và thời điểm.')
    return pack(blocks)


def send(messages):
    token, chat_id = required('TELEGRAM_BOT_TOKEN'), required('TELEGRAM_CHAT_ID')
    # Không log URL này vì token nằm ngay trong đường dẫn Telegram.
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    with httpx.Client(timeout=httpx.Timeout(30, connect=10)) as client:
        for message in messages:
            for attempt in range(4):
                try:
                    response = client.post(url, json={
                        'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML',
                        'link_preview_options': {'is_disabled': True},
                    })
                except httpx.HTTPError:
                    # Không tự retry lỗi mạng: Telegram có thể đã nhận, tránh nhân đôi tin.
                    raise RuntimeError('Telegram mất kết nối; kiểm tra nhóm trước khi gửi lại') from None
                try:
                    data = response.json()
                except ValueError:
                    raise RuntimeError('Telegram trả phản hồi không hợp lệ') from None
                if response.status_code == 429:
                    retry_after = int(data.get('parameters', {}).get('retry_after', 5))
                    if attempt == 3 or not 0 < retry_after <= 60:
                        raise RuntimeError('Telegram giới hạn tốc độ; chạy lại sau')
                    time.sleep(retry_after)
                    continue
                if response.status_code >= 500:
                    # Trạng thái gửi không chắc chắn; không retry mù.
                    raise RuntimeError('Telegram lỗi máy chủ; kiểm tra nhóm trước khi gửi lại')
                if response.status_code != 200 or data.get('ok') is not True:
                    raise RuntimeError(f'Telegram từ chối tin (HTTP {response.status_code}); kiểm tra bot/chat ID')
                break
            time.sleep(1)


STATUS = {'ok': '✅ Đủ', 'degraded': '⚠️ Suy giảm', 'failed': '❌ Lỗi', 'missing': '❌ Không có kết quả',
          'skipped': '⏭️ Không chạy trong lượt này'}


def collect_summaries(directory, expected=None):
    """summary.json của từng worker giá (mỗi kênh một thư mục). Kênh thiếu summary = worker hỏng trước khi ghi."""
    from chains import CHAINS
    found = {}
    for path in sorted(Path(directory).rglob('summary.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('stage') != 'prices' or data.get('chain_name') not in CHAINS.values():
            continue
        if data['chain_name'] in found:
            raise PipelineError(f'Hai summary cho cùng kênh {data["chain_name"]}; không tổng hợp mơ hồ')
        data['_dir'] = str(path.parent)
        found[data['chain_name']] = data
    states = {}
    for name in CHAINS.values():
        if name in found:
            states[name] = found[name]
        elif expected is not None and name not in expected:
            # Chạy lại thủ công một số kênh: kênh không chọn không bị coi là lỗi, dữ liệu cũ của nó giữ nguyên.
            states[name] = {'chain_name': name, 'status': 'skipped'}
        else:
            states[name] = {'chain_name': name, 'status': 'missing',
                            'message': 'Worker không ghi summary (lỗi trước khi chạy xong) — không coi là thành công'}
    return states


def status_block(states):
    lines = ['<b>🧭 Tình trạng 5 kênh</b>']
    for name, item in states.items():
        label = STATUS.get(item.get('status'), item.get('status'))
        if item.get('status') in ('ok','degraded') and (item.get('issues',0) or
                (item.get('prices') is not None and item.get('expected') is not None and item['prices']<item['expected'])):
            label = '⚠️ Còn mục cần kiểm tra'
        if item.get('prices') is not None and item.get('expected') is not None:
            detail = f"{item['prices']}/{item['expected']} link có giá/trạng thái"
            if item.get('blocked'):
                detail += f", {item['blocked']} bị chặn (403)"
        else:
            detail = ''
        message = item.get('message') if item.get('status') != 'ok' else ''
        lines.append(f'• {esc(name)}: {label}' + (f' — {detail}' if detail else '') + (f' — {esc(message, 160)}' if message else ''))
    return '\n'.join(lines)


def load_run_rows(db, run_id, expected):
    rows, offset = [], 0
    while True:
        batch = (db.table('daily_prices').select('*').eq('run_id', run_id)
                 .order('id').range(offset, offset + 499).execute().data)
        rows.extend(batch)
        if len(batch) < 500:
            break
        offset += 500
    if len(rows) != expected:
        raise PipelineError('Snapshot kênh thiếu dòng; không báo cáo trên dữ liệu dở dang')
    return rows


def previous_chain_rows(db, chain, year, week):
    runs = (db.table('scrape_runs').select('*').eq('chain_name', chain).eq('year', year).eq('week_number', week)
            .order('completed_at', desc=True).limit(1).execute().data)
    return load_run_rows(db, runs[0]['id'], runs[0]['product_count']) if runs else []


def daily_report(args):
    from chains import resolve
    expected = None if not args.chains or args.chains == 'all' else resolve([args.chains])
    states = collect_summaries(args.summaries, expected)
    current_week, previous_week = weeks()
    current, previous = [], []
    db = None if args.local else database()
    for name, item in states.items():
        if item.get('status') not in ('ok', 'degraded'):
            continue
        try:
            if args.local:
                loaded=json.loads((Path(item['_dir']) / 'prices.json').read_text(encoding='utf-8'))
            else:
                if not item.get('run_id') or (item.get('year'), item.get('week')) != current_week:
                    raise PipelineError('summary không có run_id của tuần hiện tại')
                loaded=load_run_rows(db,item['run_id'],item['prices'])
                previous += previous_chain_rows(db, name, *previous_week)
            # Cloud lưu đủ SKU nguồn; phạm vi báo cáo do runner xác minh theo quy chuẩn chung.
            # Không đọc watchlist cá nhân; local preview cũng áp dụng cùng phạm vi.
            if 'report_skus' in item:
                allowed=set(item['report_skus']);loaded=[r for r in loaded if r['sku'] in allowed]
            # File local có thể giữ SKU lỗi từ ngày cũ; không gọi chúng là kết quả mới.
            current += [r for r in loaded if not r.get('stale_since')]
        except PipelineError as exc:
            item.update(status='failed', message=f'Không đọc lại được dữ liệu đã lưu: {exc}')
    current, previous = filter_report_rows(current, previous, getattr(args, "watchlist", None))
    blocks_head = status_block(states)
    if not current:
        messages = pack([f'<b>📊 WEEKLY PRICE CS</b>', blocks_head, 'Không có giá trong phạm vi theo dõi nhóm hôm nay; xem trạng thái thu thập ở trên.'])
    else:
        totals = {'expected': sum(s.get('expected', 0) for s in states.values()),
                  'issues': sum(s.get('issues', 0) for s in states.values()),
                  'by_chain': {n: (s.get('expected', 0), s.get('prices', 0)) for n, s in states.items() if s.get('expected')},
                  'degraded_chains': [n for n, s in states.items() if s.get('status') != 'ok']}
        messages = render(current, previous, current_week, required('WEB_APP_URL') if not args.local else 'https://example.invalid',
                          None, fiscal_period(), totals)
        messages = pack([messages[0], blocks_head] + messages[1:])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'report.html').write_text('\n<hr>\n'.join(messages), encoding='utf-8')
    (out / 'report-status.json').write_text(json.dumps({n: {k: v for k, v in s.items() if not k.startswith('_')}
                                                         for n, s in states.items()}, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.dry_run or args.local:
        LOG.info('Đã tạo bản xem trước %s; chưa gửi Telegram', out / 'report.html')
    else:
        send(messages)
        LOG.info('Đã gửi %s phần báo cáo', len(messages))
    return states


def main(args):
    if args.summaries:
        return daily_report(args)
    manifest = json.loads(Path(args.run_file).read_text(encoding='utf-8'))
    current_week, previous_week = weeks()
    if (manifest['year'], manifest['week']) != current_week:
        raise PipelineError('Run file không thuộc tuần hiện tại')
    db = database()
    current = load_week(db, *current_week, run_id=manifest['run_id'])
    if not current:
        raise PipelineError('Không có snapshot để báo cáo')
    previous = load_week(db, *previous_week)
    current, previous = filter_report_rows(current, previous, getattr(args, 'watchlist', None))
    messages = render(current, previous, current_week, required('WEB_APP_URL'), manifest.get('catalog'),
                      manifest.get('fiscal_period') or fiscal_period(), manifest.get('summary'))
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/report.html').write_text('\n<hr>\n'.join(messages), encoding='utf-8')
    if not args.dry_run:
        send(messages)
        LOG.info('Đã gửi %s phần báo cáo', len(messages))
    else:
        LOG.info('Đã tạo bản xem trước; chưa gửi Telegram')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument('--watchlist', default='config/telegram-watchlist.json', help='Danh sách nhóm riêng; không đọc lựa chọn cá nhân Web')
    parser.add_argument('--summaries', help='Thư mục chứa kết quả các worker giá (mỗi kênh một summary.json)')
    parser.add_argument('--out', default='artifacts/report', help='Nơi ghi report.html/report-status.json')
    parser.add_argument('--local', action='store_true', help='Đọc prices.json cục bộ thay vì Supabase (chạy thử)')
    parser.add_argument('--chains', default='all', help='Kênh dự kiến trong lượt này (all hoặc tgdd,fpt,...)')
    parser.add_argument('--run-file', default='artifacts/run.json')
    parser.add_argument('--dry-run', action='store_true')
    try:
        main(parser.parse_args())
    except Exception as exc:
        LOG.error('Báo cáo thất bại: %s', str(exc) if isinstance(exc, PipelineError) else type(exc).__name__)
        raise SystemExit(1)
