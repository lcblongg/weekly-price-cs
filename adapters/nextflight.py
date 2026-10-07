"""Đọc dữ liệu server-render của Next.js App Router (self.__next_f) như JSON thuần.
Chỉ giải mã chuỗi JSON; không thực thi JavaScript của nguồn.
"""
import json
import re

from common import PipelineError

PUSH = re.compile(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)')


def flight(markup):
    parts = PUSH.findall(markup)
    if not parts:
        raise PipelineError('Trang không có dữ liệu server-render dạng Next.js')
    try:
        return ''.join(json.loads('"' + part + '"') for part in parts)
    except ValueError:
        raise PipelineError('Dữ liệu server-render không hợp lệ') from None


def balanced(text, start):
    """Cắt đúng một object/array JSON bắt đầu tại `start` (tôn trọng chuỗi và escape)."""
    if start < 0 or start >= len(text) or text[start] not in '[{':
        raise PipelineError('Không tìm thấy khối JSON mong đợi')
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in '[{':
            depth += 1
        elif char in ']}':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise PipelineError('Khối JSON bị cắt dở')


def object_after(text, marker, occurrence=None):
    """JSON ngay sau `marker` (ví dụ '"initialState":'). Nhiều lần xuất hiện → phải chỉ định rõ."""
    positions = [m.end() for m in re.finditer(re.escape(marker), text)]
    if not positions:
        raise PipelineError(f'Thiếu khối dữ liệu {marker}')
    if occurrence is None and len(positions) != 1:
        raise PipelineError(f'Khối dữ liệu {marker} không duy nhất')
    position = positions[occurrence or 0]
    while position < len(text) and text[position] in ' \t':
        position += 1
    try:
        return json.loads(balanced(text, position))
    except ValueError:
        raise PipelineError(f'Khối dữ liệu {marker} không phải JSON') from None
