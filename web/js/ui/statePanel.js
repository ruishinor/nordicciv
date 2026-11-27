// NordicCiv region panel: fylke (Norway), län (Sweden), region (Denmark).
import { css } from "../color.js";
import { esc, int, pct, popShort } from "../format.js";
import { icon } from "./icon.js";
import { showPanel } from "./infoPanel.js";
import { yieldTiles, industryBars, sparkline } from "./cityPanel.js";

const COUNTRY = { NO: "Norway", SE: "Sweden", DK: "Denmark" };
const KIND = { NO: "County (fylke)", SE: "County (län)", DK: "Region" };
const FLAG = { NO: "🇳🇴", SE: "🇸🇪", DK: "🇩🇰" };
const LAND = [["forest", "Forest", "#2f5a3a"], ["crop", "Farmland", "#c9b955"], ["pasture", "Pasture", "#8fb04e"], ["heath", "Fjell heath", "#9c9a6e"],
  ["bare", "Bare rock", "#a8a196"], ["wetland", "Mire & wetland", "#5f8a74"], ["shrub", "Woodland & scrub", "#8f9a58"], ["developed", "Built-up", "#8a8378"],
  ["ice", "Glacier", "#e8eef2"], ["grass", "Grassland", "#a9b35a"]];

export function openStatePanel(idx, ctx) {
  const { w, nation } = ctx;
  const geo = w.raw.states[idx] || {};
  let st = ctx.states?.find((s) => s.fips === geo.fips) || ctx.states?.[idx] || { ...geo };
  const cc = st.country || geo.country;
  const count = ctx.states?.length || 41;
  const cities = (ctx.cities || []).filter((c) => c.states?.[0] === geo.abbr).sort((a, b) => b.population - a.population);
  const top = cities.slice(0, 10);
  const cityRows = `<div class="city-list">${top.map((c) => `<button class="city-row" data-city="${esc(c.id)}" title="${esc(c.full)}">
      <span class="cr-name">${c.capital ? "★ " : ""}${esc(c.name)} <span class="muted">· ${esc(c.type?.label || "")}</span></span>
      <span class="cr-pop">${popShort(c.population)}</span><span class="cr-go" aria-hidden="true">›</span></button>`).join("")}</div>
      ${cities.length > 10 ? `<p class="muted small">${cities.length - 10} more municipalities.</p>` : ""}`;
  const land = st.land || {};
  const landBar = `<div class="landbar">${LAND.filter(([k]) => land[k] > 0.005).map(([k, name, c]) =>
    `<i style="flex:${land[k]};background:${c}" title="${name}: ${pct(land[k], 0)}"></i>`).join("")}</div>
    <div class="landlegend">${LAND.filter(([k]) => land[k] >= 0.03).map(([k, name, c]) => `<span><b style="background:${c}"></b>${name} ${pct(land[k], 0)}</span>`).join("")}</div>
    <p class="muted small">Average share of hex land in each CORINE 2018 group (1 km cells).</p>`;
  const growth = Number.isFinite(st.growth) ? ` · <span class="growth ${st.growth >= 0 ? "good" : "bad"}">${st.growth >= 0 ? "▲" : "▼"} ${Math.abs(st.growth * 100).toFixed(1)}% <span class="since">since ${st.growth_years?.[0]}</span></span>` : "";
  showPanel({
    kind: "state",
    stripe: css(w.stateColor[idx] || [190, 190, 190]),
    title: st.name || geo.name,
    sub: `${FLAG[cc] || ""} ${KIND[cc] || "Region"} · ${COUNTRY[cc] || ""} · ${int(st.municipalities)} municipalities · ${int(st.land_km2)} km² land`,
    headExtra: `<div class="cp-pop">${icon("pop", "👥", { size: 16 })} <b>${int(st.population)}</b> residents${growth}</div>
      <div class="cp-pop"><span class="muted">${int(st.jobs_total)} jobs · ${Number.isFinite(st.density) ? st.density.toFixed(1) : "–"} residents/km² · aged 65+ ${pct(st.share_65plus)}</span></div>`,
    sections: [
      st.yields && { title: `Yields · rank among the ${count} regions`, html: `<div class="yield-grid">${yieldTiles(nation, st, count)}</div>
        <p class="muted small">GDP is the sum of the municipalities' estimates; for Swedish län and Danish regions it equals the published regional GDP, for Norway's 2024 counties split from Viken, Vestfold og Telemark and Troms og Finnmark it is apportioned by jobs.</p>` },
      { title: "Population 2008–2026", html: sparkline(st.pop_series) },
      { title: "Land", html: landBar },
      st.jobs && { title: "Jobs by industry · place of work, 2024", html: industryBars(st, nation, 8) },
      { title: "Largest municipalities", html: cityRows },
    ],
    foot: `Sums of municipal statistics (SSB, SCB, DST); GDP: ${esc(nation.gdp_vintage || "")}.`,
    onClose: ctx.onClose,
    onPedia: ctx.onPedia,
    wire(panel) {
      panel.querySelectorAll("[data-city]").forEach((b) => {
        b.onclick = () => {
          const c = ctx.cities.find((x) => x.id === b.dataset.city);
          if (c) ctx.onCity(c);
        };
      });
    },
  });
}
