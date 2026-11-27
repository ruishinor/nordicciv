import { esc } from "../format.js";
import { icon, glyph } from "./icon.js";
import { statDefs, fmtStat, SCOPE_NAME } from "./yieldReport.js";

// The overview bar: an explicit scope (Scandinavia or one country) and its stats. Each stat names what it measures
// under the value; selecting a municipality never changes these figures (the scope only changes here).
let scope = "";
try { scope = localStorage.getItem("nc-scope") || ""; } catch { /* storage blocked */ }
if (!(scope in SCOPE_NAME)) scope = "";
export const hudScope = () => scope;

export function renderTopbar(nation) {
  const items = statDefs(nation, scope).map((d) => {
    const ic = d.yield ? glyph(d.yield, 17) : icon(d.iconId, d.emoji, { size: 17 });
    const value = (d.key === "gold" && !scope ? "Σ" : "") + fmtStat(d, d.value);
    const tip = `${d.name} — ${d.description} Status: ${d.status}. ${d.source ? "Source: " + d.source + "." : ""} Click for the report.`;
    return `<button type="button" class="yield" data-report="${esc(d.key)}" aria-expanded="false" aria-haspopup="dialog" aria-controls="yield-report"
      title="${esc(tip)}" aria-label="${esc(d.name)} in ${esc(SCOPE_NAME[scope])}: ${esc(value)} ${esc(d.measure || "")}. Open the report">
      <span class="ico" style="color:${esc(d.color)}">${ic}</span><span class="yv"><span style="color:${esc(d.color)}">${esc(value)}</span><span class="ym">${esc(shortMeasure(d))}</span></span><span class="caret" aria-hidden="true"></span></button>`;
  });
  const el = document.getElementById("yields");
  const sel = `<label class="hud-scope" title="Which area the overview figures describe"><span class="sr-only">Overview scope</span>
    <select id="hud-scope">${Object.entries(SCOPE_NAME).map(([k, v]) => `<option value="${k}" ${k === scope ? "selected" : ""}>${v}</option>`).join("")}</select></label>`;
  el.innerHTML = sel + items.join("");
  el.querySelector("#hud-scope").onchange = (e) => {
    scope = e.target.value;
    try { localStorage.setItem("nc-scope", scope); } catch { /* storage blocked */ }
    renderTopbar(nation);
    window.__app?.emit?.("hud-scope", { scope });
  };
  // When the bar is too narrow for every yield, the row scrolls on its own (search and buttons always fit);
  // a fade on the right edge shows there is more.
  const check = () => el.classList.toggle("clipped", el.scrollWidth > el.clientWidth + 1);
  if (typeof ResizeObserver === "function") new ResizeObserver(check).observe(el);
  check();
  watchBarOverflow(document.getElementById("topbar"));
  document.getElementById("turn").innerHTML = `Turn <b>${esc(nation.year ?? "")}</b> · ${esc(nation.vintage || "")}`;
}

function shortMeasure(d) {
  return { population: "residents", food: "farm/fish jobs", production: "industry jobs", gold: "€ output", science: "knowledge jobs", culture: "culture jobs", welfare: "welfare jobs" }[d.key] || "";
}

// Phones scroll the whole bar sideways. Mark which ends have more to show (.more-l / .more-r) so CSS can fade
// them: without a cue the yields look cut off after the second or third value.
function watchBarOverflow(bar) {
  if (!bar || bar.dataset.overflowWatch) return;
  bar.dataset.overflowWatch = "1";
  let raf = 0;
  const update = () => {
    raf = 0;
    const max = bar.scrollWidth - bar.clientWidth;
    bar.classList.toggle("more-l", max > 1 && bar.scrollLeft > 1);
    bar.classList.toggle("more-r", max > 1 && bar.scrollLeft < max - 1);
  };
  const queue = () => { if (!raf) raf = requestAnimationFrame(update); };
  bar.addEventListener("scroll", queue, { passive: true });
  addEventListener("resize", queue);
  if (typeof ResizeObserver === "function") {
    const ro = new ResizeObserver(queue);
    ro.observe(bar);
    for (const child of bar.children) ro.observe(child);
  }
  // Extensions add top-bar buttons later.
  if (typeof MutationObserver === "function") new MutationObserver(queue).observe(bar, { childList: true, subtree: true });
  queue();
}
