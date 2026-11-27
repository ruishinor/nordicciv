"""Resources, regional accounts, exchange rates and documented landmarks."""
from __future__ import annotations

import csv
import io
import json
from urllib.parse import quote

from ..core import jsonstat
from ..core.source import File, Source, SourceInfo
from .stats import _q

SSB = "https://data.ssb.no/api/pxwebapi/v2/tables"
SCB = "https://statistikdatabasen.scb.se/api/v2/tables"
DST = "https://api.statbank.dk/v1/data"
ESTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
GDP_YEAR = 2023


class RegionalAccounts(Source):
    info = SourceInfo(
        id="regional_accounts",
        title="Regional GDP from the national accounts of Norway, Sweden and Denmark, with Eurostat exchange rates and PPPs",
        publisher="SSB (tables 09391, 11713), SCB (TAB3138), DST (NRHP, INDKP101), Eurostat (ert_bil_eur_a, prc_ppp_ind, nama_10r_3gva)",
        homepage="https://ec.europa.eu/eurostat/web/national-accounts",
        license="NLOD/CC BY 4.0 (SSB), CC0 (SCB), CC BY 4.0 (DST, Eurostat)",
        description=f"Gross domestic product at current prices by county (fylke), län and landsdel for {GDP_YEAR}, "
                    "converted to euro with Eurostat annual average exchange rates and to PPS with Eurostat GDP "
                    "purchasing power parities (EU27_2020 = 1). Norway's continental shelf (oil and gas extraction, "
                    "pipeline transport) is 'extra-regio' and belongs to no county.",
        used_for=["Gold (GDP) by region", "GDP per person lens", "apportioned municipal GDP estimate"],
    )

    def files(self):
        def ssb(tab, p):
            return f"{SSB}/{tab}/data?lang=en&outputFormat=json-stat2&" + _q(p)

        def scb(tab, p):
            return f"{SCB}/{tab}/data?lang=en&outputFormat=json-stat2&" + _q(p)

        def dst(tab, p):
            return f"{DST}/{tab}/CSV?lang=en&delimiter=Semicolon&valuePresentation=Code&" + _q(p)

        return [
            File("ssb_09391_meta.json", f"{SSB}/09391/metadata?lang=en"),
            File("ssb_09391.json", ssb("09391", {"valueCodes[Region]": "*", "valueCodes[ContentsCode]": "*",
                                                 "valueCodes[Tid]": str(GDP_YEAR)})),
            File("scb_TAB3138.json", scb("TAB3138", {"valueCodes[Region]": "*",
                                                    "valueCodes[ContentsCode]": "NR0105AH,NR0105AJ,NR0105AL",
                                                    "valueCodes[Tid]": str(GDP_YEAR)})),
            File("dst_NRHP.csv", dst("NRHP", {"OMRÅDE": "*", "TRANSAKT": "B1GQD", "PRISENHED": "V_T,V_C",
                                             "Tid": str(GDP_YEAR)})),
            File("dst_INDKP101.csv", dst("INDKP101", {"OMRÅDE": "*", "ENHED": "116", "KOEN": "MOK",
                                                     "INDKOMSTTYPE": "100", "Tid": "2024"})),
            File("ert_bil_eur_a.json", f"{ESTAT}/ert_bil_eur_a?format=JSON&lang=EN&currency=NOK&currency=SEK"
                 f"&currency=DKK&statinfo=AVG&time={GDP_YEAR}&time=2024"),
            File("prc_ppp_ind.json", f"{ESTAT}/prc_ppp_ind?format=JSON&lang=EN&na_item=PPP_EU27_2020&ppp_cat=GDP"
                 f"&geo=NO&geo=SE&geo=DK&time={GDP_YEAR}"),
            # value added by industry, for the sector-weighted municipal allocation (pipeline/build/gva.py)
            File("ssb_11713_gva_industry.json", f"{SSB}/11713/data?lang=en&outputFormat=json-stat2&valueCodes[Region]=*"
                 "&valueCodes[NACE]=nr23_6,pub2X01_02,pub2X03,pub2X05,nr2X06_09,nr23ind,pub2X35,pub2X36_39,pub2X41_43,"
                 "pub2X45_47,pub2X49B,pub2X50A,pub2X49A_52,pub2X53,pub2X55_56,pub2X58_63,pub2X64_66,pub2X68A,pub2X68B,"
                 "pub2X69_75,pub2X77_82,pub2X84,pub2X85,pub2X86_88,pub2X90_97&valueCodes[ContentsCode]=BNPB"
                 f"&valueCodes[Tid]={GDP_YEAR}"),
            File("nama_10r_3gva.json", f"{ESTAT}/nama_10r_3gva?format=JSON&lang=EN&unit=CP_MEUR&time=2021&time=2022"
                 "&time=2023&geoLevel=nuts3"),
        ]

    def process(self):
        return {}


