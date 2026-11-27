"""Official statistics: Statistics Norway (SSB), Statistics Sweden (SCB), Statistics Denmark (DST), Eurostat.

All requests are plain public API calls without keys. Reference periods are chosen so the three countries line
up: employment refers to November / Q4 2024 in all three; population is 1 January (Sweden: 31 December of the
previous year, which is the same moment).
"""
from __future__ import annotations

import csv
import io
import json
import re
from urllib.parse import quote

from ..core import jsonstat
from ..core.source import File, Source, SourceInfo

YEARS = list(range(2008, 2027))  # population series, 1 January
EMP_YEAR = 2024


def _q(params: dict) -> str:
    parts = []
    for k, v in params.items():
        for item in (v if isinstance(v, list) else [v]):
            parts.append(f"{quote(k, safe='[]')}={quote(str(item), safe='*,')}")
    return "&".join(parts)


# --------------------------------------------------------------------------------------------------------- SSB --
SSB = "https://data.ssb.no/api/pxwebapi/v2/tables"


class SSB_(Source):
    info = SourceInfo(
        id="ssb",
        title="Statistics Norway (SSB) StatBank: population, area, employment by place of work, household income",
        publisher="Statistisk sentralbyrå (Statistics Norway)",
        homepage="https://www.ssb.no/en/statbank",
        license="NLOD 2.0 / CC BY 4.0 (Statistics Norway)",
        country="NO",
        description="Tables 07459 (population 1 January by age, municipalities 2024 boundaries with aggregated time "
                    "series), 09280 (land and freshwater area), 07984 (employed persons 4th quarter by place of work "
                    "and industry, SIC2007 17 groups), 06944 (median household income after tax), 08585 (students by "
                    "institution).",
        used_for=["municipal population and growth", "age structure", "land area", "jobs by industry (yields)",
                  "income lens", "university size"],
    )

    def files(self):
        def url(tab, p):
            return f"{SSB}/{tab}/data?lang=en&outputFormat=json-stat2&" + _q(p)

        return [
            File("07459_pop_age.json", url("07459", {
                "valueCodes[Region]": "*", "codelist[Region]": "agg_KommSummer",
                "valueCodes[Alder]": "*", "codelist[Alder]": "agg_TredeltGrupperingB2",
                "valueCodes[Tid]": ",".join(map(str, YEARS)), "valueCodes[ContentsCode]": "Personer1"})),
            File("07459_pop_country.json", url("07459", {
                "valueCodes[Region]": "0", "valueCodes[Tid]": ",".join(map(str, YEARS)),
                "valueCodes[ContentsCode]": "Personer1"})),
            File("09280_area.json", url("09280", {
                "valueCodes[Region]": "*", "codelist[Region]": "agg_KommSummer", "valueCodes[Arealtype]": "*",
                "valueCodes[Tid]": "2026", "valueCodes[ContentsCode]": "Areal1"})),
            File("07984_employment.json", url("07984", {
                "valueCodes[Region]": "*", "codelist[Region]": "agg_KommSummerS", "valueCodes[NACE2007]": "*",
                "valueCodes[Kjonn]": "0", "valueCodes[Alder]": "15-74",
                "valueCodes[ContentsCode]": "SysselsatteArb,Sysselsatte", "valueCodes[Tid]": str(EMP_YEAR)})),
            File("07984_employment_country.json", url("07984", {
                "valueCodes[Region]": "0", "valueCodes[NACE2007]": "*", "valueCodes[Kjonn]": "0",
                "valueCodes[Alder]": "15-74", "valueCodes[ContentsCode]": "SysselsatteArb,Sysselsatte",
                "valueCodes[Tid]": str(EMP_YEAR)})),
            File("06944_income.json", url("06944", {
                "valueCodes[Region]": "*", "codelist[Region]": "agg_KommGjeldende", "valueCodes[HusholdType]": "0000",
                "valueCodes[ContentsCode]": "InntSkatt", "valueCodes[Tid]": "2024"})),
            File("06944_income_country.json", url("06944", {
                "valueCodes[Region]": "0", "valueCodes[HusholdType]": "0000",
                "valueCodes[ContentsCode]": "InntSkatt", "valueCodes[Tid]": "2024"})),
            File("07459_pop_county2024.json", f"{SSB}/07459/data?lang=en&outputFormat=json-stat2&valueCodes[Region]=*"
                 "&codelist[Region]=agg_Fylker2024&valueCodes[Tid]=" + ",".join(map(str, YEARS)) +
                 "&valueCodes[ContentsCode]=Personer1"),
            File("klass131_changes_2008_2026.json", "https://data.ssb.no/api/klass/v1/classifications/131/changes.json"
                 "?from=2008-01-01&to=2026-12-31&language=nb"),
            File("08585_students.json", url("08585", {
                "valueCodes[Kjonn]": "0", "valueCodes[UtdHogLerested]": "*", "valueCodes[ContentsCode]": "Studenter",
                "valueCodes[Tid]": "2025"})),
        ]

    def process(self):
        out = {"municipalities": {}, "country": {}, "vintage": {}}
        m = out["municipalities"]

        def muni(code):
            code = re.sub(r"^K[.-]", "", code)
            if not (len(code) == 4 and code.isdigit()) or code.startswith(("21", "22", "23", "25", "99")):
                return None  # Svalbard, Jan Mayen, continental shelf, unknown
            return m.setdefault(code, {"pop": {}, "age": {}, "jobs": {}, "jobs_res": {}})

        js = jsonstat.load(self.path("07459_pop_age.json"))
        names = jsonstat.labels(js, "Region")
        out["vintage"]["population"] = jsonstat.updated(js)
        for d, v, _ in jsonstat.records(js):
            rec = muni(d["Region"])
            if rec is None:
                continue
            rec["name"] = _clean_name(names.get(d["Region"], ""))
            y = int(d["Tid"])
            rec["pop"][y] = rec["pop"].get(y, 0) + (v or 0) if v is not None else rec["pop"].get(y)
            if y == YEARS[-1]:
                rec["age"][d["Alder"]] = v
        js = jsonstat.load(self.path("07459_pop_country.json"))
        out["country"]["pop"] = {int(d["Tid"]): v for d, v, _ in jsonstat.records(js)}

        js = jsonstat.load(self.path("09280_area.json"))
        for d, v, _ in jsonstat.records(js):
            rec = muni(d["Region"])
            if rec is not None:
                rec["land_km2" if d["Arealtype"] == "1" else "fresh_km2"] = v

        js = jsonstat.load(self.path("07984_employment.json"))
        for d, v, _ in jsonstat.records(js):
            rec = muni(d["Region"])
            if rec is None or d["NACE2007"] == "00-99":
                if rec is not None and d["NACE2007"] == "00-99":
                    rec["jobs_total" if d["ContentsCode"] == "SysselsatteArb" else "employed_res"] = v
                continue
            key = "jobs" if d["ContentsCode"] == "SysselsatteArb" else "jobs_res"
            rec[key][d["NACE2007"]] = v
        js = jsonstat.load(self.path("07984_employment_country.json"))
        out["country"]["jobs"] = {d["NACE2007"]: v for d, v, _ in jsonstat.records(js) if d["ContentsCode"] == "SysselsatteArb"}

        js = jsonstat.load(self.path("06944_income.json"))
        for d, v, _ in jsonstat.records(js):
            rec = muni(d["Region"])
            if rec is not None:
                rec["income"] = v
        js = jsonstat.load(self.path("06944_income_country.json"))
        out["country"]["income"] = next(v for _, v, _ in jsonstat.records(js))

        js = jsonstat.load(self.path("08585_students.json"))
        lab = jsonstat.labels(js, "UtdHogLerested")
        out["students"] = {lab[d["UtdHogLerested"]]: v for d, v, _ in jsonstat.records(js) if v}
        # drop municipalities that no longer exist (no 2026 population)
        for code in [c for c, r in m.items() if not r["pop"].get(YEARS[-1])]:
            del m[code]
        return out


