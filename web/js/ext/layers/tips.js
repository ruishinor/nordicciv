// Hover tooltips for the map-art layers (HTML strings; every data value is escaped). Each says where the number comes
// from and the caveat that matters for it (FAF values are model estimates; bases have no published headcount; the
// trade arc is a drawing aid; curated landmarks are an editorial pick).
import { esc, compact, int, pct } from "../../format.js";
import { FORT_KINDS, fortKind, WONDER_KINDS } from "../../render/art/sites.js";
import { MODE_STYLE } from "../../render/art/improvements.js";

const muted = (s) => `<span class="muted">${s}</span>`;
const num = (n, d = 1) => (n == null || !Number.isFinite(n) ? "–" : compact(n));
const sign = (x) => (x > 0 ? "+" : x < 0 ? "−" : "±");

function usd(n) {
  if (n == null || !Number.isFinite(n)) return "–";
  const a = Math.abs(n);
  if (a >= 1e12) return `$${(n / 1e12).toFixed(2)} trillion`;
  if (a >= 1e9) return `$${(n / 1e9).toFixed(a >= 1e10 ? 1 : 2)} billion`;
  if (a >= 1e6) return `$${(n / 1e6).toFixed(1)} million`;
  return `$${int(n)}`;
}

const HUB_NAME = { L: "Large hub", M: "Medium hub", S: "Small hub", N: "Nonhub primary airport" };
const PORT_TYPE = { coastal: "Coastal port", great_lakes: "Great Lakes port", inland: "Inland river port" };

export const tips = {
  port(p, m) {
    return [
      `<b>${esc(p.name)}</b> ${muted(esc(p.country || ""))}`,
      `#${esc(p.rank)} by goods handled · <b>${num(p.tonnes)}</b> tonnes (${esc(p.year ?? "")})`,
      muted("Eurostat maritime statistics (main ports, gross weight of goods). Placed at the port's town."),
    ].join("<br>");
  },
  airport(a) {
    const HUB = { L: "Large airport (10 M+ passengers)", M: "Medium (2–10 M)", S: "Small (0.3–2 M)", N: "Regional (under 0.3 M)" };
    const lines = [`<b>${esc(a.iata || a.id)} · ${esc(a.name)}</b> ${muted(esc([a.city, a.country].filter(Boolean).join(", ")))}`];
    if (a.hub) lines.push(esc(HUB[a.hub] || a.hub));
    if (a.passengers != null) lines.push(`<b>${num(a.passengers)}</b> passengers carried in ${esc(a.year)} (arrivals + departures)`);
    lines.push(muted("Eurostat avia_paoa; positions from OurAirports."));
    return lines.join("<br>");
  },
  fort(f, m) {
    const comp = m.data.military?.components?.find((c) => c.id === f.component);
    const name = comp?.name || FORT_KINDS[fortKind(f.component)]?.name || "Defense site";
    const tier = { major: "Major installation", base: "Base", site: "Site" }[f.tier] || "";
    const status = { act: "", semi: " · semi-active", care: " · caretaker status" }[f.status] ?? "";
    const lines = [
      `<b>${esc(f.name)}</b> ${muted(esc(f.state || ""))}`,
      `${esc(name)}${f.joint ? " · joint base" : ""} · ${esc(tier)}${esc(status)}`,
    ];
    if (f.area_km2 != null) lines.push(`Boundary ${int(f.area_km2)} km²`);
    lines.push(muted("DoD MIRTA. Sized by boundary area: no per-base headcount is published."));
    return lines.join("<br>");
  },
  range(r, m) {
    const comp = m.data.military?.components?.find((c) => c.id === r.component);
    return [
      `<b>${esc(r.name)}</b> ${muted(esc(r.state || ""))}`,
      `Restricted ground · ${esc(comp?.name || "")} · ${int(r.area_km2)} km²`,
      muted("One of the 30 largest DoD boundaries (MIRTA), drawn on the hexes it covers."),
    ].join("<br>");
  },
  wonder(x, m) {
    const rule = m.data.wonders?.rules?.find((r) => r.id === x.rule);
    const mt = x.metrics || {};
    const CAT = { heritage: "World Heritage (cultural)", natural: x.rule === "world_heritage" ? "World Heritage (natural)" : "National park", university: "University", engineering: "Engineering wonder" };
    const lines = [`<b>${esc(x.name)}</b> ${muted(esc(mt.country || mt.countries?.join(", ") || ""))}`, esc(CAT[x.category || x.kind] || "Wonder")];
    if (mt.inscribed) lines.push(`Inscribed on the UNESCO list in ${esc(mt.inscribed)}${mt.components_in_scandinavia > 1 ? ` · ${esc(mt.components_in_scandinavia)} components` : ""}`);
    if (mt.area_km2 != null) lines.push(`${int(mt.area_km2)} km²${mt.established ? ` · established ${esc(mt.established)}` : ""}`);
    if (x.kind === "university") lines.push(`${mt.students ? `${int(mt.students)} students` : "student count not recorded"}${mt.founded ? ` · founded ${esc(mt.founded)}` : ""}`);
    if (mt.length_km != null) lines.push(`${esc(mt.type)} · ${esc(mt.length_km)} km · opened ${esc(mt.opened)}`);
    if (rule?.text) lines.push(muted(esc(rule.text)));
    return lines.join("<br>");
  },
  route(rt, m) {
    const r = rt.route;
    const t = m.data.trade || {};
    const a = rt.a?.short || rt.a?.name || r.a, b = rt.b?.short || rt.b?.name || r.b;
    const modes = Object.entries(r.modes || {}).filter(([, v]) => v >= 0.05).sort((p, q) => q[1] - p[1])
      .map(([k, v]) => `${esc(MODE_STYLE[k]?.label || k)} ${Math.round(v * 100)}%`).join(" · ");
    const com = t.commodities?.[r.top_commodity];
    const lines = [
      `<b>${esc(a)} ⇄ ${esc(b)}</b> ${muted(`trade route #${esc(r.rank)}`)}`,
      `<b>${usd(r.value_musd * 1e6)}</b> of freight a year, ${num(r.tons_k * 1e3)} short tons (FAF ${esc(t.year ?? "")} estimate)`,
    ];
    if (modes) lines.push(modes);
    if (com) lines.push(`Top commodity: ${esc(com)}`);
    lines.push(muted("Both directions summed. Drawn as an arc between each zone's largest city: FAF records where freight starts and ends, not its route."));
    return lines.join("<br>");
  },
};