SPARQL = "https://query.wikidata.org/sparql?format=json&query="
Q_COUNTRIES = "VALUES ?country { wd:Q20 wd:Q34 wd:Q35 }"
SPARQL_WHS = f"""SELECT ?item ?itemLabel ?whs ?coord ?countryLabel ?inscribed WHERE {{
  {Q_COUNTRIES} ?item wdt:P757 ?whs; wdt:P17 ?country.
  OPTIONAL {{ ?item wdt:P625 ?coord }}
  OPTIONAL {{ ?item p:P1435 ?h. ?h ps:P1435 wd:Q9259. OPTIONAL {{ ?h pq:P580 ?inscribed }} }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,nb,sv,da". }} }}"""
SPARQL_UNI = f"""SELECT ?u ?uLabel ?countryLabel ?coord ?students ?inception ?placeLabel WHERE {{
  {Q_COUNTRIES} ?u wdt:P31 ?t. VALUES ?t {{ wd:Q3918 wd:Q875538 wd:Q902104 wd:Q15936437 }} ?u wdt:P17 ?country.
  FILTER NOT EXISTS {{ ?u wdt:P576 ?dissolved }}
  OPTIONAL {{ ?u wdt:P625 ?coord }} OPTIONAL {{ ?u wdt:P2196 ?students }} OPTIONAL {{ ?u wdt:P571 ?inception }}
  OPTIONAL {{ ?u wdt:P131 ?place }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,nb,sv,da". }} }}"""
SPARQL_PARKS = f"""SELECT ?p ?pLabel ?countryLabel ?coord ?area_m2 ?inception WHERE {{
  {Q_COUNTRIES} ?p wdt:P31 wd:Q46169; wdt:P17 ?country.
  OPTIONAL {{ ?p wdt:P625 ?coord }} OPTIONAL {{ ?p p:P2046/psn:P2046/wikibase:quantityAmount ?area_m2 }}
  OPTIONAL {{ ?p wdt:P571 ?inception }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,nb,sv,da". }} }}"""


class Wikidata(Source):
    info = SourceInfo(
        id="wikidata",
        title="Wikidata: World Heritage Sites, universities and national parks in Norway, Sweden and Denmark",
        publisher="Wikidata (Wikimedia Foundation and contributors)",
        homepage="https://www.wikidata.org/",
        license="CC0 1.0",
        description="SPARQL queries (in pipeline/sources/extra.py) for items with a UNESCO World Heritage Site ID "
                    "(P757), universities (university / public university / technical university / research "
                    "university, not dissolved) and national parks (Q46169), with coordinates, student numbers, "
                    "area and dates. Used only for the location and identity of documented landmarks; the "
                    "inclusion rule for each wonder class is published in wonders.json.",
        used_for=["wonders", "university locations"],
    )

    def files(self):
        return [File("whs.json", SPARQL + quote(SPARQL_WHS)),
                File("universities.json", SPARQL + quote(SPARQL_UNI)),
                File("national_parks_v3.json", SPARQL + quote(SPARQL_PARKS))]

    def process(self):
        return {}


FACTPAGES = ("https://factpages.sodir.no/public?/Factpages/external/tableview/{t}&rs:Command=Render&rc:Toolbar=false"
             "&rc:Parameters=f&IpAddress=not_used&CultureCode=en&rs:Format=CSV&Top100=false")
