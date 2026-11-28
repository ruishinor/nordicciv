import copy
import unittest
from tools.reconcile_shelter_snapshot import reconcile


class ShelterSnapshotReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.old = {"source": {"sha256": "old", "retrieved": "old"},
                    "shelters": [{"id": "old", "room": 1, "places": 50,
                                  "address": "Test", "lat": 60.123456, "lon": 10.1, "x": 12, "muni": "NO-0301"}],
                    "totals": {"places": 50}}
        self.fresh = {"rows": [{"id": "12345678-1234-1234-1234-123456789abc", "room": 1,
                                "places": 50, "address": "Test", "lat": 60.1234561, "lon": 10.1,
                                "extracted": "2026-11-28T00:00:00"}], "number_matched": 1}
        self.manifest = {"sha256": "new", "retrieved": "new"}

    def test_only_identifier_and_provenance_change(self):
        result = reconcile(self.old, self.fresh, self.manifest)
        self.assertEqual(result["source"]["sha256"], "new")
        self.assertEqual(result["shelters"][0]["id"], self.fresh["rows"][0]["id"])
        self.assertEqual(result["shelters"][0]["x"], 12)
        self.assertEqual(result["totals"], self.old["totals"])
        self.assertEqual(self.old["shelters"][0]["id"], "old")

    def test_reject_substantive_changes(self):
        for key, value in (("room", 2), ("places", 51), ("address", "Other"), ("lat", 61), ("id", "invalid")):
            with self.subTest(key=key):
                fresh = copy.deepcopy(self.fresh)
                fresh["rows"][0][key] = value
                with self.assertRaises(ValueError):
                    reconcile(self.old, fresh, self.manifest)
