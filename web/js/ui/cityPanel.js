// NordicCiv municipality panel ("city" in the engine: every municipality is a city).
// Everything shown carries its meaning, unit and source; estimates are marked ≈, lower bounds ≥, missing values "–".
import { css } from "../color.js";
import { compact, esc, int, money, pct, popShort } from "../format.js";
import { icon, glyph } from "./icon.js";
import { DISTRICT_ICON, showPanel, hidePanel } from "./infoPanel.js";
import { industryIcon } from "./yieldReport.js";

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

/** Yield tiles with ranks; ≈ for estimates, ≥ for lower bounds (suppressed components). */
export function yieldTiles(nation, o, rankOf, ranks = o.ranks) {
  return nation.yields.map((y) => {
    const v = o.yields?.[y.key];
    const est = (o.yields_estimated || []).includes(y.key) || y.key === "gold" && o.municipalities == null && o.gdp_region;
    const partial = (o.yields_partial || []).includes(y.key);
    const prefix = v == null ? "" : partial ? "≥" : est ? "≈" : "";
    const val = v == null ? "–" : prefix + (y.unit === "eur" ? money(v) : compact(v));
    const r = ranks?.[y.key];
    const tip = `${y.label}: ${y.description}${partial ? " Some components are suppressed by the agency for confidentiality: this is a lower bound." : ""}`;
    return `<div class="yield-tile" title="${esc(tip)}">
      <div class="ico" style="color:${esc(y.color)}">${glyph(y, 20)}</div>
      <div class="val" style="color:${esc(y.color)}">${val}</div>
      <div class="lbl">${esc(y.key === "gold" ? "GDP" : y.label)}</div>
      ${r ? `<div class="rank" title="Rank among ${rankOf} (1 = largest)">#${r} of ${rankOf}</div>` : ""}</div>`;
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
  for (const wd of data.wonders?.wonders || []) {
    if (wd.county === city.id) out.push({ kind: "Wonder", name: wd.name, val: wd.rule.replace("_", " "), wonder: true });
  }
  for (const a of data.infrastructure?.airports || []) {
    if (a.county === city.id && a.passengers) out.push({ kind: "Airport", name: a.name, val: `${compact(a.passengers)} passengers (2024)` });
  }
  for (const p of data.infrastructure?.ports || []) {
    if (p.county === city.id) out.push({ kind: "Port", name: p.short || p.name, val: `${compact(p.tonnes)} t goods (2024)` });
  }
  return out;
}

export function openCityPanel(city, ctx) {
  const { w, nation } = ctx;
  const n = nation.nation;
  const cn = nation.countries?.[city.country] || {};
  const owner = city.cell != null ? w.raw.owner[city.cell] : -1;
  const col = css(w.stateColor[owner] || [190, 190, 190]);
  const regionIdx = w.raw.states.findIndex((s) => s.abbr === city.states?.[0]);
  const regionName = regionIdx >= 0 ? w.raw.states[regionIdx].name : "";
  const count = ctx.cities?.length || 745;
  const t = city.type || {};
  const badge = `<span class="ctype" style="--c:${esc(t.color || "#9aa4b0")}" title="City type: ${esc(t.rule || "")}">${esc(t.label || "Diversified")}</span>`;
  const growth = fin(city.growth)
    ? ` · <span class="growth ${city.growth >= 0 ? "good" : "bad"}" title="Population change ${city.growth_years.join("–")} (national registers)">${city.growth >= 0 ? "▲" : "▼"} ${Math.abs(city.growth * 100).toFixed(1)}% <span class="since">since ${city.growth_years[0]}</span></span>`
    : ` · <span class="muted" title="No ${city.growth_years?.[0]} figure on today's borders">growth n/a</span>`;
  const head = `<div class="cp-pop">${icon("pop", "👥", { size: 16 })} <b>${int(city.population)}</b> residents${growth}</div>
    <div class="cp-pop">${icon("y-production", "🏢", { size: 14 })} <b>${int(city.jobs_total)}</b> jobs located here
    <span class="muted">(${fin(city.jobs_per_100) ? Math.round(city.jobs_per_100) : "–"} per 100 residents)</span></div>`;

  const cmp = (v, nv, f) => (fin(v) && fin(nv) ? `${COUNTRY[city.country]} ${f(nv)}` : "");
  const profile = [
    row("Land area", city.land_km2 != null ? `${int(city.land_km2)} km²` : "–", "", "Land area (excluding fresh water where the agency separates it)"),
    row("Density", fin(city.density) ? `${city.density < 10 ? city.density.toFixed(1) : int(city.density)} /km²` : "–", cmp(city.density, cn.density, (x) => x.toFixed(0) + " /km²")),
    row("Aged 65+", pct(city.share_65plus), cmp(city.share_65plus, cn.share_65plus, (x) => pct(x))),
    row("Aged 0–19", pct(city.share_0_19), cmp(city.share_0_19, cn.share_0_19, (x) => pct(x))),
    row("Income vs national", fin(city.income_index) ? `${Math.round(city.income_index * 100)}%` : "–",
      city.income != null ? `${int(city.income)} ${city.income_currency}` : "",
      "Experimental: Norway median household income after tax; Sweden median net income 20+; Denmark average disposable income. Compare within a country."),
    row("Nearest larger municipality", city.nearest_bigger_km != null ? `${Math.round(city.nearest_bigger_km)} km` : "— (largest)", "",
      "Straight-line distance between main settlements to the nearest municipality with more residents"),
  ].join("");

  const specs = (city.specialisations || []).length
    ? `<div class="spec-list">${city.specialisations.map((s) => `<div class="spec"><span>${icon(industryIcon(s.group), DISTRICT_ICON[s.group] || "•", { size: 14 })} ${esc(s.label)}</span>
        <span><b>×${s.lq.toFixed(2)}</b> <span class="muted">${s.partial ? "≥" : ""}${compact(s.jobs)} jobs</span></span></div>`).join("")}</div>
       <p class="muted small">Location quotient = share of local jobs ÷ share in Norway, Sweden and Denmark combined. Listed when ≥ ${nation.lq_rule?.min_lq} with ≥ ${nation.lq_rule?.min_jobs} jobs.</p>`
    : `<p class="muted">No industry group reaches a location quotient of ${nation.lq_rule?.min_lq} with ${nation.lq_rule?.min_jobs}+ jobs: a diversified economy (or too small to tell).</p>`;
  const detail = city.jobs_detail || {};
  const detailTxt = Object.entries(detail).filter(([, v]) => v != null).map(([k, v]) => `${k === "B" ? "Mining & oil/gas extraction" : k === "C" ? "Manufacturing" : "Scientific R&D"}: ${compact(v)}`).join(" · ");

  const sites = sitesIn(city);
  const siteHtml = sites.length
    ? `<div class="site-list">${sites.slice(0, 14).map((s) => `<div class="site"><span>${s.t ? glyph(s.t, 13) : s.wonder ? "🏛️" : "•"} ${esc(s.name)}</span><span class="muted">${esc(s.kind)}${s.val ? " · " + esc(s.val) : ""}</span></div>`).join("")}${sites.length > 14 ? `<p class="muted">+${sites.length - 14} more</p>` : ""}</div>`
    : `<p class="muted">No mapped power plants, fields, mines, wonders, ports or major airports in this municipality.</p>`;

  const peers = (city.peers || []).map((id) => ctx.cities?.find((c) => c.id === id)).filter(Boolean);
  const peerHtml = peers.length ? `<div class="chips">${peers.map((p) => `<button class="chip" data-city="${esc(p.id)}" title="${esc(p.full)}">${FLAG[p.country] || ""} ${esc(p.name)} · ${popShort(p.population)}</button>`).join("")}</div>` : "";
  const gdpNote = city.gdp != null
    ? `<p class="muted small">GDP ≈ ${money(city.gdp)}: the ${city.gdp_year} GDP of ${esc(city.gdp_region_name || city.gdp_region)} × this municipality's share of the region's jobs (an estimate; output per job is assumed equal within the region).</p>` : "";

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
      { title: "Yields · rank among the 745 municipalities", html: `<div class="yield-grid">${yieldTiles(nation, city, count)}</div>${gdpNote}` },
      { title: "Population 2008–2026", html: sparkline(city.pop_series) },
      { title: "Society", html: profile },
      { title: "Specialisation", html: specs + (detailTxt ? `<p class="muted small">Finer detail published by ${COUNTRY[city.country]}: ${esc(detailTxt)}</p>` : "") },
      { title: "Jobs by industry · place of work, 2024", html: industryBars(city, nation) },
      { title: "Resources, wonders & hubs", html: siteHtml },
      peers.length && { title: "Similar-sized municipalities", html: peerHtml },
    ],
    foot: `Sources: ${city.country === "NO" ? "SSB tables 07459, 09280, 07984, 06944" : city.country === "SE" ? "SCB TAB628, TAB5557, TAB3204, TAB4840" : "DST FOLK1A, ARE207, RAS501, INDKP101"};
      GDP: ${esc(nation.gdp_vintage || "")}. Population 1 January ${nation.year}; jobs November/Q4 2024. Banner placed at ${esc(city.place || "the municipality")} (${esc(city.anchor || "")}).`,
    onClose: ctx.onClose,
    onPedia: ctx.onPedia,
    wire(panel) {
      panel.querySelectorAll("[data-state]").forEach((b) => (b.onclick = () => ctx.onState(+b.dataset.state)));
      panel.querySelectorAll("[data-city]").forEach((b) => (b.onclick = () => {
        const c = ctx.cities.find((x) => x.id === b.dataset.city);
        if (c) ctx.onCity(c);
      }));
      panel.querySelectorAll("[data-compare]").forEach((b) => (b.onclick = () => window.__app?.emit?.("compare", { add: city.id })));
    },
  });
}

export const closeCityPanel = hidePanel;
