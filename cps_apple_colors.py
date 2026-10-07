"""Chọn màu CPS từ sản phẩm con thật, không sử dụng màu trong catalog cũ để đổi nhãn giá."""
from apple_preferences import key,model_of
from common import PipelineError
from apple_sources import WrongModel
from adapters.cellphones import color_of,quote
# Chỉ đối chiếu tên thương mại trên đúng model. Không suy đoán màu gần giống.
LABELS={'iPhone 17':{'Xanh Lá Xô Thôm':['Xanh Lá Xô Thơm']},'Apple Watch Ultra 3':{'Đen':['Titan Đen']}}
def selected_quote(parent,child,rule,url):
 g=child['general'];pg=parent['general'];pid=str(g['product_id']);parent_id=str(pg['product_id'])
 if model_of(pg['name'])!=rule['model'] or model_of(g['name'])!=rule['model']:raise WrongModel('CPS: model con/cha không đúng model yêu cầu')
 children={str(i) for i in (pg.get('child_product') or [pg['product_id']])}
 if pid not in children or str(child['filterable'].get('parent_id') or pid) not in (parent_id,pid):raise PipelineError('CPS: mã màu con không thuộc sản phẩm cha')
 color=color_of(g['name'],pg['name'])
 if rule['color']:
  accepted={key(rule['color']),*(key(a) for a in rule.get('aliases',[])),*(key(s) for s in LABELS.get(rule['model'],{}).get(rule['color'],[]))}
  if not color or key(color) not in accepted:return None
 item={'variant_id':pid,'parent_id':parent_id,'url':url+'?product_id='+pid,'color':color,'name':pg['name']}
 result=quote(item,child)
 if str(result['variant_id'])!=pid:raise PipelineError('CPS: mã giá khác mã màu đã chọn')
 return dict(result,color=rule['color'],color_evidence={'model':rule['model'],'canonical_color':rule['color'],'website_color_label':color,'website_color_id':pid,'product_code':pid,'parent_id':parent_id,'selected_url':item['url']})
