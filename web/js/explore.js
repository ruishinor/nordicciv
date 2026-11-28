// Discovery: what makes a place distinctive, and surprising facts to start from (NC-X01, NC-X02).
//
// Every statement here is computed from the shipped data with a rule that is stated next to it: a municipality is
// "among the most …" only when it is in the top or bottom 5 % of the municipalities that have the figure (competition
// ranks, the same convention as everywhere else), and a discovery names its exact value, rank and the population
// filter used. Nothing is a composite score; estimates keep their ≈ and their definition.
import { compact, esc, int, pct, sentenceCase } from "./format.js";
import { rankList } from "./stats.js";

const fin = Number.isFinite;
const sgn = (v, d = 1) => (v >= 0 ? "+" : "−") + Math.abs(v * 100).toFixed(d) + "%";

/** Measures with a plain-language reading for each end. `lens` = the map lens that shows it. */
export const FACETS = [
  { id: "growth", lens: "growth", get: (c) => c.growth,
    hi: "one of the fastest-growing municipalities", lo: "one of the fastest-shrinking municipalities",
    value: (v) => `${sgn(v)} residents since 2016`, def: "Population change 1 Jan 2016 → 1 Jan 2026 on the same territory (municipalities whose boundaries changed are left out)." },
  { id: "density", lens: "density", get: (c) => c.density,
    hi: "one of the most densely populated", lo: "one of the most thinly populated",
    value: (v) => `${v < 10 ? v.toFixed(1) : int(v)} residents per km² of land`, def: "Residents (1 Jan 2026) per km² of land area (lakes excluded)." },
  { id: "ageing", lens: "ageing", get: (c) => c.share_65plus,
    hi: "one of the highest shares of residents aged 65+", lo: "one of the lowest shares of residents aged 65+",
    value: (v) => `${pct(v, 0)} of residents aged 65 or over`, def: "Share of residents aged 65+, 1 Jan 2026." },
  { id: "jobs", lens: "jobs_ratio", get: (c) => c.jobs_per_100,
    hi: "a job centre: One of the highest numbers of jobs per resident", lo: "a commuter home: One of the lowest numbers of jobs per resident",
    value: (v) => `${v.toFixed(0)} jobs located here per 100 residents`, def: "Jobs at workplaces in the municipality (2024) per 100 residents (2026). Above 100 means people commute in; it is not an employment rate." },
  // distance to a larger municipality says something about small places only (for Copenhagen it is the distance to
  // Oslo), so it is measured among municipalities under 50,000 residents
  { id: "remote", lens: null, get: (c) => ((c.population || 0) < 50000 ? c.nearest_bigger_km : null),
    hi: "remote: Unusually far from any larger municipality (among those under 50,000 residents)", lo: null,
    value: (v) => `${int(v)} km to the nearest more populous municipality`, def: "Straight-line distance between the main settlements of this and the nearest municipality with more residents." },
  { id: "area", lens: null, get: (c) => c.land_km2,
    hi: "one of the largest by land area", lo: "one of the smallest by land area",
    value: (v) => `${int(v)} km² of land`, def: "Land area (water excluded) as published by the national agency." },
];

const TOP = 0.05; // "among the most" = top or bottom 5 %

function ranked(cities, facet) {
  if (!facet._r) {
    const list = rankList(cities, facet.get); // competition ranks, largest first
    const n = list.length;
    const lo = rankList(cities, facet.get, { asc: true });
    facet._r = { n, hi: new Map(list.map((e) => [e.x.id, e.rank])), lo: new Map(lo.map((e) => [e.x.id, e.rank])), order: list };
  }
  return facet._r;
}

/** Up to `max` distinctive facts about one municipality, most extreme first; [] when it is typical everywhere. */
export function distinctive(c, cities, max = 4) {
  const out = [];
  for (const f of FACETS) {
    const v = f.get(c);
    if (!fin(v)) continue;
    const r = ranked(cities, f);
    for (const side of ["hi", "lo"]) {
      if (!f[side]) continue;
      const rank = r[side].get(c.id);
      if (rank && rank <= Math.max(1, Math.floor(TOP * r.n))) {
        // the neighbours in the ranking: municipalities most alike on this measure
        const k = r.order.findIndex((e) => e.x.id === c.id);
        const near = r.order.slice(Math.max(0, k - 2), k + 3).filter((e) => e.x.id !== c.id).slice(0, 3).map((e) => e.x);
        out.push({ facet: f, side, rank, n: r.n, v, share: rank / r.n, near,
          text: `${f[side]} in Scandinavia`, detail: `${f.value(v)} · #${rank} of ${r.n} from the ${side === "hi" ? "top" : "bottom"}` });
      }
    }
  }
  // the strongest specialisation, when it is far above the Scandinavian mix
  const sp = (c.specialisations || [])[0];
  if (sp && sp.lq >= 2.5) {
    out.push({ facet: { id: "spec", def: "Location quotient: the industry's share of local jobs ÷ its share in Norway, Sweden and Denmark combined (place of work, 2024). It measures concentration, not output." },
      side: "hi", share: 1 / sp.lq, group: sp.group,
      text: `${sp.lq.toFixed(1)} times the Scandinavian share of jobs in ${sp.label.toLowerCase()}`, detail: `${sp.partial ? "≥" : ""}${int(sp.jobs)} jobs` });
  }
  return out.sort((a, b) => a.share - b.share).slice(0, max);
}

