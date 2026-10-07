import unittest
from daily_publication import merge_history
class DailyPublicationTests(unittest.TestCase):
 def test_history_keeps_yesterday_and_new_status_replaces_today_price(self):
  old={'chain':'MW','sku':'a','observed_at':'2026-10-06T10:00:00+07:00','promo_price':1000000}
  today={**old,'observed_at':'2026-10-07T10:00:00+07:00','promo_price':1100000}
  status={**today,'observed_at':'2026-10-07T11:00:00+07:00','promo_price':None,'promo_text':'Hết hàng'}
  rows=merge_history([old,today],[status]);self.assertEqual(rows,[old,status])
 def test_timezone_and_same_sku_in_different_channels(self):
  old={'chain':'MW','sku':'a','observed_at':'2026-10-06T23:00:00Z','promo_price':1}
  fresh={**old,'observed_at':'2026-10-07T10:00:00+07:00','promo_price':2}
  other={**old,'chain':'CPS'}
  self.assertEqual(merge_history([old,other],[fresh]),[fresh,other])
 def test_retained_price_does_not_get_new_date_and_no_older_overwrite(self):
  old={'chain':'MW','sku':'a','observed_at':'2026-10-06T10:00:00+07:00','promo_price':1}
  retained={**old,'stale_since':'2026-10-07T10:00:00+07:00'}
  self.assertEqual(merge_history([old],[retained]),[retained])
  fresh={**old,'observed_at':'2026-10-06T11:00:00+07:00','promo_price':2}
  self.assertEqual(merge_history([fresh],[old]),[fresh])
