"""Historical population: observation status, territorial comparability and published reference series.

Municipal population series are published on *current* (2024–2026) boundaries where the statistical agency can
sum former units into today's municipalities (SSB codelist agg_KommSummer; SCB and DST have had no municipal
reforms in the period). Where that is not possible the agencies say so in their own way, and a raw series can
contain values that are not population at all. This module turns every municipality-year into one of:

  value + territory code 0      observed on the current boundaries
  value + territory code k > 0  observed, but for a different territory (described in `pop_terr_notes[k]`)
  null  + status "boundary"     not available for this geography (the source reports 0 for a code that could
                                not be reconstructed for that year, e.g. municipalities formed in 2020 from
                                split predecessors). Never zero population.
  null  + status "missing"      not published

Two municipality-years are comparable when, and only when, both are observed on the same territory code. All growth
figures, rankings and Timeline comparisons use that rule (see `comparable`).

Discontinuities are detected from evidence, in this order (each rule is reported in the break's `rule` field):
  R1 source-zero      SSB reports 0 persons for a municipality-year although the municipality has residents in other
                      years: the agency could not reconstruct the unit (SSB: "Hvordan ivareta historikken").
  R2 absorbed         a municipality with an R1 block was part of another one in those years: the other series jumps by
                      the absorbed unit's population at both ends of the block (±10 %). Those years of the absorbing
                      municipality describe a larger territory.
  R3 split            SSB's classification of municipalities (KLASS 131) records an old unit divided between several new
                      ones on a date; a receiving municipality whose change in that year departs from its country's
                      change by more than 1.5 percentage points gets a break there.
Remaining one-year changes above 6 % are listed for review in the validation report and are not altered: a pairing
heuristic for unrecorded boundary adjustments was tried and rejected because it also flagged ordinary demographic
changes (e.g. in Sweden, which had no municipal boundary changes in the period).
"""
from __future__ import annotations

import json
from collections import defaultdict

from ..core import jsonstat
from ..core.paths import INTERIM, RAW

YEARS = list(range(2008, 2027))
SSB_HISTORY_URL = "https://www.ssb.no/statbank/hvordan-bruke-statistikkbanken/hvordan-ivareta-historikken"
KLASS_URL = "https://data.ssb.no/api/klass/v1/classifications/131/changes"
# documentation of recorded adjustments that are too small to treat as breaks (what moved, from the decisions)
MINOR_ADJUSTMENTS = {
    ("3118", "2026-01-01"): {
        "what": "Two small areas moved from Indre Østfold on 1 January 2026: about 565 decares with eight property "
                "units by Slemmestadveien to Nordre Follo (ministry decision), and the Loska cabin area (about 17 "
                "cabins) to Vestby.",
        "sources": ["https://cms12.regjeringen.no/contentassets/184b7148f75f48c0b62ef525af395005/vedtak-om-grensejustering-mellom-indre-ostfold-og-l412550.pdf",
                    "https://www.vestby.kommune.no/politikk/styringsdokumenter/kommuneplan/rullering-av-kommuneplan-2023-2034"]},
}
EXCESS_PP = 0.015
REVIEW_JUMP = 0.06


def _national_change(country_series):
    return {y: (country_series[y] / country_series[y - 1] - 1) for y in YEARS[1:]
            if country_series.get(y) and country_series.get(y - 1)}


