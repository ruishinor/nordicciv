"""uplinks.json: public camera uplinks — outbound links to webcams their operators publish, placed on the map.

What it is: the reviewed catalogue (pipeline/catalogue/camera_uplinks.json), with each camera's position as its
provider publishes it (or, for pages without coordinates, the Wikidata coordinates of the place the camera shows),
transformed into the map frame; the municipality whose shipped outline (web/data/munis.json, the outline the map
draws and selects) contains it; and the date its public page was last checked.

What it is not: a list of live cameras, a mirror of any provider's catalogue, or anything about the pictures. No
footage, still image, thumbnail, stream address, token or player is fetched or stored; the app loads nothing from a
provider and only opens the provider's page in a new tab when the user asks.

Rules (each a build error, never silently repaired):
  * outbound URLs must be https, carry no credentials, and belong to the provider's own host;
  * a published position must lie in the country the provider lists and in, or within MAX_NEAREST_M of, a
    municipality of that country (coastal cameras on piers can sit just outside the simplified outline; the
    distance is kept);
  * no two records may be the same camera (same page, or within DUP_M of each other with similar names);
  * a camera whose page did not verify (pipeline/catalogue/camera_uplinks_verification.json) is left out and
    reported, never published with a stale page.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import date
from urllib.parse import urlsplit

import numpy as np
import shapely
from pyproj import Geod, Transformer
from shapely.geometry import Point, Polygon

from ..core import geo
from ..core.fetch import read_manifest
from ..core.paths import INTERIM, WEB_DATA
from ..core.store import read_json, write_json
from ..sources.uplinks import CATALOGUE, VERIFICATION, catalogue

MAX_NEAREST_M = 2500  # a published position this far outside every outline of its country is an error
DUP_M = 300  # two cameras closer than this with similar names are the same camera
MAX_VERIFY_AGE_DAYS = 120  # a page check older than this does not count as verified
PROVIDER_HOSTS = {
    "camstreamer": re.compile(r"^camstreamer\.com$"),
    "panomax": re.compile(r"^\d+\.panomax\.com$"),
    "webcamcollections": re.compile(r"^webcamcollections\.com$"),
    "skylinewebcams": re.compile(r"^www\.skylinewebcams\.com$"),
}
SHORT = {"camstreamer": "cs", "panomax": "pm", "webcamcollections": "wcc", "linked": "ln"}
_TO_MAP = Transformer.from_crs("EPSG:4326", geo.NORDIC_LAEA, always_xy=True)
_GEOD = Geod(ellps="GRS80")


def shipped_outlines(munis: dict) -> dict:
    """{muni id: (shapely geometry, area km²)} from munis.json level-0 rings (map km, y down)."""
    sc = munis["scale"]
    out = {}
    for f in munis["features"]:
        parts = []
        for ring in f["rings"]:
            a = np.cumsum(np.asarray(ring, dtype=np.int64).reshape(-1, 2), axis=0) * sc
            if len(a) >= 3:
                parts.append(Polygon(a).buffer(0))
        if parts:
            g = shapely.union_all(parts)
            out[f["id"]] = (g, g.area)
    return out


def check_url(url: str, provider: str, catalogue_url: str | None = None) -> str | None:
    """None when the outbound URL is acceptable, else the reason."""
    try:
        u = urlsplit(url)
    except ValueError:
        return "unparseable"
    if u.scheme != "https":
        return "not https"
    if u.username or u.password or "@" in u.netloc:
        return "credentials in URL"
    if u.port not in (None, 443):
        return "non-standard port"
    host = u.hostname or ""
    if re.fullmatch(r"[\d.]+|\[[0-9a-f:]+\]", host):
        return "raw IP address"
    pat = PROVIDER_HOSTS.get(provider)
    if pat is not None:
        return None if pat.match(host) else f"host {host} is not {provider}'s"
    # an operator's own page: exactly the reviewed address
    return None if catalogue_url == url else "operator URL differs from the reviewed catalogue"


def _tokens(s: str) -> set:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    stop = {"the", "of", "live", "webcam", "webkamera", "webbkamera", "camera", "cam", "view", "from", "norway",
            "sweden", "denmark", "and", "og", "och", "og", "i", "in"}
    return {t for t in re.findall(r"[a-z0-9]+", s) if len(t) > 2 and t not in stop}


def similar(a: str, b: str, common: str = "") -> bool:
    """Names that describe the same view: half the distinctive words shared. Words of the municipality name both
    sit in (`common`) are not distinctive: 'Kristiansund – Nordlandet' and 'Kristiansund – Kongens plass' differ."""
    skip = _tokens(common)
    ta, tb = _tokens(a) - skip, _tokens(b) - skip
    if not ta or not tb:
        return _tokens(a) == _tokens(b)
    return len(ta & tb) / min(len(ta), len(tb)) >= 0.5


def build():
    src = read_json(INTERIM / "camera_uplinks.json")
    cat = catalogue()
    ver = read_json(VERIFICATION)["results"] if VERIFICATION.exists() else {}
    world = read_json(WEB_DATA / "world.json")
    cities = {c["id"]: c for c in read_json(WEB_DATA / "cities.json")}
    outlines = shipped_outlines(read_json(WEB_DATA / "munis.json"))
    ids = list(outlines)
    tree = shapely.STRtree([outlines[k][0] for k in ids])
    g = world["grid"]
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    if src.get("missing"):
        raise SystemExit("uplinks: reviewed cameras no longer listed by their provider:\n  " + "\n  ".join(src["missing"]))
    linked_urls = {r["id"]: r["url"] for r in cat["linked"]}
    today = date.today()

    out, problems, unverified = [], [], []
    for r in src["rows"]:
        prov = r["provider"]
        sid = SHORT["linked" if r["key"].startswith("linked:") else prov] + "-" + re.sub(r"[^a-z0-9]+", "-", r["key"].split(":", 1)[1].lower()).strip("-")
        why = check_url(r["url"], prov, linked_urls.get(r.get("id")))
        if why:
            problems.append(f"{r['key']}: {r['url']}: {why}")
            continue
        v = ver.get(r["key"])
        if not v or not v.get("ok") or v.get("url") != r["url"] or (today - date.fromisoformat(v["checked"])).days > MAX_VERIFY_AGE_DAYS:
            unverified.append(f"{r['key']} ({'not checked' if not v else 'page check failed: ' + str(v.get('status')) if not v.get('ok') else 'URL changed or check too old'})")
            continue
        x, y = _TO_MAP.transform(r["lon"], r["lat"])
        mx, my = x - frame.x0, frame.y1 - y
        p = Point(mx, my)
        hit = [ids[j] for j in tree.query(p, predicate="within")]
        dist_m, how = 0, "inside"
        if hit:
            muni = min(hit, key=lambda k: outlines[k][1])  # an enclave inside another outline belongs to the enclave
        else:
            j = int(tree.nearest(p))
            muni = ids[j]
            dist_m = round(outlines[muni][0].distance(p) * 1000)
            how = "nearest"
        c = cities.get(muni)
        if c is None:
            problems.append(f"{r['key']}: municipality {muni} not in cities.json")
            continue
        listed = r.get("listed_country") or r.get("place_country_code")
        if r["position"] == "published" and listed and listed != c["country"]:
            problems.append(f"{r['key']}: listed in {listed} but positioned in {c['country']} ({c['name']})")
        if r["position"] == "place":
            want = {"Q20": "NO", "Q34": "SE", "Q35": "DK"}.get(r.get("place_country"))
            if want != c["country"]:
                problems.append(f"{r['key']}: Wikidata place {r['place']} is in {r.get('place_country')} but falls in {c['country']}")
        if dist_m > MAX_NEAREST_M:
            problems.append(f"{r['key']}: {dist_m} m outside every municipality (nearest {muni})")
        rec = {
            "id": sid, "name": r["name"], "cat": r["category"], "provider": prov, "url": r["url"],
            "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
            "x": round(float(mx), 3), "y": round(float(my), 3),
            "cell": int(geo.cell_at(np.array([mx]), np.array([my]), g["radius"], g["cols"], g["rows"])[0]),
            "muni": muni, "country": c["country"], "pos": r["position"], "verified": v["checked"],
        }
        if r["position"] == "place":
            rec["place"] = {"qid": r["place"], "label": r.get("place_label")}
        if prov not in cat["providers"]:
            rec["provider_name"] = prov  # an operator's own page: the operator is the provider
        if how == "nearest":
            rec["assigned"] = {"method": "nearest municipality outline", "distance_m": dist_m}
        out.append(rec)

    # duplicates: same page, same id, or the same spot under a similar name
    seen_url, seen_id = {}, {}
    for rec in out:
        for key, seen in ((rec["url"], seen_url), (rec["id"], seen_id)):
            if key in seen:
                problems.append(f"duplicate {key}: {seen[key]} and {rec['id']}")
            seen[key] = rec["id"]
    xy = np.array([[r["x"], r["y"]] for r in out])
    for i in range(len(out)):
        d = np.hypot(*(xy[i + 1:] - xy[i]).T) * 1000
        for j in np.nonzero(d < DUP_M)[0] + i + 1:
            common = cities[out[i]["muni"]]["name"] if out[i]["muni"] == out[j]["muni"] else ""
            if similar(out[i]["name"], out[j]["name"], common):
                problems.append(f"possible duplicate: {out[i]['id']} '{out[i]['name']}' and {out[j]['id']} '{out[j]['name']}' ({d[j - i - 1]:.0f} m)")
    if problems:
        raise SystemExit("uplinks: catalogue errors:\n  " + "\n  ".join(problems))

    out.sort(key=lambda r: (r["country"], r["muni"], r["name"]))
    by_muni = defaultdict(list)
    for r in out:
        by_muni[r["muni"]].append(r["id"])
    man = read_manifest("camera_uplinks")["files"]
    data = {
        "version": 1,
        "about": "Public camera uplinks: webcams their operators publish for anyone to watch. NordicCiv lists where "
                 "they are and links to the provider's own page; it never loads, copies or relays their pictures.",
        "policy": cat["policy"],
        "reviewed": cat["reviewed"],
        "categories": cat["categories"],
        "providers": {k: {kk: vv for kk, vv in v.items()} for k, v in cat["providers"].items()},
        "sources": {
            "lists": {k: {"url": man[k]["url"], "retrieved": man[k]["retrieved"], "sha256": man[k]["sha256"]}
                      for k in sorted(man)},
            "places": "Wikidata (CC0): coordinates of the place shown, for pages that publish none",
            "attribution": "Camera names, positions and pages as published by CamStreamer and the camera owners, "
                           "Panomax, WebcamCollections, SkylineWebcams and the operators named on each camera; "
                           "place coordinates from Wikidata (CC0). Pictures belong to their publishers and are not "
                           "reproduced here.",
            "reference": "OSIRIS (github.com/simplifaisoul/osiris, MIT) was studied for camera discovery; none of its "
                         "data is used (see docs/SOURCES.md).",
        },
        "meaning": {
            "status": "Listed is not live: whether a camera is working is only known on the provider's page.",
            "position": "Published positions are where the provider puts the camera; place positions mark the place a "
                        "page shows. The symbol marks a public viewpoint, not the camera's installation.",
            "verified": "Date the provider's public page last answered as a working page (not the camera stream).",
            "absence": "No uplink in a municipality means none was found or reviewed, not that none exists.",
        },
        "cameras": out,
        "munis": {m: {"n": len(v), "ids": v} for m, v in sorted(by_muni.items())},
        "totals": {"cameras": len(out), "by_country": {cc: sum(1 for r in out if r["country"] == cc) for cc in ("NO", "SE", "DK")},
                   "by_category": {k: sum(1 for r in out if r["cat"] == k) for k in cat["categories"]},
                   "by_provider": {k: sum(1 for r in out if r["provider"] == k) for k in sorted({r["provider"] for r in out})},
                   "munis": len(by_muni), "place_positions": sum(1 for r in out if r["pos"] == "place"),
                   "assigned_nearest": sum(1 for r in out if "assigned" in r), "unverified_left_out": len(unverified)},
        "left_out_unverified": unverified,
    }
    write_json(WEB_DATA / "uplinks.json", data)
    t = data["totals"]
    print(f"    {t['cameras']} camera uplinks ({t['by_country']}) in {t['munis']} municipalities; "
          f"{t['place_positions']} at place positions; {len(unverified)} left out (page not verified)")
    for u in unverified:
        print(f"      left out: {u}")
