"""Đọc robots.txt theo quy tắc Google/RFC 9309: hỗ trợ `*`, `$`, nhóm nhiều User-agent,
quy tắc dài nhất thắng và Allow thắng khi dài bằng nhau.
`urllib.robotparser` của Python chỉ so tiền tố, nên `Disallow: /*?*` bị bỏ qua — không dùng nó nữa.
"""
import re
from urllib.parse import urlsplit

AGENT = 'weeklypricecs'


def parse(text):
    """Trả về danh sách nhóm: {'agents': set, 'rules': [(allow, pattern)], 'delay': float|None}."""
    groups, current, last_was_agent = [], None, False
    for raw in text.splitlines():
        line = raw.split('#', 1)[0].strip()
        if ':' not in line:
            continue
        key, value = (part.strip() for part in line.split(':', 1))
        key = key.lower()
        if key == 'user-agent':
            if current is None or not last_was_agent:
                current = {'agents': set(), 'rules': [], 'delay': None}
                groups.append(current)
            current['agents'].add(value.lower())
            last_was_agent = True
            continue
        last_was_agent = False
        if current is None:
            continue
        if key in ('allow', 'disallow') and value:
            current['rules'].append((key == 'allow', value))
        elif key == 'crawl-delay':
            try:
                current['delay'] = float(value)
            except ValueError:
                pass
    return groups


def _group(groups, agent=AGENT):
    named = [g for g in groups if any(a != '*' and a in agent for a in g['agents'])]
    if named:
        return named
    return [g for g in groups if '*' in g['agents']]


def _regex(pattern):
    anchored = pattern.endswith('$')
    body = re.escape(pattern[:-1] if anchored else pattern).replace(r'\*', '.*')
    return re.compile('^' + body + ('$' if anchored else ''))


def allowed(groups, url, agent=AGENT):
    parts = urlsplit(url)
    target = (parts.path or '/') + ('?' + parts.query if parts.query else '')
    best = None
    for group in _group(groups, agent):
        for allow, pattern in group['rules']:
            if _regex(pattern).match(target):
                rank = (len(pattern), allow)
                if best is None or rank > best:
                    best = rank
    return True if best is None else best[1]


def crawl_delay(groups, agent=AGENT):
    delays = [g['delay'] for g in _group(groups, agent) if g['delay'] is not None]
    return max(delays) if delays else None
