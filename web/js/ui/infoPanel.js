// Shared building blocks for the city and state panels (both render into #city-panel).
import { compact, dollars, esc, int, money, pct } from "../format.js";
import { icon } from "./icon.js";

// Industry → a "district" glyph: SVG icons i-<key> from icons.js; these emoji are only the fallback.
export const DISTRICT_ICON = {
  agriculture: "🌾", mining: "⛏️", construction: "🏗️", manufacturing: "🏭", wholesale: "📦", retail: "🛍️",
  transportation: "🚢", utilities: "⚡", information: "📡", finance: "🏦", real_estate: "🏘️", professional: "🔬",
  management: "🏢", admin: "🗂️", education: "🎓", health: "🏥", arts: "🎭", accommodation: "🍽️", other: "🔧",
  public_admin: "🏛️",
  A: "🌾", BC: "🏭", DE: "⚡", F: "🏗️", G: "🛍️", H: "🚢", I: "🍽️", J: "📡", K: "🏦", LMN: "🔬", O: "🏛️", P: "🎓", Q: "🏥", RS: "🎭", X: "❔",
};

const panelEl = () => document.getElementById("city-panel");
const restoreEl = () => document.getElementById("btn-inspector");
let collapsed = false, currentKey = null;
function syncPanel(focus = false) {
  const panel = panelEl(), restore = restoreEl();
  panel.hidden = collapsed;
  document.body.classList.toggle("panel-open", !collapsed);
  restore.hidden = !collapsed;
  restore.setAttribute("aria-expanded", String(!collapsed));
  if (focus) (collapsed ? restore : panel.querySelector(".cp-collapse"))?.focus();
  document.dispatchEvent(new Event("nc-panel-layout"));
}
export function expandPanel() {
  if (!collapsed) return;
  collapsed=false; syncPanel();
}


// One "value ▲ US value" row. higherIsGood: true / false / null (neutral).
export function statRow(ic, fallback, label, v, nv, fmt, higherIsGood) {
  let cmp = "";
  if (v != null && nv != null && nv !== 0) {
    const ratio = v / nv;
    const cls = Math.abs(ratio - 1) < 0.03 || higherIsGood == null ? "" : (higherIsGood ? ratio >= 1 : ratio <= 1) ? "good" : "bad";
    // Within 3% of the U.S. value reads as level: no arrow, no colour (the colour uses the same band).
    const arrow = Math.abs(ratio - 1) < 0.03 ? "≈" : ratio > 1 ? "▲" : "▼";
    cmp = `<span class="cmp ${cls}">${arrow} US ${fmt(nv)}</span>`;
  }
  return `<div class="stat-row"><span class="sl">${icon(ic, fallback, { size: 14 })}${esc(label)}</span><span><b>${fmt(v)}</b>${cmp}</span></div>`;
}

export function amenities(o, n) {
  return `
    ${statRow("unemployment", "😐", "Unemployment", o.unemployment, n.unemployment, (x) => pct(x), false)}
    ${statRow("l-income", "💵", "Median household income", o.median_income, n.median_income, dollars, true)}
    ${statRow("l-home", "🏠", "Median home value", o.home_value, n.home_value, dollars, null)}
    ${statRow("l-homeownership", "🔑", "Median gross rent / mo", o.median_rent, n.median_rent, dollars, false)}
    ${statRow(null, "⚖️", "Rent ÷ income", o.rent_burden, n.rent_burden, (x) => pct(x), false)}`;
}

// Workforce by industry with location quotients vs. the nation ("specialisation"). limit = max rows (0 = all).
export function industries(o, nation, limit = 0) {
  const n = nation.nation;
  const total = o.employed || 1;
  const nTotal = n.employed || 1;
  let rows = Object.entries(o.jobs || {})
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
  if (limit) rows = rows.slice(0, limit);
  if (!rows.length) return `<p class="muted">No industry data.</p>`;
  const maxShare = rows[0][1] / total;
  return rows
    .map(([k, v]) => {
      const share = v / total;
      const nShare = (n.jobs?.[k] || 0) / nTotal;
      const lq = nShare > 0 ? share / nShare : 1;
      const tip = `Share of jobs is ${lq.toFixed(1)}× the national share`;
      const badge = lq >= 1.3 ? `<span class="lq hi" title="${tip}">×${lq.toFixed(1)}</span>`
        : lq <= 0.6 ? `<span class="lq lo" title="${tip}">×${lq.toFixed(1)}</span>` : "";
      return `<div class="ind"><span aria-hidden="true">${icon(`i-${k}`, DISTRICT_ICON[k] || "•")}</span>
        <span>${esc(nation.industries?.[k] || k)}${badge}</span><span class="n">${compact(v)} · ${pct(share, 0)}</span>
        <div class="bar"><i style="width:${(share / maxShare) * 100}%;background:${lq >= 1.3 ? "#9fd76a" : "#c9a45c"}"></i></div></div>`;
    })
    .join("");
}

