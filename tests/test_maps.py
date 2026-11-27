"""Opening screen and "Open in Maps" (v0.5): projection, URL building, version wiring and static privacy guards.

Runs web/js/util/geo.js and web/js/app/maps.js in Node (tests/maps_urls.mjs) on the shipped data and checks them against
pyproj and Google's documented Maps URL format (https://developers.google.com/maps/documentation/urls/get-started).
"""
import json
import random
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WEB = ROOT / "web"


def run_node(points):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node not installed")
    out = subprocess.run([node, str(ROOT / "tests" / "maps_urls.mjs")], input=json.dumps(points), capture_output=True, text=True, timeout=60)
    if out.returncode:
        raise AssertionError(out.stderr[-2000:])
    return json.loads(out.stdout)


def parse(url):
    u = urlsplit(url)
    return u, {k: v[0] for k, v in parse_qs(u.query, keep_blank_values=True).items()}


class Maps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pyproj import Transformer
        from pipeline.core import geo
        cls.world = json.loads((WEB / "data" / "world.json").read_text())
        p = cls.world["projection"]
        random.seed(5)
        cls.pts = [(random.uniform(0, cls.world["width"]), random.uniform(0, cls.world["height"])) for _ in range(500)]
        cls.out = run_node(cls.pts)
        cls.to_geo = Transformer.from_crs(geo.NORDIC_LAEA, "EPSG:4326", always_xy=True)
        cls.x0, cls.y1 = p["x0_km"], p["y1_km"]

    def geo(self, x, y):
        return self.to_geo.transform(x + self.x0, self.y1 - y)  # lon, lat

    def test_inverse_projection_matches_pyproj(self):
        worst = rt = 0
        for (x, y), (lon, lat, bx, by) in zip(self.pts, self.out["inverse"]):
            plon, plat = self.geo(x, y)
            worst = max(worst, abs(plon - lon), abs(plat - lat))
            rt = max(rt, abs(bx - x), abs(by - y))
        self.assertLess(worst, 1e-7, "map → lon/lat differs from pyproj")  # ≈ 1 cm
        self.assertLess(rt, 1e-6, "lon/lat → map round trip")

    def test_url_formats(self):
        for k, t in self.out["targets"].items():
            if t is None:
                continue
            u, q = parse(t["url"])
            self.assertEqual((u.scheme, u.netloc), ("https", "www.google.com"), k)
            self.assertEqual(q.get("api"), "1", k)
            self.assertNotIn(",", u.query, f"{k}: commas must be encoded as %2C")
            self.assertLessEqual(len(t["url"]), 2048, k)
            if t.get("pin"):
                self.assertEqual(u.path, "/maps/search/", k)
                self.assertEqual(set(q), {"api", "query"}, k)
                lat, lon = map(float, q["query"].split(","))
            else:
                self.assertEqual(u.path, "/maps/@", k)
                self.assertEqual(set(q), {"api", "map_action", "center", "zoom", "basemap"}, k)
                self.assertEqual((q["map_action"], q["basemap"]), ("map", "satellite"), k)
                lat, lon = map(float, q["center"].split(","))
                self.assertTrue(0 <= int(q["zoom"]) <= 21, k)
            # latitude first, in Scandinavia
            self.assertTrue(54 < lat < 72 and 4 < lon < 32, f"{k}: {lat},{lon} not in Scandinavia (order?)")
            self.assertAlmostEqual(lat, t["lat"], places=5)
            self.assertAlmostEqual(lon, t["lon"], places=5)

    def test_positions_are_the_features_own(self):
        T, S = self.out["targets"], self.out["sources"]
        for k, a in S["airports"].items():  # map km → WGS84, as pyproj does it
            lon, lat = self.geo(a["x"], a["y"])
            t = {"EKCH": T["airport_cph"], "ESSA": T["airport_arn"], "ENGM": T["airport_osl"]}[k]
            self.assertAlmostEqual(t["lat"], lat, places=6)
            self.assertAlmostEqual(t["lon"], lon, places=6)
        self.assertAlmostEqual(T["airport_cph"]["lat"], 55.618, delta=0.01)  # Kastrup
        self.assertAlmostEqual(T["airport_cph"]["lon"], 12.656, delta=0.01)
        self.assertAlmostEqual(T["airport_osl"]["lat"], 60.194, delta=0.01)  # Gardermoen
        lon, lat = self.geo(S["port_bergen"]["x"], S["port_bergen"]["y"])
        self.assertAlmostEqual(T["port_bergen"]["lat"], lat, places=6)
        for k in ("cam_published", "cam_place"):
            self.assertEqual((T[k]["lat"], T[k]["lon"]), (S[k]["lat"], S[k]["lon"]), k)
        self.assertEqual((T["park"]["lat"], T["park"]["lon"]), (S["park"]["lat"], S["park"]["lon"]))
        cities = {c["id"]: c for c in json.loads((WEB / "data" / "cities.json").read_text())}
        self.assertEqual((T["town_copenhagen"]["lat"], T["town_copenhagen"]["lon"]), (cities["DK-101"]["lat"], cities["DK-101"]["lon"]))

    def test_behaviour_and_zoom_by_kind(self):
        T = self.out["targets"]
        z = {k: int(parse(t["url"])[1].get("zoom", -1)) for k, t in T.items() if t and not t.get("pin")}
        # areas: whole extent, bigger areas further out; never a town close-up
        self.assertLess(z["muni_kiruna"], z["muni_stranda"])
        self.assertLess(z["muni_stranda"], z["muni_copenhagen"])
        self.assertTrue(8 <= z["muni_kiruna"] <= 9 and 10 <= z["muni_copenhagen"] <= 12 and z["muni_frederiksberg"] >= 12, z)
        self.assertLessEqual(z["region_more"], 8)
        self.assertTrue(8 <= z["park"] <= 13)
        # towns at town or city scale; a municipality without a named settlement has none
        self.assertEqual((z["town_copenhagen"], z["town_stockholm"], z["town_tromso"]), (12, 12, 13))
        self.assertIsNone(T["town_none"])
        # points: a landmark close up; cameras close where the position is published, wider where it is only a place
        self.assertEqual((z["landmark"], z["cam_published"], z["cam_place"]), (15, 16, 14))
        self.assertIn("not published", T["cam_place"]["what"])
        # marked: airports and campuses use the coordinate search (a pin), everything else is an unmarked view
        self.assertTrue(T["airport_cph"]["pin"] and T["campus"]["pin"])
        self.assertTrue(all(not T[k].get("pin") for k in z))

    def test_invalid_input(self):
        self.assertTrue(all(u is None for u in self.out["invalid"]), self.out["invalid"])
        zs = [parse(u)[1]["zoom"] for u in self.out["zoomClamp"]]
        self.assertEqual(zs, ["21", "0", "15"])
        self.assertIsNone(self.out["noProjection"], "without the projection no position is guessed")
        self.assertEqual(self.out["linkNone"], "", "no link without a valid position")

    def test_link_markup(self):
        a = self.out["link"]
        for attr in ('target="_blank"', 'rel="noopener noreferrer external"', 'referrerpolicy="no-referrer"', ">Open in Maps "):
            self.assertIn(attr, a)
        self.assertNotIn("<img", self.out["escaped"])
        self.assertIn("&lt;img", self.out["escaped"])


