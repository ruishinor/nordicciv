// NordicCiv municipality panel ("city" in the engine: every municipality is a city).
// Everything shown carries its meaning, unit and source; estimates are marked ≈, lower bounds ≥, missing values "–".
import { css } from "../color.js";
import { compact, esc, int, money, pct, popShort } from "../format.js";
import { icon, glyph } from "./icon.js";
import { DISTRICT_ICON, showPanel, hidePanel } from "./infoPanel.js";
import { industryIcon } from "./yieldReport.js";
import { popChart, breakNotes, rankText, isPartial } from "../stats.js";
import { distinctiveHtml } from "../explore.js";
import { mapsLink, municipalityTarget, settlementTarget, wonderTarget, airportTarget, portTarget } from "../app/maps.js";
import { muniFeature } from "../render/art/relief.js";

const COUNTRY = { NO: "Norway", SE: "Sweden", DK: "Denmark" };
const FLAG = { NO: "🇳🇴", SE: "🇸🇪", DK: "🇩🇰" };
const fin = Number.isFinite;
export const signed = (g, d = 1) => (fin(g) ? `${g >= 0 ? "+" : "−"}${Math.abs(g * 100).toFixed(d)}%` : "–");

/** Small inline SVG line chart of a {year: value} series. */
export function sparkline(series, { w = 280, h = 54, color = "#c9a45c" } = {}) {
  const pts = Object.entries(series || {}).filter(([, v]) => fin(v)).map(([y, v]) => [+y, v]);
  if (pts.length < 2) return `<p class="muted">No series.</p>`;
  const x0 = pts[0][0], x1 = pts.at(-1)[0];
  let lo = Math.min(...pts.map((p) => p[1])), hi = Math.max(...pts.map((p) => p[1]));
  if (hi - lo < hi * 0.02) { lo -= hi * 0.01; hi += hi * 0.01; }
  const X = (y) => 4 + ((y - x0) / (x1 - x0 || 1)) * (w - 8);
  const Y = (v) => h - 14 - ((v - lo) / (hi - lo || 1)) * (h - 22);
  const d = pts.map(([y, v], k) => `${k ? "L" : "M"}${X(y).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="100%" height="${h}" role="img" aria-label="Population ${x0}–${x1}: ${int(pts[0][1])} to ${int(pts.at(-1)[1])}">
    <path d="${d}" fill="none" stroke="${color}" stroke-width="2"/>
    <circle cx="${X(x1)}" cy="${Y(pts.at(-1)[1])}" r="3" fill="${color}"/>
    <text x="4" y="${h - 2}" font-size="10" fill="#9aa4b0">${x0} · ${compact(pts[0][1])}</text>
    <text x="${w - 4}" y="${h - 2}" font-size="10" fill="#9aa4b0" text-anchor="end">${x1} · ${compact(pts.at(-1)[1])}</text></svg>`;
}

const DETAIL_LABEL = { B: "Mining & oil/gas extraction", C: "Manufacturing", M72: "Scientific R&D", L: "Real estate",
  "68-75": "Real estate, professional & technical", "77-82": "Administrative & support" };

/** Yield tiles: game name, value with its real unit, status (≈ estimate, ≥ lower bound), rank or rank interval. */
export function yieldTiles(nation, o, rankOf, ranks = o.ranks) {
  return nation.yields.map((y) => {
    const v = o.yields?.[y.key];
    const est = y.key === "gold" && (o.yields_estimated || []).includes("gold") || y.key === "gold" && o.municipalities == null && o.gdp_region;
    const partial = isPartial(o, y.key);
    const prefix = v == null ? "" : partial ? "≥" : est ? "≈" : "";
    const val = v == null ? "–" : prefix + (y.unit === "eur" ? money(v) : compact(v));
    const hi = partial && fin(o.yields_hi?.[y.key]) ? ` (at most ${y.unit === "eur" ? money(o.yields_hi[y.key]) : compact(o.yields_hi[y.key])})` : "";
    const nOf = typeof rankOf === "object" ? rankOf[y.key] : rankOf;
    const rk = ranks === o.ranks ? rankText(o, y.key, rankOf) : (ranks?.[y.key] ? `#${ranks[y.key]} of ${nOf}` : "");
    const tip = `${y.label} = ${y.measure || ""}. ${y.description}${partial ? ` Some small job counts are withheld for privacy. The total is at least the number shown${hi}.` : ""}`;
    return `<div class="yield-tile" title="${esc(tip)}">
      <div class="ico" style="color:${esc(y.color)}">${glyph(y, 20)}</div>
      <div class="val" style="color:${esc(y.color)}">${val}</div>
      <div class="lbl">${esc(y.key === "gold" ? "Gold" : y.label)}</div>
      <div class="meas">${esc(y.measure || "")}</div>
      ${rk ? `<div class="rank" title="Rank among the ${nOf} areas with a value (1 = largest; equal values share a rank)${o.rank_range?.[y.key] ? ". Possible ranks because some job counts are not published" : ""}">${rk}</div>` : ""}</div>`;
  }).join("");
}

function row(label, value, cmp = "", tip = "") {
  return `<div class="stat-row" ${tip ? `title="${esc(tip)}"` : ""}><span class="sl">${label}</span><span><b>${value}</b>${cmp ? `<span class="cmp">${cmp}</span>` : ""}</span></div>`;
}

/** Jobs by harmonised industry group, with location quotients against Norway+Sweden+Denmark. */
export function industryBars(o, nation, limit = 0) {
  const total = o.jobs_total || o.employed || 0;
  const bench = nation.nation.jobs || {};
  const bTot = nation.nation.jobs_total || 1;
  let rows = Object.entries(o.jobs || {}).filter(([k, v]) => v > 0 && k !== "X").sort((a, b) => b[1] - a[1]);
  if (limit) rows = rows.slice(0, limit);
  if (!rows.length || !total) return `<p class="muted">No industry data.</p>`;
  const maxShare = rows[0][1] / total;
  return rows.map(([k, v]) => {
    const share = v / total;
    const lq = bench[k] ? share / (bench[k] / bTot) : null;
    const partial = (o.jobs_partial || []).includes(k);
    const badge = lq == null ? "" : lq >= 1.5 ? `<span class="lq hi" title="Location quotient: share of local jobs ÷ Scandinavian share">×${lq.toFixed(1)}</span>`
      : lq <= 0.6 ? `<span class="lq lo" title="Location quotient">×${lq.toFixed(1)}</span>` : "";
    return `<div class="ind"><span aria-hidden="true">${icon(industryIcon(k), DISTRICT_ICON[k] || "•")}</span>
      <span>${esc(nation.industries?.[k] || k)}${badge}</span><span class="n">${partial ? "≥" : ""}${compact(v)} · ${pct(share, 0)}</span>
      <div class="bar"><i style="width:${(share / maxShare) * 100}%;background:${lq >= 1.5 ? "#9fd76a" : "#c9a45c"}"></i></div></div>`;
  }).join("");
}

function sitesIn(city) {
  const data = window.__app?.data || {};
  const out = [];
  const res = data.resources?.items || [];
  const types = new Map((data.resources?.types || []).map((t) => [t.id, t]));
  for (const it of res) {
    if (it.cbsa !== city.id) continue;
    const t = types.get(it.type) || {};
    out.push({ kind: t.name || it.type, name: it.name, val: it.value != null ? `${it.value.toLocaleString("en-US")} ${t.unit || ""}` : it.detail || "", t });
  }
  // Public places a visitor can go to get an "Open in Maps" link; energy and extraction sites do not.
  for (const wd of data.wonders?.wonders || []) {
    if (wd.county === city.id) out.push({ kind: "Wonder", name: wd.name, val: wd.rule.replace("_", " "), wonder: true, maps: wonderTarget(wd) });
  }
  for (const a of data.infrastructure?.airports || []) {
    if (a.county === city.id && a.passengers) out.push({ kind: "Airport", name: a.name, val: `${compact(a.passengers)} passengers (2024)`, maps: airportTarget(a) });
  }
  for (const p of data.infrastructure?.ports || []) {
    if (p.county === city.id) out.push({ kind: "Port", name: p.short || p.name, val: `${compact(p.tonnes)} t goods (2024)`, maps: portTarget(p) });
  }
  return out;
}

const SOURCES = {
  NO: [["Population, age", "SSB 07459 (1 January 2008–2026, 2024 municipalities, aggregated series)"], ["Area", "SSB 09280 (2026)"],
    ["Jobs by industry", "SSB 07984 (employed 15–74 by place of work, Q4 2024)"], ["Income", "SSB 06944 (median household income after tax, 2024)"]],
  SE: [["Population, area", "SCB TAB628 (31 December 2007–2025)"], ["Age", "SCB TAB5557 (2025)"],
    ["Jobs by industry", "SCB TAB3204 (employed 16–74 by place of work, November 2024)"], ["Income", "SCB TAB4840 (median net income 20+, 2024)"]],
  DK: [["Population, age", "DST FOLK1A (1st quarter 2008–2026)"], ["Area", "DST ARE207"],
    ["Jobs by industry", "DST RAS501 (employed by place of work, November 2024)"], ["Income", "DST INDKP101 (average disposable income, 2024)"]],
};

export function openCityPanel(city, ctx) {
  const { w, nation } = ctx;
  const cn = nation.countries?.[city.country] || {};
  const owner = city.cell != null ? w.raw.owner[city.cell] : -1;
  const col = css(w.stateColor[owner] || [190, 190, 190]);
  const regionIdx = w.raw.states.findIndex((s) => s.abbr === city.states?.[0]);
  const regionName = regionIdx >= 0 ? w.raw.states[regionIdx].name : "";
  const count = ctx.cities?.length || 745;
  const t = city.type || {};
  const badge = `<span class="ctype" style="--c:${esc(t.color || "#9aa4b0")}" title="Strongest specialisation: ${esc(t.rule || "")}">${esc(t.label || "Diversified")}</span>`;
  const gy = city.growth_years || [2016, 2026];
  const growth = fin(city.growth)
    ? ` · <span class="growth ${city.growth >= 0 ? "up" : "down"}" title="Population change ${gy.join("–")} on the same territory (national registers)">${city.growth >= 0 ? "▲" : "▼"} ${Math.abs(city.growth * 100).toFixed(1)}% <span class="since">since ${gy[0]}</span></span>`
    : ` · <span class="muted" title="${esc(city.growth_note || "")}">no comparable ${gy[0]} figure <button class="link" data-cptab-go="Society">why?</button></span>`;
  const head = `<div class="cp-pop">${icon("pop", "👥", { size: 16 })} <b>${int(city.population)}</b> residents <span class="muted">(1 Jan ${nation.year})</span>${growth}</div>
    <div class="cp-pop">${icon("y-production", "🏢", { size: 14 })} <b>${int(city.jobs_total)}</b> jobs located here
    <span class="muted">(place of work, 2024 · ${fin(city.jobs_per_100) ? Math.round(city.jobs_per_100) : "–"} per 100 residents)</span></div>`;

  const cmp = (v, nv, f) => (fin(v) && fin(nv) ? `${COUNTRY[city.country]} ${f(nv)}` : "");
  const incDef = nation.income_definitions?.[city.country] || "";
  const profile = [
    row("Land area", city.land_km2 != null ? `${int(city.land_km2)} km²` : "–", "", "Land area (excluding fresh water where the agency separates it)"),
    row("Density", fin(city.density) ? `${city.density < 10 ? city.density.toFixed(1) : int(city.density)} /km²` : "–", cmp(city.density, cn.density, (x) => x.toFixed(0) + " /km²")),
    row("Aged 65+", pct(city.share_65plus), cmp(city.share_65plus, cn.share_65plus, (x) => pct(x))),
    row("Aged 0–19", pct(city.share_0_19), cmp(city.share_0_19, cn.share_0_19, (x) => pct(x))),
    row("Income relative to national reference", fin(city.income_index) ? `${Math.round(city.income_index * 100)}%` : "–",
      city.income != null ? `${int(city.income)} ${city.income_currency}` : "",
      `${incDef}. 100% = ${COUNTRY[city.country]}'s own figure. Compare within a country only: the three statistics differ.`),
    row("Nearest larger municipality", city.nearest_bigger_km != null ? `${Math.round(city.nearest_bigger_km)} km` : "— (largest)", "",
      "Straight-line distance between main settlements to the nearest municipality with more residents"),
  ].join("");

  // largest industry vs strongest relative specialisation: two different questions (§16.1)
  const jobsRows = Object.entries(city.jobs || {}).filter(([k, v]) => k !== "X" && v > 0).sort((a, b) => b[1] - a[1]);
  const largest = jobsRows[0];
  const sp = city.specialisations || [];
  const specSummary = `<div class="spec-two">
      <div><span class="muted small">Largest industry by jobs</span><br><b>${largest ? esc(nation.industries[largest[0]]) : "–"}</b>
        ${largest ? `<span class="muted">${compact(largest[1])} jobs · ${pct(largest[1] / city.jobs_total, 0)}</span>` : ""}</div>
      <div><span class="muted small">Strongest relative specialisation</span><br><b>${sp[0] ? esc(sp[0].label) : "none (diversified)"}</b>
        ${sp[0] ? `<span class="muted">×${sp[0].lq.toFixed(2)} · ${sp[0].partial ? "≥" : ""}${compact(sp[0].jobs)} jobs</span>` : ""}</div></div>
    <p class="muted small">A location quotient (×) compares the industry's share of local jobs with its share in Norway, Sweden and Denmark combined.
      It measures relative concentration — not output, productivity or importance. Listed from ×${nation.lq_rule?.min_lq} with ≥ ${nation.lq_rule?.min_jobs} jobs.</p>`;
  const specs = sp.length
    ? `<div class="spec-list">${sp.map((s) => `<div class="spec"><span>${icon(industryIcon(s.group), DISTRICT_ICON[s.group] || "•", { size: 14 })} ${esc(s.label)}</span>
        <span><b>×${s.lq.toFixed(2)}</b> <span class="muted">${s.partial ? "≥" : ""}${compact(s.jobs)} jobs</span>
        <button class="chip sm" data-spec="${esc(s.group)}" title="Show where this industry concentrates">Map ›</button></span></div>`).join("")}</div>`
    : `<p class="muted">No industry group reaches ×${nation.lq_rule?.min_lq} with ${nation.lq_rule?.min_jobs}+ jobs: a diversified economy (or too small to tell).</p>`;
  const detail = city.jobs_detail || {};
  const detailTxt = Object.entries(detail).filter(([, v]) => v != null).map(([k, v]) => `${DETAIL_LABEL[k] || k}: ${compact(v)}`).join(" · ");

  const sites = sitesIn(city);
  const siteHtml = sites.length
    ? `<div class="site-list">${sites.slice(0, 14).map((s) => `<div class="site${s.maps ? " has-maps" : ""}"><span>${s.t ? glyph(s.t, 13) : s.wonder ? "🏛️" : "•"} ${esc(s.name)}</span><span class="muted">${esc(s.kind)}${s.val ? " · " + esc(s.val) : ""}</span>${s.maps ? mapsLink(s.maps, { cls: "chip sm maps-open", label: "Open in Maps" }) : ""}</div>`).join("")}${sites.length > 14 ? `<p class="muted">+${sites.length - 14} more</p>` : ""}</div>
       <p class="muted small">The Almanac lists the site types and minimum sizes included on the map.</p>`
    : `<p class="muted">No sites of the types and sizes shown on this map are listed here.</p>`;

  const peers = (city.peers || []).map((id) => ctx.cities?.find((c) => c.id === id)).filter(Boolean);
  const peerHtml = peers.length ? `<div class="chips">${peers.map((p) => `<button class="chip" data-city="${esc(p.id)}" title="${esc(p.full)}">${FLAG[p.country] || ""} ${esc(p.name)} · ${popShort(p.population)}</button>`).join("")}</div>
    <p class="muted small">Closest in population size (log scale), any country. The Council's Compare tab finds peers by other criteria.</p>` : "";
  const gdpBlock = city.gdp != null
    ? `<div class="stat-row"><span class="sl">${icon("y-gold", "🪙", { size: 14 })}Economic output (estimate)</span><span><b>≈ ${money(city.gdp)}</b><span class="cmp">${city.population ? "≈ " + money(city.gdp / city.population) + " per resident" : ""}</span></span></div>
      <p class="muted small">${esc(city.gdp_region_name || city.gdp_region)}'s published ${city.gdp_year} output (${esc(city.gdp_concept || "")}) shared ${city.gdp_method === "sector"
        ? "by each industry's regional value added and this municipality's jobs in that industry (real estate by residents)" : "by this municipality's share of the region's jobs"}.
        Estimated from published regional statistics. ${fin(city.gdp_jobshare) ? `A plain job-share split would give ≈ ${money(city.gdp_jobshare)}.` : ""}
        Concepts differ between countries; Norway excludes the continental shelf.</p>` : `<p class="muted">No output estimate.</p>`;

  const actions = `<div class="cp-actions" role="group" aria-label="Explore from here">
      <button class="chip" data-act="neighbours" title="Compare with the municipalities that border it">Compare with neighbours</button>
      <button class="chip" data-act="peers" title="Municipalities of similar size and economic structure">Similar municipalities</button>
      ${sp[0] ? `<button class="chip" data-spec="${esc(sp[0].group)}" title="Colour the map by this specialisation">Where else: ${esc(sp[0].label)}</button>` : ""}
      <button class="chip" data-act="council" title="What the advisors observe about ${esc(city.name)}">Ask the Council</button>
      <button class="chip" data-act="history" title="Population over time">Population history</button>
      <button class="chip" data-compare="${esc(city.id)}" title="Add to the comparison">Compare ⇄</button></div>`;
  // The real place: the municipality as an area, and its main settlement (a named place) at town scale.
  const muniMaps = municipalityTarget(city, { grid: w.grid, muniFeature });
  const townMaps = settlementTarget(city);
  const townName = (city.place || "").split("/")[0];
  // The settlement's own name where it differs ("Open København in Maps"); "the town"/"the city" where it is the
  // municipality's name too, so the two links never read the same.
  const townLabel = townName && townName !== city.name ? `Open ${townName} in Maps` : `Open the ${city.population >= 50000 ? "city" : "town"} in Maps`;
  const mapsHtml = muniMaps || townMaps ? `<div class="cp-actions" role="group" aria-label="Open external maps">
      ${mapsLink(muniMaps, { id: "municipality" })}
      ${townMaps ? mapsLink(townMaps, { label: townLabel, id: "settlement" }) : ""}</div>` : "";

  const srcRows = (SOURCES[city.country] || []).map(([k, v]) => row(k, "", v)).join("");
  const status = `<ul class="status-list">
      <li><b>Published figures</b>: population, age, area, jobs by industry (as published by ${city.country === "NO" ? "SSB" : city.country === "SE" ? "SCB" : "DST"})</li>
      ${(city.yields_partial || []).length ? `<li><b>Lower bound (≥)</b>: ${city.yields_partial.map((k) => esc(nation.yields.find((y) => y.key === k)?.label || k)).join(", ")} — ${int(city.jobs_unallocated || 0)} jobs have no published industry breakdown</li>` : ""}
      <li><b>Estimate (≈)</b>: economic output (Gold)</li>
      ${!fin(city.growth) ? `<li><b>Population change</b>: ${esc(city.growth_note || "No comparable figures")}</li>` : ""}</ul>`;

  showPanel({
    kind: "city",
    stripe: col,
    title: city.name,
    titleHtml: `${city.capital ? `<span class="cap" title="National capital">★</span> ` : ""}${esc(city.name)} ${badge}`,
    sub: `${FLAG[city.country] || ""} Municipality in ${esc(regionName)}, ${COUNTRY[city.country]}${city.place && city.place !== city.name ? ` · main settlement ${esc(city.place)}` : ""}
      <div class="chips">${regionIdx >= 0 ? `<button class="chip" data-state="${regionIdx}" title="Open ${esc(regionName)}">${esc(regionName)} ›</button>` : ""}
      <button class="chip" data-compare="${esc(city.id)}" title="Compare this municipality with others">Compare ⇄</button></div>`,
    headExtra: head,
    sections: [
      { tab: "Overview", title: "What stands out", html: distinctiveHtml(city, ctx.cities || []) },
      { tab: "Overview", title: `Yields · what each measures · rank among ${count}`, html: `<div class="yield-grid">${yieldTiles(nation, city, nation.rank_of?.municipalities || count)}</div>
        <p class="muted small">Yields are game names for real figures: five count jobs at the place of work (2024), Gold is economic output (estimate). They are not production, research output or welfare quality. <a href="#" data-pedia-yields>What each yield measures ›</a></p>` },
      { tab: "Overview", title: "Economic profile", html: specSummary },
      { tab: "Overview", title: "Explore from here", html: actions },
      mapsHtml && { tab: "Overview", title: "Maps", html: mapsHtml },
      ...extraSections(ctx, city, "Overview"),
      { tab: "Economy", title: "Economic output", html: gdpBlock },
      { tab: "Economy", title: "Specialisations", html: specs + (detailTxt ? `<p class="muted small">Finer detail published by ${COUNTRY[city.country]}: ${esc(detailTxt)}</p>` : "") },
      { tab: "Economy", title: "Jobs by industry · place of work, 2024", html: industryBars(city, nation) },
      { tab: "Economy", title: "Resources, wonders & hubs", html: siteHtml },
      { tab: "Society", title: `Population ${Object.keys(city.pop_series || {})[0] || 2008}–${nation.year}`, html: popChart(city) + breakNotes(city) },
      { tab: "Society", title: "People and place", html: profile },
      ...extraSections(ctx, city, "Society"),
      peers.length && { tab: "Society", title: "Similar-sized municipalities", html: peerHtml },
      { tab: "Sources", title: "Data status", html: status },
      { tab: "Sources", title: "Tables", html: srcRows + row("Economic output", "", nation.gdp_vintage || "") + row("Boundary", "", "Municipal polygons for display; statistics refer to the municipality as published") },
    ],
    foot: `Population 1 January ${nation.year}; jobs November/Q4 2024. Banner placed at ${esc(city.place || "the municipality")} (${esc(city.anchor || "")}).`,
    onClose: ctx.onClose,
    onPedia: ctx.onPedia,
    wire(panel) {
      panel.querySelectorAll("[data-state]").forEach((b) => (b.onclick = () => ctx.onState(+b.dataset.state)));
      panel.querySelectorAll("[data-city]").forEach((b) => (b.onclick = () => {
        const c = ctx.cities.find((x) => x.id === b.dataset.city);
        if (c) ctx.onCity(c);
      }));
      panel.querySelectorAll("[data-compare]").forEach((b) => (b.onclick = () => window.__app?.emit?.("compare", { add: city.id })));
      panel.querySelectorAll("[data-spec]").forEach((b) => (b.onclick = () => window.__app?.emit?.("focus-industry", { group: b.dataset.spec, from: city.id })));
      panel.querySelectorAll("[data-facet]").forEach((b) => (b.onclick = () => window.__app?.emit?.("explore-facet", { facet: b.dataset.facet, city: city.id })));
      panel.querySelectorAll("[data-act]").forEach((b) => (b.onclick = () => window.__app?.emit?.("discover", { act: b.dataset.act, city: city.id })));
      panel.querySelectorAll("[data-cptab-go]").forEach((b) => (b.onclick = () => panel.querySelector(`[data-cptab="${b.dataset.cptabGo}"]`)?.click()));
      panel.querySelector("[data-pedia-yields]")?.addEventListener("click", (e) => { e.preventDefault(); ctx.onPedia?.("yields"); });
      for (const fn of ctx.extraWire || []) {
        try { fn(panel, city); } catch (err) { console.error("city panel wiring failed", err); }
      }
    },
  });
}

export const closeCityPanel = hidePanel;

// Sections contributed by extensions (app.addCitySections): fn(city) → [{tab, title, html, wire?}]; a failing
// provider is logged and skipped so the panel always opens.
function extraSections(ctx, city, tab) {
  const out = [];
  for (const fn of ctx.extraSections || []) {
    try {
      for (const s of fn(city) || []) if (s && (s.tab || "Society") === tab) out.push({ tab, ...s });
    } catch (err) {
      console.error("city panel section failed", err);
    }
  }
  return out;
}