export const gdpRow = (o) =>
  o.gdp != null
    ? `<div class="stat-row"><span class="sl">${icon("y-gold", "💰", { size: 14 })}GDP${o.gdp_year ? ` (${o.gdp_year})` : ""}</span><span><b>${money(o.gdp)}</b>${
        o.population ? `<span class="cmp">${money(o.gdp / o.population)} per person</span>` : ""}</span></div>`
    : "";

// " · ▲ 3.4% since 2021" from growth / growth_years (cities and states), compared with the U.S. in the tooltip.
// Empty when growth is missing (null means "not measured", never zero).
export function growthSpan(o, n = null) {
  if (!Number.isFinite(o?.growth)) return "";
  const yrs = Array.isArray(o.growth_years) && o.growth_years.length === 2 ? o.growth_years : null;
  const p = (g) => `${g >= 0 ? "+" : "−"}${Math.abs(g * 100).toFixed(1)}%`;
  const period = yrs ? `${yrs[0]}–${yrs[1]}` : "the last few years";
  const us = Number.isFinite(n?.growth) ? ` (U.S. ${p(n.growth)})` : "";
  const tip = `Population change ${period}, Census population estimates: ${p(o.growth)}${us}`;
  const cls = o.growth >= 0 ? "good" : "bad";
  return ` · <span class="growth ${cls}" title="${esc(tip)}">${o.growth >= 0 ? "▲" : "▼"} ${Math.abs(o.growth * 100).toFixed(1)}%${
    yrs ? ` <span class="since">since ${yrs[0]}</span>` : ""}</span>`;
}

export const popLine = (o, extra = "") =>
  `<div class="cp-pop">${icon("pop", "👥", { size: 16 })} <b>${int(o.population)}</b> people · ${int(o.employed)} employed${extra}</div>`;

/**
 * Fill and show the panel.
 * spec: {kind: "city"|"state", stripe, title, sub, headExtra, sections: [{title, html}], foot, onClose, onPedia, wire(panel)}
 */
export function showPanel(spec) {
  const panel = panelEl();
  const key=spec.kind+":"+spec.title;
  const same=key===currentKey;
  if(!same) collapsed=false;
  currentKey=key;
  const oldScroll=same?panel.scrollTop:0;
  panel.dataset.kind = spec.kind;
  panel.setAttribute("aria-label", `${spec.kind === "state" ? "Region" : "Municipality"}: ${spec.title}`);
  panel.innerHTML = `
    <div class="sheet-grip" aria-hidden="true"></div>
    <div class="cp-head">
      <div class="stripe" style="background:${spec.stripe}"></div>
      <button class="icon-btn cp-collapse" type="button" aria-label="Collapse details" aria-expanded="true" aria-controls="city-panel" title="Collapse details">›</button>
      <button class="icon-btn cp-close" aria-label="Close panel (Esc)" title="Close (Esc)">${icon("close", "✕", { size: 13 })}</button>
      <div class="cp-kind">${spec.kind === "state" ? "Region" : "Municipality"}</div>
      <h2 class="cp-name">${spec.titleHtml ?? esc(spec.title)}</h2>
      ${spec.sub ? `<div class="cp-full">${spec.sub}</div>` : ""}
      ${spec.headExtra || ""}
    </div>
    ${tabBar(spec)}
    ${spec.sections.filter(Boolean).map((s) => `<section class="cp-section" ${s.tab ? `data-tab="${esc(s.tab)}" role="tabpanel"` : ""} ${s.tab && s.tab !== activeTab(spec) ? "hidden" : ""}>${s.title ? `<h3>${s.title}</h3>` : ""}${s.html}</section>`).join("")}
    <div class="cp-foot">${spec.foot || ""} <button type="button" class="link" data-pedia>About yields</button></div>`;
  restoreEl().textContent="‹ "+spec.title;
  restoreEl().setAttribute("aria-label","Expand details for "+spec.title);
  restoreEl().onclick=()=>{collapsed=false;syncPanel(true);};
  panel.querySelector(".cp-collapse").onclick=()=>{collapsed=true;syncPanel(true);};
  syncPanel();
  panel.scrollTop = oldScroll;
  panel.classList.remove("dragging-sheet");
  panel.style.transform = "";
  panel.querySelector(".cp-close").onclick = spec.onClose;
  panel.querySelector("[data-pedia]").onclick = (e) => {
    e.preventDefault();
    spec.onPedia?.();
  };
  wireTabs(panel, spec);
  spec.wire?.(panel);
}

