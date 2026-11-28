// Shared statistical semantics for every view (panels, Timeline, Explorer, Compare, advisors, exports), so they all
// apply the same rules (NC-T01, T02, T06):
//  * two population years are comparable only when both are observed on the same territory (pop_terr);
//  * a value with a suppressed component is a lower bound, and its rank is an interval when the order is uncertain;
//  * estimates are marked ≈, lower bounds ≥, missing values "–" (never 0).
import { esc, int } from "./format.js";

const fin = Number.isFinite;

/** Population of a municipality in a year, or null (unavailable, never 0). */
export const popIn = (c, y) => {
  const v = c?.pop_series?.[String(y)];
  return fin(v) ? v : null;
};

/** Is the change between y0 and y1 a demographic change on one territory? (cities: pop_terr; aggregates: values) */
export function comparable(c, y0, y1) {
  const a = popIn(c, y0), b = popIn(c, y1);
  if (!(a > 0) || b == null) return false;
  const t = c.pop_terr;
  if (!t) return true; // published aggregates (country, region) are on one territory by construction
  const t0 = t[String(y0)], t1 = t[String(y1)];
  return t0 != null && t0 === t1;
}

export function growthBetween(c, y0, y1) {
  return comparable(c, y0, y1) ? popIn(c, y1) / popIn(c, y0) - 1 : null;
}

/** Why a municipality has no comparable change between y0 and y1 (short text), or "". */
export function whyNotComparable(c, y0, y1) {
  if (comparable(c, y0, y1)) return "";
  const st = c.pop_status || {};
  for (const y of [y0, y1]) {
    if (st[String(y)] === "boundary") return `${y}: not available for today's territory`;
    if (st[String(y)] === "missing") return `${y}: not published`;
  }
  const t = c.pop_terr || {};
  const k = t[String(y0)] || t[String(y1)];
  const note = c.pop_terr_notes?.[String(k)];
  return note ? `boundary change: ${note}` : "territory changed between the two years";
}

/** Per-year status label for charts and tooltips. */
export function yearStatus(c, y) {
  const st = c.pop_status?.[String(y)];
  if (st === "boundary") return { kind: "unavailable", note: "Not available for today's territory (boundary change)" };
  if (st === "missing") return { kind: "missing", note: "Not published" };
  const k = c.pop_terr?.[String(y)];
  if (k) return { kind: "other-territory", note: c.pop_terr_notes?.[String(k)] || "Different territory" };
  return { kind: "observed", note: "Observed on today's boundaries" };
}

/** Rank text: "#12 of 745", "joint" ranks are plain competition ranks, and "#10–14 of 745" (possible ranks) when
 *  suppressed values make the order uncertain. `of` is the comparison size: a number or {key: n}. */
export function rankText(o, key, of) {
  const n = typeof of === "object" && of ? of[key] : of;
  const rr = o?.rank_range?.[key];
  if (rr) return rr[1] - rr[0] >= n / 2 ? `Rank unavailable` : `#${rr[0]}–${rr[1]} of ${n}`;
  const r = o?.ranks?.[key];
  return r ? `#${r} of ${n}` : "";
}

export const isPartial = (o, key) => (o?.yields_partial || []).includes(key);
export const isEstimate = (o, key) => (o?.yields_estimated || []).includes(key) || key === "gold";