class OpeningAndVersion(unittest.TestCase):
    def test_version_file_is_the_repository_version(self):
        from pipeline.build.version import read_version
        v = json.loads((WEB / "data" / "version.json").read_text())
        self.assertEqual(v, {"version": read_version()})
        self.assertEqual(read_version(), (ROOT / "VERSION").read_text().strip())

    def test_opening_markup(self):
        html = (WEB / "index.html").read_text()
        self.assertIn('id="opening"', html)
        self.assertLess(html.index('src="js/opening.js"'), html.index('src="js/main.js"'), "opening.js must run before the app's code arrives")
        for el in ('<header id="topbar" inert', '<canvas id="map" inert', '<div id="lens-area" inert', 'id="mobile-nav" class="panel mobile-nav" aria-label="Main" inert',
                   '<div id="minimap-wrap" class="panel" inert', '<button id="btn-minimap" inert'):
            self.assertIn(el, html, "the app is inert until the first map frame")
        self.assertNotRegex(html, r"0\.\d+\.\d+", "no hard-coded version in the page (it comes from version.json)")
        self.assertIn("connect-src 'self'", html)
        self.assertNotRegex(html, r"(src|href)=\"https?://", "no external resource on the page")
        js = (WEB / "js" / "opening.js").read_text()
        for msg in ("Loading the landscape…", "Loading cities and settlements…", "Loading population and economy…", "Preparing the map…", "Ready to explore."):
            self.assertIn(msg, js)
        self.assertNotRegex(js, r"setTimeout\([^)]*\b(1[5-9]\d\d|[2-9]\d{3})\b\s*\)\s*;?\s*//.*hold", "no hold-open delay")
        self.assertNotRegex(js.lower(), r"verif|authentic|trustworth|calibrat|intelligence|secure", "no clinical or intelligence wording")
        css = (WEB / "css" / "style.css").read_text()
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)

    def test_no_map_service_is_loaded(self):
        """Google Maps appears only as link targets built in app/maps.js: no API, script, tiles, embed or iframe."""
        hits = []
        for p in (WEB / "js").rglob("*.js"):
            t = p.read_text()
            if re.search(r"maps\.googleapis|maps\.gstatic|googleusercontent|<iframe|google\.com/maps/embed|geolocation", t):
                hits.append(str(p.relative_to(WEB)))
            if "google.com/maps" in t and p.name != "maps.js":
                hits.append(f"{p.relative_to(WEB)}: builds a Maps URL outside app/maps.js")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