// Progressive disclosure: sections may carry a `tab`; the panel shows one tab at a time and remembers the last one.
const lastTab = {};
function tabsOf(spec) {
  const t = [];
  for (const s of spec.sections) if (s && s.tab && !t.includes(s.tab)) t.push(s.tab);
  return t;
}
function activeTab(spec) {
  const t = tabsOf(spec);
  return t.includes(lastTab[spec.kind]) ? lastTab[spec.kind] : t[0];
}
function tabBar(spec) {
  const t = tabsOf(spec);
  if (t.length < 2) return "";
  const a = activeTab(spec);
  return `<div class="cp-tabs" role="tablist" aria-label="Sections">${t.map((x) => `<button role="tab" data-cptab="${esc(x)}" aria-selected="${x === a}" tabindex="${x === a ? 0 : -1}">${esc(x)}</button>`).join("")}</div>`;
}
export function showPanelTab(name) {
  const panel = panelEl();
  const b = panel?.querySelector(`[data-cptab="${CSS.escape(name)}"]`);
  b?.click();
}
function wireTabs(panel, spec) {
  const btns = [...panel.querySelectorAll("[data-cptab]")];
  const pick = (b, focus = false) => {
    lastTab[spec.kind] = b.dataset.cptab;
    btns.forEach((x) => { const on = x === b; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1; });
    panel.querySelectorAll(".cp-section[data-tab]").forEach((sec) => (sec.hidden = sec.dataset.tab !== b.dataset.cptab));
    if (focus) b.focus();
  };
  btns.forEach((b, k) => {
    b.onclick = () => pick(b);
    b.onkeydown = (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        pick(btns[(k + (e.key === "ArrowRight" ? 1 : btns.length - 1)) % btns.length], true);
      }
    };
  });
}

export function hidePanel() {
  const panel = panelEl();
  collapsed=false; currentKey=null;
  restoreEl().hidden=true;
  panel.hidden = true;
  panel.innerHTML = "";
  delete panel.dataset.kind;
  document.body.classList.remove("panel-open");
}

// Bottom-sheet swipe-down to close (mobile). Installed once.
export function installSheetSwipe(onClose) {
  const panel = panelEl();
  let start = null;
  panel.addEventListener("pointerdown", (e) => {
    if (e.pointerType === "mouse" || !matchMedia("(max-width: 700px)").matches) return;
    // Only from the grip/head, or anywhere while the sheet is scrolled to the top.
    const fromHead = e.target.closest(".sheet-grip, .cp-head");
    if (!fromHead && panel.scrollTop > 0) return;
    if (e.target.closest("button, a, input")) return;
    start = { y: e.clientY, id: e.pointerId, dy: 0, head: !!fromHead };
  });
  panel.addEventListener("pointermove", (e) => {
    if (!start || e.pointerId !== start.id) return;
    start.dy = Math.max(0, e.clientY - start.y);
    if (start.dy > 6 && (start.head || panel.scrollTop <= 0)) {
      panel.classList.add("dragging-sheet");
      panel.style.transform = `translateY(${start.dy}px)`;
    }
  });
  const end = (e) => {
    if (!start || e.pointerId !== start.id) return;
    const dy = start.dy;
    start = null;
    panel.classList.remove("dragging-sheet");
    panel.style.transform = "";
    if (dy > 80) onClose();
  };
  panel.addEventListener("pointerup", end);
  panel.addEventListener("pointercancel", end);
}