def classify(munis: list[dict], country_pop: dict[str, dict[int, float]]) -> dict:
    """Return {muni id: {"series", "terr", "status", "breaks", "terr_notes"}} and a list of review notes."""
    by_id = {m["id"]: m for m in munis}
    nat = {cc: _national_change(s) for cc, s in country_pop.items()}
    out = {}
    for m in munis:
        raw = {y: m["pop"].get(y) for y in YEARS}
        positive = [y for y, v in raw.items() if v]
        series, status, terr = {}, {}, {}
        for y, v in raw.items():
            if v is None:
                series[y], status[y], terr[y] = None, "missing", None
            elif v == 0 and positive:
                series[y], status[y], terr[y] = None, "boundary", None
            else:
                series[y], status[y], terr[y] = v, "observed", 0
        breaks = []
        zero_years = [y for y in YEARS if status[y] == "boundary"]
        if zero_years:
            breaks.append({"rule": "R1", "kind": "source-zero", "years": [zero_years[0], zero_years[-1]],
                           "note": f"Statistics Norway publishes 0 persons for {zero_years[0]}–{zero_years[-1]}: the "
                                   "municipality could not be reconstructed on today's boundaries for those years "
                                   "(predecessors were split or the unit did not exist). Shown as not available.",
                           "source": SSB_HISTORY_URL})
        out[m["id"]] = {"series": series, "status": status, "terr": terr, "breaks": breaks, "terr_notes": {}}

    # R2: absorbed units -> the absorbing municipality describes a larger territory in the block years
    for mid, h in out.items():
        b = next((b for b in h["breaks"] if b["rule"] == "R1"), None)
        if not b:
            continue
        y0, y1 = b["years"]
        m = by_id[mid]
        before, after = m["pop"].get(y0 - 1), m["pop"].get(y1 + 1)
        if not before or not after:
            continue  # block at the start or end of the period: no absorbing partner to look for
        for pid, ph in out.items():
            if pid == mid or by_id[pid]["country"] != m["country"]:
                continue
            p = by_id[pid]["pop"]
            if not all(p.get(y) for y in (y0 - 1, y0, y1, y1 + 1)):
                continue
            jump_in, jump_out = p[y0] - p[y0 - 1], p[y1] - p[y1 + 1]
            if abs(jump_in - before) <= 0.1 * before and abs(jump_out - after) <= 0.1 * after:
                k = max(ph["terr_notes"], default=0) + 1
                ph["terr_notes"][k] = f"{y0}–{y1}: includes {m['name']}, which was part of {by_id[pid]['name']} in those years"
                for y in range(y0, y1 + 1):
                    ph["terr"][y] = k
                ph["breaks"].append({"rule": "R2", "kind": "absorbed", "years": [y0, y1], "related": [mid], "terr": k,
                                     "note": ph["terr_notes"][k] + "; not comparable with other years.",
                                     "source": SSB_HISTORY_URL})
                b["related"] = [pid]
                b["note"] += f" In {y0}–{y1} its residents are counted in {by_id[pid]['name']}."
                break

    # R3: splits recorded in KLASS 131
    klass = RAW / "ssb" / "klass131_changes_2008_2026.json"
    if klass.exists():
        changes = json.loads(klass.read_text())["codeChanges"]
        dest = defaultdict(set)
        later = defaultdict(list)  # code -> [(date, new code)] to follow a code to today's code
        for c in changes:
            dest[(c["oldCode"], c["changeOccurred"])].add(c["newCode"])
            if c["oldCode"] != c["newCode"]:
                later[c["oldCode"]].append((c["changeOccurred"], c["newCode"]))

        def current(code, date, depth=0):
            nxt = sorted((d, n) for d, n in later.get(code, []) if d > date)
            if not nxt or depth > 6:
                return {code}
            d0 = nxt[0][0]
            return set().union(*(current(n, d0, depth + 1) for d, n in nxt if d == d0))
        for (old, date), news in dest.items():
            if len(news) < 2:
                continue
            year = int(date[:4])
            if year not in YEARS[1:]:
                continue
            receivers = set().union(*(current(n, date) for n in news))
            for code in receivers:
                mid = f"NO-{code}"
                h = out.get(mid)
                if not h or h["terr"].get(year) is None or h["terr"].get(year - 1) is None:
                    continue
                if h["terr"][year] != h["terr"][year - 1]:
                    continue  # already separated by R2
                ch = h["series"][year] / h["series"][year - 1] - 1
                excess = ch - nat["NO"].get(year, 0)
                if abs(excess) > EXCESS_PP:
                    _split_before(h, year, f"Before {year}: boundaries before part of a divided municipality "
                                           f"(code {old}) was transferred; the {year} change ({ch:+.1%}) is mainly "
                                           "the transfer, not demographic growth.", "R3", "split",
                                  [f"NO-{c}" for c in receivers if f"NO-{c}" != mid], KLASS_URL)
                else:
                    # a recorded adjustment too small to separate from ordinary change: kept comparable, but noted
                    others = sorted(by_id[f"NO-{c}"]["name"] for c in receivers if c != old and f"NO-{c}" in by_id)
                    doc = MINOR_ADJUSTMENTS.get((old, date), {})
                    h.setdefault("adjustments", []).append({
                        "year": year, "change": round(ch, 4), "national": round(nat["NO"].get(year, 0), 4),
                        "note": f"{year}: SSB's classification records a boundary adjustment between "
                                f"{by_id.get('NO-' + old, {}).get('name', old)} and {', '.join(others)}. "
                                + (doc.get("what", "") + " " if doc else "")
                                + f"The {year - 1}→{year} change here ({ch:+.1%}; the year before "
                                f"{(h['series'][year - 1] / h['series'][year - 2] - 1) if h['series'].get(year - 2) else float('nan'):+.1%}; "
                                f"Norway {nat['NO'].get(year, 0):+.1%}) does not stand out, so the years are treated as "
                                "comparable. SSB's table does not say how many residents moved.",
                        "sources": [KLASS_URL] + doc.get("sources", [])})

    # SSB's own notes on table 07459 document small transfers it does not harmonise (and series it does): shown as
    # context on the municipality, never used to change a value
    src = RAW / "ssb" / "07459_pop_age.json"
    if src.exists():
        notes = json.loads(src.read_text())["dimension"]["Region"]["category"].get("note", {})
        for code, txt in notes.items():
            h = out.get("NO-" + code[2:])
            if h is None or h["breaks"]:
                continue
            h.setdefault("adjustments", []).append({"year": None, "note": "Statistics Norway's note: " + " ".join(t.strip() for t in txt),
                                                    "sources": ["https://www.ssb.no/en/statbank/table/07459"]})

    review = []
    for mid, h in out.items():
        s, t = h["series"], h["terr"]
        for y in YEARS[1:]:
            if t.get(y) is not None and t.get(y) == t.get(y - 1) and s[y - 1]:
                ch = s[y] / s[y - 1] - 1
                if abs(ch) > REVIEW_JUMP:
                    review.append(f"{mid} {by_id[mid]['name']} {y - 1}→{y}: {ch:+.1%} (no recorded boundary change)")
                    h.setdefault("review", []).append({"years": [y - 1, y], "change": round(ch, 4)})
    return {"munis": out, "review": review}