def _clean_name(s: str) -> str:
    # "Kautokeino - Guovdageaidnu" style bilingual names: keep both; strip year qualifiers "(2020-2023)"
    import re
    return re.sub(r"\s*\(\d{4}-?\d{0,4}\)\s*$", "", s).strip()


# --------------------------------------------------------------------------------------------------------- SCB --
SCB = "https://statistikdatabasen.scb.se/api/v2/tables"


class SCB_(Source):
    info = SourceInfo(
        id="scb",
        title="Statistics Sweden (SCB) Statistical Database: population, land area, employment by place of work, income",
        publisher="Statistiska centralbyrån (Statistics Sweden)",
        homepage="https://www.statistikdatabasen.scb.se/",
        license="CC0 1.0 (Statistics Sweden open data)",
        country="SE",
        description="TAB628 (population, land area and density by municipality, 31 December), TAB5557/TAB638 "
                    "(population by age), TAB3204 (employed 15–74 by region of work and NACE Rev. 2, annual register "
                    "BAS), TAB4840 (median net income, persons 20+). From reference year 2025 SCB adds small random "
                    "noise to protect privacy (cell key method), so parts may not sum exactly to totals.",
        used_for=["municipal population and growth", "age structure", "land area", "jobs by industry (yields)", "income lens"],
    )

    def files(self):
        def url(tab, p):
            return f"{SCB}/{tab}/data?lang=en&outputFormat=json-stat2&" + _q(p)

        return [
            File("TAB628_pop_area.json", url("TAB628", {
                "valueCodes[Region]": "*", "valueCodes[Kon]": "1+2", "valueCodes[ContentsCode]": "*",
                "valueCodes[Tid]": ",".join(str(y - 1) for y in YEARS)})),
            File("TAB5557_age.json", url("TAB5557", {
                "valueCodes[Region]": "*", "valueCodes[Alder]": "*", "codelist[Alder]": "vs_CKMÅlder5årTOT",
                "valueCodes[Civilstand]": "*", "valueCodes[Kon]": "TotSa", "valueCodes[ContentsCode]": "000007ME",
                "valueCodes[Tid]": "2025"})),
            File("TAB3204_employment.json", url("TAB3204", {
                "valueCodes[Region]": "*", "valueCodes[Kon]": "1+2", "valueCodes[SNI2007]": "*",
                "valueCodes[Fodelseregion]": "tot", "valueCodes[ContentsCode]": "*", "valueCodes[Tid]": str(EMP_YEAR)})),
            File("TAB4840_income.json", url("TAB4840", {
                "valueCodes[Region]": "*", "valueCodes[Kon]": "1+2", "valueCodes[Alder]": "20+",
                "codelist[Alder]": "vs_Ålder4gr", "valueCodes[ContentsCode]": "000001ON", "valueCodes[Tid]": "2024"})),
        ]

    def process(self):
        out = {"municipalities": {}, "lan": {}, "country": {}, "vintage": {}}
        m = out["municipalities"]

        def reg(code):
            if code == "00":
                return out["country"]
            if len(code) == 2:
                return out["lan"].setdefault(code, {})
            return m.setdefault(code, {"pop": {}, "age": {}, "jobs": {}, "jobs_res": {}})

        js = jsonstat.load(self.path("TAB628_pop_area.json"))
        names = jsonstat.labels(js, "Region")
        cl = jsonstat.labels(js, "ContentsCode")
        out["vintage"]["population"] = jsonstat.updated(js)
        for d, v, _ in jsonstat.records(js):
            r = reg(d["Region"])
            r["name"] = names.get(d["Region"])
            label = cl[d["ContentsCode"]].lower()
            y = int(d["Tid"]) + 1  # 31 Dec of year Y-1 == 1 Jan of year Y
            if "land area" in label:
                if int(d["Tid"]) == YEARS[-1] - 1:
                    r["land_km2"] = v
            elif "population" in label and "density" not in label:
                r.setdefault("pop", {})[y] = v
        js = jsonstat.load(self.path("TAB5557_age.json"))
        acc = {}
        for d, v, _ in jsonstat.records(js):
            if v is None or d.get("Civilstand") != "SC":
                continue
            mm = re.match(r"(\d+)", d["Alder"].lstrip("-"))
            if not mm or d["Alder"].startswith("TOT"):
                continue
            age = int(mm.group(1)) if not d["Alder"].startswith("-") else 0
            grp = "F0-19" if age < 20 else "F20-64" if age < 65 else "F65+"
            key = (d["Region"], grp)
            acc[key] = acc.get(key, 0) + v
        for (code, grp), v in acc.items():
            if len(code) == 4:
                reg(code).setdefault("age", {})[grp] = v
        js = jsonstat.load(self.path("TAB3204_employment.json"))
        cl = jsonstat.labels(js, "ContentsCode")
        for d, v, _ in jsonstat.records(js):
            r = reg(d["Region"])
            work = "region of work" in cl[d["ContentsCode"]]
            if d["SNI2007"] == "A-U+US":
                r["jobs_total" if work else "employed_res"] = v
            else:
                r.setdefault("jobs" if work else "jobs_res", {})[d["SNI2007"]] = v
        js = jsonstat.load(self.path("TAB4840_income.json"))
        for d, v, _ in jsonstat.records(js):
            r = reg(d["Region"])
            r["income"] = v * 1000 if v is not None else None
        out["sni_labels"] = jsonstat.labels(js := jsonstat.load(self.path("TAB3204_employment.json")), "SNI2007")
        return out


