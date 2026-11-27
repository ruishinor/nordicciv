// Camera uplinks (NordicCiv v0.5): webcams their operators publish for anyone to watch, as a geographical index.
// One optional map layer ("Camera uplinks" in the Map menu, off by default), a compact card for a selected uplink
// with one outbound action, a concise "camera uplinks" section in the municipality panel's Overview, a few Discover
// entries and an Almanac page.
//
// NordicCiv is not a viewer. Nothing from a provider is ever loaded here: no player, stream, snapshot, thumbnail,
// script, font or cookie — not when the layer is on, not when a symbol is hovered or selected. The only way to a
// camera is the "Open camera uplink" link, which opens the provider's own public page in a new tab (no opener, no
// referrer). Every outbound address is checked again before it is put in a link (https, the provider's own host).
// Nothing here says a camera is live: that is only known on the provider's page.
//
// Scale. Far out (the whole of Scandinavia) the layer draws nothing, so it never clutters the overview. From the
// region view in, uplinks that would overlap on screen share one symbol with a count at the mean of their positions;
// closer in, each uplink stands at its own position. Positions are never moved to make room. The symbol is drawn
// smaller than shelters and sites and fades under an active lens, so it stays subordinate to the analysis.
import { drawUplink, drawUplinkGroup } from "../../render/art/uplink.js";
import { esc } from "../../format.js";

const LAYER_Z = 63; // under public shelters (64), ports & airports (65), forts and wonders; over roads and rail
const MIN_RPX = 4.5; // below this (country view) the layer is suppressed
const COUNTRY = { NO: "Norway", SE: "Sweden", DK: "Denmark" };
const HOSTS = {
  camstreamer: /^camstreamer\.com$/, panomax: /^\d+\.panomax\.com$/,
  webcamcollections: /^webcamcollections\.com$/, skylinewebcams: /^www\.skylinewebcams\.com$/,
};
const NOTE = "Opens the provider's page in a new tab. Check that page for the current camera feed.";
// a few uplinks for Discover: distinct landscapes across the three countries (ids from uplinks.json)
const DISCOVER = ["ln-reinefjorden", "cs-425493061", "pm-1267069", "wcc-sweden-are-areskutan", "ln-abisko", "ln-gaustabanen",
  "pm-3058468", "wcc-sweden-ulvon", "cs-1943", "wcc-sweden-gotland-farosund-harbour", "cs-847741412", "wcc-sweden-bastad-hovs-hallar"];

/** The outbound address when it is safe to link to, else null (https only, the provider's own host, no credentials). */
export function safeUrl(u, allowedHosts = null) {
  let url;
  try { url = new URL(u.url); } catch { return null; }
  if (url.protocol !== "https:" || url.username || url.password || (url.port && url.port !== "443")) return null;
  const pat = HOSTS[u.provider];
  if (pat) return pat.test(url.hostname) ? url.href : null;
  return allowedHosts && allowedHosts.has(url.hostname) ? url.href : null; // an operator's own reviewed page
}

