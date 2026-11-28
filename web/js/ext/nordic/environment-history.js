import { esc } from "../../format.js";

// Published areas, NVE Fakta 1/2024, p. 1. These are whole glaciers,
// not municipal or county totals. Only the two observed years are shown.
const SOURCE = "https://publikasjoner.nve.no/fakta/2024/fakta2024_01.pdf";
const HAZARDS = "https://www.nve.no/naturfare/utredning-av-naturfare/flom-og-skredfare-i-din-kommune/faresonekart-kommuner/";
const FLOOD = "https://temakart.nve.no/tema/flomaktsomhet";
export const GLACIERS = Object.freeze([
  {name: "Jostedalsbreen", region: "NO-46", place: "Vestland", from: 1966, to: 2020, before: 486, after: 456},
  {name: "Nordmannsjøkelen", region: "NO-56", place: "Seiland, Finnmark", from: 1970, to: 2023, before: 4.8, after: 1.4},
  {name: "Seilandsjøkelen", region: "NO-56", place: "Seiland, Finnmark", from: 1970, to: 2023, before: 14.9, after: 7.9},
].map(Object.freeze));

export function glacierChanges(scope = "") {
  return GLACIERS.filter(g => !scope || scope === "NO" || g.region === scope)
    .map(g => ({...g, loss: Math.round((g.before - g.after) * 10) / 10,
      percent: Math.round((1 - g.after / g.before) * 1000) / 10}));
}

function external(url, label) {
  return '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">' + esc(label) + ' ↗</a>';
}

export function glacierHistoryHtml(scope = "") {
  const rows = glacierChanges(scope);
  if (!rows.length) return "";
  return '<div class="environment-history"><h4>Glacier area over time</h4><p class="muted small">Selected Norwegian glaciers, not totals for the surrounding area. Each comparison uses its own observation years.</p>' +
    rows.map(g => '<p><b>' + esc(g.name) + '</b> · ' + esc(g.place) + '<br>' +
      g.from + ': ' + g.before + ' km² → ' + g.to + ': ' + g.after + ' km²<br>' +
      '<span class="muted">Down ' + g.loss + ' km² (' + g.percent + '%)</span></p>').join("") +
    '<p class="muted small">' + external(SOURCE, "NVE glacier overview, 2024") + '</p></div>';
}

export function hazardLinksHtml(scope = "") {
  if (scope && scope !== "NO" && !scope.startsWith("NO-")) return "";
  return '<div class="environment-hazards"><h4>Flood and landslide maps in Norway</h4>' +
    '<p>' + external(HAZARDS, "NVE hazard maps by municipality") + ' · ' +
    external(FLOOD, "NVE flood susceptibility map") + '</p>' +
    '<p class="muted small">Hazard maps show modeled areas; the flood susceptibility map shows areas to investigate, not flood probability. These are not current warnings or a property-level assessment.</p></div>';
}
