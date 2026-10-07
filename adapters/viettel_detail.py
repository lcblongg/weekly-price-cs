"""Giá/CTKM Viettel theo đúng mã màu, qua các request chỉ đọc của trang chi tiết.
Không chạy JS tải từ đại lý; Chromium chỉ phân tích HTML trong context tắt JavaScript.
"""
import json
import httpx
import re
from urllib.parse import urljoin, urlsplit
from price_availability import annotate,explicit_status
from common import PipelineError, vnd
from scraper import validate_url, robots_allowed
from adapters.viettel import response_ok

AJAX = '/AjaxAction.aspx'
PRICE = '/Site/_Sys/ajax.asmx/ProductRule_GetPriceByRule'

async def field(page, identifier):
    element = page.locator('#' + identifier)
    if await element.count() != 1:
        raise PipelineError(f'Viettel: thiếu hoặc trùng trường {identifier}')
    return await element.get_attribute('value')

async def text(locator):
    # Loại mã script/style, chỉ giữ nội dung mô tả; không thực thi mã nguồn.
    value = await locator.evaluate("el => {const c=el.cloneNode(true); c.querySelectorAll('script,style').forEach(n=>n.remove());return c.textContent;}")
    return ' '.join(value.split())

async def read_product(url, client, browser, expected_rule=None, rules_only=False):
    validate_url('Viettel Store', url)
    product_match = re.search(r'-pid(\d+)\.html$', urlsplit(url).path)
    if not product_match:
        raise PipelineError('Viettel: URL chi tiết thiếu product ID')
    product_id = product_match[1]
    await robots_allowed(client, 'Viettel Store', url)
    main = await response_ok(client, 'GET', url)
    calls = re.findall(r'loadInfoProduct\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*;', main.text)
    if not calls and 'PREORDER_ONLPREORDERID' in main.text:
        from adapters.viettel_preorder import read
        return await read(url,main,client,expected_rule,rules_only)
    if calls and calls != [(product_id, product_id)]:
        raise PipelineError('Viettel: trang chi tiết chuyển model/biến thể hoặc đổi contract')
    headers = {'X-Requested-With':'XMLHttpRequest', 'Referer':str(main.url)}
    ajax, price_url = urljoin(str(main.url), AJAX), urljoin(str(main.url), PRICE)
    for endpoint in (ajax, price_url):
        await robots_allowed(client, 'Viettel Store', endpoint)
    context = await browser.new_context(java_script_enabled=False)
    await context.route('**/*', lambda route: route.abort())
    page = await context.new_page()
    async def fragment(payload):
        response = await response_ok(client, 'POST', ajax, headers=headers, data=payload)
        if '<meta' in response.text.lower() and 'viewport' in response.text.lower():
            raise PipelineError('Viettel: endpoint trả trang lỗi thay vì fragment')
        await page.set_content(response.text, wait_until='domcontentloaded')
        return response
    try:
        if not calls:
            # Template mới không còn lời gọi JS; vẫn phải đối chiếu canonical của trang thật.
            await page.set_content(main.text,wait_until='domcontentloaded')
            canonical=page.locator('link[rel="canonical"]')
            if await canonical.count()!=1 or urlsplit(await canonical.get_attribute('href')).path!=urlsplit(url).path or urlsplit(str(main.url)).path!=urlsplit(url).path:
                raise PipelineError('Viettel: không xác minh được canonical/product ID của template mới')
        await fragment({'action':'get-block-info-product','productId':product_id,'productIdMain':product_id})
        if await field(page,'ProductId') != product_id:
            raise PipelineError('Viettel: fragment sai product ID')
        name = ' '.join((await field(page,'ProductTitle')).split())
        heading = page.locator('h1')
        if await heading.count() != 1 or await text(heading) != name:
            raise PipelineError('Viettel: tên sản phẩm không nhất quán')
        validate_url('Viettel Store', await field(page,'meta-url'))
        if urlsplit(await field(page,'meta-url')).path != urlsplit(url).path:
            raise PipelineError('Viettel: canonical không khớp sản phẩm')
        if await page.locator('.normal-order').count() != 1:
            raise PipelineError('Viettel: chưa hỗ trợ cấu trúc bán hàng này')
        notes=[]
        for element in await page.locator('.frame-promotion-header, .box-promotion .promo-content').all():
            value=await text(element)
            if value: notes.append(value)
        # Chỉ đọc khu vực giá của sản phẩm; không lấy chữ hết hàng trong bài viết/CTKM.
        shown=list(dict.fromkeys([await text(el) for el in await page.locator('.price-product .new-price').all()]))
        shown=[v for v in shown if v]
        shown_status=explicit_status({'statusText':shown[0]}) if len(shown)==1 else None
        displayed_price=None
        if len(shown)==1 and not shown_status:
            try:displayed_price=vnd(shown[0])
            except PipelineError:pass
        await fragment({'action':'get-list-rule-by-product','productId':product_id})
        rules=[]
        for label in await page.locator('.option-color-product .color-check').all():
            rule_id=await label.get_attribute('id')
            color=await label.get_attribute('title')
            inputs=label.locator('input[data-erp]')
            if not rule_id or not color or await inputs.count()!=1 or not re.fullmatch(r'[a-f0-9-]{36}',rule_id):
                raise PipelineError('Viettel: thiếu định danh biến thể màu')
            erp=await inputs.get_attribute('data-erp')
            if not erp or not erp.isdigit():
                raise PipelineError('Viettel: thiếu mã ERP biến thể')
            rules.append({'rule_id':rule_id,'color':color,'erp_id':erp,
                          'active':'active' in (await label.get_attribute('class') or '').split()})
        if not rules and (shown_status or displayed_price):
            # Website không công bố ERP/màu: giữ riêng định danh trang, không giả lập SKU màu.
            identifier='product-'+product_id
            if expected_rule and expected_rule!=identifier:raise PipelineError('Viettel: không còn xác minh được SKU màu đã khóa')
            variant={'rule_id':identifier,'erp_id':identifier,'color':None,'active':True}
            return {'chain_name':'Viettel Store','product_name':name,'source_url':str(main.url),'variant':variant,'variants':[variant],
                    'promo_price':displayed_price,'original_price':None,'promotion_complete':False,
                    'promo_text':annotate('Website chưa công bố SKU màu; bản ghi dùng product ID trang chi tiết. CTKM chưa xác minh đầy đủ.',shown_status),
                    'price_scope':'Giá/trạng thái hiển thị trên trang sản phẩm; chưa xác minh ERP hoặc màu.'}
        if not rules or len({r['rule_id'] for r in rules})!=len(rules):
            raise PipelineError('Viettel: danh sách biến thể rỗng/trùng')
        if rules_only:return {'product_name':name,'variants':rules,'source_url':str(main.url)}
        selected=[r for r in rules if r['rule_id']==expected_rule] if expected_rule else [r for r in rules if r['active']]
        if len(selected)!=1:
            raise PipelineError('Viettel: biến thể đã đổi hoặc không có màu mặc định duy nhất')
        variant=selected[0]
        response=await client.post(price_url,headers=headers,json={'id':variant['rule_id'],'pid':product_id})
        validate_url('Viettel Store',str(response.url))
        if response.status_code!=200 or 'json' not in response.headers.get('content-type','') or len(response.content)>100_000:
            raise PipelineError('Viettel: API giá không trả JSON hợp lệ')
        try:
            result=response.json()['d']
            if isinstance(result,str): result=json.loads(result) # Chỉ JSON; tuyệt đối không eval.
            if result['stt']!=1: raise ValueError()
            price=result['data']
            display=int(price['PriceDisplayType'])
            if display not in (0,1,2) or str(price['Erp_Product_ID'])!=variant['erp_id']: raise ValueError()
            availability=('đặt trước, cần xác minh ngày giao hàng.' if int(price['SaleState'])!=0 else 'biến thể hết hàng tại khu vực mặc định.' if int(price['AmounInstock'])<=0 else None)
            raw=price['Price'] if display in (1,2) else price['SellPrice']
            sale=vnd(str(raw)) if raw not in (None,'',0,'0') else None
            if sale is None and not availability and variant['active']:availability=shown_status
            if sale is None and not availability:raise PipelineError('Viettel: bot chưa đọc được giá hoặc trạng thái SKU')
            old=vnd(str(price['Price'])) if sale is not None and str(price['Price']) not in ('0','',str(sale)) else None
        except (KeyError,TypeError,ValueError) as exc:
            if isinstance(exc,PipelineError): raise
            raise PipelineError('Viettel: contract API giá thay đổi') from None
        if old is not None and sale is not None and old<sale:
            raise PipelineError('Viettel: giá gốc thấp hơn giá bán')
        promotion_complete=True
        try:
            await fragment({'action':'get-product-promotion-erp','productId':product_id,'ruleId':variant['rule_id']})
            has_offer=await field(page,'HiddenHasPromotionOffer')
            if has_offer not in ('0','1'):
                raise PipelineError('Viettel: không xác định trạng thái ưu đãi ERP')
            if await field(page,'HiddenMinDiscountAmount') != '0' and has_offer == '0':
                raise PipelineError('Viettel: giá giảm ERP chưa xác định')
            if has_offer=='1':
                raise PipelineError('Viettel: ưu đãi ERP có lựa chọn; cần nghiệm thu giá theo lựa chọn')
            # Kể cả không có ERP offer, phải đọc xong ưu đãi thanh toán; lỗi thì không công bố CTKM đầy đủ.
            payment = await fragment({'action':'get-payment-promotion','ErpProductId':variant['erp_id']})
            if 'BEGIN BlockPaymentPromotion' not in payment.text:
                raise PipelineError('Viettel: phản hồi CTKM thanh toán không xác định')
            for element in await page.locator('.frame-promotion').all():
                value=await text(element)
                if value: notes.append(value)
        except (PipelineError,httpx.HTTPError) as exc:
            promotion_complete=False
            notes.append('CTKM chưa xác minh đầy đủ: '+str(exc)+' Giá trên là giá API của đúng mã ERP, chưa trừ ưu đãi có lựa chọn.')
        return {'chain_name':'Viettel Store','product_name':name,'source_url':str(main.url),
                'promo_price':sale,'original_price':old,'promo_text':annotate('\n'.join(dict.fromkeys(notes)),availability),
                'variant':variant,'variants':rules,'promotion_complete':promotion_complete,
                'price_scope':'Giá trực tiếp của biến thể màu đã chọn; chưa trừ ưu đãi có điều kiện'}
    finally:
        await context.close()

async def extract_product(item,client,browser):
    if not item.get('variant_rule_id'):
        raise PipelineError('Viettel: cấu hình chưa khóa biến thể màu')
    row=await read_product(item['url'],client,browser,item['variant_rule_id'])
    if ' '.join(row['product_name'].casefold().split()) != ' '.join(item.get('source_product_name','').casefold().split()):
        raise PipelineError('Viettel: tên model nguồn đã đổi; cần khám phá lại')
    if not all(token.casefold() in row['product_name'].casefold() for token in item['verify_tokens']):
        raise PipelineError('Viettel: model/dung lượng không khớp cấu hình')
    if row['variant']['erp_id']!=item.get('variant_erp_id'):
        raise PipelineError('Viettel: ERP biến thể đổi; cần khám phá lại')
    return {key:row[key] for key in ('chain_name','original_price','promo_price','promo_text','source_url')} | {
        'sku':item['sku'],'product_name':item['product_name']}
