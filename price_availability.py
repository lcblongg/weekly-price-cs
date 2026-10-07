"""Giá hiển thị và khả năng đặt mua là hai thông tin độc lập.
Lưu ghi chú qua promo_text hiện có để lịch sử/Supabase/Excel không mất trạng thái tồn kho.
"""
def annotate(notes, message=None):
    if message:
        return '[Tình trạng] ' + message + ('\n' + notes if notes else '')
    return notes


def explicit_status(data):
    """Chỉ lấy nhãn trạng thái từ trường riêng của website, không tìm trong CTKM/tên model.
    Không suy diễn ‘ngừng kinh doanh’ từ tồn kho 0 hoặc boolean thiếu.
    """
    if not isinstance(data,dict):return None
    for key in ('statusOnWeb','statusText','statusName','stockStatusName','sellingStatusName'):
        text=data.get(key)
        coded={'ngung_kinh_doanh':'Ngừng kinh doanh','het_hang':'Hết hàng','tam_het_hang':'Tạm hết hàng','dat_truoc':'Đặt trước'}
        if isinstance(text,str) and text.casefold() in coded:return coded[text.casefold()]
        if isinstance(text,str) and any(word in text.casefold() for word in ('hết hàng','ngừng kinh doanh','ngừng bán','tạm hết','đặt trước','liên hệ')):
            return ' '.join(text.split())
    return None