# --------------------------------------------------------------------------------------------------------- DST --
DST = "https://api.statbank.dk/v1/data"


class DST_(Source):
    info = SourceInfo(
        id="dst",
        title="Statistics Denmark (DST) StatBank: population, area, employment by workplace, income",
        publisher="Danmarks Statistik (Statistics Denmark)",
        homepage="https://www.statbank.dk/",
        license="CC BY 4.0 (Statistics Denmark terms of use)",
        country="DK",
        description="FOLK1A (population 1st day of Q1, by municipality and age), ARE207 (area 1 January), RAS501 "
                    "(employed end November by workplace municipality and industry, DB25 36-grouping; also gives the "
                    "landsdel (NUTS 3) of each municipality), INDKP107 (average disposable income per person).",
        used_for=["municipal population and growth", "age structure", "area", "jobs by industry (yields)",
                  "NUTS 3 membership", "income lens"],
    )

    def files(self):
        def url(tab, p):
            return f"{DST}/{tab}/CSV?lang=en&delimiter=Semicolon&valuePresentation=Code&" + _q(p)

        return [
            File("FOLK1A_pop.csv", url("FOLK1A", {"OMRÅDE": "*", "KØN": "TOT", "ALDER": "IALT", "CIVILSTAND": "TOT",
                                                  "Tid": ",".join(f"{y}K1" for y in YEARS)})),
            File("FOLK1A_age.csv", url("FOLK1A", {"OMRÅDE": "*", "KØN": "TOT", "ALDER": "*", "CIVILSTAND": "TOT",
                                                  "Tid": f"{YEARS[-1]}K1"})),
            File("ARE207_area.csv", url("ARE207", {"OMRÅDE": "*", "Tid": str(YEARS[-1])})),
            File("RAS501_employment.csv", url("RAS501", {"ARBKOM": "*", "BRANCHEDB2536": "*", "KOEN": "00",
                                                         "Tid": str(EMP_YEAR)})),
            File("INDKP107_income.csv", url("INDKP107", {"OMRÅDE": "*", "ENHED": "116", "KOEN": "MOK", "UDDNIV": "*",
                                                         "INDKOMSTTYPE": "100", "Tid": "2024"})),
            File("RAS501_meta.json", "https://api.statbank.dk/v1/tableinfo/RAS501?lang=en&format=JSON"),
        ]

    def process(self):
        out = {"municipalities": {}, "landsdele": {}, "country": {}, "vintage": {}}
        m = out["municipalities"]

        def rows(name):
            text = self.path(name).read_text(encoding="utf-8-sig")
            return list(csv.DictReader(io.StringIO(text), delimiter=";"))

        def num(s):
            s = (s or "").strip()
            return None if s in ("", "..", "-") else float(s)

        def rec(code):
            if code == "000":
                return out["country"]
            if len(code) == 3 and code not in ("081", "082", "083", "084", "085") and code != "411":
                return m.setdefault(code, {"pop": {}, "age": {}, "jobs": {}})
            return None

        meta = json.loads(self.path("RAS501_meta.json").read_text())
        labels = {}
        for var in meta["variables"]:
            labels[var["id"]] = {v["id"]: v["text"] for v in var["values"]}
            if var["id"] == "ARBKOM":
                landsdel = None
                for v in var["values"]:
                    if len(v["id"]) == 2:
                        landsdel = v["id"]
                        out["landsdele"][landsdel] = {"name": v["text"].replace("Province ", ""), "municipalities": []}
                    elif len(v["id"]) == 3 and landsdel and v["id"] not in ("000",) and not v["id"].startswith("08"):
                        out["landsdele"][landsdel]["municipalities"].append(v["id"])
        out["industry_labels"] = labels.get("BRANCHEDB2536", {})
        for r in rows("FOLK1A_pop.csv"):
            t = rec(r["OMRÅDE"])
            if t is None:
                continue
            t.setdefault("pop", {})[int(r["TID"][:4])] = num(r["INDHOLD"])
        for r in rows("FOLK1A_age.csv"):
            t = rec(r["OMRÅDE"])
            if t is None or r["ALDER"] == "IALT":
                continue
            age = int(r["ALDER"])
            grp = "F0-19" if age < 20 else "F20-64" if age < 65 else "F65+"
            t.setdefault("age", {})[grp] = t.setdefault("age", {}).get(grp, 0) + (num(r["INDHOLD"]) or 0)
        for r in rows("ARE207_area.csv"):
            t = rec(r["OMRÅDE"])
            if t is not None:
                t["land_km2"] = num(r["INDHOLD"])
        for r in rows("RAS501_employment.csv"):
            t = rec(r["ARBKOM"])
            if t is None:
                continue
            code = r["BRANCHEDB2536"]
            if code == "A-V":
                t["jobs_total"] = num(r["INDHOLD"])
            else:
                t.setdefault("jobs", {})[code] = num(r["INDHOLD"])
        for r in rows("INDKP107_income.csv"):
            t = rec(r["OMRÅDE"])
            if t is not None and r["UDDNIV"] == "TOT":
                t["income"] = num(r["INDHOLD"])
        valid = {c for ld in out["landsdele"].values() for c in ld["municipalities"]} - {"411"}
        names = labels.get("ARBKOM", {})
        for code in list(m):
            if code not in valid:
                del m[code]
            else:
                m[code]["name"] = names.get(code)
        return out