/** HTML for the panel section; buttons carry data-facet / data-spec / data-city for the caller to wire. */
export function distinctiveHtml(c, cities) {
  const items = distinctive(c, cities);
  if (!items.length) {
    return `<p class="muted">Close to the Scandinavian middle on every measure checked here (growth, density, age, jobs per resident,
      distance, area, specialisation): No figure is in the top or bottom 5%. The similar-municipality and Council views show how it compares.</p>`;
  }
  return `<ul class="standout">${items.map((it) => `<li title="${esc(it.facet.def)}">
      <div><b>${esc(sentenceCase(it.text))}</b> <span class="muted">${esc(it.detail)}</span></div>
      <div class="chips">${it.facet.lens ? `<button class="chip sm" data-facet="${esc(it.facet.id)}" title="Colour the map by this measure">Map ›</button>` : ""}
        ${it.group ? `<button class="chip sm" data-spec="${esc(it.group)}" title="Where else this industry concentrates">Where else ›</button>` : ""}
        ${(it.near || []).map((x) => `<button class="chip sm" data-city="${esc(x.id)}" title="${esc(x.full || x.name)}">${esc(x.name)}</button>`).join("")}</div></li>`).join("")}</ul>
    <p class="muted small">"Among the most" = top or bottom 5% of the municipalities with the figure. The names are its neighbours in that ranking. Hover an item for the definition.</p>`;
}

/** Facts worth discovering, each tied to a municipality and a lens. Small municipalities are filtered where a ratio
 *  would otherwise be dominated by a few hundred people (the filter is part of the sentence). */
export function discoveries(cities, nation) {
  const out = [];
  const big = cities.filter((c) => (c.population || 0) >= 5000);
  const top = (list, get, asc = false) => rankList(list, get, { asc })[0];
  const add = (c, text, lens, extra = {}) => c && out.push({ id: `${extra.key || lens}:${c.id}`, city: c.id, text, lens,
    facet: extra.facet || FACETS.find((f) => f.lens && f.lens === lens)?.id || null, ...extra });
  let e = top(big, (c) => c.growth);
  add(e?.x, `${e?.x.name} has grown faster than any other municipality of 5,000+ residents: ${sgn(e?.v)} since 2016.`, "growth");
  e = top(big, (c) => c.growth, true);
  add(e?.x, `${e?.x.name} has lost the largest share of its residents among municipalities of 5,000+: ${sgn(e?.v)} since 2016.`, "growth", { key: "shrink" });
  e = top(cities, (c) => c.jobs_per_100);
  add(e?.x, `${e?.x.name} has ${e?.v.toFixed(0)} jobs located there for every 100 residents — the most in Scandinavia. Most of its workers live elsewhere.`, "jobs_ratio");
  e = top(cities, (c) => c.share_65plus);
  add(e?.x, `In ${e?.x.name}, ${pct(e?.v, 0)} of residents are 65 or older — the oldest population in Scandinavia.`, "ageing");
  e = top(big, (c) => c.share_0_19);
  add(e?.x, `${e?.x.name} has the youngest population of the municipalities with 5,000+ residents: ${pct(e?.v, 0)} are under 20.`, "youth", { def: "Share of residents aged 0–19, 1 Jan 2026." });
  e = top(cities, (c) => ((c.population || 0) < 50000 ? c.nearest_bigger_km : null));
  add(e?.x, `Of the municipalities under 50,000 residents, ${e?.x.name} is the furthest from a larger one: ${int(e?.v)} km to the nearest municipality with more residents.`, null, { key: "remote", facet: "remote" });
  e = top(cities, (c) => c.density);
  add(e?.x, `${e?.x.name} is the most densely populated municipality: ${int(e?.v)} residents per km² of land.`, "density");
  e = top(cities, (c) => c.land_km2);
  add(e?.x, `${e?.x.name} is the largest municipality by land area: ${int(e?.v)} km² — and has ${compact(e?.x.population)} residents.`, null, { key: "area", facet: "area" });
  // strongest concentration of each industry among municipalities with 250+ jobs in it
  for (const g of Object.keys(nation.industries || {})) {
    if (g === "X") continue;
    const list = cities.filter((c) => (c.jobs?.[g] || 0) >= 250 && fin(c.lq?.[g]));
    const b = top(list, (c) => c.lq[g]);
    if (b && b.v >= 3) add(b.x, `${b.x.name} has ${b.v.toFixed(1)} times the Scandinavian share of jobs in ${nation.industries[g].toLowerCase()} (${int(b.x.jobs[g])} jobs; municipalities with 250+ such jobs).`, null, { key: `lq_${g}`, group: g });
  }
  // places whose history is a boundary story (from the population breaks)
  for (const c of cities) {
    const b = (c.pop_breaks || []).find((x) => x.kind === "absorbed" || x.rule === "R2");
    if (b && (c.population || 0) >= 5000) add(c, `${c.name}'s population series jumps because of a boundary change, not migration: ${b.note}`, null, { key: "history",
      def: "Population years are compared only on the same territory; the Society tab shows the series with the break marked." });
  }
  return out;
}

export { sgn };
