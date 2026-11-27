"""Public civil-defence shelters (Norway): DSB 'Tilfluktsrom – Offentlige' through Kartverket's WFS.

Only the *public* shelter register is used. Private shelters (in housing, schools, workplaces), military facilities
and anything not in DSB's public dataset are not included and are never inferred. Sweden and Denmark are recorded as
'not integrated' (see COVERAGE): their systems are classified differently, and no openly licensed national dataset
of the same kind was found when this source was added (2026-11-27).
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from ..core.source import File, Source, SourceInfo

WFS = "https://wfs.geonorge.no/skwms1/wfs.tilfluktsrom_offentlige?"
GETFEATURE = WFS + "service=WFS&version=2.0.0&request=GetFeature&typeNames=app:Tilfluktsrom&srsName=urn:ogc:def:crs:EPSG::4258"
NS = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml/3.2",
      "app": "http://skjema.geonorge.no/SOSI/produktspesifikasjon/TilfluktsromOffentlige/20191001"}
DATASET_URL = "https://data.norge.no/nb/datasets/17dc5b4a-ac2c-396d-8490-c0b961d6e8da/tilfluktsrom-offentlige"
GUIDANCE_URL = "https://www.dsb.no/sikkerhverdag/egenberedskap/verdt-a-vite-om-tilfluktsrom/"
MAP_URL = "https://dsb--gis.maps.arcgis.com/apps/instant/nearby/index.html?appid=db2340bc3f9a4fefbe64d62d811fb639"

COVERAGE = {
    "NO": {"status": "integrated", "dataset": "DSB – Tilfluktsrom – Offentlige (public shelters only)"},
    "SE": {"status": "not_integrated",
           "reason": "Sweden's register (Myndigheten för civilt försvar) covers about 64,000 shelters, which in war are "
                     "open to anyone nearby; it is published as a map, but no openly licensed dataset with redistribution "
                     "terms was found. The Swedish and Norwegian classifications also differ (Sweden has no separate "
                     "'public' class), so the two would not be comparable."},
    "DK": {"status": "not_integrated",
           "reason": "Denmark has no published national dataset of public shelter locations; a national inspection of "
                     "public shelters (betondækningsgrave) ran in 2025–26, and the results have not been released as open data."},
}


class Shelters(Source):
    info = SourceInfo(
        id="dsb_shelters",
        title="Tilfluktsrom – Offentlige (public shelters)",
        publisher="Direktoratet for samfunnssikkerhet og beredskap (DSB); WFS hosted by Kartverket (Geonorge)",
        homepage=DATASET_URL,
        license="NLOD 1.0 (Norwegian Licence for Open Government Data)",
        country="NO",
        description="Public civil-defence shelters in Norway: position (ETRS89), shelter room number, registered places "
                    "(plasser) and the published address/description. Public shelters only: private shelters, which make "
                    "up most of Norway's shelter places, are not in this dataset.",
        used_for=["public shelters layer", "municipal shelter summary", "Council: civil preparedness notes"],
    )

    def files(self):
        return [File("tilfluktsrom_4258.gml", GETFEATURE),
                File("capabilities.xml", WFS + "request=GetCapabilities&service=WFS"),
                File("describe_feature_type.xsd", WFS + "service=WFS&version=2.0.0&request=DescribeFeatureType&typeNames=app:Tilfluktsrom"),
                File("hits.xml", WFS + "service=WFS&version=2.0.0&request=GetFeature&typeNames=app:Tilfluktsrom&resultType=hits")]

    def process(self):
        root = ET.parse(self.path("tilfluktsrom_4258.gml")).getroot()
        hits = ET.parse(self.path("hits.xml")).getroot().get("numberMatched")
        rows = []
        for m in root.findall("wfs:member", NS):
            t = m.find("app:Tilfluktsrom", NS)

            def g(p):
                e = t.find(p, NS)
                return e.text.strip() if e is not None and e.text is not None else None

            pt = t.find("app:posisjon/gml:Point", NS)
            pos = g("app:posisjon/gml:Point/gml:pos")
            lat, lon = (float(v) for v in pos.split()) if pos else (None, None)  # EPSG:4258 axis order: lat, lon
            places = g("app:plasser")
            rows.append({
                "id": g("app:identifikasjon/app:Identifikasjon/app:lokalId"),
                "namespace": g("app:identifikasjon/app:Identifikasjon/app:navnerom"),
                "version": g("app:identifikasjon/app:Identifikasjon/app:versjonId"),
                "room": int(g("app:romnr")) if g("app:romnr") not in (None, "") else None,
                "places": int(places) if places not in (None, "") else None,  # missing stays None, never 0
                "address": g("app:adresse"),
                "lat": lat, "lon": lon, "srs": pt.get("srsName") if pt is not None else None,
                "extracted": g("app:datauttaksdato"),
                "origin": g("app:opphav"),
            })
        return {"rows": rows, "number_matched": int(hits) if hits and hits.isdigit() else None,
                "timestamp": root.get("timeStamp"), "request": GETFEATURE}
