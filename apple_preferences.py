"""Danh sách Apple do người dùng quản lý. Chỉ lọc hiển thị; không xóa catalog/giá nguồn.
Màu chỉ khớp nguyên tên hoặc alias đã cấu hình theo model, không suy đoán từ ‘đen/xanh’.
"""
import json,re,unicodedata
from pathlib import Path
from identity import storage_of
from apple_rules import COLORS as DEFAULT
def key(value):return ' '.join(unicodedata.normalize('NFC',str(value or '')).casefold().split())
def load(path=DEFAULT):
    config=json.loads(Path(path).read_text());seen=set()
    if config.get('version')!=1 or not isinstance(config.get('products'),list):raise ValueError('Cấu hình Apple không hợp lệ')
    for row in config['products']:
        if not isinstance(row.get('model'),str) or not row['model'].strip() or key(row['model']) in seen:raise ValueError('Model thiếu/trùng')
        if row.get('color') is not None and not isinstance(row['color'],str):raise ValueError('Màu không hợp lệ')
        if not isinstance(row.get('aliases',[]),list) or any(not isinstance(a,str) or not a.strip() for a in row.get('aliases',[])):raise ValueError('Alias màu không hợp lệ')
        seen.add(key(row['model']))
    return config

def model_of(name):
    """Nhận cả model có và chưa có trong danh sách; giữ Pro/Max/chip/ANC riêng."""
    from product_standard import canonical_model
    canonical=canonical_model(name)
    if canonical:return canonical
    text=key(name)
    m=re.search(r'\biphone\s+(\d{1,2}e?|air|duo)(?:\s+(pro\s+max|pro|plus|mini))?\b',text)
    if m:return 'iPhone '+({'air':'Air','duo':'Duo'}.get(m[1],m[1]))+(' '+m[2].title() if m[2] else '')
    m=re.search(r'\bipad\s+(air|pro)\b',text)
    if m:
        size=re.search(r'\b(11|13)\s*(?:inch)?\b',text);chip=re.search(r'\b(m\d+)(?:\s+(pro|max))?\b',text)
        if size and chip:return 'iPad '+m[1].title()+' '+chip[0].upper()+' '+size[1]
        return None
    if re.search(r'\bipad\s+mini\b',text):
        if re.search(r'\bmini\s+7\b',text):return 'iPad Mini 7'
        return None
    if re.search(r'\bipad\b',text) and re.search(r'\ba16\b',text):return 'iPad A16'
    if re.search(r'\bmacbook\s+neo\b',text):return 'MacBook Neo'
    m=re.search(r'\bmacbook\s+(air|pro)\b',text)
    if m:
        size=re.search(r'\b(13|14|15|16)\s*(?:inch)?\b',text);chip=re.search(r'\b(m\d+)(?:\s+(pro|max))?\b',text)
        if size and chip:return 'MacBook '+m[1].title()+' '+size[1]+' '+chip[1].upper()+(' '+chip[2].title() if chip[2] else '')
        return None
    if re.search(r'\bmac\s*mini\b',text):return 'Mac Mini'
    if re.search(r'\bimac\b',text):return 'iMac'
    m=re.search(r'\bapple\s+watch\s+(?:series\s*|s)(\d+)\b',text)
    if m:return 'Apple Watch S'+m[1]
    m=re.search(r'\bapple\s+watch\s+(se|ultra)\s*(\d+)\b',text)
    if m:return 'Apple Watch '+('SE' if m[1]=='se' else 'Ultra')+' '+m[2]
    m=re.search(r'\bairpods\s+(pro\s*\d+|max(?:\s*\d+)?|\d+)\b',text)
    if m:
        model='AirPods '+re.sub(r'(pro|max)(\d)',r'\1 \2',m[1]).title()
        if model=='AirPods 4' and re.search(r'\banc\b|chống ồn',text):return 'AirPods 4 with ANC'
        if model=='AirPods 5' and re.search(r'sạc (?:không|ko) dây|wireless charging',text):return 'AirPods 5 sạc ko dây'
        return model
    return None