FACTMAPS = "https://factmaps.sodir.no/api/rest/services/Factmaps/FactMapsWGS84/MapServer"


class Sodir(Source):
    info = SourceInfo(
        id="sodir",
        title="Norwegian Offshore Directorate FactPages and FactMaps: oil and gas fields and production",
        publisher="Sokkeldirektoratet (Norwegian Offshore Directorate)",
        homepage="https://factpages.sodir.no/",
        license="NLOD 2.0 (Norwegian Licence for Open Government Data)",
        country="NO",
        description="Field outlines (FactMaps layer 502 'Field by status') and yearly saleable production per field "
                    "(million Sm³ oil equivalents).",
        used_for=["oil and gas resources", "petroleum production"],
    )

    def files(self):
        q = ("/502/query?where=1%3D1&outFields=fldName,fldCurrentActivitySatus,fldHcType,fldMainArea,fldNpdidField,"
             "fldDiscoveryYear,cmpLongName,fldMainSupplyBase&returnGeometry=true&maxAllowableOffset=0.01&outSR=4326&f=geojson")
        return [File("field_production_yearly.csv", FACTPAGES.format(t="field_production_yearly")),
                File("field.csv", FACTPAGES.format(t="field")),
                File("fields.geojson", FACTMAPS + q)]

    def process(self):
        return {}


SGU_API = "https://api.sgu.se/oppnadata/mineralresurser/ogc/features/v1/collections/mineralresurser/items?f=json&limit=10000"


class SGU(Source):
    info = SourceInfo(
        id="sgu",
        title="SGU Mineral resources database (mines, quarries and deposits)",
        publisher="Sveriges geologiska undersökning (Geological Survey of Sweden)",
        homepage="https://www.sgu.se/en/products-and-services/geological-data/",
        license="CC0 1.0 (SGU open data)",
        country="SE",
        description="Ore and mineral occurrences with economic status. Only entries classed 'mine/quarry' and "
                    "'deposit' are used; production status comes from the production start/end fields.",
        used_for=["mines and mineral deposits"],
    )

    def files(self):
        return [File("mines.json", SGU_API + "&filter=" + quote("e_stat_cde=1") + "&filter-lang=cql-text"),
                File("deposits.json", SGU_API + "&filter=" + quote("e_stat_cde=2") + "&filter-lang=cql-text")]

    def process(self):
        return {}


RESOURCE_SOURCES = [RegionalAccounts(), Wikidata(), Sodir(), SGU()]


SPARQL_LINKS = f"""SELECT ?x ?xLabel ?countryLabel ?coord ?length ?opened ?kind WHERE {{
  {Q_COUNTRIES} ?x wdt:P17 ?country; wdt:P2043 ?length.
  {{ ?x wdt:P31/wdt:P279* wd:Q12280. BIND("bridge" AS ?kind) }} UNION {{ ?x wdt:P31/wdt:P279* wd:Q44377. BIND("tunnel" AS ?kind) }}
  FILTER(?length >= 5000)
  OPTIONAL {{ ?x wdt:P625 ?coord }} OPTIONAL {{ ?x wdt:P1619 ?opened }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,nb,sv,da". }} }}"""


class Links(Source):
    info = SourceInfo(
        id="links",
        title="Fixed links (Wikidata) and main-port freight (Eurostat)",
        publisher="Wikidata contributors; Eurostat",
        homepage="https://www.wikidata.org/",
        license="CC0 1.0 (Wikidata); CC BY 4.0 (Eurostat)",
        description="Bridges and tunnels in Norway, Sweden and Denmark recorded with a length of at least 5 km; gross "
                    "weight of goods handled in main ports (Eurostat mar_go_aa).",
        used_for=["engineering wonders", "port size"],
    )

    def files(self):
        return [File("fixed_links.json", SPARQL + quote(SPARQL_LINKS)),
                File("mar_go_aa.json", f"{ESTAT}/mar_go_aa?format=JSON&lang=EN&direct=TOTAL&unit=THS_T&time=2024")]

    def process(self):
        return {}


RESOURCE_SOURCES.append(Links())
