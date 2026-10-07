"""Nghiệm thu bảng so sánh thực tế: lọc, watchlist, Excel, chi tiết SKU và mobile.
Không khởi chạy bot, không gửi Telegram, không sửa quy chuẩn dùng chung.
"""
import asyncio,json,os
from pathlib import Path
from playwright.async_api import async_playwright
from openpyxl import load_workbook
ROOT=Path(__file__).resolve().parents[2]
URL=os.environ.get('DASHBOARD_URL','http://127.0.0.1:3000')
OUT=ROOT/'artifacts/production-readiness/ui';OUT.mkdir(parents=True,exist_ok=True)
async def main():
 async with async_playwright() as pw:
  browser=await pw.chromium.launch();page=await browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
  errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  await page.goto(URL,wait_until='networkidle');await page.locator('tbody tr').first.wait_for()
  assert await page.locator('thead th').all_text_contents()==['BASE MODEL','MW','CPS','FPT','VIETTEL','PV']
  await page.get_by_label('Chọn ngày',exact=True).select_option('2026-10-07')
  await page.get_by_label('Chọn model',exact=True).select_option('iPhone 17 Pro Max')
  quote=page.get_by_role('button',name='iPhone 17 Pro Max 256GB, CPS: 34.990.000 ₫',exact=True)
  await quote.click();await page.locator('dialog[open]').wait_for()
  detail=await page.locator('dialog').inner_text();assert 'Cam vũ trụ' in detail and 'cps-112615' in detail and '7/10/2026' in detail
  assert 'Giá gốc' not in detail
  await page.get_by_role('button',name='Đóng chi tiết',exact=True).click()
  await page.get_by_label('Chọn ngày',exact=True).select_option('2026-10-06')
  await page.get_by_label('Chọn hãng',exact=True).select_option('Apple')
  await page.get_by_label('Chọn danh mục',exact=True).select_option('Điện thoại')
  await page.get_by_label('Chọn model',exact=True).select_option('iPhone 16')
  assert await page.locator('tbody tr').count()>0
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  assert await page.locator('fieldset legend').count()>1
  await page.get_by_label('Tìm model theo dõi',exact=True).fill('iPhone 16')
  await page.get_by_role('checkbox',name='iPhone 16',exact=True).uncheck()
  await page.wait_for_function("JSON.parse(localStorage.getItem('weekly-price-cs:watchlist:v1')).hidden.length===1")
  assert await page.locator('tbody tr').count()==0
  await page.reload(wait_until='networkidle')
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  assert not await page.get_by_role('checkbox',name='iPhone 16',exact=True).is_checked()
  assert await page.get_by_role('checkbox',name='iPhone 16 Plus',exact=True).is_checked()
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  await page.get_by_label('Chọn ngày',exact=True).select_option('2026-10-06')
  await page.get_by_label('Chọn hãng',exact=True).select_option('Apple')
  await page.get_by_label('Chọn danh mục',exact=True).select_option('Điện thoại')
  await page.get_by_label('Chọn model',exact=True).select_option('iPhone 16 Plus')
  assert await page.locator('tbody tr').count()>0
  await page.get_by_label('Chọn kênh',exact=True).select_option('CPS')
  assert await page.locator('thead th').all_text_contents()==['BASE MODEL','CPS']
  async with page.expect_download() as download:await page.get_by_role('button',name='Xuất Excel',exact=True).click()
  f=await download.value;await f.save_as(OUT/'filtered.xlsx');book=load_workbook(OUT/'filtered.xlsx')
  records=list(book['Chi tiết SKU'].values)[1:];assert records
  assert all(r[0]=='CPS' and 'iPhone 16 Plus' in r[1] for r in records)
  assert all(r[4] is None or isinstance(r[4],(int,float)) and r[4]>0 for r in records)
  await page.get_by_role('button',name='Theo tuần',exact=True).click()
  assert await page.locator('[aria-pressed]').count()>=9
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  await page.get_by_role('button',name='Khôi phục mặc định',exact=True).click()
  await page.wait_for_function("JSON.parse(localStorage.getItem('weekly-price-cs:watchlist:v1')).hidden.length===0")
  await page.get_by_role('button',name='Sản phẩm theo dõi',exact=True).click()
  await page.get_by_label('Chọn hãng',exact=True).select_option('');await page.get_by_label('Chọn kênh',exact=True).select_option('')
  await page.set_viewport_size({'width':390,'height':844})
  assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), 'Trang mobile tràn ngang ngoài vùng bảng'
  await page.screenshot(path=str(OUT/'mobile.png'),full_page=False)
  await page.set_viewport_size({'width':1440,'height':1000});await page.screenshot(path=str(OUT/'desktop.png'))
  assert not errors,errors
  (OUT/'result.json').write_text(json.dumps({'ok':True,'export_skus':len(records),'checks':['5 channels','CPS real price/color/SKU','date-brand-category-model-chain','watchlist persistence/exact model','Excel filtering','week days','mobile'],'browser_errors':errors},ensure_ascii=False,indent=2))
  await browser.close();print('PASS: matrix filters, verified CPS detail, watchlist persistence, Excel, week, mobile')
asyncio.run(main())
