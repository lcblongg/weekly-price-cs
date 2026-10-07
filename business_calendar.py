"""Tuần nghiệp vụ luôn T2–CN, theo giờ Việt Nam; không suy đoán ranh giới quý FY."""
from datetime import datetime, timedelta
from common import TZ

def week_bounds(now=None):
    now = now or datetime.now(TZ)
    day = now.astimezone(TZ).date() if isinstance(now,datetime) else now
    monday = day - timedelta(days=day.weekday())
    return monday,monday+timedelta(days=6)

def completed_week(now=None):
    """Tuần gần nhất đã kết thúc; không gắn tuần thiếu ngày là tuần hoàn chỉnh."""
    monday,_=week_bounds(now)
    return monday-timedelta(days=7),monday-timedelta(days=1)

def fiscal_period(now=None):
    """Lịch 4 quý × 13 tuần, neo vào tuần đã được người dùng xác nhận."""
    import json
    from pathlib import Path
    config=json.loads((Path(__file__).parent/'config/fiscal_calendar.json').read_text())
    anchor=date_from_iso(config['anchor_week_start'])
    monday,sunday=week_bounds(now)
    offset=(monday-anchor).days//7
    year_offset,year_week=divmod(offset,52)
    quarter,quarter_week=divmod(year_week,13)
    fy=config['anchor_fiscal_year']+year_offset
    return {'week_start':monday.isoformat(),'week_end':sunday.isoformat(),
            'fiscal_year':fy,'quarter':quarter+1,'week':quarter_week+1,
            'label':f'W{quarter_week+1}Q{quarter+1}FY{fy:02d}'}

def date_from_iso(value):
    from datetime import date
    return date.fromisoformat(value)
