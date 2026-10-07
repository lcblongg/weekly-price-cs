"""Viettel Store theo giao diện adapter chung (listing/read_product), dùng lại adapter HTTP đã nghiệm thu."""
from common import PipelineError
from http_policy import wait_turn
from adapters.viettel import listing_links
from adapters.viettel_detail import read_product as read_detail

CHAIN = 'Viettel Store'


async def listing(source, http, browser=None):
    links = await listing_links(source, http)
    return {url: {'url': url, 'name': name} for url, name in links.items()}


async def read_product(item, http, browser):
    if browser is None:
        raise PipelineError('Viettel: cần Chromium (tắt JavaScript) để phân tích fragment')
    await wait_turn(http, item['url'])  # giãn cách theo host như các adapter khác
    quote = await read_detail(item['url'], http, browser, item.get('variant_id'))
    variant = quote['variant']
    if item.get('variant_erp_id') and variant['erp_id'] != item['variant_erp_id']:
        raise PipelineError('Viettel: ERP biến thể đổi; cần khám phá lại')
    return {'chain_name': CHAIN, 'product_name': quote['product_name'], 'source_url': quote['source_url'],
            'variant_id': variant['rule_id'], 'variant_erp_id': variant['erp_id'], 'sku_key': variant['erp_id'],
            'color': variant['color'],
            'promo_price': quote['promo_price'], 'original_price': quote['original_price'],
            'promo_text': quote['promo_text'], 'promotion_complete': quote['promotion_complete'],
            'price_scope': quote['price_scope']}
