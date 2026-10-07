"""Đếm dữ liệu thực tế đang công bố, không biến lịch sử thành giá mới hôm nay."""
from datetime import datetime
from common import TZ


def dashboard_metrics(rows, today):
    # Một SKU/kênh chỉ tính bản ghi cuối; bản chỉ trạng thái vẫn thay giá số cũ.
    latest = {}
    for row in rows:
        observed = datetime.fromisoformat(row['observed_at'].replace('Z', '+00:00'))
        key = (row['slug'], row['sku'])
        if key not in latest or observed > latest[key][0]:
            latest[key] = (observed, row)
    current = [row for _, row in latest.values()]
    fresh = [row for stamp, row in latest.values()
             if stamp.astimezone(TZ).date().isoformat() == today and not row.get('stale_since')]
    return {
        'history_rows': len(rows),
        'latest_skus': len(current),
        'latest_models': len({row['apple_model'] for row in current}),
        'today_verified_skus': len(fresh),
        'today_numeric': sum(row.get('promo_price') is not None for row in fresh),
        'today_status_only': sum(row.get('promo_price') is None for row in fresh),
        'not_verified_today': len(current) - len(fresh),
        'explicitly_stale': sum(bool(row.get('stale_since')) for row in current),
        'models_without_today_data': sorted(
            {row['apple_model'] for row in current} - {row['apple_model'] for row in fresh}),
    }
