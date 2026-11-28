import { esc } from "../../format.js";

const RAD = Math.PI / 180;
const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
const MAX_KM = 100;
const METRICS = [
  { key: "temperature_c", counts: "temperature_years", label: "Mean temperature", unit: "°C" },
  { key: "precipitation_mm", counts: "precipitation_years", label: "Precipitation", unit: "mm" },
];
const fmt = (v) => v.toLocaleString("en-GB", { maximumFractionDigits: 1 });
const has = (station, metric) => station[metric.key].some(Number.isFinite) || Number.isFinite(station[`annual_${metric.key}`]);
const available = (station) => METRICS.filter((metric) => has(station, metric));

function distanceKm(a, b) {
  const dLat = (a.lat - b.lat) * RAD, dLon = (a.lon - b.lon) * RAD;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * RAD) * Math.cos(b.lat * RAD) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(Math.min(h, 1)));
}

function nearby(stations, city) {
  if (!Number.isFinite(city?.lat) || !Number.isFinite(city.lon)) return [];
  const candidates = stations.filter((s) => s.country === city.country)
    .map((station) => ({ station, km: distanceKm(station, city), metrics: [] }))
    .filter(({ km }) => km <= MAX_KM)
    .sort((a, b) => a.km - b.km || available(b.station).length - available(a.station).length);
  for (const metric of METRICS) candidates.find(({ station }) => has(station, metric))?.metrics.push(metric);
  return candidates.filter(({ metrics }) => metrics.length);
}

export function sourceLink(url, label) {
  return `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">${esc(label)} ↗</a>`;
}

export const showOnMap = `<button type="button" class="chip" data-climate-map>Show climate stations</button>`;
const stationButton = (s) => `<button class="chip" type="button" data-climate-station="${esc(s.id)}">Show ${esc(s.name)} on map</button>`;

function valuesTable(station, metrics) {
  function row(label, i) {
    const cells = metrics.map((m) => {
      const v = i === 12 ? station[`annual_${m.key}`] : station[m.key][i];
      const count = station[m.counts][i];
      if (!Number.isFinite(v)) return '<td aria-label="Unavailable">—</td>';
      return `<td>${fmt(v)}${count != null ? ` <small>${count} yr</small>` : ""}</td>`;
    }).join("");
    return `<tr><th scope="row">${label}</th>${cells}</tr>`;
  }
  return `<table class="climate-table" aria-label="Climate normals at ${esc(station.name)}">
    <thead><tr><th scope="col">Month</th>${metrics.map((m) => `<th scope="col">${m.label} (${m.unit})</th>`).join("")}</tr></thead>
    <tbody>${MONTHS.map(row).join("")}</tbody><tfoot>${row("Year", 12)}</tfoot></table>`;
}

function stationProfile(data, { station, metrics, km }, city) {
  const annual = metrics.map((m) => {
    const value = station[`annual_${m.key}`];
    const label = `Annual ${m.label.toLowerCase()}`;
    return Number.isFinite(value) ? `${label} <b>${fmt(value)} ${m.unit}</b>` : `${label} unavailable`;
  }).join(" · ");
  const unknown = metrics.some((m) => [...station[m.key], station[`annual_${m.key}`]]
    .some((value, i) => Number.isFinite(value) && station[m.counts][i] == null));
  const from = city ? ` · ${km < 1 ? "under 1" : Math.round(km)} km from ${esc(city.place || city.name)}` : "";
  return `<div class="climate-profile">
    <p><b>${esc(station.name)}</b>${from}${Number.isFinite(station.elevation_m) ? ` · ${fmt(station.elevation_m)} m above sea level` : ""}</p>
    <p>${annual}</p>
    <details${city ? "" : " open"}><summary>Month by month</summary>${valuesTable(station, metrics)}</details>
    <p class="muted small">${unknown ? "The source leaves some observation-year counts blank. " : ""}${sourceLink(station.source_url, `Station data from ${data.publishers[station.country]}`)}</p>
    ${city ? stationButton(station) : ""}</div>`;
}

export function localProfile(data, city, region = null) {
  if (!data || !city) return "";
  const matches = nearby(data.stations, city);
  const shown = matches.flatMap((m) => m.metrics);
  const missing = METRICS.filter((m) => !shown.includes(m)).map((m) => m.label.toLowerCase());
  return `<div class="climate-local">
    ${region ? `<p>Stations near <b>${esc(city.name)}</b>, the largest municipality in ${esc(region.name)}.</p>` : ""}
    <p class="muted small">1991–2020 averages at weather stations. Distances are in a straight line from the place shown on the map.</p>
    ${matches.map((m) => stationProfile(data, m, city)).join("")}
    ${missing.length ? `<p class="muted small">No station in this sample within ${MAX_KM} km supplies ${missing.join(" or ")}.</p>` : ""}
    ${matches.length ? "" : showOnMap}</div>`;
}

export function stationDetails(data, station) {
  return stationProfile(data, { station, metrics: available(station) });
}