def _split_before(h, year, note, rule, kind, related, source):
    k = max(h["terr_notes"], default=0) + 1
    h["terr_notes"][k] = note
    for y in YEARS:
        if y < year and h["terr"].get(y) == 0:
            h["terr"][y] = k
    h["breaks"].append({"rule": rule, "kind": kind, "years": [year, year], "related": related, "terr": k, "note": note,
                        "source": source})


def comparable(h: dict, y0: int, y1: int) -> bool:
    t0, t1 = h["terr"].get(y0), h["terr"].get(y1)
    return t0 is not None and t0 == t1 and bool(h["series"].get(y0)) and h["series"].get(y1) is not None


def growth(h: dict, y0: int, y1: int):
    return (h["series"][y1] / h["series"][y0] - 1) if comparable(h, y0, y1) else None


# --- published reference series -----------------------------------------------------------------------------------
def country_series() -> dict:
    """{cc: {year: population}} from each agency's own national total (not a sum of municipalities)."""
    ssb = json.loads((INTERIM / "ssb.json").read_text())
    scb = json.loads((INTERIM / "scb.json").read_text())
    dst = json.loads((INTERIM / "dst.json").read_text())
    return {
        "NO": {int(k): v for k, v in ssb["country"]["pop"].items() if v},
        "SE": {int(k): v for k, v in scb["country"]["pop"].items() if v},
        "DK": {int(k): v for k, v in dst["country"]["pop"].items() if v},
    }


COUNTRY_SOURCE = {
    "NO": "SSB 07459, the whole country (excl. Svalbard and Jan Mayen)",
    "SE": "SCB TAB628, Sweden (31 December of the previous year)",
    "DK": "DST FOLK1A, all Denmark (1st day of Q1)",
}


def norway_counties() -> dict:
    """{region id: {year: population}} from SSB 07459 on the 2024 counties; years the county did not exist are 0
    in the source and are dropped here."""
    p = RAW / "ssb" / "07459_pop_county2024.json"
    if not p.exists():
        return {}
    js = jsonstat.load(p)
    out = defaultdict(dict)
    for d, v, _ in jsonstat.records(js):
        if v:
            out[f"NO-{d['Region']}"][int(d["Tid"])] = v
    return dict(out)


def sweden_lan() -> dict:
    scb = json.loads((INTERIM / "scb.json").read_text())
    return {f"SE-{k}": {int(y): v for y, v in r.get("pop", {}).items() if v} for k, r in scb["lan"].items()}


def region_series(members: list[dict], hist: dict, published: dict | None) -> tuple[dict, dict, dict]:
    """Population of a region by year, with its basis per year: 'published' (agency total for the region),
    'sum' (sum of member municipalities, all comparable on current boundaries) or None (not available; coverage
    gives the share of the region's 2026 population that could be summed)."""
    series, basis, coverage = {}, {}, {}
    tot26 = sum(hist[m["id"]]["series"].get(2026) or 0 for m in members) or 1
    for y in YEARS:
        if published and published.get(y):
            series[y], basis[y] = published[y], "published"
            continue
        ids = {m["id"] for m in members}

        def covered(h):
            t = h["terr"].get(y)
            if t == 0:
                return True
            for b in h["breaks"]:  # transfers wholly inside the region do not change the region's territory
                rel = set(b.get("related") or [])
                if not rel or not rel <= ids:
                    continue
                if t is not None and b.get("terr") == t:
                    return True
                if t is None and b["rule"] == "R1" and b["years"][0] <= y <= b["years"][1]:
                    return all(hist[r]["series"].get(y) for r in rel)
            return False
        ok = [m for m in members if covered(hist[m["id"]])]
        if len(ok) == len(members):
            series[y], basis[y] = sum(hist[m["id"]]["series"][y] or 0 for m in members), "sum"
        else:
            series[y], basis[y] = None, None
            coverage[y] = round(sum(hist[m["id"]]["series"].get(2026) or 0 for m in ok) / tot26, 4)
    return series, basis, coverage
