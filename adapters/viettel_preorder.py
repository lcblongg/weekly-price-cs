"""Đọc trang đặt trước Viettel từ tree công khai; chỉ phân tích JSON, không thực thi JavaScript."""
import json,re
from urllib.parse import urljoin,urlsplit
from common import PipelineError,vnd
from scraper import robots_allowed,validate_url
from price_availability import annotate
from adapters.viettel import response_ok

def tree_rows(text):
    try:
        data=json.loads(text)
        if data.get('stt')!=1:raise ValueError()
        rows=data['data'];rows=json.loads(rows) if isinstance(rows,str) else rows
    except (ValueError,TypeError,KeyError,AttributeError):
        # Endpoint website trả wrapper literal cố định. Chỉ trích JSON bên trong, không eval/new Function.
        match=re.fullmatch(r"\s*\{\s*stt:\s*1,\s*msg:\s*'OK',\s*data:\s*'(.*)'\s*\}\s*",text,re.S)
        if not match:raise PipelineError('Viettel đặt trước: phản hồi không đúng contract')
        try:rows=json.loads(match[1].replace("\\'","'"))
        except ValueError:raise PipelineError('Viettel đặt trước: tree không phải JSON') from None
    if not isinstance(rows,list):raise PipelineError('Viettel đặt trước: thiếu danh sách sản phẩm')
    return rows

async def read(url,main,http,expected_rule=None,rules_only=False):
    product_id=re.search(r'-pid(\d+)\.html$',urlsplit(url).path)[1]
    event=re.search(r"var\s+PREORDER_ONLPREORDERID\s*=\s*'([A-Za-z0-9_]+)'",main.text)
    if not event:raise PipelineError('Viettel: trang không phải contract đặt trước đã nghiệm thu')
    endpoint=urljoin(url,'/Site/_Sys/ajax.aspx');await robots_allowed(http,'Viettel Store',endpoint)
    headers={'Referer':url,'X-Requested-With':'XMLHttpRequest'}
    response=await response_ok(http,'POST',endpoint,headers=headers,data={'a':'preorder-get-tree','onlPreOrderId':event[1]})
    rows=[r for r in tree_rows(response.text) if str(r.get('Product_ID'))==product_id and r.get('Rules_ID') and r.get('PreorderProductId')]
    titles={str(r.get('Title','')).strip() for r in rows}
    if len(titles)!=1 or not rows:raise PipelineError('Viettel đặt trước: không tìm thấy duy nhất model theo product ID URL')
    name=titles.pop();rules=[]
    for row in rows:
        rule=str(row['Rules_ID']);erp=str(row['PreorderProductId']);color=re.sub(r'^Màu sắc:\s*','',str(row.get('RuleName',''))).strip()
        if not re.fullmatch(r'[a-f0-9-]{36}',rule) or not erp.isdigit() or not color:raise PipelineError('Viettel đặt trước: thiếu SKU/màu')
        rules.append({'rule_id':rule,'erp_id':erp,'color':color,'active':False,'has_stock':str(row.get('HasStock'))=='1'})
    if len({r['rule_id'] for r in rules})!=len(rules):raise PipelineError('Viettel đặt trước: trùng biến thể')
    selected=[r for r in rules if r['rule_id']==expected_rule] if expected_rule else [next((r for r in rules if r['has_stock']),rules[0])]
    if len(selected)!=1:raise PipelineError('Viettel đặt trước: mã màu đã khóa không thuộc sản phẩm')
    selected[0]['active']=True
    if rules_only:return {'product_name':name,'variants':rules,'source_url':url}
    variant=selected[0];price_url=urljoin(url,'/Site/_Sys/ajax.asmx/ProductRule_GetPriceByRule');await robots_allowed(http,'Viettel Store',price_url)
    response=await http.post(price_url,headers=headers,json={'id':variant['rule_id'],'pid':product_id});validate_url('Viettel Store',str(response.url))
    try:
        result=response.json()['d'];result=json.loads(result) if isinstance(result,str) else result;p=result['data']
        if response.status_code!=200 or result['stt']!=1 or str(p['Erp_Product_ID'])!=variant['erp_id']:raise ValueError()
        display=int(p['PriceDisplayType'])
        if display not in (0,1,2):raise ValueError()
        raw=p['Price'] if display in (1,2) else p['SellPrice'];sale=vnd(str(raw)) if raw not in (None,'',0,'0') else None
    except (ValueError,TypeError,KeyError,AttributeError):raise PipelineError('Viettel đặt trước: API giá không khớp ERP/contract') from None
    return {'product_name':name,'source_url':url,'variants':rules,'variant':variant,'promo_price':sale,'original_price':None,'promo_text':annotate('CTKM trang đặt trước chưa được xác minh đầy đủ; chưa trừ ưu đãi thanh toán/thu cũ.','Trang đặt trước; xác minh ngày giao và điều kiện đặt hàng trên website.'+(' Mã màu hiện không còn suất đặt.' if not variant['has_stock'] else '')),'promotion_complete':False,'price_scope':'Giá API công khai của đúng ERP trên trang đặt trước.'}
