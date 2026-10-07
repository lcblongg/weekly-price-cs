"""Dựng 7 cột T2–CN; thiếu ngày giữ None, không điền giá hôm trước."""
from datetime import date,timedelta
from common import PipelineError

def weekly_grid(rows, week_start):
    start=date.fromisoformat(week_start)
    if start.weekday()!=0: raise PipelineError('Tuần phải bắt đầu vào thứ Hai')
    days=[(start+timedelta(days=i)).isoformat() for i in range(7)]
    groups={}
    for row in rows:
        day=row['business_date']
        if day not in days: continue
        group=groups.setdefault((row['chain_name'],row['sku']),
            {'chain_name':row['chain_name'],'sku':row['sku'],'product_name':row['product_name'],'days':{d:None for d in days}})
        old=group['days'][day]
        # Nếu chạy lại trong ngày, hiển thị snapshot mới nhất nhưng DB vẫn giữ cả hai.
        if old is None or row['captured_at']>old['captured_at']:
            group['days'][day]=row
    return {'dates':days,'products':list(groups.values()),
            'missing_dates':[d for d in days if not any(g['days'][d] for g in groups.values())]}
