import { esc, int, popShort, compact } from "../format.js";
import { formatLensValue } from "./lenses.js";
import { glyph } from "./icon.js";
import { FOREIGN } from "../world.js";

const el = () => document.getElementById("tooltip");

const nameOf = (table, id) => table.find((t) => t.id === id)?.name;

export function showCellTooltip(mx, my, w, i, lens, showResources = true, muni = null) {
  const raw = w.raw;
  const lines = [];
  const city = w.cityByCell.get(i);
  if (city) lines.push(`<b>${esc(city.name)}</b> <span class="muted">· ${popShort(city.population)} people</span>`);

  const wt = w.water[i];
  if (wt) {
    const e = raw.elev[i];
    const band = e >= 0 ? "" : e > -200 ? "shelf, under 200 m" : e > -1000 ? "200–1,000 m deep" : e > -2000 ? "1,000–2,000 m deep" : e > -3000 ? "2,000–3,000 m deep" : "over 3,000 m deep";
    const depth = band ? ` <span class="muted">· ${band}</span>` : "";
    lines.push(`<b>${esc(nameOf(w.tables.water, wt) || "Water")}</b>${depth}`);
  } else {
    const cover = w.cover[i] > 0 ? nameOf(w.tables.cover, w.cover[i]) : null;
    const relief = w.relief[i] > 0 ? nameOf(w.tables.relief, w.relief[i]) : null;
    const terrain = [cover, relief].filter(Boolean).join(" · ") || (relief ?? "Land");
    lines.push(`<b>${esc(terrain)}</b> <span class="muted">· ${int(raw.elev[i])} m</span>`);
  }
  const o = raw.owner[i];
  if (muni) {
    // the municipality under the pointer, from its polygon (not the hex's dominant owner)
    lines.push(`<b>${esc(muni.name)}</b> <span class="muted">· municipality, ${esc(raw.states[muni.region]?.name || "")}</span>`);
  }
  if (o >= 0 || muni) {
    if (!muni && o >= 0) {
      const county = raw.county[i] >= 0 ? raw.counties[raw.county[i]].name + ", " : "";
      lines.push(`${esc(county)}${esc(raw.states[o].name)}`);
    }
    if (o >= 0 && Number.isFinite(raw.pop?.[i])) lines.push(`<span class="muted">This hex (93.5 km²): ≈ ${int(raw.pop[i])} residents (estimate) · ${Math.round(raw.tcd?.[i] ?? 0)}% tree cover</span>`);
    if (lens) {
      const perMuni = lens.muni_values && muni;
      const v = perMuni ? lens.muni_values[muni.id] : lens.values[i];
      const unitOf = perMuni ? (lens.resolution === "region" ? "region value" : "municipal value") : lens.resolution === "hex" ? "hex value" : lens.resolution === "derived" ? "estimate" : `${lens.resolution} value`;
      lines.push(`${glyph(lens, 13)} ${esc(lens.name)}: <b>${formatLensValue(lens, v)}</b> <span class="muted">(${unitOf})</span>`);
    }
  } else if (o === FOREIGN) {
    lines.push(`<span class="muted">Outside Norway, Sweden and Denmark (not mapped)</span>`);
  }
  const res = showResources && w.resources?.byCell.get(i);
  if (res) {
    for (const it of res.slice(0, 4)) {
      const t = w.resources.typeById.get(it.type);
      const num = it.value == null ? "" : Math.abs(it.value) < 1e6 ? int(it.value) : compact(it.value);
      const val = num ? ` · ${num}${t.unit ? " " + esc(t.unit) : ""}` : "";
      const kind = it.name && it.name !== t.name ? ` <span class="muted">· ${esc(t.name)}${val}</span>` : `<span class="muted">${val}</span>`;
      lines.push(`<span style="color:${esc(t.color || "#efe4c6")}">${glyph(t, 13)}</span> ${esc(it.name || t.name)}${kind}`);
    }
    if (res.length > 4) lines.push(`<span class="muted">+${res.length - 4} more</span>`);
  }
  if (o >= 0) lines.push(`<span class="muted">Click to open the municipality</span>`);
  show(mx, my, lines.join("<br>"));
}

/**
 * A tooltip with ready-made content: a string is HTML (escape any data yourself with format.js esc), {text} is
 * plain text. Used for registered static layers' tooltip(item).
 */
export function showHtmlTooltip(mx, my, content) {
  if (content == null || content === "") return hideTooltip();
  const html = typeof content === "string" ? content : esc(content.text ?? "");
  show(mx, my, html);
}

export function showCityTooltip(mx, my, city) {
  show(mx, my, `<b>${esc(city.full)}</b><br><span class="muted">${esc(city.type?.label || "")} · click to open the municipality</span>`);
}

function show(mx, my, html) {
  const t = el();
  t.innerHTML = html;
  t.hidden = false;
  const r = t.getBoundingClientRect();
  t.style.left = Math.max(4, Math.min(window.innerWidth - r.width - 8, mx + 16)) + "px";
  t.style.top = Math.max(4, Math.min(window.innerHeight - r.height - 8, my + 16)) + "px";
}

export function hideTooltip() {
  el().hidden = true;
}
