"""Tổng hợp kết quả 5 worker discovery: kênh nào đã công bố catalog mới, kênh nào lỗi (giữ catalog cũ)."""
import argparse
import json
import logging
import os
from pathlib import Path

from chains import CHAINS
from common import PipelineError
from telegram_reporter import esc, pack, send

LOG = logging.getLogger('discovery-status')


def collect(directory, expected=None):
    found = {}
    for path in sorted(Path(directory).rglob('summary.json')):
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('stage') == 'discovery' and data.get('chain_name') in CHAINS.values():
            if data['chain_name'] in found:
                raise PipelineError(f'Hai summary discovery cho {data["chain_name"]}')
            found[data['chain_name']] = data
    states = {}
    for name in CHAINS.values():
        if name in found:
            states[name] = found[name]
        elif expected is not None and name not in expected:
            states[name] = {'chain_name': name, 'status': 'skipped', 'published': False}
        else:
            states[name] = {'chain_name': name, 'status': 'missing', 'published': False,
                            'message': 'Worker không ghi summary — catalog thành công trước đó vẫn được dùng'}
    return states


def lines(states):
    out = []
    for name, s in states.items():
        if s.get('status') == 'skipped':
            out.append(f'{name}: không chạy trong lượt này (catalog hiện có giữ nguyên)')
            continue
        if s.get('status') == 'ok':
            state = 'đã công bố catalog mới' if s.get('published') else 'chạy thử OK (chưa công bố)'
        else:
            state = 'LỖI — giữ catalog thành công trước đó'
        detail = (f"{s.get('sources_ok', 0)}/{s.get('sources', '?')} nguồn OK, {s.get('links', 0)} link, "
                  f"{s.get('ready', 0)} ready, {s.get('review', 0)} cần xem") if 'links' in s else ''
        out.append(f'{name}: {state}' + (f' · {detail}' if detail else '') + (f' · {s["message"]}' if s.get('message') and s.get('status') != 'ok' else ''))
        for failed in s.get('failed_sources', [])[:5]:
            out.append(f'   - {failed["category"]}/{failed["brand"]}: {failed["error"]}')
    return out


def main(args):
    from chains import resolve
    states = collect(args.summaries, None if args.chains == 'all' else resolve([args.chains]))
    text = lines(states)
    print('\n'.join(text))
    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_file:
        with open(summary_file, 'a', encoding='utf-8') as handle:
            handle.write('## Discovery theo kênh\n\n' + '\n'.join('- ' + t if not t.startswith('   ') else '  ' + t.strip() for t in text) + '\n')
    if args.send:
        send(pack(['<b>🔎 Discovery Chủ nhật — catalog theo kênh</b>'] + [esc(t, 600) for t in text]))
    return 0 if all(s.get('status') in ('ok', 'skipped') for s in states.values()) else 1


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
    parser = argparse.ArgumentParser()
    parser.add_argument('--summaries', required=True)
    parser.add_argument('--send', action='store_true', help='Gửi trạng thái vào Telegram')
    parser.add_argument('--chains', default='all')
    raise SystemExit(main(parser.parse_args()))
