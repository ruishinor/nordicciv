"""Validation gates. Every line is PASS, NOTE, WARN, SKIP or FAIL; any FAIL exits 1.

Modes (NC-T03), each a superset of the one before:

  built    the generated web/data files on their own: schemas, identifiers, internal consistency, null ≠ 0,
           finite numbers, provenance fields. Needs nothing but web/data. Runs anywhere (CI, a fresh clone).
  source   reconciles web/data against the original downloads in data/raw, read independently of the processors
           (national and county totals, historical series, municipal joins, employment, regional output), and
           verifies every cached download against its manifest (SHA-256 and request identity).
  release  everything in `source`, plus: no mandatory check may be skipped, the browser journeys must have passed
           against exactly these data files (tests/results/browser.json, matched by data hash) and the key totals
           must match tests/fixtures/release_summary.json (update it deliberately with --accept).

A skipped check is reported as SKIP and never counts as a pass. The report states the mode it ran in.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import sys
from collections import defaultdict

from .build.yields import YIELDS
from .core.paths import INTERIM, RAW, ROOT, WEB_DATA


def _ranks_independent(vals, his):
    """Independent re-derivation of the published ranking convention (vectorised; not the build's code):
    rank = 1 + #greater; interval = [1 + #(lo_j > hi_i), 1 + #(hi_j > lo_i, j != i)]."""
    import numpy as np
    have = np.array([v is not None for v in vals])
    lo = np.array([v if v is not None else np.nan for v in vals], dtype=float)
    hi = np.array([h if h is not None else (v if v is not None else np.nan) for v, h in zip(vals, his)], dtype=float)
    L, H = lo[have], hi[have]
    rank = 1 + (L[None, :] > L[:, None]).sum(1)
    best = 1 + (L[None, :] > H[:, None]).sum(1)
    gt = H[None, :] > L[:, None]
    np.fill_diagonal(gt, False)
    worst = 1 + gt.sum(1)
    out_r, out_i, k = [None] * len(vals), [None] * len(vals), 0
    for i in range(len(vals)):
        if have[i]:
            out_r[i], out_i[i] = int(rank[k]), [int(best[k]), int(worst[k])]
            k += 1
    return out_r, out_i

TOL_POP = 0.0005  # municipal sums vs national totals: Sweden adds random noise from 2025; DK has ~90 without municipality
YEARS = list(range(2008, 2027))
SUMMARY = ROOT / "tests" / "fixtures" / "release_summary.json"
BROWSER_RESULT = ROOT / "tests" / "results" / "browser.json"

KNOWN_PLACES = {  # name: (lon, lat) of the main town, for a placement check (±25 km)
    "Oslo": (10.75, 59.91), "Stockholm": (18.07, 59.33), "Copenhagen": (12.57, 55.68), "Bergen": (5.32, 60.39),
    "Göteborg": (11.97, 57.71), "Trondheim": (10.40, 63.43), "Malmö": (13.00, 55.60), "Aarhus": (10.20, 56.16),
    "Tromsø": (18.96, 69.65), "Kiruna": (20.23, 67.86), "Luleå": (22.15, 65.58), "Stavanger": (5.73, 58.97),
}
DATA_FILES = ["world", "cities", "states", "nation", "lenses", "sources", "resources", "infrastructure", "wonders",
              "detail", "munis"]


class Report:
    def __init__(self, mode):
        self.mode = mode
        self.lines = []

    def add(self, level, msg):
        self.lines.append((level, msg))
        print(f"{level:4s}  {msg}")

    def ok(self, cond, msg, bad="FAIL"):
        self.add("PASS" if cond else bad, msg)

    def skip(self, msg, mandatory_in=("release",)):
        self.add("FAIL" if self.mode in mandatory_in else "SKIP", msg + (" (mandatory in this mode)" if self.mode in mandatory_in else ""))

    def count(self, level):
        return sum(1 for l, _ in self.lines if l == level)

    @property
    def failed(self):
        return self.count("FAIL") > 0


def load(name):
    p = WEB_DATA / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def data_hash() -> str:
    h = hashlib.sha256()
    for n in DATA_FILES:
        p = WEB_DATA / f"{n}.json"
        if p.exists():
            h.update(n.encode())
            h.update(p.read_bytes())
    return h.hexdigest()


# ===================================================================================================== built ====
def check_files(r):
    for n in DATA_FILES:
        p = WEB_DATA / f"{n}.json"
        if not p.exists():
            r.add("FAIL", f"files: web/data/{n}.json missing")
            continue
        txt = p.read_text()
        bad = re.search(r"(?<![\w\"])(NaN|-?Infinity)(?![\w\"])", txt)
        r.ok(not bad, f"files: {n}.json parses as strict JSON numbers (no NaN/Infinity) [{len(txt) / 1e6:.2f} MB]")


def check_world(r, world):
    g = world["grid"]
    n = g["cols"] * g["rows"]
    for k in ("owner", "county", "elev", "water", "relief", "cover", "pop"):
        if len(world[k]) != n:
            r.add("FAIL", f"world.{k} has {len(world[k])} cells, expected {n}")
    owned = [i for i in range(n) if world["owner"][i] >= 0]
    area = len(owned) * 3 * math.sqrt(3) / 2 * g["radius"] ** 2
    r.ok(700_000 < area < 900_000, f"world: {len(owned):,} Scandinavian land hexes ≈ {area:,.0f} km² (land of NO+SE+DK ≈ 774,000 km² + inland water)")
    bad = [i for i in owned if world["county"][i] < 0]
    r.ok(not bad, f"world: every Scandinavian land hex has a dominant municipality ({len(bad)} without)")
    return sum(world["pop"])


def check_cities(r, cities, world, nation, states):
    ids = [c["id"] for c in cities]
    r.ok(len(ids) == len(set(ids)), f"ids: {len(ids)} municipality ids, all unique")
    r.ok(all(re.fullmatch(r"(NO-\d{4}|SE-\d{4}|DK-\d{3})", i) for i in ids), "ids: every id has the form NO-nnnn / SE-nnnn / DK-nnn")
    counts = defaultdict(int)
    for c in cities:
        counts[c["country"]] += 1
    exp = {"NO": 357, "SE": 290, "DK": 98}
    r.ok(dict(counts) == exp, f"ids: municipalities per country {dict(counts)} (expected {exp}, 2024–2026 boundaries)")
    owner = world["owner"]
    off = [c["name"] for c in cities if c["cell"] is None or owner[c["cell"]] < 0]
    r.ok(not off, f"cities: every banner stands on Scandinavian land ({len(off)} off: {off[:5]})")
    for cc in ("NO", "SE", "DK"):
        s = sum(c["population"] for c in cities if c["country"] == cc)
        n = nation["countries"][cc]["population"]
        r.ok(s == n, f"cities: {cc} municipal population sum {s:,} = mapped country aggregate {n:,}")

    # population history semantics (NC-T01/T02)
    zeros = [(c["name"], y) for c in cities for y, v in c["pop_series"].items() if v == 0]
    r.ok(not zeros, f"history: no municipality-year is recorded as 0 residents ({len(zeros)}; source zeros must be null with a status)")
    unexplained = [c["name"] for c in cities for y, v in c["pop_series"].items()
                   if v is None and not c.get("pop_status", {}).get(y)]
    r.ok(not unexplained, f"history: every null population year carries a status ({len(unexplained)} without)")
    cross = []
    for c in cities:
        t = c.get("pop_terr", {})
        g0, g1 = (str(y) for y in c["growth_years"])
        if c["growth"] is not None and (t.get(g0) is None or t.get(g0) != t.get(g1)):
            cross.append(c["name"])
    r.ok(not cross, f"history: no growth figure spans a territorial break ({len(cross)}: {cross[:5]})")
    nonfin = [c["name"] for c in cities if c["growth"] is not None and not math.isfinite(c["growth"])]
    r.ok(not nonfin, f"history: all growth figures finite ({len(nonfin)} not)")
    noted = [c["name"] for c in cities if c["growth"] is None and not c.get("growth_note")]
    r.ok(not noted, f"history: every municipality without a growth figure says why ({len(noted)} silent)")
    br = [c["name"] for c in cities if c.get("pop_breaks")]
    r.add("NOTE", f"history: {len(br)} municipalities with recorded territorial breaks: {', '.join(br)}")
    no_growth = [c["name"] for c in cities if c.get("growth") is None]
    r.add("NOTE", f"history: {len(no_growth)} municipalities without a comparable 2016–26 figure: {', '.join(no_growth)}")
    al = next((c for c in cities if c["id"] == "NO-1508"), None)
    if al:
        r.ok(al["pop_terr"].get("2023") != al["pop_terr"].get("2024") and al["pop_terr"].get("2019") == al["pop_terr"].get("2024"),
             "history fixture: Ålesund 2020–23 (incl. Haram) is a different territory from 2019 and 2024")
    nat = nation["nation"]
    for k in ("2008", "2016", "2026"):
        v = nat["pop_series"].get(k)
        r.ok(v is not None and all(nation["countries"][cc]["pop_series"].get(k) for cc in ("NO", "SE", "DK"))
             and v == sum(nation["countries"][cc]["pop_series"][k] for cc in ("NO", "SE", "DK")),
             f"history: Scandinavia {k} = sum of the three published national totals ({v:,.0f})")
    r.ok(nat.get("pop_series_source") and all(nation["countries"][cc].get("pop_series_source") for cc in ("NO", "SE", "DK")),
         "history: national series name their published source (not a sum of municipalities)")
    for st in states:
        for y, v in st["pop_series"].items():
            if v is None and y not in st.get("pop_coverage", {}):
                r.add("FAIL", f"history: {st['name']} {y} is null without a coverage figure")
                break

    # suppression (NC-T06)
    miss = []
    for c in cities:
        for y in c["yields_partial"]:
            if y not in c.get("yields_hi", {}) or c["yields_hi"][y] < c["yields"][y]:
                miss.append((c["name"], y))
    r.ok(not miss, f"suppression: every partial yield has an upper bound ≥ its lower bound ({len(miss)} missing)")
    ident = []
    for c in cities:
        if c["jobs_total"] is None:
            continue
        s = sum(c["jobs"].values()) + (c.get("jobs_unallocated") or 0)
        # SCB applies a disclosure-protection method, so its totals need not equal the sum of components (TAB3204
        # note); the tolerance is 1 %. NO and DK must match exactly.
        tol = 0.01 * c["jobs_total"] if c["country"] == "SE" else 0.5
        if abs(s - c["jobs_total"]) > tol:
            ident.append((c["name"], s, c["jobs_total"]))
    r.ok(not ident, f"industry: groups (+ suppressed remainder) add up to total jobs in every municipality ({len(ident)} off: {ident[:3]})")
    # the suppressed remainder must be compatible with the published total and with the classification
    res_bad = []
    for c in cities:
        if c["jobs_total"] is None:
            continue
        raw = c["jobs_total"] - sum(c["jobs"].values())
        un = c.get("jobs_unallocated") or 0
        if c["jobs_partial"]:
            if raw < 0 or abs(un - raw) > 0.5:
                res_bad.append((c["name"], "remainder", raw, un))
            for y in c["yields_partial"]:
                if abs(c["yields_hi"][y] - c["yields"][y] - un) > 0.5:
                    res_bad.append((c["name"], y, "upper bound ≠ lower bound + remainder"))
            groups = {g for yy in YIELDS for g in yy["groups"] if yy["key"] in c["yields_partial"]}
            if not set(c["jobs_partial"]) & groups and c["yields_partial"]:
                res_bad.append((c["name"], "partial yield without a suppressed group"))
        else:
            if un or c.get("yields_hi"):
                res_bad.append((c["name"], "remainder or upper bound without any suppressed group"))
            if c["country"] != "SE" and abs(raw) > 0.5:
                res_bad.append((c["name"], "unsuppressed groups do not add up", raw))
        for yy in YIELDS:
            part = any(g in c["jobs_partial"] for g in yy["groups"])
            if part != (yy["key"] in c["yields_partial"]):
                res_bad.append((c["name"], yy["key"], "partial flag does not follow the suppressed groups"))
    r.ok(not res_bad, f"suppression: remainders are non-negative, equal total − published groups, bound only yields that "
                      f"contain a suppressed group, and are absent where nothing is suppressed ({len(res_bad)} off: {res_bad[:3]})")
    # ranks follow the single convention (pipeline/build/ranking.py)
    rk_bad = []
    keys = ["population", "gdp", "growth", "density"] + [yy["key"] for yy in YIELDS]
    for k in keys:
        vals = [c["yields"].get(k) if k in c["yields"] else c.get(k) for c in cities]
        his = [(c.get("yields_hi") or {}).get(k, v) if v is not None else None for c, v in zip(cities, vals)]
        comp, ivs = _ranks_independent(vals, his)
        for c, v, rk, iv in zip(cities, vals, comp, ivs):
            if c["ranks"].get(k) != rk:
                rk_bad.append((c["name"], k, "rank", c["ranks"].get(k), rk))
            rr = (c.get("rank_range") or {}).get(k)
            want = iv if iv and iv[0] != iv[1] else None
            if rr != want:
                rk_bad.append((c["name"], k, "interval", rr, want))
            if rr and not (rr[0] <= c["ranks"][k] <= rr[1]):
                rk_bad.append((c["name"], k, "rank outside interval", c["ranks"][k], rr))
    n_iv = sum(len(c.get("rank_range") or {}) for c in cities)
    r.ok(not rk_bad, f"ranking: {n_iv} published intervals; every rank is a competition rank (ties share), every interval is "
                     f"the possible-rank interval for the published bounds and contains the rank ({len(rk_bad)} off: {rk_bad[:3]})")
    st_bad = []
    for k in [yy["key"] for yy in YIELDS] + ["population"]:
        vals = [(s_["yields"].get(k) if k != "population" else s_["population"]) for s_ in states]
        his = [(s_.get("yields_hi") or {}).get(k, v) if v is not None else None for s_, v in zip(states, vals)]
        for s_, rk, iv in zip(states, *_ranks_independent(vals, his)):
            rr = (s_.get("rank_range") or {}).get(k)
            if s_["ranks"].get(k) != rk or rr != (iv if iv and iv[0] != iv[1] else None):
                st_bad.append((s_["name"], k))
    r.ok(not st_bad, f"ranking: region ranks and intervals follow the same convention ({len(st_bad)} off: {st_bad[:3]})")
    over = [c["name"] for c in cities if c["jobs_total"] is not None and sum(c["jobs"].values()) > c["jobs_total"] + 50]
    r.ok(not over, f"industry: no double counting — group sums never exceed total jobs ({len(over)})")
    uncertain = sum(1 for c in cities if c.get("rank_range"))
    r.add("NOTE", f"suppression: {sum(1 for c in cities if c['yields_partial'])} municipalities with a suppressed yield component; "
                  f"{uncertain} carry at least one rank interval instead of an exact rank")

    # economic output (NC-T07)
    by = defaultdict(float)
    for c in cities:
        if c["gdp"] is not None:
            by[c["gdp_region"]] += c["gdp"]
    est = [c["name"] for c in cities if "gold" not in (c.get("yields_estimated") or [])]
    r.ok(not est, "economy: every municipal output value is flagged as an estimate")
    r.ok(all(c.get("gdp_concept") for c in cities if c["gdp"] is not None), "economy: every municipal output names its accounting concept")
    r.ok(bool(nation.get("gdp_label")) and "not harmonised" in nation["gdp_label"], "economy: the Scandinavian total is labelled as combined regional output, not harmonised GDP")
    comp = nation.get("gdp_components", {})
    tot = sum(v["eur"] for v in comp.values())
    r.ok(comp and abs(tot - nation["nation"]["gdp"]) / tot < 1e-9, f"economy: country components add up to the combined €{tot / 1e9:,.1f} bn")
    return by

    # placement handled in check_places


def check_places(r, cities, world):
    from .core import geo
    frame = geo.Frame(world["projection"]["x0_km"], world["projection"]["y1_km"])
    for name, (lon, lat) in KNOWN_PLACES.items():
        c = next((x for x in cities if x["name"] == name), None)
        if not c:
            r.add("FAIL", f"cities: {name} missing")
            continue
        x, y = frame.from_ll(lon, lat)
        d = math.hypot(float(x) - c["x"], float(y) - c["y"])
        r.ok(d < 25, f"places: {name} banner {d:.1f} km from its reference position")


def check_munis(r, munis, cities):
    if munis is None:
        r.add("FAIL", "geometry: munis.json missing")
        return
    have = {m["id"] for m in munis["features"]}
    missing = [c["name"] for c in cities if c["id"] not in have]
    r.ok(not missing, f"geometry: every municipality has its own polygon ({len(missing)} without: {missing[:5]})")
    empty = [m["id"] for m in munis["features"] if not m["rings"]]
    r.ok(not empty, f"geometry: no empty polygons ({len(empty)})")
    small = [c["name"] for c in cities if c["id"] in have and c["id"] in {"DK-147", "SE-0184", "SE-0183", "NO-1106", "NO-1151", "NO-1856", "NO-1857", "NO-3232", "NO-1127"}]
    r.ok(len(small) == 9, f"geometry fixture: Frederiksberg, Solna, Sundbyberg, Haugesund, Utsira, Røst, Værøy, Rælingen, Randaberg are selectable polygons ({len(small)}/9)")
    r.add("NOTE", f"geometry: {len(have)} polygons, {sum(len(m['rings']) for m in munis['features'])} rings, "
                  f"{munis.get('vertices', '?')} vertices at full detail")


def check_lenses(r, lenses, sources, world):
    ids = {s["id"] for s in sources}
    if lenses.get("packed") == "owned":
        idx = [i for i, o in enumerate(world["owner"]) if o >= 0]
        for l in lenses["lenses"]:
            full = [None] * len(world["owner"])
            for k, i in enumerate(idx):
                full[i] = l["values"][k]
            l["values"] = full
    for l in lenses["lenses"]:
        srcs = [x.strip() for x in (l.get("source") or "").split(",") if x.strip()]
        missing = [s for s in srcs if s not in ids]
        ok = srcs and not missing and l.get("description") and l.get("unit") is not None and l.get("resolution")
        r.ok(ok, f"lens {l['id']}: source {srcs or '—'}, unit '{l.get('unit')}', resolution {l.get('resolution')}" + (f", unknown {missing}" if missing else ""))


def check_resources(r, res, world):
    owner = world["owner"]
    outside = [it["name"] for it in res["items"] if it["cell"] < 0]
    r.ok(not outside, f"resources: {len(res['items'])} sites, all inside the map ({len(outside)} outside)")
    on_foreign = [it["name"] for it in res["items"] if it["cell"] >= 0 and owner[it["cell"]] == -2]
    r.ok(not on_foreign, f"resources: {len(on_foreign)} on foreign hexes {on_foreign[:4]}", bad="WARN")


def check_sources(r, sources):
    for s in sources:
        ok = s.get("license") and s.get("publisher") and s.get("file_count", 0) > 0
        r.ok(ok, f"source {s['id']}: {s.get('file_count', 0)} files, licence: {s.get('license', '')[:60]}")


# ==================================================================================================== source ====
def _jsonstat_by(path, keydims):
    from .core import jsonstat
    js = jsonstat.load(path)
    out = defaultdict(float)
    seen = set()
    dup = 0
    for d, v, _ in jsonstat.records(js):
        k = tuple(d[x] for x in keydims)
        full = tuple(sorted(d.items()))
        dup += full in seen
        seen.add(full)
        out[k] += v or 0
    return out, dup


def check_source(r, cities, nation, states, gdp_by_region):
    raw_missing = [p for p in ("ssb/07459_pop_age.json", "ssb/07459_pop_country.json", "scb/TAB628_pop_area.json",
                               "dst/FOLK1A_pop.csv", "regional_accounts/ssb_09391.json") if not (RAW / p).exists()]
    if raw_missing:
        r.skip(f"source: original downloads not available ({', '.join(raw_missing)}); source reconciliation not run",
               mandatory_in=("source", "release"))
        return
    by_id = {c["id"]: c for c in cities}
    # --- Norway, read straight from the JSON-stat answers
    muni, dup = _jsonstat_by(RAW / "ssb/07459_pop_age.json", ("Region", "Tid"))
    r.ok(dup == 0, f"source: SSB 07459 has no duplicate observations ({dup})")
    nat, _ = _jsonstat_by(RAW / "ssb/07459_pop_country.json", ("Tid",))
    bad = []
    for c in cities:
        if c["country"] != "NO":
            continue
        code = "K-" + c["id"][3:]
        for y in YEARS:
            v = muni.get((code, str(y)))
            mine = c["pop_series"].get(str(y))
            st = c["pop_status"].get(str(y))  # None = observed
            # each status is validated against the source value it claims; a status never excuses a mismatch
            if st is None:
                okv = v is not None and v != 0 and mine == v
            elif st == "boundary":
                okv = v == 0 and mine is None
            elif st == "missing":
                okv = v is None and mine is None
            else:
                okv = False
            if not okv:
                bad.append((c["name"], y, st or "observed", v, mine))
    r.ok(not bad, f"source join: every Norwegian municipality-year matches SSB 07459 according to its status "
                  f"(observed = equal and non-zero, boundary = source 0, missing = source empty) ({len(bad)} off: {bad[:3]})")
    rest = {y: muni.get(("K-Rest", str(y)), 0) for y in YEARS}
    off = []
    for y in YEARS:
        s = sum(c["pop_series"].get(str(y)) or 0 for c in cities if c["country"] == "NO")
        if s + rest[y] != nat[(str(y),)]:
            off.append((y, s, rest[y], nat[(str(y),)]))
    r.ok(not off, f"source: Norway, every year 2008–2026: Σ municipalities + SSB's 'divided municipalities' bucket = national total ({len(off)} years off: {off[:2]})")
    for cc, label in (("NO", "SSB 07459 country"),):
        for y in YEARS:
            if nation["countries"][cc]["pop_series"].get(str(y)) != nat[(str(y),)]:
                r.add("FAIL", f"source: {cc} {y} published series differs from {label}")
                break
        else:
            r.add("PASS", f"source: Norway national series 2008–2026 identical to {label}")
    # --- Sweden
    sw, dup = _jsonstat_by(RAW / "scb/TAB628_pop_area.json", ("Region", "ContentsCode", "Tid"))
    ccode = next((k[1] for k in sw if k[0] == "00" and sw[k] > 1e6), None)
    for y in (2008, 2016, 2026):
        v = sw.get(("00", ccode, str(y - 1)))
        mine = nation["countries"]["SE"]["pop_series"].get(str(y))
        r.ok(v and mine == v, f"source: Sweden {y} published total {mine:,.0f} = SCB TAB628 '00' {v:,.0f}")
        s = sum(c["pop_series"].get(str(y)) or 0 for c in cities if c["country"] == "SE")
        r.ok(abs(s - v) / v <= TOL_POP, f"source: Sweden {y} Σ municipalities {s:,.0f} vs national {v:,.0f} (Δ {abs(s - v):,.0f}; SCB cell-key noise from 2025)")
    # --- Denmark
    rows = list(csv.DictReader(io.StringIO((RAW / "dst/FOLK1A_pop.csv").read_text(encoding="utf-8-sig")), delimiter=";"))
    dk = defaultdict(float)
    for row in rows:
        m = re.match(r"(\d{4})K1", row["TID"])
        if m and row["INDHOLD"] not in ("", ".."):
            dk[(row["OMRÅDE"], int(m.group(1)))] += float(row["INDHOLD"])
    for y in (2008, 2016, 2026):
        v = dk.get(("000", y))
        mine = nation["countries"]["DK"]["pop_series"].get(str(y))
        r.ok(v and mine == v, f"source: Denmark {y} published total {mine:,.0f} = DST FOLK1A '000' {v:,.0f}")
    mism = [c["name"] for c in cities if c["country"] == "DK" and dk.get((c["id"][3:], 2026)) != c["population"]]
    r.ok(not mism, f"source join: every Danish municipality's 2026 population equals DST FOLK1A ({len(mism)} off)")
    # --- regional output: Σ municipal estimates = published region totals (in euro)
    g = json.loads((INTERIM / "_gdp_regions.json").read_text())["regions"] if (INTERIM / "_gdp_regions.json").exists() else None
    if g:
        # the interim file stores regional totals rounded to €0.1 million
        worst = max(abs(gdp_by_region.get(k, 0) - v["eur"] * 1e6) for k, v in g.items())
        r.ok(worst <= 0.05e6 + 1, f"economy: Σ municipal estimates reconcile with all {len(g)} published regional totals (worst Δ €{worst:,.0f}; totals stored to €0.1 m)")
    else:
        r.skip("economy: regional totals not available", mandatory_in=("source", "release"))
    from .core import jsonstat
    js = jsonstat.load(RAW / "regional_accounts/ssb_09391.json")
    shelf = next(v for d, v, _ in jsonstat.records(js) if d["Region"] == "23" and d["ContentsCode"] == "BNPB")
    fx = nation["fx"]["NOK"]
    r.ok(abs(shelf / fx * 1e6 - nation["extra_regio"]["NO_continental_shelf_eur"]) < 1, f"economy: continental shelf GVA €{shelf / fx / 1e3:,.1f} bn reported separately, not in any municipality")
    # --- employment totals vs national tables
    ssb = json.loads((INTERIM / "ssb.json").read_text())
    for cc, jt in (("NO", ssb["country"]["jobs"].get("00-99")),):
        sj = sum(c["jobs_total"] or 0 for c in cities if c["country"] == cc)
        r.ok(abs(sj - jt) / jt <= 0.01, f"source: {cc} jobs {sj:,.0f} vs national {jt:,.0f} (Δ {abs(sj - jt) / jt:.3%}; Svalbard/continental shelf/unknown excluded)", bad="WARN")
    # --- review list of unexplained large one-year changes
    rv = INTERIM / "_population_review.json"
    if rv.exists():
        for line in json.loads(rv.read_text())["review"]:
            r.add("NOTE", f"history review: {line}")


def check_cache(r):
    from .core import fetch
    from .sources import registry
    n = bad = 0
    for s in registry().values():
        for f in s.files():
            n += 1
            ok, why = fetch.verify(s.id, f.rel_path, url=f.url, method=f.method, body=f.body)
            if not ok:
                bad += 1
                if bad <= 5:
                    r.add("FAIL", f"cache: {s.id}/{f.rel_path}: {why}")
    r.ok(bad == 0, f"cache: {n - bad}/{n} declared downloads match their manifest (SHA-256, size, request identity)")


# =================================================================================================== release ====
def summary(cities, nation):
    nat = nation["nation"]
    return {
        "municipalities": len(cities), "population_2026": nat["population"],
        "population_published_2026": nat.get("population_published"),
        "pop_2008": nat["pop_series"]["2008"], "pop_2016": nat["pop_series"]["2016"],
        "growth_2016_2026": round(nat["growth"], 6), "jobs": nat["jobs_total"], "gdp_eur": round(nat["gdp"]),
        "no_growth": sorted(c["id"] for c in cities if c["growth"] is None),
        "breaks": sorted(c["id"] for c in cities if c.get("pop_breaks")),
    }


def check_release(r, cities, nation, accept=False):
    cur = summary(cities, nation)
    if accept or not SUMMARY.exists():
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps(cur, indent=1, ensure_ascii=False))
        r.add("NOTE", f"release: summary baseline {'accepted' if accept else 'created'} at {SUMMARY.relative_to(ROOT)}")
    base = json.loads(SUMMARY.read_text())
    diff = {k: (base.get(k), v) for k, v in cur.items() if base.get(k) != v}
    r.ok(not diff, f"release: key totals unchanged against the accepted baseline {('— changed: ' + str(diff)[:300]) if diff else ''}")
    if not BROWSER_RESULT.exists():
        r.skip("release: no browser test result (run tests/smoke_browser.py)")
        return
    b = json.loads(BROWSER_RESULT.read_text())
    same = b.get("data_hash") == data_hash()
    r.ok(same, f"release: browser journeys ran against these data files ({b.get('data_hash', '')[:12]} vs {data_hash()[:12]})")
    r.ok(b.get("failed") == 0 and b.get("passed", 0) > 0, f"release: browser journeys {b.get('passed')} passed, {b.get('failed')} failed ({b.get('browser')})")