export function install(app) {
  let data = null;
  let on = false;
  let selected = null;
  let version = 0;
  const vis = new Map(); // zoom bucket → drawn items

  // ---- model ------------------------------------------------------------------------------------------------------
  function setData(d) {
    if (!d || !Array.isArray(d.cameras)) return;
    data = d;
    data.byId = new Map(d.cameras.map((c) => [c.id, c]));
    data.byMuni = new Map();
    for (const c of d.cameras) {
      if (!data.byMuni.has(c.muni)) data.byMuni.set(c.muni, []);
      data.byMuni.get(c.muni).push(c);
    }
    // operators' own pages were reviewed one by one: their hosts are the only other hosts a link may go to
    data.operatorHosts = new Set(d.cameras.filter((c) => !HOSTS[c.provider]).map((c) => { try { return new URL(c.url).hostname; } catch { return ""; } }).filter(Boolean));
    vis.clear();
    version++;
    app.requestDraw();
    if (app.state?.selectedCity) app.selectCity(app.state.selectedCity, { fly: false });
    addDiscoveries();
  }

  const symbolPx = (Rpx) => Math.max(14, Math.min(24, 12 + Rpx * 0.2)); // css px across
  const providerName = (c) => data?.providers?.[c.provider]?.name || c.provider;
  const categoryName = (c) => data?.categories?.[c.cat] || c.cat;
  const muniName = (id) => app.cityById.get(id)?.name || id;
  const regionName = (c) => {
    const city = app.cityById.get(c.muni);
    const st = city && app.data.states?.find((s) => s.fips === city.states?.[0]);
    return st?.name || "";
  };

  /** Items drawn at this zoom: [{x, y, members, kind: "one"|"group"}] (screen-space grouping, never moved). */
  function items(Rpx) {
    const b = Math.round(Rpx * 4) / 4;
    let out = vis.get(b);
    if (out) return out;
    const s = b / app.w.grid.R; // css px per km
    const rad = (symbolPx(b) * 1.05) / s; // km: symbols never overlap
    out = [];
    for (const c of data.cameras) {
      const g = out.find((o) => (o.x - c.x) ** 2 + (o.y - c.y) ** 2 < rad * rad);
      if (g) {
        g.members.push(c);
        g.sx += c.x; g.sy += c.y;
        g.x = g.sx / g.members.length; g.y = g.sy / g.members.length;
      } else out.push({ x: c.x, y: c.y, sx: c.x, sy: c.y, members: [c] });
    }
    for (let again = true; again;) {
      again = false;
      outer: for (let i = 0; i < out.length; i++) for (let j = i + 1; j < out.length; j++) {
        const p = out[i], q = out[j];
        if ((p.x - q.x) ** 2 + (p.y - q.y) ** 2 < rad * rad) {
          p.members.push(...q.members);
          p.sx += q.sx; p.sy += q.sy;
          p.x = p.sx / p.members.length; p.y = p.sy / p.members.length;
          out.splice(j, 1);
          again = true;
          break outer;
        }
      }
    }
    for (const o of out) {
      o.n = o.members.length;
      o.kind = o.n === 1 ? "one" : "group";
      if (o.n === 1) { o.x = o.members[0].x; o.y = o.members[0].y; }
    }
    if (vis.size > 200) vis.clear();
    vis.set(b, out);
    return out;
  }

  // ---- layer ------------------------------------------------------------------------------------------------------
  const layer = {
    id: "uplinks", z: LAYER_Z, minRpx: MIN_RPX,
    visible: () => on && !!data,
    sig: () => `u${version}|${selected || ""}`,
    draw(ctx, vp, w, o) {
      const list = items(o.Rpx);
      const size = symbolPx(o.Rpx) / o.s;
      const pad = size * 2;
      ctx.globalAlpha = o.lens ? 0.78 : 1;
      for (const it of list) {
        if (it.x < vp.x0 - pad || it.x > vp.x1 + pad || it.y < vp.y0 - pad || it.y > vp.y1 + pad) continue;
        if (it.kind === "one") drawUplink(ctx, it.x, it.y, size, { selected: it.members[0].id === selected });
        else drawUplinkGroup(ctx, it.x, it.y, size * 1.06, it.n, o, { selected: !!selected && it.members.some((c) => c.id === selected) });
      }
      ctx.globalAlpha = 1;
    },
    hit(x, y, Rpx) {
      if (Rpx < MIN_RPX) return null;
      const size = symbolPx(Rpx) / (Rpx / app.w.grid.R);
      let best = null, bd = Infinity;
      for (const it of items(Rpx)) {
        const d = (it.x - x) ** 2 + (it.y - size * 0.15 - y) ** 2;
        if (d < bd && d <= (size * 0.6) ** 2) { bd = d; best = it; }
      }
      return best;
    },
    tooltip: (it) => tipHtml(it),
    click(it) {
      if (it.kind === "one") { openCard(it.members[0]); return true; }
      const xs = it.members.map((c) => c.x), ys = it.members.map((c) => c.y);
      const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
      if (span < 0.3 || app.cam.scale * app.w.grid.R >= 90) { openList(it.members); return true; }
      const pad = Math.max(span * 0.3, 2);
      app.fitBounds(Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad, { maxScale: 120 / app.w.grid.R });
      return true;
    },
  };
  app.registerStaticLayer(layer);

  function tipHtml(it) {
    if (it.kind === "one") {
      const c = it.members[0];
      return `<b>${esc(c.name)}</b><br>Camera uplink · ${esc(categoryName(c))} · ${esc(muniName(c.muni))}<br><span class="muted">${esc(providerName(c))} · click for the link</span>`;
    }
    const munis = [...new Set(it.members.map((c) => c.muni))];
    return `<b>${it.n} camera uplinks</b> · ${munis.length === 1 ? esc(muniName(munis[0])) : `${munis.length} municipalities`}<br><span class="muted">Grouped at this scale · click to zoom in</span>`;
  }

  // ---- map toggle ---------------------------------------------------------------------------------------------------
  app.ui.addMapToggle({
    id: "uplinks", label: "Camera uplinks", icon: "c-uplink", default: false,
    title: "Public webcams published by their operators: where they are, with a link to the provider's page (no pictures are loaded here)",
    get: () => on,
    set: (v) => {
      on = !!v;
      if (!on) closeCard();
      app.requestDraw();
      app.emit?.("uplinks-layer", { on });
    },
  });
  const show = (v = true) => (app.ui.setMapToggle ? app.ui.setMapToggle("uplinks", v) : ((on = v), app.requestDraw()));

  // ---- card -------------------------------------------------------------------------------------------------------
  const card = document.createElement("section");
  card.id = "uplink-card";
  card.className = "panel uplink-card";
  card.hidden = true;
  card.setAttribute("aria-live", "polite");
  card.setAttribute("aria-label", "Camera uplink");
  document.body.appendChild(card);

  function linkHtml(c, label = "Open camera uplink") {
    const href = safeUrl(c, data.operatorHosts);
    if (!href) return `<span class="muted small">Link withheld: the address did not pass the link check.</span>`;
    return `<a class="chip uplink-open" data-uplink-out="${esc(c.id)}" href="${esc(href)}" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">${esc(label)} ↗</a>`;
  }
  function openCard(c) {
    selected = c.id;
    const city = app.cityById.get(c.muni);
    const where = [city ? `<button class="link" data-uc="muni">${esc(city.name)}</button>` : esc(c.muni), esc(regionName(c)), esc(COUNTRY[c.country] || c.country)].filter(Boolean).join(", ");
    const pos = c.pos === "place" ? `place shown (${esc(c.place?.label || "Wikidata")}, Wikidata)` : "as published by the provider";
    let host = "";
    try { host = new URL(c.url).hostname; } catch { /* checked in linkHtml */ }
    card.innerHTML = `<div class="uc-head"><span class="uc-k">Camera uplink · ${esc(categoryName(c))}</span><button class="x" data-uc="close" aria-label="Close">✕</button></div>
      <h3 class="uc-t">${esc(c.name)}</h3>
      <dl class="uc-dl">
        <dt>Location</dt><dd>${where}</dd>
        <dt>Provider</dt><dd>${esc(providerName(c))} <span class="muted">· ${esc(host)}</span></dd>
        <dt>Position</dt><dd class="muted">${pos}</dd>
      </dl>
      <div class="uc-act">${linkHtml(c)}</div>
      <p class="muted small">${esc(NOTE)}</p>
      <p class="muted tiny">Page checked ${esc(c.verified)} · <button class="link" data-uc="pedia">About camera uplinks</button></p>`;
    card.hidden = false;
    wire(city);
    app.requestDraw();
    card.querySelector(".uplink-open")?.focus({ preventScroll: true });
  }
  function openList(members) {
    selected = null;
    const rows = [...members].sort((a, b) => a.name.localeCompare(b.name, "nb"));
    card.innerHTML = `<div class="uc-head"><span class="uc-k">${rows.length} camera uplinks here</span><button class="x" data-uc="close" aria-label="Close">✕</button></div>
      <ul class="uc-list">${rows.map((c) => `<li><button class="link" data-uplink-open="${esc(c.id)}">${esc(c.name)}</button> <span class="muted">· ${esc(categoryName(c))}</span></li>`).join("")}</ul>
      <p class="muted small">These uplinks are close together, so they share one symbol at this scale.</p>`;
    card.hidden = false;
    wire(null);
    app.requestDraw();
  }
  function wire(city) {
    card.querySelector('[data-uc="close"]').onclick = () => closeCard(true);
    const m = card.querySelector('[data-uc="muni"]');
    if (m && city) m.onclick = () => app.selectCity(city, { fly: false });
    const p = card.querySelector('[data-uc="pedia"]');
    if (p) p.onclick = () => app.pedia?.open(PAGE);
  }
  function closeCard(focusMap = false) {
    if (card.hidden) return;
    card.hidden = true;
    selected = null;
    app.requestDraw();
    if (focusMap) document.getElementById("map")?.focus?.({ preventScroll: true });
  }
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !card.hidden) closeCard(true); });
  app.on("mode", () => closeCard());

  /** Turn the layer on, frame the uplink and open its card. */
  function open(id, { fly = true } = {}) {
    const c = data?.byId.get(id);
    if (!c) return false;
    show(true);
    if (fly) app.flyTo(c.x, c.y, Math.max(app.cam.scale, 40 / app.w.grid.R));
    openCard(c);
    return true;
  }
  function frameMuni(id) {
    const list = data?.byMuni.get(id);
    if (!list?.length) return;
    show(true);
    const xs = list.map((c) => c.x), ys = list.map((c) => c.y);
    const pad = 4, narrow = app.isMobile?.();
    app.fitBounds(Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad,
      { maxScale: 60 / app.w.grid.R, padRight: narrow ? 24 : 420, padBottom: narrow ? 300 : 24 });
  }

  // ---- municipality panel: Overview (only where there is something to explore) ------------------------------------
  app.addCitySections?.((city) => {
    const list = data?.byMuni.get(city.id);
    if (!list?.length) return [];
    const names = list.slice(0, 4).map((c) => `<button class="link" data-uplink-open="${esc(c.id)}">${esc(c.name)}</button>`).join(", ");
    return [{ tab: "Overview", title: "Camera uplinks", html: `<p class="small">${list.length === 1 ? "One public webcam" : `${list.length} public webcams`} in ${esc(city.name)}: ${names}${list.length > 4 ? ", …" : ""}.</p>
      <div class="chips"><button class="chip" data-uplink-muni="${esc(city.id)}">Explore ${list.length === 1 ? "the camera uplink" : `${list.length} camera uplinks`} on the map</button></div>
      <p class="muted tiny">Open a webcam on its provider's website.</p>` }];
  });

  // one delegated handler for buttons in panels, cards, Discover and the Almanac
  document.addEventListener("click", (e) => {
    const o = e.target.closest("[data-uplink-open]");
    if (o) { open(o.dataset.uplinkOpen); return; }
    const m = e.target.closest("[data-uplink-muni]");
    if (m) { frameMuni(m.dataset.uplinkMuni); return; }
    const out = e.target.closest("a[data-uplink-out]");
    if (out) app.emit?.("uplink-out", { id: out.dataset.uplinkOut }); // for tests: the link is followed by the browser
  });

  // ---- Discover -----------------------------------------------------------------------------------------------------
  let discoveredAdded = false;
  function addDiscoveries() {
    if (discoveredAdded || !app.explore?.addDiscoveries || !data) return;
    discoveredAdded = true;
    const list = DISCOVER.map((id) => data.byId.get(id)).filter(Boolean).map((c) => ({
      id: `uplink:${c.id}`, city: c.muni, lens: null, key: "uplink",
      text: `A public camera looks out over ${c.name} in ${muniName(c.muni)}. Visit the provider to see the place as it is now.`,
      def: `Camera uplink · ${categoryName(c)} · ${providerName(c)}. Open the provider's website to view the camera.`,
      uplink: c.id,
    }));
    app.explore.addDiscoveries(list, (d) => open(d.uplink, { fly: false }));
  }
  app.on?.("extensions", addDiscoveries);

  // ---- Almanac ------------------------------------------------------------------------------------------------------
  const PAGE = "Camera uplinks";
  app.pedia?.addPage?.(PAGE, () => {
    if (!data) return `<h2>${esc(PAGE)}</h2><p>Loading…</p>`;
    const t = data.totals, s = data.sources;
    const provs = Object.entries(t.by_provider).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${esc(data.providers[k]?.name || k)} (${n})`).join(", ");
    return `<h2><span>${esc(PAGE)}</span></h2>
      <p><b>What they are.</b> Webcams their operators publish for anyone to watch — over towns, mountains, fjords, coasts, islands, ski slopes and weather stations. Select a viewpoint to open the provider's website. Camera feeds load on the provider's site.</p>
      <p><b>On the map.</b> ${t.cameras} uplinks (Norway ${t.by_country.NO}, Sweden ${t.by_country.SE}, Denmark ${t.by_country.DK}) in ${t.munis} municipalities, reviewed ${esc(data.reviewed)}. The layer is off until switched on in the Map menu and is hidden at the scale of the whole of Scandinavia. The spyglass on a stone lookout marks a public viewpoint, not the camera's installation.</p>
      <p><b>Positions.</b> ${esc(data.meaning.position)} ${t.place_positions} uplinks are at place positions (their pages publish no coordinates).</p>
      <p><b>Live?</b> ${esc(data.meaning.status)} ${esc(data.meaning.verified)}</p>
      <p><b>Camera coverage.</b> ${esc(data.policy.exclude.join("; "))}. ${esc(data.meaning.absence)}</p>
      <p><b>Providers.</b> ${provs}.</p>
      <h4>Sources and attribution</h4>
      <ul><li>${esc(s.attribution)}</li>
      ${Object.entries(data.providers).map(([, p]) => `<li>${esc(p.name)} — ${esc(p.note)} (<a href="${esc(p.home)}" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">${esc(new URL(p.home).hostname)}</a>)</li>`).join("")}
      <li>${esc(s.places)}</li>
      ${Object.entries(s.lists).map(([k, v]) => `<li><code>${esc(k)}</code> retrieved ${esc((v.retrieved || "").slice(0, 10))}, SHA-256 ${esc((v.sha256 || "").slice(0, 12))}…</li>`).join("")}
      <li>${esc(s.reference)}</li></ul>`;
  });

  // ---- data -------------------------------------------------------------------------------------------------------
  if (app.data.uplinks !== undefined) setData(app.data.uplinks);
  else app.loadData("uplinks").then(setData, (err) => console.warn("camera uplinks failed to load", err));

  app.uplinks = {
    get data() { return data; }, get on() { return on; }, get selected() { return selected; },
    show, items, open, openCard, openList, closeCard, frameMuni, symbolPx, safeUrl, page: PAGE, MIN_RPX,
  };
}
