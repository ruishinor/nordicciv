import unittest

from pipeline.check import reconcile_regional_totals


class RegionalReconciliationTests(unittest.TestCase):
    def test_coverage_and_tolerance(self):
        expected = {"NO-01": 1000000, "SE-01": 2000000, "DK-01": 3000000}
        self.assertTrue(reconcile_regional_totals(expected, dict(expected))[0])
        self.assertFalse(reconcile_regional_totals(expected, {"NO-01": 1000000})[0])
        self.assertFalse(reconcile_regional_totals(expected, {**expected, "NO-99": 100000})[0])
        self.assertTrue(reconcile_regional_totals(expected, {**expected, "NO-01": 1050001})[0])
        self.assertFalse(reconcile_regional_totals(expected, {**expected, "NO-01": 1050002})[0])
        self.assertFalse(reconcile_regional_totals({}, {})[0])
