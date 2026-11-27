"""Public shelters (v0.4): acquisition parsing, missing vs zero, identity, positions, municipal association, lens."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures" / "dsb_shelters"
DATA = ROOT / "web" / "data"


class ParseTest(unittest.TestCase):
    def test_fixture_parse_keeps_missing_and_zero_apart(self):
        from pipeline.sources.shelters import Shelters
        src = Shelters()
        with mock.patch.object(Shelters, "path", lambda self, rel: FIX / rel):
            out = src.process()
        rows = out["rows"]
        self.assertEqual(out["number_matched"], 3)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["places"], 400)
        self.assertIsNone(rows[1]["places"], "an empty <plasser> is 'not stated', never 0")
        self.assertEqual(rows[2]["places"], 0, "a published 0 stays 0")
        # EPSG:4258 in GML 3.2 is lat, lon: the first record is Borre (59.40 N, 10.46 E)
        self.assertAlmostEqual(rows[0]["lat"], 59.404915)
        self.assertAlmostEqual(rows[0]["lon"], 10.462108)
        self.assertEqual(rows[0]["srs"], "urn:ogc:def:crs:EPSG::4258")
        self.assertTrue(all(r["id"] and len(r["id"]) == 36 for r in rows))


@unittest.skipUnless((DATA / "shelters.json").exists(), "shelters.json not built")
class BuiltTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sh = json.loads((DATA / "shelters.json").read_text())
        cls.world = json.loads((DATA / "world.json").read_text())
        cls.cities = {c["id"]: c for c in json.loads((DATA / "cities.json").read_text())}

    def test_identity_and_completeness(self):
        rows = self.sh["shelters"]
        self.assertEqual(len(rows), self.sh["source"]["number_matched"])
        self.assertEqual(len({r["id"] for r in rows}), len(rows))

    def test_positions_are_the_published_ones(self):
        from pyproj import Transformer
        from pipeline.core.geo import NORDIC_LAEA
        tr = Transformer.from_crs("EPSG:4258", NORDIC_LAEA, always_xy=True)
        p = self.world["projection"]
        for r in self.sh["shelters"]:
            x, y = tr.transform(r["lon"], r["lat"])
            self.assertAlmostEqual(x - p["x0_km"], r["x"], delta=0.001)
            self.assertAlmostEqual(p["y1_km"] - y, r["y"], delta=0.001)

    def test_municipality_contains_record_or_is_nearest_within_limit(self):
        # independent of the build's boundary files: the shipped display polygons (munis.json, 80 m simplification)
        from shapely.geometry import Point, Polygon
        from shapely.ops import unary_union
        mj = json.loads((DATA / "munis.json").read_text())
        sc = mj["scale"]
        polys = {}
        for f in mj["features"]:
            if not f["id"].startswith("NO-"):
                continue
            shells, holes = [], []
            for ring in f["rings"]:
                xs, ys, x, y = [], [], 0, 0
                for k in range(0, len(ring), 2):
                    x += ring[k]; y += ring[k + 1]
                    xs.append(x * sc); ys.append(y * sc)
                pg = Polygon(list(zip(xs, ys))).buffer(0)
                shells.append(pg)
            polys[f["id"]] = unary_union(shells)
        for r in self.sh["shelters"]:
            d = polys[r["muni"]].distance(Point(r["x"], r["y"]))  # km
            if "assigned" in r:
                self.assertLessEqual(r["assigned"]["distance_m"], 1500)
                self.assertLess(d, 1.6, r["id"])
            else:
                self.assertLess(d, 0.25, r["id"])  # inside, up to the display simplification

    def test_aggregates_and_coverage(self):
        sh = self.sh
        self.assertEqual(sum(a["n"] for a in sh["munis"].values()), len(sh["shelters"]))
        self.assertEqual(sum(a["places"] for a in sh["munis"].values()), sh["totals"]["places"])
        self.assertEqual(sh["coverage"]["SE"]["status"], "not_integrated")
        self.assertEqual(sh["coverage"]["DK"]["status"], "not_integrated")
        self.assertTrue(all(m.startswith("NO-") for m in sh["munis"]))

    def test_lens_bands(self):
        lenses = json.loads((DATA / "lenses.json").read_text())
        lens = next(l for l in lenses["lenses"] if l["id"] == "shelter_places")
        mv = lens["muni_values"]
        for mid, v in mv.items():
            if not mid.startswith("NO-"):
                self.assertIsNone(v, mid)
            elif mid not in self.sh["munis"]:
                self.assertEqual(v, 0, mid)
            else:
                p = self.sh["munis"][mid]["places"]
                want = 4 if p >= 20000 else 3 if p >= 5000 else 2 if p >= 1000 else 1  # shelters present: never class 0
                self.assertEqual(v, want, mid)


if __name__ == "__main__":
    unittest.main()
