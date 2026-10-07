import unittest
from datetime import datetime,date,timezone
from business_calendar import week_bounds,completed_week

class BusinessCalendarTests(unittest.TestCase):
    def test_tuesday_in_current_business_week(self):
        self.assertEqual(week_bounds(date(2026,10,6)),(date(2026,10,5),date(2026,10,11)))
    def test_sunday_still_belongs_to_same_week(self):
        self.assertEqual(week_bounds(date(2026,10,11))[0],date(2026,10,5))
    def test_utc_boundary_uses_vietnam(self):
        self.assertEqual(week_bounds(datetime(2026,10,11,17,tzinfo=timezone.utc))[0],date(2026,10,12))
    def test_completed_week_does_not_include_current_week(self):
        self.assertEqual(completed_week(date(2026,10,11)),(date(2026,9,28),date(2026,10,4)))

    def test_fiscal_reference_and_transitions(self):
        from business_calendar import fiscal_period
        self.assertEqual(fiscal_period(date(2026,10,6))['label'],'W2Q1FY27')
        self.assertEqual(fiscal_period(date(2026,9,28))['label'],'W1Q1FY27')
        self.assertEqual(fiscal_period(date(2026,12,28))['label'],'W1Q2FY27')
        self.assertEqual(fiscal_period(date(2027,9,27))['label'],'W1Q1FY28')