/** Population chart with gaps for unavailable years and separate, labelled segments for other territories. */
export function popChart(c, { w = 300, h = 74, color = "#c9a45c", alt = "#8aa0c8" } = {}) {
  const ys = Object.keys(c?.pop_series || {}).map(Number).sort((a, b) => a - b);
  const pts = ys.map((y) => ({ y, v: popIn(c, y), s: c.pop_terr ? yearStatus(c, y) : { kind: "observed" } }));
  const vals = pts.filter((p) => p.v != null);
  if (vals.length < 2) return `<p class="muted">No series.</p>`;
  const x0 = ys[0], x1 = ys.at(-1);
  let lo = Math.min(...vals.map((p) => p.v)), hi = Math.max(...vals.map((p) => p.v));
  if (hi - lo < hi * 0.02) { lo -= hi * 0.01; hi += hi * 0.01; }
  const X = (y) => 6 + ((y - x0) / (x1 - x0 || 1)) * (w - 12);
  const Y = (v) => h - 18 - ((v - lo) / (hi - lo || 1)) * (h - 28);
  // one path per run of consecutive observed years on the same territory: gaps and breaks are never bridged
  const runs = [];
  let cur = null;
  for (const p of pts) {
    const key = p.v == null ? null : (c.pop_terr?.[String(p.y)] ?? 0);
    if (key == null) { cur = null; continue; }
    if (!cur || cur.key !== key) { cur = { key, pts: [] }; runs.push(cur); }
    cur.pts.push(p);
  }
  const paths = runs.map((r) => {
    const d = r.pts.map((p, k) => `${k ? "L" : "M"}${X(p.y).toFixed(1)},${Y(p.v).toFixed(1)}`).join("");
    const col = r.key ? alt : color;
    const dots = r.pts.length === 1 ? `<circle cx="${X(r.pts[0].y)}" cy="${Y(r.pts[0].v)}" r="2.5" fill="${col}"/>` : "";
    return `<path d="${d}" fill="none" stroke="${col}" stroke-width="2" ${r.key ? 'stroke-dasharray="4 3"' : ""}/>${dots}`;
  }).join("");
  const gaps = pts.filter((p) => p.v == null).map((p) => `<rect x="${X(p.y) - (w - 12) / (x1 - x0) / 2}" y="6" width="${(w - 12) / (x1 - x0)}" height="${h - 24}" fill="rgba(255,255,255,.06)"/>`).join("");
  const breaks = (c.pop_breaks || []).map((b) => b.years[0]).filter((y) => y > x0).map((y) =>
    `<line x1="${X(y - 0.5)}" x2="${X(y - 0.5)}" y1="6" y2="${h - 18}" stroke="#e5707a" stroke-width="1" stroke-dasharray="2 2"/>`).join("");
  const last = vals.at(-1), first = vals[0];
  const label = `Population ${first.y}–${last.y}: ${int(first.v)} to ${int(last.v)}` +
    (gaps ? "; some years not available for today's territory" : "") + (runs.some((r) => r.key) ? "; dashed years describe a different territory" : "");
  const legend = [];
  if (gaps) legend.push(`<span><i class="lg gap"></i>not available</span>`);
  if (runs.some((r) => r.key)) legend.push(`<span><i class="lg alt"></i>different territory</span>`);
  if (breaks) legend.push(`<span><i class="lg brk"></i>boundary change</span>`);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img" aria-label="${esc(label)}">${gaps}${breaks}${paths}
    <circle cx="${X(last.y)}" cy="${Y(last.v)}" r="3" fill="${color}"/>
    <text x="6" y="${h - 4}" font-size="10" fill="#9aa4b0">${first.y} · ${int(first.v)}</text>
    <text x="${w - 6}" y="${h - 4}" font-size="10" fill="#9aa4b0" text-anchor="end">${last.y} · ${int(last.v)}</text></svg>
    ${legend.length ? `<div class="spark-legend">${legend.join("")}</div>` : ""}`;
}

/** Boundary notes for a municipality (list items), or "". */
export function breakNotes(c) {
  const b = c?.pop_breaks || [];
  const r = c?.pop_review || [];
  const a = c?.pop_adjustments || [];
  if (!b.length && !r.length && !a.length) return "";
  const adj = a.map((x) => `<li class="muted">${esc(x.note)} ${x.sources.map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">source ${i + 1}</a>`).join(" ")}</li>`).join("");
  return `<ul class="breaks">${adj}${b.map((x) => `<li>${esc(x.note)} <a href="${esc(x.source)}" target="_blank" rel="noopener noreferrer" class="muted">source</a></li>`).join("")}
    ${r.map((x) => `<li class="muted">${x.years[0]}→${x.years[1]}: a one-year change of ${(x.change * 100).toFixed(1)}% with no boundary change recorded in SSB's classification. It may be demographic (for example a reception centre) or an unrecorded boundary adjustment; treat comparisons across it with care.</li>`).join("")}</ul>`;
}

/** Competition ranks (1 = largest, ties share a rank); null for unavailable values. Same convention as
 *  pipeline/build/ranking.py, checked against tests/fixtures/ranking_cases.json. */
export function competitionRanks(vals) {
  const sorted = vals.filter(fin).sort((a, b) => b - a);
  const first = new Map();
  sorted.forEach((v, i) => { if (!first.has(v)) first.set(v, i + 1); });
  return vals.map((v) => (fin(v) ? first.get(v) : null));
}

/** Possible-rank interval [best, worst] for each value given lower bounds lo and upper bounds hi (hi null/absent =
 *  exact): best = 1 + #(lo_j > hi_i), worst = 1 + #(hi_j > lo_i, j ≠ i). */
export function rankIntervals(lo, hi) {
  const H = lo.map((v, i) => (fin(hi?.[i]) ? hi[i] : v));
  const idx = lo.map((v, i) => i).filter((i) => fin(lo[i]));
  return lo.map((v, i) => {
    if (!fin(v)) return null;
    let best = 1, worst = 1;
    for (const j of idx) {
      if (j === i) continue;
      if (lo[j] > H[i]) best++;
      if (H[j] > v) worst++;
    }
    return [best, worst];
  });
}

/** Rank a (possibly filtered) list under the shared convention. Returns entries in deterministic display order
 *  (value, then name, then id) with {x, v, rank, range}; range is set only when bounds make the order uncertain.
 *  asc ranks the smallest first; hiOf gives an item's upper bound (lower-bound values only). */
export function rankList(list, get, { asc = false, hiOf = null } = {}) {
  const items = list.map((x) => ({ x, v: get(x) })).filter((e) => fin(e.v));
  const s = asc ? -1 : 1;
  const lo = items.map((e) => (asc ? -(hiOf ? hiOf(e.x) ?? e.v : e.v) : e.v));
  const hi = items.map((e) => (asc ? -e.v : (hiOf ? hiOf(e.x) ?? e.v : e.v)));
  const ranks = competitionRanks(items.map((e) => s * e.v));
  const ivs = hiOf ? rankIntervals(lo, hi) : null;
  items.forEach((e, i) => {
    e.rank = ranks[i];
    if (ivs && ivs[i][0] !== ivs[i][1]) e.range = ivs[i];
  });
  return items.sort((a, b) => s * (b.v - a.v) || String(a.x.name).localeCompare(String(b.x.name)) || String(a.x.id ?? a.x.ref).localeCompare(String(b.x.id ?? b.x.ref)));
}

/** Deterministic sort: by value (desc by default), ties by name then id; nulls never ranked. */
export function rankBy(list, get, desc = true) {
  return list.map((x) => [x, get(x)]).filter(([, v]) => fin(v))
    .sort((a, b) => (desc ? b[1] - a[1] : a[1] - b[1]) || String(a[0].name).localeCompare(String(b[0].name)) || String(a[0].id).localeCompare(String(b[0].id)));
}
