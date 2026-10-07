"""Đọc giao diện MW cũ bằng HTML tĩnh, không chạy JavaScript từ website.
Khóa document.productCode và lựa chọn màu active trước khi nhận giá hiển thị.
"""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin
from common import PipelineError,vnd
from price_availability import annotate
class Node:
 def __init__(self,tag,attrs=None):self.tag=tag;self.attrs=dict(attrs or []);self.children=[]
 def has(self,name):return name in self.attrs.get('class','').split()
 def text(self):return ' '.join(' '.join(c if isinstance(c,str) else c.text() if c.tag not in ('script','style') else '' for c in self.children).split())
 def all(self,predicate):
  result=[]
  for child in self.children:
   if isinstance(child,Node):
    if predicate(child):result.append(child)
    result+=child.all(predicate)
  return result
class Tree(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.root=Node('root');self.stack=[self.root]
 def handle_starttag(self,tag,attrs):
  node=Node(tag,attrs);self.stack[-1].children.append(node)
  if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(node)
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==tag:self.stack=self.stack[:i];break
 def handle_data(self,data):self.stack[-1].children.append(data)
 def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
def parse(markup,url):
 codes=set(re.findall(r'document\.productCode\s*=\s*["\'](\d{8,20})["\']',markup))
 if len(codes)!=1:raise PipelineError('MW giao diện cũ: chưa xác minh được mã sản phẩm')
 code=codes.pop();tree=Tree();tree.feed(markup);root=tree.root
 heads=root.all(lambda n:n.tag=='h1')
 if len(heads)!=1 or not heads[0].text():raise PipelineError('MW giao diện cũ: tên sản phẩm không duy nhất')
 rights=root.all(lambda n:n.has('box_right'))
 if len(rights)!=1:raise PipelineError('MW giao diện cũ: vùng giá không duy nhất')
 right=rights[0];color_boxes=right.all(lambda n:n.has('box03') and n.has('color'))
 color_nodes=[n for box in color_boxes for n in box.all(lambda n:n.tag=='a' and n.attrs.get('data-code'))]
 active=[n for n in color_nodes if n.has('act')]
 if color_nodes and (len(active)!=1 or active[0].attrs['data-code']!=code):raise PipelineError('MW giao diện cũ: màu active khác mã sản phẩm')
 colors=[{'name':n.text(),'code':n.attrs.get('data-color'),'productCodes':[n.attrs['data-code']]} for n in color_nodes]
 boxes=right.all(lambda n:n.has('box04'))
 saving=False
 if not boxes:
  boxes=right.all(lambda n:n.has('box_saving'))
  saving=True
 if len(boxes)!=1:raise PipelineError('MW giao diện cũ: không xác định một vùng giá/trạng thái')
 box=boxes[0];prices=box.all(lambda n:n.has('box-price-present'))
 if saving:
  price_groups=box.all(lambda n:n.has('bs_price'))
  if len(price_groups)!=1:raise PipelineError('MW: giá online không duy nhất')
  prices=price_groups[0].all(lambda n:n.tag=='strong')
 amounts={vnd(n.text()) for n in prices if n.text()}
 if len(amounts)>1:raise PipelineError('MW giao diện cũ: có nhiều giá hiển thị; cần kiểm tra điều kiện')
 statuses=box.all(lambda n:n.has('productstatus'))
 status=' '.join(dict.fromkeys(n.text() for n in statuses if n.text()))
 sale=next(iter(amounts)) if amounts else None
 if sale is None and not status:raise PipelineError('MW giao diện cũ: không đọc được giá hoặc trạng thái')
 promos=box.all(lambda n:n.has('block__promo'))
 notes='\n'.join(dict.fromkeys(n.text() for n in promos if n.text()))
 if not promos:notes='CTKM: chưa có vùng chi tiết để xác minh trong giao diện này.'
 name=heads[0].text()
 quote={'chain_name':'TGDD','product_name':name,'source_url':url,'variant_id':code,'color':active[0].text() if active else '', 'promo_price':sale,'original_price':None,'promo_text':annotate(notes,status or None),'promotion_complete':bool(promos),'price_scope':'Giá bán hiển thị đúng mã sản phẩm/màu, giao diện MW cũ; ưu đãi có điều kiện giữ ở ghi chú'}
 # Giao diện cũ chỉ chứng minh mã màu của phiên bản hiện tại; không đoán mã màu cho dung lượng khác.
 data={'name':name,'productCode':code,'filter':[{'label':'Màu','values':colors}] if colors else [],'_legacy_quote':quote}
 return data
