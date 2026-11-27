"""Public camera uplinks: webcams that their operators publish for anyone to watch, as outbound links only.

NordicCiv is a geographical index to these cameras, never a viewer. What is kept for a camera is its identity, a
position, its category, its provider and the address of the provider's own public viewing page. No footage, stream
address, snapshot, thumbnail, token or player is fetched, stored or shown, and nothing from a provider is loaded by
the app: a camera is reached only when the user follows the link to the provider's page.

Where the cameras come from (see pipeline/catalogue/camera_uplinks.json for the editorial selection):

  camstreamer  CamStreamer's public camera map (camstreamer.com/live/map). Each camera there is published by its
               owner, with the position the owner gave, on a public stream page. Only reviewed stream ids listed in
               the catalogue are used; anything new on the map stays out until reviewed.
  panomax      Panomax's public camera search (panomax.com). Positions are published by Panomax; every instance has
               a public viewer at <instanceId>.panomax.com. Only reviewed instance ids are used.
  webcamcollections  WebcamCollections' public webcam map (webcamcollections.com/en/map), a Swedish webcam
               publisher: positions as published on the map, a public page per camera. Reviewed pins only.
  linked       Cameras on other providers' public pages (SkylineWebcams, operators' own sites, Wikidata's
               'webcam page URL'). These pages publish no coordinates, so the camera is placed at the Wikidata
               coordinates of the place it shows (a named viewpoint, harbour, village or resort) — a place position,
               not the camera's installation, and it is labelled as such.

What is never included: traffic and road-monitoring cameras, private or residential cameras, cameras aimed at
people (shops, queues, courts, playgrounds, offices), exposed network cameras, vendor demonstrations, test streams
and unpublished endpoints. No network scanning is done to find cameras.

OSIRIS (github.com/simplifaisoul/osiris, MIT) was studied as a reference for camera discovery. Its code is MIT, but
its generated webcam lists are derived from third-party catalogues (SkylineWebcams, an index of public webcams)
whose database rights the MIT licence cannot grant, and a sample of its Norwegian positions was wrong by hundreds of
kilometres (geocoded captions). Nothing from it is imported; NordicCiv reads the providers' own public listings
and positions, and Wikidata (CC0) for places.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from ..core.source import File, Source, SourceInfo

CATALOGUE = Path(__file__).resolve().parents[1] / "catalogue" / "camera_uplinks.json"
VERIFICATION = Path(__file__).resolve().parents[1] / "catalogue" / "camera_uplinks_verification.json"

CAMSTREAMER = "https://camstreamer.com"
CAMSTREAMER_MAP = CAMSTREAMER + "/live/update-search-map?country%5B0%5D={country}"
CAMSTREAMER_HEADERS = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
PANOMAX_SEARCH = "https://www.panomax.com/api/panomax-search?sort=-1"
WCC = "https://webcamcollections.com"
WCC_MAP = WCC + "/en/map"
SPARQL = "https://query.wikidata.org/sparql?format=json&query="
COUNTRY_NAMES = {"NO": "Norway", "SE": "Sweden", "DK": "Denmark"}
COUNTRY_QID = {"NO": "Q20", "SE": "Q34", "DK": "Q35"}


def catalogue() -> dict:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))


def place_qids(cat: dict | None = None) -> list[str]:
    cat = cat or catalogue()
    return sorted({r["place"] for r in cat["linked"]}, key=lambda q: int(q[1:]))


def sparql_places(qids: list[str]) -> str:
    return ("SELECT ?item ?itemLabel ?coord ?country WHERE { VALUES ?item { " + " ".join(f"wd:{q}" for q in qids) +
            " } ?item wdt:P625 ?coord. OPTIONAL { ?item wdt:P17 ?country } "
            "SERVICE wikibase:label { bd:serviceParam wikibase:language \"nb,nn,sv,da,en\". } }")


SPARQL_WEBCAMS = ("SELECT ?item ?itemLabel ?cam ?coord ?country WHERE { VALUES ?country { wd:Q20 wd:Q34 wd:Q35 } "
                  "?item wdt:P4238 ?cam; wdt:P17 ?country. OPTIONAL { ?item wdt:P625 ?coord } "
                  "SERVICE wikibase:label { bd:serviceParam wikibase:language \"nb,nn,sv,da,en\". } }")


_WCC_CACHE: dict = {}


def wcc_pins(path) -> dict:
    """{pin url without '/countries/': pin} for the Nordic pins embedded in the map page (__NEXT_DATA__)."""
    key = str(path)
    if key not in _WCC_CACHE:
        import re
        html = Path(path).read_text(encoding="utf-8")
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            raise ValueError("webcamcollections: no __NEXT_DATA__ in the map page")
        pins = json.loads(m.group(1))["props"]["pageProps"]["mapPins"]
        _WCC_CACHE[key] = {p["url"].removeprefix("/countries/"): p for p in pins if p.get("countryCode") in ("NO", "SE", "DK")}
    return _WCC_CACHE[key]


def _point(wkt: str | None):
    """'Point(lon lat)' → (lon, lat)."""
    if not wkt or not wkt.startswith("Point("):
        return None
    lon, lat = wkt[6:-1].split()
    return float(lon), float(lat)


class CameraUplinks(Source):
    info = SourceInfo(
        id="camera_uplinks",
        title="Public camera uplinks (links to providers' public webcam pages)",
        publisher="CamStreamer (public camera map), Panomax (public camera search), SkylineWebcams and operators' own "
                  "pages (links only), Wikidata (place coordinates, CC0); selection by NordicCiv",
        homepage="https://camstreamer.com/live/map",
        license="Facts and links only: names, positions and page addresses as each provider publishes them, with "
                "attribution; Wikidata CC0. No camera images or streams are copied.",
        country="ALL",
        description="Webcams their operators publish for anyone to watch, in Norway, Sweden and Denmark, kept as a "
                    "name, a position, a category, a provider and the provider's public viewing page. NordicCiv links "
                    "out to the provider and never loads, copies or relays the camera's pictures.",
        used_for=["Camera uplinks map layer", "municipality panel: camera uplinks", "Discover"],
    )

    def files(self):
        cat = catalogue()
        out = [File(f"camstreamer_{cc}.json", CAMSTREAMER_MAP.format(country=COUNTRY_NAMES[cc]), headers=CAMSTREAMER_HEADERS)
               for cc in ("NO", "SE", "DK")]
        out.append(File("panomax_search.json", PANOMAX_SEARCH))
        out.append(File("webcamcollections_map.html", WCC_MAP))
        out.append(File("wikidata_webcams.json", SPARQL + quote(SPARQL_WEBCAMS)))
        out.append(File("wikidata_places.json", SPARQL + quote(sparql_places(place_qids(cat)))))
        return out

    def process(self):
        """Every reviewed camera with its published (or place) position, exactly as the providers list them."""
        cat = catalogue()
        rows, missing = [], []

        # CamStreamer: owner-published positions
        cs = {}
        for cc in ("NO", "SE", "DK"):
            for v in json.loads(self.path(f"camstreamer_{cc}.json").read_text(encoding="utf-8")).get("videos", []):
                link = v.get("detail_link") or ""
                sid = link.split("/")[-1].split("-")[0] if link.startswith("/live/stream/") else None
                if sid:
                    cs[sid] = {**v, "_country": cc}
        for sid, rec in cat["camstreamer"]["include"].items():
            v = cs.get(sid)
            if v is None:
                missing.append(f"camstreamer {sid}")
                continue
            rows.append({
                "key": f"camstreamer:{sid}", "provider": "camstreamer", "listed_name": v.get("name"),
                "url": CAMSTREAMER + v["detail_link"], "lon": float(v["lng"]), "lat": float(v["lat"]),
                "position": "published", "listed_country": v["_country"], **rec,
            })
        # Panomax: provider-published positions
        pm = {str(x["instanceId"]): x for x in json.loads(self.path("panomax_search.json").read_text(encoding="utf-8"))["data"]}
        for iid, rec in cat["panomax"]["include"].items():
            x = pm.get(iid)
            if x is None:
                missing.append(f"panomax {iid}")
                continue
            rows.append({
                "key": f"panomax:{iid}", "provider": "panomax", "listed_name": x.get("instanceName"),
                "url": f"https://{iid}.panomax.com/", "lon": float(x["camLongitude"]), "lat": float(x["camLatitude"]),
                "position": "published", "listed_country": x.get("countryCode", "").upper(), **rec,
            })
        # WebcamCollections: positions published on its map (the page's embedded Next.js data)
        for pin_url, rec in cat["webcamcollections"]["include"].items():
            p = wcc_pins(self.path("webcamcollections_map.html")).get(pin_url)
            if p is None:
                missing.append(f"webcamcollections {pin_url}")
                continue
            pos = (p.get("media") or {}).get("position") or {}
            rows.append({
                "key": f"webcamcollections:{pin_url}", "provider": "webcamcollections", "listed_name": p.get("title"),
                "url": f"{WCC}/en/countries/{pin_url}", "lon": float(pos["long"]), "lat": float(pos["lat"]),
                "position": "published", "listed_country": p.get("countryCode"), **rec,
            })
        # Linked pages without coordinates: the Wikidata place they show
        places = {}
        for b in json.loads(self.path("wikidata_places.json").read_text(encoding="utf-8"))["results"]["bindings"]:
            q = b["item"]["value"].rsplit("/", 1)[-1]
            p = _point(b.get("coord", {}).get("value"))
            if p and q not in places:  # an item with several coordinates: the first (Wikidata's preferred order)
                places[q] = {"lon": p[0], "lat": p[1], "label": b.get("itemLabel", {}).get("value"),
                             "country": b.get("country", {}).get("value", "").rsplit("/", 1)[-1]}
        for rec in cat["linked"]:
            p = places.get(rec["place"])
            if p is None:
                missing.append(f"wikidata place {rec['place']} ({rec['name']})")
                continue
            rows.append({"key": f"linked:{rec['id']}", "lon": p["lon"], "lat": p["lat"], "position": "place",
                         "place_label": p["label"], "place_country": p["country"], **rec})
        # Wikidata 'webcam page URL' (P4238): read so the build can show which ones the catalogue uses
        wd = []
        for b in json.loads(self.path("wikidata_webcams.json").read_text(encoding="utf-8"))["results"]["bindings"]:
            wd.append({"item": b["item"]["value"].rsplit("/", 1)[-1], "label": b.get("itemLabel", {}).get("value"),
                       "url": b["cam"]["value"], "coord": b.get("coord", {}).get("value")})
        listed = {"camstreamer": len(cs), "webcamcollections_nordic": len(wcc_pins(self.path("webcamcollections_map.html"))), "panomax_nordic": sum(1 for x in pm.values() if x.get("countryCode") in ("no", "se", "dk")),
                  "wikidata_webcam_items": len(wd)}
        return {"rows": rows, "missing": missing, "listed": listed, "wikidata_webcams": wd,
                "requests": {f.rel_path: f.url for f in self.files()}}
