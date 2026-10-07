import unittest
from daily_history import weekly_grid

class DailyHistoryTests(unittest.TestCase):
    def test_seven_days_gaps_and_latest_snapshot(self):
        base={'chain_name':'Viettel Store','sku':'one','product_name':'iPhone','business_date':'2026-10-05'}
        grid=weekly_grid([{**base,'captured_at':'2026-10-05T03:00:00+00:00','promo_price':20000000},
                          {**base,'captured_at':'2026-10-05T04:00:00+00:00','promo_price':19000000}], '2026-10-05')
        self.assertEqual(len(grid['dates']),7)
        self.assertEqual(grid['dates'][-1],'2026-10-11')
        self.assertEqual(grid['products'][0]['days']['2026-10-05']['promo_price'],19000000)
        self.assertIsNone(grid['products'][0]['days']['2026-10-06'])
        self.assertEqual(len(grid['missing_dates']),6)