def presentation(row,config):
    name=row.get('source_product_name') or row.get('product_name') or row.get('discovered_name') or ''
    apple=key(row.get('brand'))=='apple' or bool(re.search(r'\b(?:iphone|ipad|macbook|imac|mac mini|apple watch|airpods)\b',key(name)))
    if not apple:return dict(row,display_name=re.sub(r'^(?:Điện thoại|Máy tính bảng|Máy tính xách tay|Laptop|Đồng hồ thông minh)\s+','',(row.get('product_name') or name).split(' · ')[0],flags=re.I),source_color=row.get('color') or (row.get('product_name','').split(' · ',1)[1] if ' · ' in row.get('product_name','') else ''),apple_selection='other')
    model=model_of(name);rule=next((p for p in config['products'] if key(p['model'])==key(model)),None) if model else None
    color=row.get('color') or (row.get('product_name','').split(' · ',1)[1] if ' · ' in row.get('product_name','') else '')
    storage=row.get('storage') or storage_of(name)
    display=model or re.sub(r'^(?:Điện thoại|Máy tính bảng|Laptop|Tai nghe Bluetooth|Đồng hồ thông minh)\s+','',name,flags=re.I)
    if model and storage:display+=' '+storage
    variant=[]
    if re.search(r'\bipad\b',key(name+' '+str(row.get('source_parent_name') or ''))):
        if re.search(r'\b(?:5g|cellular)\b',key(name+' '+str(row.get('source_parent_name') or ''))):variant.append('5G / Cellular')
        elif re.search(r'\bwi[ -]?fi\b',key(name+' '+str(row.get('source_parent_name') or ''))):variant.append('WiFi')
    if re.search(r'\bapple\s+watch\b',key(name+' '+str(row.get('source_parent_name') or ''))):
        size=re.search(r'\b(\d{2})\s*mm\b',key(name+' '+str(row.get('source_parent_name') or '')))
        if size:variant.append(size[1]+'mm')
        if re.search(r'\b(?:lte|cellular)\b',key(name+' '+str(row.get('source_parent_name') or ''))):variant.append('LTE / Cellular')
        elif re.search(r'\bgps\b',key(name+' '+str(row.get('source_parent_name') or ''))):variant.append('GPS')
    if re.search(r'\bmacbook\b',key(name+' '+str(row.get('source_parent_name') or ''))):
        ram=re.search(r'\b(\d{1,2})\s*gb\s*/',key(name+' '+str(row.get('source_parent_name') or '')))
        if ram:variant.append('RAM '+ram[1]+'GB')
        charger=re.search(r'\b(\d{2,3})\s*w\b',key(name+' '+str(row.get('source_parent_name') or '')))
        if charger:variant.append(charger[1]+'W')
    # Các đặc tính còn lại vẫn ở tên nguồn/SKU; không gộp dòng sau khi rút gọn tên.
    if not rule:state='unconfigured'
    elif not rule['color']:state='selected'
    elif not color:state='unknown_color'
    elif key(color) in {key(rule['color']),*(key(a) for a in rule.get('aliases',[]))}:state='selected'
    else:state='other_color'
    if rule and rule['color'] and row.get('chain_name') in ('TGDD','CellphoneS','FPT Shop','Viettel Store','Phong Vũ') and 'promo_price' in row:
        proof=row.get('color_evidence') or {}
        names={model,*(rule.get('previous_names') or [])}  # đổi nhãn quy tắc viết tay: bằng chứng theo tên cũ vẫn hợp lệ
        if not (proof.get('model') in names and key(proof.get('canonical_color'))==key(rule['color']) and str(proof.get('product_code'))==str(row.get('variant_id')) and proof.get('website_color_id') is not None and proof.get('verified_at')):
            state='needs_verified_color'
    return dict(row,display_name=display,display_variant=' · '.join(variant),apple_model=model,source_color=color,selected_color=rule['color'] if rule else None,apple_selection=state)
