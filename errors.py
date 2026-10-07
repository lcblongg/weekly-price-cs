"""Phân loại lỗi để log, summary và dashboard nêu rõ nguyên nhân (đặc biệt HTTP 403 = bị chặn)."""
import re

KINDS = [
    ('blocked', r'HTTP (401|403)\b|bị chặn|forbidden'),
    ('rate_limited', r'HTTP 429|giới hạn tốc độ'),
    ('robots', r'robots\.txt'),
    ('http_error', r'HTTP \d{3}'),
    ('network', r'lỗi mạng|không phản hồi|Timeout|TransportError'),
    ('out_of_stock', r'hết hàng|không bán|ngừng kinh doanh|không đặt mua'),
    ('preorder', r'đặt trước'),
    ('variant_changed', r'biến thể|SKU khác|màu đã khóa|khám phá lại|ERP'),
    ('incomplete_listing', r'thẻ|thiếu|max_candidates|phân trang|Xem thêm|tổng'),
    ('no_price_data', r'không có dữ liệu giá|giao diện cũ|chưa mở bán'),
    ('structure_changed', r'cấu trúc|contract|JSON|không tìm thấy khối|server-render'),
    ('out_of_scope', r'ngoài phạm vi'),
]
LABELS = {'blocked': 'Bị chặn truy cập (401/403)', 'rate_limited': 'Bị giới hạn tốc độ (429)',
          'robots': 'robots.txt không cho phép', 'http_error': 'Lỗi HTTP', 'network': 'Lỗi mạng/timeout',
          'out_of_stock': 'Hết hàng/ngừng bán', 'preorder': 'Đặt trước', 'variant_changed': 'Biến thể đổi',
          'incomplete_listing': 'Danh mục đọc thiếu', 'structure_changed': 'Trang đổi cấu trúc',
          'out_of_scope': 'Ngoài phạm vi', 'no_price_data': 'Trang chưa có giá (thường chưa mở bán)', 'technical': 'Lỗi kỹ thuật', 'other': 'Khác'}


def classify(message):
    text = str(message or '')
    if text.startswith('Lỗi kỹ thuật'):
        return 'technical'
    for kind, pattern in KINDS:
        if re.search(pattern, text, re.I):
            return kind
    return 'other'
