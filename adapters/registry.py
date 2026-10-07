"""Bảng adapter theo đại lý. Mỗi adapter có `listing(source, http, browser)` và
`read_product(item, http, browser)`; có thể có `read_many` (đọc hàng loạt) và `variants` (mở rộng màu)."""
from adapters import tgdd, cellphones, fptshop, phongvu, viettel_store

ADAPTERS = {'TGDD': tgdd, 'CellphoneS': cellphones, 'FPT Shop': fptshop,
            'Phong Vũ': phongvu, 'Viettel Store': viettel_store}
