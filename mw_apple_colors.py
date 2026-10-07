"""Chọn mã biến thể màu từ chính PRODUCT_DETAIL của MW trước khi đọc giá.
Quy tắc tên màu được giới hạn theo model; không lấy biến thể mặc định thay thế.
"""
from urllib.parse import urljoin,urlsplit
from apple_preferences import key,model_of
from common import PipelineError
from apple_sources import WrongModel,ColorNotFound
# Tên thương mại Apple + tên trên MW đã đối chiếu palette của đúng dòng sản phẩm.
# Những tên khác không được đoán bằng substring hoặc màu RGB.
COLOR_LABELS={
 ('iPhone 15','Hồng'):['Hồng nhạt'],
 ('iPhone 15 Plus','Hồng'):['Hồng nhạt'],
 ('iPhone 17','Xanh Lá Xô Thôm'):['Xanh Lá Xô Thơm'],
 ('MacBook Air 13 M5','Xanh Da Trời'):['Xanh da trời nhạt'],
 ('MacBook Air 15 M5','Xanh Da Trời'):['Xanh da trời nhạt'],
 ('iPad Air M4 11','Xám Không Gian'):['Đen - Xám'],
 ('iPad Air M4 13','Xám Không Gian'):['Đen - Xám'],
 ('iPad Pro M5 11','Đen Không Gian'):['Đen'],
 ('iPad Pro M5 13','Đen Không Gian'):['Đen'],
 ('MacBook Pro 14 M5','Đen Không Gian'):['Đen'],
 ('MacBook Pro 16 M5 Pro','Đen Không Gian'):['Đen'],
 ('Apple Watch SE 3','Ánh Sao'):['Trắng Starlight'],
 ('Apple Watch Ultra 3','Đen'):['Titan đen'],
 ('iPad Mini 7','Xám'):['Đen - Xám'],
 ('AirPods Max','Đêm Xanh Thẳm'):['Xanh đen'],
 ('AirPods Max 2','Đêm Xanh Thẳm'):['Xanh đen'],
 ('MacBook Neo','Vàng Citrus'):['Vàng nhạt'],
}

def selected_variants(data,url,rule):
 if model_of(data.get('name',''))!=rule['model']:raise WrongModel('MW: model trên trang khác model yêu cầu; không dùng màu/giá của model khác')
 colors=[v for g in data.get('filter') or [] if g.get('label') in ('Màu','Màu sắc','Màu sắc master') for v in g.get('values') or []]
 target=rule['color']
 if target:
  accepted={key(target),*(key(a) for a in rule.get('aliases',[])),*(key(v) for v in next((labels for (model,color),labels in COLOR_LABELS.items() if key(model)==key(rule['model']) and key(color)==key(target)),[]))}
  matches=[c for c in colors if key(c.get('name')) in accepted]
  if len(matches)!=1:raise ColorNotFound('MW: chưa xác minh được một lựa chọn màu đúng yêu cầu '+target)
  chosen=matches[0];codes={str(c) for c in chosen.get('productCodes') or []}
  if not codes:raise PipelineError('MW: màu yêu cầu không có mã biến thể')
 else:
  chosen=None;codes={str(data.get('productCode') or '')}
 versions=[v for g in data.get('filter') or [] if g.get('label')=='Phiên bản' for v in g.get('values') or []]
 result=[];seen=set()
 for version in versions:
  for code in (str(c) for c in version.get('productCodes') or []):
   if code not in codes or code in seen:continue
   link=urljoin('https://www.thegioididong.com/',version.get('url') or url)
   if urlsplit(link).hostname not in ('www.thegioididong.com','thegioididong.com'):raise PipelineError('MW: URL biến thể ngoài đại lý')
   seen.add(code);result.append({'url':link,'variant_id':code,'requested_color':target,'color_evidence':{'model':rule['model'],'canonical_color':target,'website_color_label':chosen.get('name') if chosen else None,'website_color_id':chosen.get('code') if chosen else None,'product_code':code,'version':version.get('name'),'selection_url':url}})
 if not versions:
  for code in sorted(codes):
   if code:result.append({'url':url,'variant_id':code,'requested_color':target,'color_evidence':{'model':rule['model'],'canonical_color':target,'website_color_label':chosen.get('name') if chosen else None,'website_color_id':chosen.get('code') if chosen else None,'product_code':code,'selection_url':url}})
 if not result:raise PipelineError('MW: chưa ghép được màu yêu cầu với URL/SKU phiên bản')
 return result

def verify_quote(quote,item,rule):
 evidence=item['color_evidence']
 if str(quote.get('variant_id'))!=item['variant_id'] or model_of(quote.get('product_name',''))!=rule['model']:raise PipelineError('MW: phản hồi không đúng model/mã màu đã chọn')
 if rule['color'] and key(quote.get('color'))!=key(evidence['website_color_label']):raise PipelineError('MW: màu trả về không đúng mã màu đã chọn')
 return evidence