def main(argv=None):
    argv = list(argv or [])
    mode = next((a.split("=", 1)[1] for a in argv if a.startswith("--mode=")), "built")
    if "--mode" in argv:
        mode = argv[argv.index("--mode") + 1]
    if mode not in ("built", "source", "release"):
        print("mode must be built, source or release")
        return 2
    r = Report(mode)
    r.add("NOTE", f"validation mode: {mode}; data hash {data_hash()[:16]}")
    check_files(r)
    world, cities, nation, lenses, sources, res, states, munis = (load(n) for n in ("world", "cities", "nation", "lenses", "sources", "resources", "states", "munis"))
    if any(x is None for x in (world, cities, nation, lenses, sources, states)):
        r.add("FAIL", "required data files missing; stopping")
        return _finish(r)
    hex_pop = check_world(r, world)
    city_pop = sum(c["population"] for c in cities)
    dev = abs(hex_pop - city_pop) / city_pop
    r.ok(dev < 1e-4, f"dasymetric: hex population {hex_pop:,} vs municipal total {city_pop:,} (Δ {dev:.5%}, rounding only)")
    by_region = check_cities(r, cities, world, nation, states)
    check_places(r, cities, world)
    check_munis(r, munis, cities)
    check_lenses(r, lenses, sources, world)
    if res:
        check_resources(r, res, world)
    check_sources(r, sources)
    if mode in ("source", "release"):
        check_source(r, cities, nation, states, by_region)
        check_cache(r)
    else:
        r.add("SKIP", "source reconciliation and cache verification not run in 'built' mode")
    if mode == "release":
        check_release(r, cities, nation, accept="--accept" in argv)
    return _finish(r)


def _finish(r):
    worst = "FAIL" if r.failed else "WARN" if r.count("WARN") else "PASS"
    line = (f"{r.count('PASS')} pass, {r.count('NOTE')} note, {r.count('WARN')} warn, {r.count('SKIP')} skipped, "
            f"{r.count('FAIL')} fail → {worst} (mode: {r.mode})")
    print("\n" + line)
    out = ROOT / "docs" / f"CHECK_REPORT{'' if r.mode == 'release' else '_' + r.mode.upper()}.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(f"{l:4s}  {m}" for l, m in r.lines) + "\n\n" + line + "\n")
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
