"""Hàm dùng chung; không ghi secret hoặc URL chứa token vào log."""
import os
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

TZ = ZoneInfo('Asia/Ho_Chi_Minh')


class PipelineError(ValueError):
    """Lỗi nghiệp vụ với thông báo an toàn để hiển thị, không chứa secret."""
    pass


def required(name):
    value = os.environ.get(name, '').strip()
    if not value:
        raise PipelineError(f'Thiếu biến môi trường {name}')
    return value


def database():
    from supabase import create_client
    return create_client(required('SUPABASE_URL'), required('SUPABASE_SERVICE_ROLE_KEY'))


def weeks(now=None):
    now = now or datetime.now(TZ)
    current, previous = now.isocalendar(), (now - timedelta(days=7)).isocalendar()
    return (current.year, current.week), (previous.year, previous.week)


def https_url(value):
    parsed = urlparse(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise PipelineError('URL phải dùng HTTPS và không chứa thông tin đăng nhập')
    return value


def vnd(text):
    """Chỉ nhận một số tiền VND rõ ràng; không ghép nhiều mức giá thành một số."""
    value = re.sub(r'(?i)(vnd|vnđ|đ|₫)', '', text).strip().replace('\u00a0', '')
    if not re.fullmatch(r'(?:[1-9]\d*|[1-9]\d{0,2}(?:[., ]\d{3})+)', value):
        raise PipelineError('Giá không phải một số tiền VND duy nhất')
    amount = int(re.sub(r'[., ]', '', value))
    if not 10_000 <= amount <= 500_000_000:
        raise PipelineError('Giá ngoài khoảng hợp lý 10.000–500.000.000 VND')
    return amount
