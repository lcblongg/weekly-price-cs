"""Hợp nhất lịch sử theo ngày cào thực tế, không sao chép giá cũ thành giá hôm nay."""
from datetime import datetime
from zoneinfo import ZoneInfo
TZ=ZoneInfo('Asia/Ho_Chi_Minh')
def observation_key(row):
    day=datetime.fromisoformat(row['observed_at']).astimezone(TZ).date().isoformat()
    return row['chain'],row['sku'],day

def merge_history(previous,current):
    result={observation_key(row):row for row in previous}
    for row in current:
        key=observation_key(row);old=result.get(key)
        if old is None or datetime.fromisoformat(row['observed_at'])>=datetime.fromisoformat(old['observed_at']):
            result[key]=row
    return list(result.values())
