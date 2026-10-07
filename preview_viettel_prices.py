"""Quét thử giá Viettel từ Excel; không ghi DB hoặc gửi Telegram khi CTKM chưa đủ."""
import argparse
import asyncio
import json
from html import escape
from datetime import datetime
from pathlib import Path
import httpx
from adapters.viettel import listing_links
from common import PipelineError, TZ
from import_sources import prepare

def render_preview(rows, captured_at, errors, notice=None):
    """HTML cục bộ để đối chiếu; mọi nội dung từ đại lý đều được escape."""
    def money(value):
        return f"{value:,} đ".replace(',', '.') if value is not None else 'Chưa xác định'
    notice = notice or 'Giá được đọc từ danh mục. Ghi chú khuyến mãi có thể bị rút gọn; chưa xác minh CTKM đầy đủ và biến thể màu trên trang chi tiết. Chưa gửi Telegram hoặc ghi dữ liệu chính thức.'
    body = ''.join(
        '<tr><td>'+escape(row['category'])+'</td><td><a target="_blank" rel="noopener noreferrer" href="'+escape(row['source_url'],quote=True)+'">'+escape(row['name'])+'</a></td><td>'+money(row['original_price'])+'</td><td>'+money(row['promo_price'])+'</td><td>'+escape(row['promo_text'] or 'Không thấy ghi chú trong danh mục')+'</td></tr>'
        for row in rows)
    return ("<!doctype html><html lang='vi'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Viettel — Kiểm tra dữ liệu</title>"
            "<style>body{font:15px system-ui;margin:24px;color:#162032;background:#f6f8fb}h1{font-size:25px}p{max-width:900px;line-height:1.6}.notice{padding:14px;background:#fff3cd;border-radius:10px}.table{overflow:auto;background:white;border-radius:10px}table{border-collapse:collapse;width:100%;min-width:850px}td,th{padding:12px;text-align:left;border-bottom:1px solid #e4e7ec}th{background:#eaf0f7}td:nth-child(3),td:nth-child(4){white-space:nowrap}a{color:#155cb0}input{padding:12px;margin:18px 0;width:min(90%,420px);border:1px solid #bcc5d1;border-radius:8px}</style>"
            '<h1>Viettel — Bản kiểm tra giá danh mục</h1><p>'+str(len(rows))+' sản phẩm · '+escape(captured_at)+'</p>'
            '<p class="notice">'+escape(notice)+' Nguồn lỗi: '+str(len(errors))+'.</p>'
            '<input id="search" placeholder="Tìm tên sản phẩm hoặc danh mục" aria-label="Tìm sản phẩm"><div class="table"><table><thead><tr><th>Danh mục</th><th>Sản phẩm</th><th>Giá gốc hiển thị</th><th>Giá bán hiển thị</th><th>Ghi chú danh mục</th></tr></thead><tbody>'+body+'</tbody></table></div>'
            "<script>document.getElementById('search').addEventListener('input',function(){const q=this.value.toLocaleLowerCase('vi');document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLocaleLowerCase('vi').includes(q));});</script></html>")

async def run(args):
    sources = prepare(args.input, 'config/retailer_adapters.json')
    rows, errors = {}, []
    captured_at = datetime.now(TZ).isoformat()
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        for source in sources:
            if source['chain_name'] != 'Viettel Store':
                continue
            try:
                quotes = await listing_links(source, client, quotes=True)
                for url, quote in quotes.items():
                    rows[url] = {**quote, 'chain_name':'Viettel Store',
                                 'category':source['category'], 'brand_name':source['brand'],
                                 'listing_url':source['seeds'][0], 'captured_at':captured_at,
                                 'status':'review', 'price_scope':'Giá hiển thị trên danh mục',
                                 'review_reason':'CTKM danh mục có thể bị rút gọn; chưa xác minh trang chi tiết'}
                print(f"{source['category']} / {source['brand']}: {len(quotes)} sản phẩm", flush=True)
            except Exception as exc:
                errors.append({'url':source['seeds'][0], 'error':str(exc) if isinstance(exc,PipelineError) else type(exc).__name__})
            await asyncio.sleep(2)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'captured_at':captured_at,'complete':not errors,
                                 'production_ready':False,'count':len(rows),
                                 'rows':list(rows.values()),'errors':errors},ensure_ascii=False,indent=2))
    output.with_suffix('.html').write_text(render_preview(list(rows.values()),captured_at,errors),encoding='utf-8')
    print(f'Đã lưu {len(rows)} sản phẩm vào {output}; chưa ghi Supabase hoặc gửi Telegram')
    if errors:
        raise PipelineError(f'{len(errors)} nguồn lỗi; xem errors trong file kết quả')

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default='inputs/data.xlsx')
    parser.add_argument('--output',default='artifacts/viettel-price-preview.json')
    try:
        asyncio.run(run(parser.parse_args()))
    except Exception as exc:
        print(str(exc) if isinstance(exc,PipelineError) else type(exc).__name__)
        raise SystemExit(1)
