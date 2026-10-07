"""Chính sách truy cập chung cho mọi adapter: tự xưng danh, tôn trọng robots.txt/Crawl-delay,
giãn cách theo host. Không đổi IP, không giả mạo trình duyệt, không vượt CAPTCHA.
"""
import asyncio
import time
from urllib.parse import urlsplit

import httpx

import robots
from common import PipelineError

USER_AGENT = 'Mozilla/5.0 (compatible; WeeklyPriceCS/1.0; internal price monitoring)'
DEFAULT_GAP = 2.0          # giây giữa hai request tới cùng host khi robots không khai báo
_rules, _last, _locks = {}, {}, {}


def client(timeout=30):
    return httpx.AsyncClient(timeout=timeout, follow_redirects=True,
                             headers={'User-Agent': USER_AGENT, 'Accept-Language': 'vi-VN,vi;q=0.9'})


async def _load(http, origin):
    if origin in _rules:
        return _rules[origin]
    response = await http.get(origin + '/robots.txt')
    if response.status_code == 404:
        groups = []
    elif response.status_code == 200:
        groups = robots.parse(response.text)
    else:
        # 401/403/5xx: không biết nguồn cho phép gì → dừng thay vì đoán.
        raise PipelineError(f'Không đọc được robots.txt của {urlsplit(origin).hostname} (HTTP {response.status_code})')
    _rules[origin] = groups
    return groups


async def ensure_allowed(http, url, label=''):
    parts = urlsplit(url)
    groups = await _load(http, f'{parts.scheme}://{parts.netloc}')
    if not robots.allowed(groups, url):
        raise PipelineError(f'robots.txt không cho truy cập {label or parts.hostname}: {parts.path}')
    return groups


async def wait_turn(http, url):
    """Giãn cách tuần tự theo host; Crawl-delay của nguồn được ưu tiên nếu lớn hơn."""
    parts = urlsplit(url)
    origin = f'{parts.scheme}://{parts.netloc}'
    groups = await _load(http, origin)
    gap = max(DEFAULT_GAP, robots.crawl_delay(groups) or 0)
    lock = _locks.setdefault(origin, asyncio.Lock())
    async with lock:
        delay = _last.get(origin, 0) + gap - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        _last[origin] = time.monotonic()


async def fetch(http, method, url, *, label='', max_bytes=8_000_000, retries=2, **kwargs):
    """Request chỉ đọc có robots + giãn cách + retry giới hạn cho lỗi tạm thời."""
    await ensure_allowed(http, url, label)
    for attempt in range(retries + 1):
        await wait_turn(http, url)
        try:
            response = await http.request(method, url, **kwargs)
        except httpx.TransportError:
            if attempt == retries:
                raise PipelineError(f'{label}: lỗi mạng khi đọc nguồn') from None
            await asyncio.sleep(3 * (attempt + 1))
            continue
        if response.status_code in (429, 502, 503, 504) and attempt < retries:
            await asyncio.sleep(5 * (attempt + 1))
            continue
        if response.status_code in (401, 403):
            # Không thử né chặn (đổi IP/giả trình duyệt): báo rõ và để người vận hành xử lý với nguồn.
            raise PipelineError(f'{label}: HTTP {response.status_code} — bị chặn truy cập, không lưu giá')
        if response.status_code != 200:
            raise PipelineError(f'{label}: HTTP {response.status_code}')
        if len(response.content) > max_bytes:
            raise PipelineError(f'{label}: phản hồi vượt giới hạn an toàn')
        return response
    raise PipelineError(f'{label}: nguồn không phản hồi')


def reset():
    """Dùng trong test."""
    _rules.clear(); _last.clear(); _locks.clear()