# ---------------------------------------------------------------------------------------------------- Eurostat --
ESTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"


class Eurostat(Source):
    info = SourceInfo(
        id="eurostat",
        title="Eurostat: regional GDP (NUTS 3), electricity production, airport passengers, port freight",
        publisher="Eurostat (European Commission)",
        homepage="https://ec.europa.eu/eurostat/data/database",
        license="Eurostat reuse policy (CC BY 4.0)",
        description="nama_10r_3gdp (GDP at current market prices by NUTS 3 region: million EUR and PPS per inhabitant), "
                    "nama_10r_3popgdp (average population used for GDP per capita), nrg_bal_peh (gross electricity "
                    "production by fuel), avia_paoa (passengers carried by reporting airport), mar_mg_aa_pwhd "
                    "(gross weight of goods handled in main ports).",
        used_for=["Gold (GDP)", "national energy mix", "airport size", "port size"],
    )

    def files(self):
        return [
            File("nama_10r_3gdp.json", f"{ESTAT}/nama_10r_3gdp?format=JSON&lang=EN&unit=MIO_EUR&unit=PPS_EU27_2020_HAB"
                 "&unit=EUR_HAB&sinceTimePeriod=2015&geoLevel=nuts3"),
            File("nama_10r_3gdp_nat.json", f"{ESTAT}/nama_10r_3gdp?format=JSON&lang=EN&unit=MIO_EUR"
                 "&unit=PPS_EU27_2020_HAB&sinceTimePeriod=2015&geo=NO&geo=SE&geo=DK"),
            File("nrg_bal_peh.json", f"{ESTAT}/nrg_bal_peh?format=JSON&lang=EN&nrg_bal=GEP&unit=GWH&geo=NO&geo=SE"
                 "&geo=DK&sinceTimePeriod=2019"),
            File("avia_paoa.json", f"{ESTAT}/avia_paoa?format=JSON&lang=EN&unit=PAS&tra_meas=PAS_CRD&time=2024"),
            File("mar_mg_aa_pwhd.json", f"{ESTAT}/mar_mg_aa_pwhd?format=JSON&lang=EN&direct=TOTAL&unit=THS_T&time=2024"),
        ]

    def process(self):
        def parse(name):
            js = json.loads(self.path(name).read_text())
            return js

        out = {}
        for name in ("nama_10r_3gdp", "nama_10r_3gdp_nat", "nrg_bal_peh", "avia_paoa", "mar_mg_aa_pwhd"):
            js = parse(f"{name}.json")
            out[name] = {"updated": js.get("updated"), "records": list(estat_records(js))}
        return out


def estat_records(js):
    """Eurostat JSON-stat 2.0 (dimension index maps; value is a sparse dict)."""
    ids = js["id"]
    sizes = js["size"]
    cats = []
    for d in ids:
        idx = js["dimension"][d]["category"]["index"]
        cats.append(sorted(idx, key=idx.get))
    labels = {d: js["dimension"][d]["category"].get("label", {}) for d in ids}
    status = js.get("status", {})
    for k, v in js["value"].items():
        n = int(k)
        coords = []
        for s in reversed(sizes):
            coords.append(n % s)
            n //= s
        coords.reverse()
        rec = {d: cats[i][coords[i]] for i, d in enumerate(ids)}
        rec["value"] = v
        if k in status:
            rec["flag"] = status[k]
        yield rec
