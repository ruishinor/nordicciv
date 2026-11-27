"""Camera uplinks (v0.5): outbound-link safety, duplicate rule, the reviewed catalogue, the built file, and a static
guard that the app code for the layer can never load anything from a provider."""
import json
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "web" / "data"
CAT = ROOT / "pipeline" / "catalogue"

from pipeline.build.uplinks import check_url, similar  # noqa: E402


class UrlRules(unittest.TestCase):
    def test_provider_pages_accepted(self):
        self.assertIsNone(check_url("https://camstreamer.com/live/stream/5386-molde-live", "camstreamer"))
        self.assertIsNone(check_url("https://2614.panomax.com/", "panomax"))
        self.assertIsNone(check_url("https://webcamcollections.com/en/countries/sweden/ulvon", "webcamcollections"))
        self.assertIsNone(check_url("https://www.skylinewebcams.com/en/webcam/norge/western-norway/bergen/bergen.html", "skylinewebcams"))

    def test_unsafe_addresses_refused(self):
        for url, prov in [("http://camstreamer.com/live/stream/1", "camstreamer"),          # not https
                          ("https://evil.example/live/stream/1", "camstreamer"),            # another host
                          ("https://camstreamer.com.evil.example/x", "camstreamer"),         # look-alike host
                          ("https://user:pw@webcamcollections.com/en", "webcamcollections"), # credentials
                          ("https://webcamcollections.com:8443/en", "webcamcollections"),    # odd port
                          ("javascript:alert(1)", "panomax"),
                          ("https://192.168.1.20/view.html", "Some Operator"),              # raw IP
                          ("https://panomax.com/", "panomax")]:                             # not an instance page
            self.assertIsNotNone(check_url(url, prov), url)

    def test_operator_page_must_be_the_reviewed_one(self):
        self.assertIsNone(check_url("https://gaustabanen.no/en/live-updates", "Gaustabanen", "https://gaustabanen.no/en/live-updates"))
        self.assertIsNotNone(check_url("https://gaustabanen.no/other", "Gaustabanen", "https://gaustabanen.no/en/live-updates"))

    def test_duplicate_names(self):
        self.assertTrue(similar("Geiranger cruise port", "Geirangerfjord cruise port, Geiranger"))
        self.assertFalse(similar("Kristiansund – Nordlandet", "Kristiansund – Kongens plass", "Kristiansund"))
        self.assertFalse(similar("Poolviken, Varberg", "Varberg Fortress", "Varberg"))


class Catalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads((CAT / "camera_uplinks.json").read_text(encoding="utf-8"))
        cls.ver = json.loads((CAT / "camera_uplinks_verification.json").read_text(encoding="utf-8"))["results"]

    def test_reviewed_selection_is_consistent(self):
        cat = self.cat
        cats = set(cat["categories"])
        inc = cat["camstreamer"]["include"]
        self.assertFalse(set(inc) & set(cat["camstreamer"]["exclude"]), "a camera both included and excluded")
        self.assertTrue(all(r["category"] in cats for d in (inc, cat["panomax"]["include"], cat["webcamcollections"]["include"]) for r in d.values()))
        self.assertTrue(all(r["category"] in cats and re.fullmatch(r"Q\d+", r["place"]) and r["url"].startswith("https://") for r in cat["linked"]))
        self.assertTrue(all(reason.strip() for reason in cat["camstreamer"]["exclude"].values()), "every exclusion says why")
        ids = [r["id"] for r in cat["linked"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_reviewed_page_was_checked_on_its_provider_host(self):
        n = len(self.cat["camstreamer"]["include"]) + len(self.cat["panomax"]["include"]) + len(self.cat["webcamcollections"]["include"]) + len(self.cat["linked"])
        self.assertEqual(len(self.ver), n)
        for k, v in self.ver.items():
            self.assertTrue(v["ok"] and v["url"].startswith("https://") and re.fullmatch(r"\d{4}-\d\d-\d\d", v["checked"]), k)


class Built(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up = json.loads((DATA / "uplinks.json").read_text(encoding="utf-8"))
        cls.world = json.loads((DATA / "world.json").read_text())
        cls.cities = {c["id"]: c for c in json.loads((DATA / "cities.json").read_text())}

    def test_links_only(self):
        for c in self.up["cameras"]:
            self.assertFalse({"stream", "stream_url", "feed_url", "snapshot", "thumbnail", "image", "embed", "token", "player"} & set(c), c["id"])
            self.assertIsNone(check_url(c["url"], c["provider"], c["url"] if c.get("provider_name") else None), c["id"])

    def test_positions_and_municipalities(self):
        # independent of the build: the shipped display outlines (munis.json) decoded here, and pyproj directly
        from pyproj import Transformer
        from shapely.geometry import Point, Polygon
        from shapely.ops import unary_union
        from pipeline.core.geo import NORDIC_LAEA
        tr = Transformer.from_crs("EPSG:4326", NORDIC_LAEA, always_xy=True)
        p = self.world["projection"]
        mj = json.loads((DATA / "munis.json").read_text())
        sc = mj["scale"]
        polys = {}
        for f in mj["features"]:
            parts = []
            for ring in f["rings"]:
                xs, ys, x, y = [], [], 0, 0
                for k in range(0, len(ring), 2):
                    x += ring[k]; y += ring[k + 1]
                    xs.append(x * sc); ys.append(y * sc)
                parts.append(Polygon(list(zip(xs, ys))).buffer(0))
            polys[f["id"]] = unary_union(parts)
        for c in self.up["cameras"]:
            x, y = tr.transform(c["lon"], c["lat"])
            self.assertAlmostEqual(x - p["x0_km"], c["x"], delta=0.002)
            self.assertAlmostEqual(p["y1_km"] - y, c["y"], delta=0.002)
            d = polys[c["muni"]].distance(Point(c["x"], c["y"]))
            self.assertLess(d, 2.6 if "assigned" in c else 0.05, c["id"])
            self.assertEqual(self.cities[c["muni"]]["country"], c["country"])

    def test_no_duplicates(self):
        cams = self.up["cameras"]
        self.assertEqual(len({c["url"] for c in cams}), len(cams))
        for i, a in enumerate(cams):
            for b in cams[i + 1:]:
                if math.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 0.3 and a["muni"] == b["muni"]:
                    self.assertFalse(similar(a["name"], b["name"], self.cities[a["muni"]]["name"]), (a["id"], b["id"]))

    def test_coverage_spans_the_three_countries_and_landscapes(self):
        t = self.up["totals"]
        self.assertTrue(all(t["by_country"][cc] > 0 for cc in ("NO", "SE", "DK")))
        self.assertGreaterEqual(sum(1 for v in t["by_category"].values() if v), 8)


class NoProviderLoads(unittest.TestCase):
    """The layer's code may only link out. It must not create media elements, fetch remote resources or embed players."""

    def test_static_guard(self):
        for path in [ROOT / "web/js/ext/uplinks/index.js", ROOT / "web/js/render/art/uplink.js"]:
            src = path.read_text(encoding="utf-8")
            code = re.sub(r"//[^\n]*", "", src)  # comments may name what is not done
            for bad in [r"<img", r"<iframe", r"<video", r"<audio", r"<object", r"<embed", r"new Image\(", r"createElement\([\"'](img|iframe|video|audio|script|link)",
                        r"\bfetch\(", r"XMLHttpRequest", r"sendBeacon", r"EventSource", r"WebSocket", r"\.src\s*=", r"import\(\s*[\"']https?:"]:
                self.assertIsNone(re.search(bad, code), f"{path.name}: {bad}")
            if path.name == "index.js":
                self.assertIn('rel="noopener noreferrer external"', code)
                self.assertIn('referrerpolicy="no-referrer"', code)
                self.assertIn('target="_blank"', code)


if __name__ == "__main__":
    unittest.main()
