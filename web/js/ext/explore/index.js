// Discovery and first-run guidance (NC-X01–X03): a "Discover" button that opens a computed fact about a real place
// (flies there, opens its panel, colours the map by the measure), the "what stands out" links from the municipality
// panel, and a short, dismissible first-run hint. Facts and rules: ../../explore.js.
import { FACETS, discoveries } from "../../explore.js";
import { esc } from "../../format.js";

export function install(app) {
  const { cities, nation } = app.data;
  const all = discoveries(cities, nation);
  let order = shuffle(all.map((_, k) => k), Date.now() % 100000);
  let pos = 0;

  // --- top-bar button
  const bar = document.querySelector("#topbar .tb-buttons");
  const btn = document.createElement("button");
  btn.id = "btn-discover";
  btn.className = "btn";
  btn.title = "Show a surprising fact about a real place (computed from the data)";
  btn.setAttribute("aria-label", "Discover: show a surprising fact about a place");
  btn.innerHTML = `<span aria-hidden="true">✦</span><span class="lbl">Discover</span>`;
  bar?.insertBefore(btn, bar.firstChild);
  btn.onclick = () => surprise();

  // --- discovery card
  const card = document.createElement("section");
  card.id = "discovery";
  card.className = "panel discovery";
  card.hidden = true;
  card.setAttribute("aria-live", "polite");
  card.setAttribute("aria-label", "Discovery");
  document.body.appendChild(card);

  function show(d) {
    const c = app.cityById.get(d.city);
    if (!c) return;
    app.selectCity(c, { fly: true });
    const hl = { cities: new Set([c.id]), cells: new Set(), color: "#ffe08a" };
    if (d.group) app.emit("focus-industry", { group: d.group, from: c.id });
    else { app.setLens(d.lens || null); app.setHighlight(hl); }
    if (d.key === "history") setTimeout(() => app.panels.element?.querySelector?.('[data-cptab="Society"]')?.click(), 60);
    const f = FACETS.find((x) => x.id === d.facet);
    const def = d.def || f?.def;
    card.innerHTML = `<div class="disc-k">Discovery ${pos}/${all.length}</div>
      <p class="disc-t">${esc(d.text)}</p>
      ${def ? `<p class="muted small">${esc(def)}</p>` : d.group ? `<p class="muted small">Location quotient: the industry's share of local jobs ÷ its share in the three countries combined. Concentration, not output.</p>` : ""}
      <div class="chips"><button class="chip" data-d="next">Another ›</button><button class="chip" data-d="close">Close</button></div>`;
    card.hidden = false;
    card.querySelector('[data-d="next"]').onclick = () => surprise();
    card.querySelector('[data-d="close"]').onclick = () => { card.hidden = true; btn.focus(); };
  }
  function surprise() {
    if (!all.length) return;
    if (pos >= order.length) { order = shuffle(order, pos + 7); pos = 0; }
    show(all[order[pos++]]);
  }

  // --- "what stands out" links from the municipality panel
  app.on("explore-facet", ({ facet, city }) => {
    const f = FACETS.find((x) => x.id === facet);
    if (!f?.lens) return;
    app.setLens(f.lens);
    app.setHighlight({ cities: new Set([city]), cells: new Set(), color: "#ffe08a" });
  });

  // --- first-run hint (once per browser; nothing is sent anywhere)
  let seen = false;
  try { seen = localStorage.getItem("nc-intro") === "1"; } catch { /* storage blocked: show it */ }
  if (!seen) {
    const intro = document.createElement("section");
    intro.id = "intro";
    intro.className = "panel intro";
    intro.setAttribute("aria-label", "Getting started");
    intro.innerHTML = `<h2>Scandinavia, from official statistics</h2>
      <ul><li><b>Click a municipality</b> to see what stands out about it and where to go next.</li>
      <li><b>Lenses</b> colour the map by one measure; the legend says what it means.</li>
      <li><b>Discover</b> shows a surprising fact about a real place.</li></ul>
      <div class="chips"><button class="chip" data-i="go">✦ Discover something</button><button class="chip" data-i="ok">Got it</button></div>`;
    document.body.appendChild(intro);
    const done = () => { intro.remove(); try { localStorage.setItem("nc-intro", "1"); } catch { /* fine */ } };
    intro.querySelector('[data-i="go"]').onclick = () => { done(); surprise(); };
    intro.querySelector('[data-i="ok"]').onclick = done;
    // a hint, not a gate: it sits under every panel, and goes once the person has started exploring
    const off = () => { if (intro.isConnected) done(); app.off?.("select", off); app.off?.("lens", off); };
    app.on("select", off);
    app.on("lens", off);
  }

  app.explore = { discoveries: all, surprise, show };
}

function shuffle(a, seed) {
  let s = seed || 1;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const out = [...a];
  for (let i = out.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [out[i], out[j]] = [out[j], out[i]]; }
  return out;
}
