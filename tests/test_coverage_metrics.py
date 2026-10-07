import unittest
from coverage_metrics import dashboard_metrics


class CoverageMetricsTests(unittest.TestCase):
    def row(self, stamp, price=100, **extra):
        return dict(slug='tgdd', sku='a', apple_model='iPhone 17',
                    observed_at=stamp, promo_price=price, **extra)

    def test_history_does_not_count_as_fresh_and_status_replaces_price(self):
        rows = [self.row('2026-10-06T10:00:00+07:00'),
                self.row('2026-10-07T10:00:00+07:00', None)]
        result = dashboard_metrics(rows, '2026-10-07')
        self.assertEqual(result['history_rows'], 2)
        self.assertEqual(result['latest_skus'], 1)
        self.assertEqual(result['today_numeric'], 0)
        self.assertEqual(result['today_status_only'], 1)

    def test_timezone_and_stale_are_not_claimed_fresh(self):
        rows = [self.row('2026-10-06T18:00:00Z', stale_since='2026-10-07')]
        result = dashboard_metrics(rows, '2026-10-07')
        self.assertEqual(result['today_verified_skus'], 0)
        self.assertEqual(result['explicitly_stale'], 1)
        self.assertEqual(result['models_without_today_data'], ['iPhone 17'])
        self.assertEqual(dashboard_metrics([self.row('2026-10-06T18:00:00Z')],
                                          '2026-10-07')['today_verified_skus'], 1)

    def test_same_sku_across_channels_remains_separate(self):
        a = self.row('2026-10-07T10:00:00+07:00')
        b = {**a, 'slug': 'cellphones'}
        self.assertEqual(dashboard_metrics([a, b], '2026-10-07')['latest_skus'], 2)
