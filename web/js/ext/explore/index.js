// Discovery and first-run guidance (NC-X01–X03): a "Discover" button that opens a computed fact about a real place
// (flies there, opens its panel, colours the map by the measure), the "what stands out" links from the municipality
// panel, and a short, dismissible first-run hint. Facts and rules: ../../explore.js.
import { FACETS, discoveries } from "../../explore.js";
import { esc } from "../../format.js";
import { buildJourneys, buildConnectionJourneys, contextLinks, resolveJourney } from "./journeys.js";
import { placeLists } from "./places.js";

export async function install(app) {
  const { cities, nation } = app.data;
  const all = discoveries(cities, nation);
  const names = ["commuting", "commuting_se", "commuting_dk", "transport", "cross_border"];
  await Promise.all(names.map(name => app.loadData(name).catch(() => null)));
  const journeys = [...buildJourneys(app.data), ...buildConnectionJourneys(app.data)];
  let storage = null;
  try { storage = localStorage; } catch { /* browser storage unavailable */ }
  const places = placeLists(id => app.cityById.has(id), storage);
  const country = {NO:"Norway",SE:"Sweden",DK:"Denmark"};
  places.visit(app.state.selectedCity?.id);
  let active = null, moving = false;
  let order = shuffle(all.map((_, k) => k), Date.now() % 100000);
  let pos = 0;

  // --- top-bar button
  const bar = document.querySelector("#topbar .tb-buttons");
  const btn = document.createElement("button");
  btn.id = "btn-discover";
  btn.className = "btn";
  btn.title = "Explore journeys or discover a surprising place";
  btn.setAttribute("aria-label", "Discover journeys and places");
  btn.innerHTML = `<span aria-hidden="true">✦</span><span class="lbl">Discover</span>`;
  bar?.insertBefore(btn, bar.firstChild);
  const openDiscover = () => menu();
  btn.onclick = openDiscover;
  // phones: the top bar scrolls, so Discover also gets a place in the bottom navigation
  const mnav = document.getElementById("mobile-nav");
  if (mnav) {
    const mb = document.createElement("button");
    mb.dataset.mnav = "discover";
    mb.setAttribute("aria-label", "Discover journeys and places");
    mb.innerHTML = `<span aria-hidden="true">✦</span>Discover`;
    mb.onclick = openDiscover;
    mnav.appendChild(mb);
  }

  // --- discovery card
  const card = document.createElement("section");
  card.id = "discovery";
  card.className = "panel discovery";
  card.hidden = true;
  card.setAttribute("aria-live", "polite");
  card.setAttribute("aria-label", "Discovery");
  document.body.appendChild(card);

  const focusDiscover = () => (btn.getClientRects().length ? btn : mnav?.querySelector('[data-mnav="discover"]'))?.focus();
  function clearJourney() {
    if (!active) return;
    active = null;
    delete card.dataset.journeys;
    app.hash.soon();
  }
  function closeCard() {
    clearJourney();
    card.hidden = true;
    delete card.dataset.journeys;
    focusDiscover();
  }
  function menu() {
    clearJourney();
    card.dataset.journeys = "menu";
    card.innerHTML = '<h2 class="disc-t" tabindex="-1">Discover Scandinavia</h2><p class="muted small">Pick a theme to explore places on the map.</p><div class="journey-list">' +
      journeys.map(j => '<button type="button" class="chip" data-journey="' + esc(j.id) + '">' + esc(j.title) + ' · ' + j.stops.length + ' stops<br><span class="muted small">' +
        j.stops.map(s => esc(app.cityById.get(s.city)?.name || s.city)).join(' → ') + '</span></button>').join("") +
      '</div><div class="chips"><button type="button" class="chip" data-d="saved">Saved places (' + places.saved.length + ')</button>' +
      '<button type="button" class="chip" data-d="recent">Recent places (' + places.recent.length + ')</button></div>' +
      '<div class="chips"><button type="button" class="chip" data-d="next">Surprise me</button><button type="button" class="chip" data-d="close">Close</button></div>';
    card.hidden = false;
    card.querySelector('[data-d="saved"]').onclick = () => placeMenu("saved");
    card.querySelector('[data-d="recent"]').onclick = () => placeMenu("recent");
    card.querySelectorAll("[data-journey]").forEach(b => b.onclick = () => step(b.dataset.journey, 0));
    card.querySelector('[data-d="next"]').onclick = surprise;
    card.querySelector('[data-d="close"]').onclick = closeCard;
    card.querySelector("h2").focus({preventScroll: true});
  }
  function saveButton(b, id) {
    const saved = places.has(id);
    b.setAttribute("aria-pressed", String(saved));
    b.textContent = saved ? "Remove saved place" : "Save this place";
  }
  function placeMenu(kind) {
    clearJourney();
    const saved = kind === "saved", ids = saved ? places.saved : places.recent;
    card.dataset.journeys = "places";
    card.innerHTML = '<h2 class="disc-t" tabindex="-1">' + (saved ? "Saved places" : "Recent places") + '</h2>' +
      '<p class="muted small">' + (saved ? (places.persistent ? "Saved on this browser." : "Available until this page closes.") :
        "Municipalities visited on this page. Cleared when you reload.") + '</p>' +
      (ids.length ? '<div class="journey-list">' + ids.map(id => {
        const c = app.cityById.get(id);
        return '<div class="chips"><button class="chip" type="button" data-place-open="' + esc(id) + '">' +
          esc(c.name) + ' · ' + esc(country[c.country] || c.country) + '</button>' +
          (saved ? '<button class="chip" type="button" data-place-remove="' + esc(id) +
          '" aria-label="Remove ' + esc(c.name) + '">Remove</button>' : '') + '</div>';
      }).join("") + '</div>' : '<p>No places yet.</p>') +
      '<div class="chips">' + (!saved && ids.length ? '<button class="chip" type="button" data-place-clear>Clear recent places</button>' : '') +
      '<button class="chip" type="button" data-place-back>Back</button><button class="chip" type="button" data-d="close">Close</button></div>';
    card.hidden = false;
    card.querySelectorAll("[data-place-open]").forEach(b => b.onclick = () => {
      const c = app.cityById.get(b.dataset.placeOpen);
      if (!c) return;
      closeCard();
      app.setHighlight(null);
      app.selectCity(c, {fly:true});
    });
    card.querySelectorAll("[data-place-remove]").forEach(b => b.onclick = () => {
      places.remove(b.dataset.placeRemove);
      const current = app.panels.element.querySelector("[data-save-city]");
      if (current) saveButton(current, current.dataset.saveCity);
      placeMenu("saved");
    });
    const clear = card.querySelector("[data-place-clear]");
    if (clear) clear.onclick = () => { places.clearRecent(); placeMenu("recent"); };
    card.querySelector("[data-place-back]").onclick = menu;
    card.querySelector('[data-d="close"]').onclick = closeCard;
    card.querySelector("h2").focus({preventScroll:true});
  }
  function step(id, index, navigate = true) {
    const journey = journeys.find(j => j.id === id);
    const stop = journey?.stops[index], city = app.cityById.get(stop?.city);
    if (!city || (!navigate && app.state.selectedCity?.id !== city.id)) return false;
    active = {id, index, city: city.id};
    if (navigate) {
      moving = true;
      try {
        app.selectCity(city, {fly: true});
        app.setLens(stop.lens || null);
        app.setHighlight({cities: new Set([city.id]), cells: new Set(), color: "#ffe08a"});
        if (stop.hydro) app.setShowResources(true);
        if (stop.commuting || stop.transport || stop.crossBorder) {
          app.ui.setMapToggle("commuting-connections", !!stop.commuting);
          if (stop.transport) app.transport?.setCategory(stop.transport);
          app.ui.setMapToggle("transport-connections", !!stop.transport);
        }
        if (stop.daylight) app.panels.element.querySelector('[data-cptab="Daylight"]')?.click();
      } finally { moving = false; }
    }
    card.dataset.journeys = "step";
    card.innerHTML = '<div class="disc-k">' + esc(journey.title) + ' · ' + (index + 1) + ' of ' + journey.stops.length + '</div>' +
      '<h2 class="disc-t" tabindex="-1">' + esc(city.name) + '</h2><p>' + esc(stop.text) + '</p><p class="muted small">' + esc(stop.source) + '</p>' +
      '<div class="chips" role="group" aria-label="Journey stops">' + journey.stops.map((s, i) =>
        '<button type="button" class="chip" data-journey-stop="' + i + '"' + (i === index ? ' aria-current="step" disabled' : '') + '>' +
        (i + 1) + '. ' + esc(app.cityById.get(s.city)?.name || s.city) + '</button>').join("") + '</div>' +
      '<div class="chips"><button type="button" class="chip" data-d="prev"' + (index === 0 ? ' disabled' : '') + '>Previous</button>' +
      '<button type="button" class="chip" data-d="forward">' + (index + 1 === journey.stops.length ? 'Finish' : 'Next stop ›') + '</button>' +
      '<button type="button" class="chip" data-d="journeys">Journeys</button><button type="button" class="chip" data-d="close">Close</button></div>';
    card.hidden = false;
    card.querySelectorAll("[data-journey-stop]").forEach(b => b.onclick = () => step(id, Number(b.dataset.journeyStop)));
    card.querySelector('[data-d="prev"]').onclick = () => step(id, index - 1);
    card.querySelector('[data-d="forward"]').onclick = () => index + 1 < journey.stops.length ? step(id, index + 1) : menu();
    card.querySelector('[data-d="journeys"]').onclick = menu;
    card.querySelector('[data-d="close"]').onclick = closeCard;
    if (navigate) { card.querySelector("h2").focus({preventScroll: true}); app.hash.soon(); }
    return true;
  }
  app.hash.register("journey", {
    get: () => active ? active.id + ":" + active.index : null,
    set(value) {
      const parsed = resolveJourney(journeys, value);
      if (parsed && step(parsed.id, parsed.index, false)) return;
      if (active) { active = null; card.hidden = true; delete card.dataset.journeys; }
    },
  });
  app.on("select", () => {
    places.visit(app.state.selectedCity?.id);
    if (active && !moving && app.state.selectedCity?.id !== active.city) {
      clearJourney(); card.hidden = true;
    }
  });
  app.addCitySections(city => {
    const sections = [{tab:"Overview",title:"Save this municipality",
      html:'<button type="button" class="chip" data-save-city="' + esc(city.id) + '" aria-pressed="' + places.has(city.id) + '">' +
        (places.has(city.id) ? "Remove saved place" : "Save this place") + '</button>'}];
    const related = journeys.flatMap(j => {
      const index = j.stops.findIndex(s => s.city === city.id);
      return index < 0 ? [] : [{j, index}];
    });
    if (related.length) sections.push({tab: "Overview", title: "Journeys through here",
      html: '<div class="journey-list">' + related.map(({j, index}) =>
        '<button type="button" class="chip" data-discover-journey="' + esc(j.id + ":" + index) + '">' +
        esc(j.title) + ' · stop ' + (index + 1) + ' of ' + j.stops.length + '</button>').join("") + '</div>'});
    const cross = app.data.cross_border;
    if (cross && ["DK-101","SE-1280"].includes(city.id)) {
      const names = {DK:"Denmark",SE:"Sweden"};
      sections.push({tab:"Overview",title:"Commuting across Øresund · "+esc(cross.period),
        html:'<p>'+esc(cross.source.note)+'</p><ul>'+cross.flows.map(f=>'<li>'+names[f.residence]+' → '+names[f.work]+': <b>'+f.value.toLocaleString("en-GB")+'</b> commuters</li>').join("")+
          '</ul><p class="muted small">Regional totals, not municipality pairs. <a href="'+esc(cross.source.url)+'" target="_blank" rel="noopener noreferrer">Nordic Statistics · COMP53 ↗</a></p>'});
    }
    const html = contextLinks(city);
    if (html) sections.push({tab: "Overview", title: "Weather and satellite imagery", html});
    return sections;
  }, (panel, city) => {
    const save = panel.querySelector("[data-save-city]");
    if (save) save.onclick = () => {
      if (app.state.selectedCity?.id !== city.id) return;
      if (!places.has(city.id) && places.saved.length >= places.maxSaved) {
        app.ui.toast("Your saved places list is full. Remove a place first.");
        return;
      }
      places.toggle(city.id);
      saveButton(save, city.id);
    };
    panel.querySelectorAll("[data-discover-journey]").forEach(b => {
      b.onclick = () => {
        const parsed = resolveJourney(journeys, b.dataset.discoverJourney);
        if (parsed && app.state.selectedCity?.id === city.id) step(parsed.id, parsed.index);
      };
    });
  });

  const showers = new Map(); // key → (d) => void, for discoveries contributed by other extensions
  function show(d) {
    const c = app.cityById.get(d.city);
    if (!c) return;
    clearJourney();
    delete card.dataset.journeys;
    app.selectCity(c, { fly: true });
    const custom = showers.get(d.key);
    const hl = { cities: new Set([c.id]), cells: new Set(), color: "#ffe08a" };
    if (custom) { app.setLens(null); app.setHighlight(hl); }
    else if (d.group) app.emit("focus-industry", { group: d.group, from: c.id });
    else { app.setLens(d.lens || null); app.setHighlight(hl); }
    if (d.key === "history") setTimeout(() => app.panels.element?.querySelector?.('[data-cptab="Society"]')?.click(), 60);
    const f = FACETS.find((x) => x.id === d.facet);
    const def = d.def || f?.def;
    card.innerHTML = `<div class="disc-k">Discovery ${pos}/${all.length}</div>
      <p class="disc-t">${esc(d.text)}</p>
      ${def ? `<p class="muted small">${esc(def)}</p>` : d.group ? `<p class="muted small">Location quotient: the industry's share of local jobs ÷ its share in the three countries combined. Concentration, not output.</p>` : ""}
      <div class="chips"><button class="chip" data-d="next">Another ›</button>${journeys.length ? '<button class="chip" data-d="journeys">Journeys</button>' : ""}<button class="chip" data-d="close">Close</button></div>`;
    card.hidden = false;
    card.querySelector('[data-d="next"]').onclick = () => surprise();
    const journeysButton = card.querySelector('[data-d="journeys"]');
    if (journeysButton) journeysButton.onclick = menu;
    card.querySelector('[data-d="close"]').onclick = closeCard;
    if (custom) setTimeout(() => custom(d), 0);
  }
  /** Other extensions add discoveries of their own kind (same card); onShow(d) runs after the place is selected. */
  function addDiscoveries(list, onShow) {
    if (!list?.length) return;
    for (const d of list) {
      if (!d.key || !d.city || all.some((x) => x.id === d.id)) continue;
      if (onShow) showers.set(d.key, onShow);
      order.splice(pos + 1 + Math.floor(((order.length - pos) * (all.length % 7)) / 7), 0, all.length);
      all.push(d);
    }
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
      <li><b>Discover</b> offers map journeys and surprising places.</li></ul>
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

  app.explore = { discoveries: all, surprise, show, addDiscoveries, journeys };
}

function shuffle(a, seed) {
  let s = seed || 1;
  const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  const out = [...a];
  for (let i = out.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [out[i], out[j]] = [out[j], out[i]]; }
  return out;
}
