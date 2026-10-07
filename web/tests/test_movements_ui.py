"""Nghiệm thu dữ liệu thật, thông báo và bảng tuần 7 ngày. Không sửa giá hoặc bot."""
import asyncio,json
from pathlib import Path
from playwright.async_api import async_playwright
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'artifacts/price-movements-ui';OUT.mkdir(exist_ok=True)
async def main():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1000})
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto('http://localhost:3000/',wait_until='networkidle')
  assert await page.get_by_role('button',name='Xuất Excel',exact=True).count()==0
  flash=page.get_by_role('region',name='Thông báo biến động giá')
  # Section có aria-label tương ứng role region.
  await flash.wait_for()
  assert await flash.locator('button').count()>0
  await page.get_by_label('Chọn model',exact=True).select_option('iPhone 17')
  text=await flash.inner_text();assert 'MW' in text and '3.500.000' in text,text
  await flash.locator('button').first.focus()
  await flash.locator('button').first.click();await page.locator('dialog[open]').wait_for()
  detail=await page.locator('dialog').inner_text();assert '6/10/2026' in detail and '7/10/2026' in detail and 'SKU' in detail
  await page.get_by_role('button',name='Đóng chi tiết',exact=True).click()
  down=page.get_by_role('button',name='iPhone 17 256GB, MW: 25.490.000 ₫',exact=True).locator('..')
  assert await down.evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(254, 236, 235)'
  assert await down.evaluate('(el)=>getComputedStyle(el).color')=='rgb(180, 35, 24)'
  up=page.get_by_role('button',name='iPhone 17 256GB, CPS: 26.490.000 ₫',exact=True).locator('..')
  assert await up.evaluate('(el)=>getComputedStyle(el).backgroundColor')=='rgb(225, 243, 233)'
  await page.screenshot(path=str(OUT/'daily-red-green.png'))
  await page.get_by_role('button',name='Theo tuần',exact=True).click()
  table=page.get_by_role('table',name='So sánh tuần này với tuần trước')
  assert await table.locator('thead th').count()==5
  assert 'Chưa có dữ liệu tuần trước' in await table.inner_text()
  assert '3.500.000' not in await flash.inner_text()
  await page.get_by_role('button',name='Xem chi tiết 7 ngày',exact=True).click()
  assert await table.locator('thead th').count()==12
  text=await table.inner_text();assert all(d in text for d in ['05/10','06/10','07/10','08/10','09/10','10/10','11/10'])
  assert 'Chưa có dữ liệu' in text and 'Chưa có dữ liệu tuần trước' in text
  assert await page.get_by_label('Chọn tuần',exact=True).count()==1
  await page.screenshot(path=str(OUT/'week-and-flash.png'))
  await page.get_by_label('Chọn kênh',exact=True).select_option('CPS')
  assert 'MW ·' not in await flash.inner_text()
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  await page.get_by_label('Tìm model theo dõi',exact=True).fill('iPhone 17')
  await page.get_by_role('checkbox',name='iPhone 17',exact=True).uncheck()
  assert await table.locator('tbody tr').count()==0
  assert 'iPhone 17 256GB:' not in await flash.inner_text()
  await page.get_by_role('button',name='Khôi phục mặc định',exact=True).click()
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  await page.set_viewport_size({'width':390,'height':844})
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
  await page.screenshot(path=str(OUT/'mobile.png'))
  await page.goto('http://localhost:3000/history',wait_until='networkidle')
  assert await page.get_by_role('table',name='So sánh tuần này với tuần trước').count()==1
  assert await page.get_by_role('button',name='Xuất Excel',exact=True).count()==0
  assert not errors,errors
  (OUT/'result.json').write_text(json.dumps({'passed':True,'checks':['no Excel','real MW iPhone17 -3500000','two-date SKU detail','week vs prior week; no fake baseline','7 simultaneous detail days','daily red decrease/green increase','missing days explicit','chain filter','watchlist filters alerts/week','mobile','history uses current data'],'errors':errors},ensure_ascii=False,indent=2))
  await browser.close();print('PASS: real flash, seven-day history, filters/watchlist, mobile, no Excel')
asyncio.run(main())
