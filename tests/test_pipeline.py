"""Unit tests for the geographic and statistical core (standard library unittest; run: python -m unittest discover -s tests)."""
import json
import math
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from pipeline.core import geo, jsonstat  # noqa: E402
from pipeline.core.hexgrid import HexGrid  # noqa: E402
from pipeline.build import admin  # noqa: E402

WEB = ROOT / "web" / "data"


class HexGridTest(unittest.TestCase):
    def test_vectorised_cell_at_matches_scalar(self):
        g = HexGrid(6.0, 200, 260)
        rnd = random.Random(1)
        xs = [rnd.uniform(-10, 2100) for _ in range(5000)]
        ys = [rnd.uniform(-10, 2400) for _ in range(5000)]
        vec = geo.cell_at(np.array(xs), np.array(ys), 6.0, 200, 260)
        for x, y, v in zip(xs, ys, vec):
            self.assertEqual(g.cell_at(x, y), int(v))

    def test_centres_round_trip(self):
        g = HexGrid(6.0, 50, 40)
        cx, cy = geo.centers(6.0, 50, 40)
        for i in range(0, g.size, 7):
            self.assertEqual(g.cell_at(cx[i], cy[i]), i)

    def test_neighbours_are_adjacent(self):
        g = HexGrid(6.0, 30, 30)
        for i in (0, 31, 455, 899):
            ci, ri = g.col_row(i)
            x, y = g.center(ci, ri)
            for j in g.neighbours(i):
                cj, rj = g.col_row(j)
                x2, y2 = g.center(cj, rj)
                self.assertAlmostEqual(math.hypot(x2 - x, y2 - y), math.sqrt(3) * 6.0, places=6)


class ProjectionTest(unittest.TestCase):
    def test_equal_area(self):
        # a 1°x1° cell at 60N and at 70N: projected area must equal the ellipsoidal area within 0.5%
        from pyproj import Geod
        geod = Geod(ellps="GRS80")
        for lat in (56, 63, 70):
            lons = [10, 11, 11, 10, 10]
            lats = [lat, lat, lat + 1, lat + 1, lat]
            true_area = abs(geod.polygon_area_perimeter(lons, lats)[0]) / 1e6
            x, y = geo.projected_from_ll(np.linspace(10, 11, 50).tolist() + [11] * 50 + np.linspace(11, 10, 50).tolist() + [10] * 50,
                                         [lat] * 50 + np.linspace(lat, lat + 1, 50).tolist() + [lat + 1] * 50 + np.linspace(lat + 1, lat, 50).tolist())
            a = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))
            self.assertLess(abs(a - true_area) / true_area, 0.005, f"lat {lat}")


class JsonStatTest(unittest.TestCase):
    def test_records_order_and_status(self):
        js = {"id": ["A", "B"], "size": [2, 2], "dimension": {
            "A": {"category": {"index": {"a1": 0, "a2": 1}}}, "B": {"category": {"index": ["b1", "b2"]}}},
            "value": [1, None, 3, 4], "status": {"1": ".."}}
        recs = list(jsonstat.records(js))
        self.assertEqual(recs[0], ({"A": "a1", "B": "b1"}, 1, None))
        self.assertEqual(recs[1], ({"A": "a1", "B": "b2"}, None, ".."))
        self.assertEqual(recs[3][0], {"A": "a2", "B": "b2"})


class HarmonisationTest(unittest.TestCase):
    def test_groups_sum_and_partial(self):
        jobs = {"01-03": 10, "05-09": None, "10-33": 5, "41-43": 2, "00-99": 99}
        out, detail, partial = admin._harmonise(jobs, admin.MAP_NO)
        self.assertEqual(out["A"], 10)
        self.assertEqual(out["BC"], 5)
        self.assertEqual(out["F"], 2)
        self.assertIn("BC", partial)
        self.assertIsNone(detail["B"])
        self.assertEqual(detail["C"], 5)

    def test_danish_nace21_mapping(self):
        self.assertEqual(admin._dk_group("C20"), ("BC", "C"))
        self.assertEqual(admin._dk_group("L"), "K")       # NACE 2.1 L = finance -> Rev.2 K
        self.assertEqual(admin._dk_group("Q"), "P")       # NACE 2.1 Q = education -> Rev.2 P
        self.assertEqual(admin._dk_group("R86"), "Q")     # health
        self.assertEqual(admin._dk_group("K62-K63"), "J")  # IT -> ICT


@unittest.skipUnless((WEB / "world.json").exists(), "built data not present")
class BuiltDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = json.loads((WEB / "world.json").read_text())
        cls.cities = json.loads((WEB / "cities.json").read_text())
        cls.lenses = json.loads((WEB / "lenses.json").read_text())

    def test_population_reconciles(self):
        self.assertLess(abs(sum(self.world["pop"]) - sum(c["population"] for c in self.cities)), 1000)

    def test_lens_packing(self):
        owned = sum(1 for o in self.world["owner"] if o >= 0)
        for l in self.lenses["lenses"]:
            self.assertEqual(len(l["values"]), owned, l["id"])

    def test_no_zero_for_missing_growth(self):
        for c in self.cities:
            if c["pop_series"].get("2016") is None:
                self.assertIsNone(c["growth"], c["name"])

    def test_capitals(self):
        caps = sorted(c["name"] for c in self.cities if c["capital"])
        self.assertEqual(caps, ["Copenhagen", "Oslo", "Stockholm"])

    def test_specialisation_rule(self):
        for c in self.cities:
            for s in c["specialisations"]:
                self.assertGreaterEqual(s["lq"], 1.5)
                self.assertGreaterEqual(s["jobs"], 250)


if __name__ == "__main__":
    unittest.main()
