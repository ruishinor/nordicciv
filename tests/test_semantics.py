"""Unit tests for the statistical semantics added in v0.2: each uses small, hand-checkable inputs so the expected
values are obvious, plus a few fixtures against the shipped data (skipped when web/data is absent).

    python -m unittest discover -s tests
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.build import gva, history  # noqa: E402
from pipeline.core import fetch  # noqa: E402

WEB = ROOT / "web" / "data"


def muni(id_, pop, country="NO", region="NO-15", name=None):
    return {"id": id_, "name": name or id_, "country": country, "region": region, "pop": pop}


NAT = {"NO": {y: 1000 * (1 + 0.01 * (y - 2008)) for y in history.YEARS}}


class HistoryClassificationTest(unittest.TestCase):
    def test_source_zero_becomes_unavailable_not_zero(self):
        pop = {y: (0 if y < 2020 else 500) for y in history.YEARS}
        r = history.classify([muni("NO-1806", pop)], NAT)["munis"]["NO-1806"]
        self.assertIsNone(r["series"][2010])
        self.assertEqual(r["status"][2010], "boundary")
        self.assertEqual(r["series"][2020], 500)
        self.assertIsNone(history.growth(r, 2016, 2026))
        self.assertAlmostEqual(history.growth(r, 2020, 2026), 0.0)

    def test_absorbed_unit_marks_the_larger_territory(self):
        # Haram (100) was part of Ålesund (1000) in 2020–2023, then re-established
        haram = {y: (0 if 2020 <= y <= 2023 else 100) for y in history.YEARS}
        ales = {y: (1100 if 2020 <= y <= 2023 else 1000) for y in history.YEARS}
        out = history.classify([muni("NO-1580", haram, name="Haram"), muni("NO-1508", ales, name="Ålesund")], NAT)["munis"]
        a = out["NO-1508"]
        self.assertEqual(a["terr"][2019], 0)
        self.assertEqual(a["terr"][2024], 0)
        self.assertNotEqual(a["terr"][2021], 0)
        self.assertTrue(history.comparable(a, 2016, 2026))  # same territory at both ends
        self.assertFalse(history.comparable(a, 2019, 2021))  # crosses the merger
        self.assertIn("NO-1508", out["NO-1580"]["breaks"][0].get("related", []))

    def test_ordinary_growth_is_untouched(self):
        pop = {y: 1000 + 10 * (y - 2008) for y in history.YEARS}
        r = history.classify([muni("SE-0180", pop, country="SE", region="SE-01")], {"SE": NAT["NO"]})["munis"]["SE-0180"]
        self.assertEqual(r["breaks"], [])
        self.assertAlmostEqual(history.growth(r, 2016, 2026), (1180 - 1080) / 1080)

    def test_region_series_prefers_published_and_reports_coverage(self):
        h = {"A": {"series": {y: 10 for y in history.YEARS}, "terr": {y: 0 for y in history.YEARS}, "breaks": []},
             "B": {"series": {y: (None if y < 2020 else 5) for y in history.YEARS},
                   "terr": {y: (None if y < 2020 else 0) for y in history.YEARS}, "breaks": [{"rule": "R1", "years": [2008, 2019]}]}}
        s, basis, cov = history.region_series([{"id": "A"}, {"id": "B"}], h, {2008: 99})
        self.assertEqual(s[2008], 99)
        self.assertEqual(basis[2008], "published")
        self.assertIsNone(s[2010])
        self.assertAlmostEqual(cov[2010], 10 / 15, places=3)
        self.assertEqual(s[2026], 15)


class SectorAllocationTest(unittest.TestCase):
    def test_keys_follow_industry_value_added(self):
        # two municipalities with the same number of jobs; all value added is in industry B-E, where only m1 works
        ms = [{"id": "m1", "jobs": {"BC": 100, "G": 0}, "jobs_total": 100, "pop": 50},
              {"id": "m2", "jobs": {"BC": 0, "G": 100}, "jobs_total": 100, "pop": 50}]
        k = gva.keys(ms, {"total": 1000, "B-E": 900, "G-I": 100})
        self.assertAlmostEqual(k["m1"], 900)
        self.assertAlmostEqual(k["m2"], 100)

    def test_real_estate_follows_residents_and_remainder_jobs(self):
        ms = [{"id": "m1", "jobs": {"G": 10}, "jobs_total": 10, "pop": 90}, {"id": "m2", "jobs": {"G": 30}, "jobs_total": 30, "pop": 10}]
        k = gva.keys(ms, {"total": 200, "L": 100, "G-I": None})  # 100 unallocated (suppressed industry)
        self.assertAlmostEqual(k["m1"], 90 + 25)
        self.assertAlmostEqual(k["m2"], 10 + 75)
        self.assertAlmostEqual(sum(k.values()), 200)


class CacheIntegrityTest(unittest.TestCase):
    def test_fingerprint_detects_changed_request_and_corruption(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(fetch, "RAW", Path(d)):
            fetch.record("src", "a.json", "https://x/a?q=1", b'{"v": 1}')
            ok, _ = fetch.verify("src", "a.json", url="https://x/a?q=1")
            self.assertTrue(ok)
            ok, why = fetch.verify("src", "a.json", url="https://x/a?q=2")
            self.assertFalse(ok)
            self.assertIn("different request", why)
            ok, why = fetch.verify("src", "a.json", url="https://x/a?q=1", method="POST", body="{}")
            self.assertFalse(ok)
            (Path(d) / "src" / "a.json").write_bytes(b'{"v": 2}')
            ok, why = fetch.verify("src", "a.json", url="https://x/a?q=1")
            self.assertFalse(ok)
            self.assertIn("sha256", why)


class RegistryTest(unittest.TestCase):
    def test_registry_can_be_called_repeatedly(self):  # NC-T13
        from pipeline.sources import registry
        a, b, c = registry(), registry(), registry()
        self.assertEqual(sorted(a), sorted(b))
        self.assertEqual(sorted(b), sorted(c))
        self.assertIn("regional_accounts", c)


@unittest.skipUnless((WEB / "cities.json").exists(), "web/data not built")
class ShippedDataFixturesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cities = {c["id"]: c for c in json.loads((WEB / "cities.json").read_text())}
        cls.nation = json.loads((WEB / "nation.json").read_text())

    def test_no_zero_population(self):
        zeros = [(i, y) for i, c in self.cities.items() for y, v in c["pop_series"].items() if v == 0]
        self.assertEqual(zeros, [])

    def test_known_boundary_cases(self):
        for mid in ("NO-1806", "NO-5059", "NO-5055", "NO-5056", "NO-1875"):
            self.assertIsNone(self.cities[mid]["pop_series"]["2012"], mid)
            self.assertIsNone(self.cities[mid]["growth"], mid)
        al = self.cities["NO-1508"]
        self.assertNotEqual(al["pop_terr"]["2023"], al["pop_terr"]["2024"])
        self.assertIsNone(self.cities["NO-1580"]["pop_series"]["2021"])

    def test_published_national_series(self):
        s = self.nation["nation"]["pop_series"]
        self.assertEqual(s["2008"], 19395889)
        self.assertEqual(s["2016"], 20772253)
        self.assertEqual(s["2026"], 22258532)
        self.assertAlmostEqual(self.nation["nation"]["growth"], 22258532 / 20772253 - 1, places=9)
        self.assertAlmostEqual(self.nation["countries"]["NO"]["growth"], 0.0793, places=3)

    def test_growth_always_finite_or_null(self):
        for c in self.cities.values():
            g = c["growth"]
            self.assertTrue(g is None or math.isfinite(g), c["id"])

    def test_partial_yields_have_bounds(self):
        for c in self.cities.values():
            for k in c["yields_partial"]:
                self.assertGreaterEqual(c["yields_hi"][k], c["yields"][k])

    def test_rank_ranges_are_ordered(self):
        for c in self.cities.values():
            for k, (lo, hi) in (c.get("rank_range") or {}).items():
                self.assertLessEqual(lo, hi)
                self.assertLessEqual(lo, c["ranks"][k])

    def test_regional_output_reconciles(self):
        by = {}
        for c in self.cities.values():
            by[c["gdp_region"]] = by.get(c["gdp_region"], 0) + (c["gdp"] or 0)
        self.assertAlmostEqual(sum(by.values()), self.nation["nation"]["gdp"], delta=1)

    def test_every_municipality_has_a_polygon(self):
        m = json.loads((WEB / "munis.json").read_text())
        have = {f["id"] for f in m["features"]}
        self.assertEqual(set(self.cities) - have, set())
        for small in ("DK-147", "SE-0184", "SE-0183", "NO-1151", "NO-1856", "NO-1857"):
            self.assertIn(small, have)


if __name__ == "__main__":
    unittest.main()
