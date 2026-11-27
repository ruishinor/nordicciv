// Public civil-defence shelters (NordicCiv v0.4): Norway's public shelters as published by DSB, as one optional map
// layer ("Public shelters" in the Map menu, off by default), a compact card for a selected shelter, a section in the
// municipality panel's Society tab, notes for the Council's Resilience advisor and an Almanac page.
//
// Scale. Far out, shelters are summarised by county (one symbol with a count at the mean of the members' true
// positions); at the region view by municipality; closer in, every record is drawn at its own published position and
// records that would overlap on screen share one group symbol instead of being nudged apart. Nothing is ever moved to
// make room. Groups and records are computed per zoom bucket only (not per viewport), so what is hit is what was drawn.
//
// What the data can and cannot say is kept next to every number: registered places are DSB's recorded capacity, not
// availability or readiness; private shelters (most of Norway's places) are not published; Sweden and Denmark are
// "not integrated", never zero. No score, ranking or coverage share is computed.
import { drawShelter, drawShelterGroup } from "../../render/art/shelter.js";
import { esc } from "../../format.js";

const LAYER_Z = 64; // above ports & airports' slot neighbours, under forts, wonders and the fog
const int = (v) => (v == null ? "–" : Math.round(v).toLocaleString("en-GB"));
const COUNTRY = { NO: "Norway", SE: "Sweden", DK: "Denmark" };
const EMERGENCY = "In an emergency, follow current instructions from the authorities (DSB, the police and your municipality) and listen to official channels. This map is not an emergency or shelter-availability service.";

export function install(app) {
  let data = null;
  let on = false;
  let selected = null; // shelter id with an open card
  let version = 0;
  const vis = new Map(); // zoom bucket → drawn items

  // ---- model ------------------------------------------------------------------------------------------------------
  function setData(d) {
    if (!d || !Array.isArray(d.shelters)) return;
    data = d;
    data.byId = new Map(d.shelters.map((s) => [s.id, s]));
    data.byMuni = new Map();
    for (const s of d.shelters) {
      if (!data.byMuni.has(s.muni)) data.byMuni.set(s.muni, []);
      data.byMuni.get(s.muni).push(s);
    }
    vis.clear();
    version++;
    app.requestDraw();
    if (app.state.selectedCity?.country === "NO") app.selectCity(app.state.selectedCity, { fly: false });
  }

  const symbolPx = (Rpx) => Math.max(15, Math.min(26, 12 + Rpx * 0.22)); // css px across
  const tier = (Rpx) => (Rpx < 5 ? "region" : Rpx < 14 ? "muni" : "record");

  /** Items drawn at this zoom: [{x, y, n, places, members, kind: "one"|"group", level}] (members are records). */
  function items(Rpx) {
    const b = Math.round(Rpx * 4) / 4;
    let out = vis.get(b);
    if (out) return out;
    const s = b / app.w.grid.R; // css px per km
    const t = tier(b);
    let base;
    if (t === "record") base = data.shelters.map((r) => ({ x: r.x, y: r.y, w: 1, members: [r] }));
    else {
      const key = t === "region" ? (r) => app.cityById.get(r.muni)?.states?.[0] : (r) => r.muni;
      const groups = new Map();
      for (const r of data.shelters) {
        const k = key(r);
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(r);
      }
      base = [...groups].map(([k, m]) => {
        const a = (t === "region" ? data.regions : data.munis)[k]?.anchor;
        return { x: a ? a[0] : m[0].x, y: a ? a[1] : m[0].y, w: m.length, members: m, key: k };
      });
    }
    // greedy screen-space grouping, largest first; a group stands at the mean of its members' true positions
    base.sort((p, q) => q.w - p.w);
    const rad = (symbolPx(b) * (t === "record" ? 1.0 : 1.2)) / s; // km: symbols never overlap
    out = [];
    for (const it of base) {
      const g = out.find((o) => (o.x - it.x) ** 2 + (o.y - it.y) ** 2 < rad * rad);
      if (g) {
        g.members.push(...it.members);
        g.sx += it.x * it.members.length; g.sy += it.y * it.members.length; g.cnt += it.members.length;
        g.x = g.sx / g.cnt; g.y = g.sy / g.cnt;
      } else out.push({ x: it.x, y: it.y, sx: it.x * it.members.length, sy: it.y * it.members.length, cnt: it.members.length, members: [...it.members], level: t });
    }
    // a group's mean can drift next to another symbol: merge again until no two symbols overlap
    for (let again = true; again;) {
      again = false;
      outer: for (let i = 0; i < out.length; i++) for (let j = i + 1; j < out.length; j++) {
        const p = out[i], q = out[j];
        if ((p.x - q.x) ** 2 + (p.y - q.y) ** 2 < rad * rad) {
          p.members.push(...q.members);
          p.sx += q.sx; p.sy += q.sy; p.cnt += q.cnt;
          p.x = p.sx / p.cnt; p.y = p.sy / p.cnt;
          out.splice(j, 1);
          again = true;
          break outer;
        }
      }
    }
    for (const o of out) {
      o.n = o.members.length;
      o.kind = o.n === 1 ? "one" : "group";
      o.places = o.members.reduce((p, r) => p + (r.places ?? 0), 0);
      o.missing = o.members.some((r) => r.places == null);
      if (o.n === 1) { o.x = o.members[0].x; o.y = o.members[0].y; } // a single record: exactly where it is
    }
    if (vis.size > 200) vis.clear();
    vis.set(b, out);
    return out;
  }

  // ---- layer ------------------------------------------------------------------------------------------------------
  const layer = {
    id: "shelters", z: LAYER_Z, minRpx: 0,
    visible: () => on && !!data,
    sig: () => `s${version}|${selected || ""}`,
    draw(ctx, vp, w, o) {
      const list = items(o.Rpx);
      const size = symbolPx(o.Rpx) / o.s;
      const pad = size * 2;
      ctx.globalAlpha = o.lens ? 0.9 : 1;
      for (const it of list) {
        if (it.x < vp.x0 - pad || it.x > vp.x1 + pad || it.y < vp.y0 - pad || it.y > vp.y1 + pad) continue;
        // the shield's point sits on the position: draw the symbol centred a little above it
        const cy = it.y - size * 0.42;
        if (it.kind === "one") drawShelter(ctx, it.x, cy, size, { selected: it.members[0].id === selected });
        else drawShelterGroup(ctx, it.x, cy, size * 1.08, it.n, o);
      }
      ctx.globalAlpha = 1;
    },
    hit(x, y, Rpx) {
      const s = Rpx / app.w.grid.R;
      const size = symbolPx(Rpx) / s;
      const list = items(Rpx);
      let best = null, bd = Infinity;
      for (const it of list) {
        const d = (it.x - x) ** 2 + (it.y - size * 0.42 - y) ** 2;
        if (d < bd && d <= (size * 0.62) ** 2) { bd = d; best = it; }
      }
      return best;
    },
    tooltip: (it) => tipHtml(it),
    click(it) {
      if (it.kind === "one") { openCard(it.members[0]); return true; }
      // a group: zoom in on it, or list its members once they no longer separate (same building)
      const xs = it.members.map((r) => r.x), ys = it.members.map((r) => r.y);
      const span = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
      if (span < 0.05 || app.cam.scale * app.w.grid.R >= 90) { openGroup(it); return true; }
      const pad = Math.max(span * 0.25, 1.5);
      app.fitBounds(Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad, { maxScale: 160 / app.w.grid.R });
      return true;
    },
  };
  app.registerStaticLayer(layer);

  const muniName = (id) => app.cityById.get(id)?.name || id;
  function tipHtml(it) {
    if (it.kind === "one") {
      const r = it.members[0];
      return `<b>Public shelter</b> · ${esc(r.address || `room ${r.room}`)}<br>${r.places == null ? "Registered places not stated" : `${int(r.places)} registered places`} · ${esc(muniName(r.muni))}<br><span class="muted">DSB register · click for details</span>`;
    }
    const munis = [...new Set(it.members.map((r) => r.muni))];
    const where = it.level === "region" ? esc(app.data.states.find((s) => s.fips === app.cityById.get(munis[0])?.states?.[0])?.name || "") + (munis.length > 1 ? ` (${munis.length} municipalities)` : "")
      : munis.length === 1 ? esc(muniName(munis[0])) : `${munis.length} municipalities`;
    return `<b>${int(it.n)} public shelters</b> · ${where}<br>${int(it.places)} registered places in total${it.missing ? " (some not stated)" : ""}<br><span class="muted">Grouped at this scale · click to zoom in</span>`;
  }

  // ---- map toggle (Map menu) ----------------------------------------------------------------------------------------
  app.ui.addMapToggle({
    id: "shelters", label: "Public shelters (NO)", icon: "c-shelter", default: false,
    title: "Norway's public civil-defence shelters as registered by DSB (public shelters only; not availability or readiness)",
    get: () => on,
    set: (v) => {
      on = !!v;
      if (!on) closeCard();
      app.requestDraw();
      app.emit?.("shelters-layer", { on });
    },
  });
  const show = (v = true) => app.ui.setMapToggle ? app.ui.setMapToggle("shelters", v) : (on = v, app.requestDraw());

  // ---- card -------------------------------------------------------------------------------------------------------
  const card = document.createElement("section");
  card.id = "shelter-card";
  card.className = "panel shelter-card";
  card.hidden = true;
  card.setAttribute("aria-live", "polite");
  card.setAttribute("aria-label", "Public shelter");
  document.body.appendChild(card);

  const srcLine = () => `${esc(data.source.authority)} · ${esc(data.source.dataset)} · extracted ${esc(data.source.extracted || "")} · ${esc(data.source.license)}`;
  function openCard(r) {
    selected = r.id;
    const c = app.cityById.get(r.muni);
    card.innerHTML = `<div class="sc-head"><span class="sc-k">Public shelter · Norway</span><button class="x" data-sc="close" aria-label="Close">✕</button></div>
      <h3 class="sc-t">${esc(r.address || "Address not stated")}</h3>
      <dl class="sc-dl">
        <dt>Registered places</dt><dd>${r.places == null ? "not stated in the register" : `<b>${int(r.places)}</b>`}</dd>
        <dt>Municipality</dt><dd>${c ? `<button class="link" data-sc="muni">${esc(c.name)}</button>` : esc(r.muni)}${r.assigned ? ` <span class="muted" title="Just outside the simplified outline; assigned to the nearest municipality">(nearest, ${int(r.assigned.distance_m)} m)</span>` : ""}</dd>
        <dt>Shelter room no.</dt><dd>${r.room ?? "–"}</dd>
        <dt>Identifier</dt><dd><code title="DSB lokalId">${esc(r.id.slice(0, 8))}…</code></dd>
      </dl>
      <p class="muted small">Registered places show the capacity listed by DSB. For current opening, readiness and access information, follow official instructions.</p>
      <p class="sc-note small">${esc(EMERGENCY)}</p>
      <div class="chips"><a class="chip" href="${esc(data.source.official_map_url)}" target="_blank" rel="noopener">DSB shelter map ↗</a>
        <a class="chip" href="${esc(data.source.guidance_url)}" target="_blank" rel="noopener">About shelters (DSB) ↗</a>
        <button class="chip" data-sc="pedia">About public shelters</button></div>
      <p class="muted tiny">${srcLine()}</p>`;
    card.hidden = false;
    wireCard(c);
    app.requestDraw();
    card.querySelector('[data-sc="close"]').focus({ preventScroll: true });
  }
  function openGroup(it) {
    selected = null;
    const rows = [...it.members].sort((a, b) => (b.places ?? -1) - (a.places ?? -1));
    card.innerHTML = `<div class="sc-head"><span class="sc-k">${int(it.n)} public shelters at this spot</span><button class="x" data-sc="close" aria-label="Close">✕</button></div>
      <p class="muted small">These records share (almost) the same position, so they stay one symbol at every zoom.</p>
      <ul class="sc-list">${rows.slice(0, 12).map((r) => `<li><button class="link" data-sc-id="${esc(r.id)}">${esc(r.address || `room ${r.room}`)}</button> · ${r.places == null ? "places not stated" : `${int(r.places)} places`}</li>`).join("")}</ul>
      <p class="sc-note small">${esc(EMERGENCY)}</p>
      <p class="muted tiny">${srcLine()}</p>`;
    card.hidden = false;
    wireCard(null);
    card.querySelectorAll("[data-sc-id]").forEach((b) => (b.onclick = () => openCard(data.byId.get(b.dataset.scId))));
    app.requestDraw();
  }
  function wireCard(c) {
    card.querySelector('[data-sc="close"]').onclick = () => closeCard(true);
    const m = card.querySelector('[data-sc="muni"]');
    if (m && c) m.onclick = () => app.selectCity(c, { fly: false });
    const p = card.querySelector('[data-sc="pedia"]');
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

  // ---- municipality panel: Society tab ------------------------------------------------------------------------------
  function muniSection(city) {
    if (city.country !== "NO") {
      const cov = data?.coverage?.[city.country];
      return [{ tab: "Society", title: "Civil preparedness · public shelters", html: `<p class="muted small"><b>Shelter data unavailable for ${COUNTRY[city.country]}</b>. ${esc(cov?.reason || "")}</p>` }];
    }
    if (!data) return [{ tab: "Society", title: "Civil preparedness · public shelters", html: `<p class="muted small">Loading the public shelter register…</p>` }];
    const list = data.byMuni.get(city.id) || [];
    const a = data.munis[city.id];
    const src = `<p class="muted tiny">${srcLine()}</p>`;
    const guide = `<a class="chip" href="${esc(data.source.guidance_url)}" target="_blank" rel="noopener">About shelters (DSB) ↗</a><button class="chip" data-shelter-pedia>About public shelters</button>`;
    if (!list.length) {
      return [{ tab: "Society", title: "Civil preparedness · public shelters", html: `<p>DSB's register lists <b>no public shelter</b> in ${esc(city.name)}.</p>
        <p class="muted small">The register covers public shelters. Private shelters in homes, schools and workplaces are outside its coverage.</p>
        <div class="chips">${guide}</div>${src}` }];
    }
    const top = [...list].sort((p, q) => (q.places ?? -1) - (p.places ?? -1)).slice(0, 3);
    return [{ tab: "Society", title: "Civil preparedness · public shelters", html: `<div class="sh-stats">
        <div><b>${int(a.n)}</b><span>public shelter${a.n === 1 ? "" : "s"} mapped</span></div>
        <div><b>${int(a.places)}</b><span>registered places in total${a.missing ? ` (${a.missing} not stated)` : ""}</span></div></div>
      <p class="small">Largest: ${top.map((r) => `${esc(r.address || `room ${r.room}`)} (${r.places == null ? "–" : int(r.places)})`).join("; ")}.</p>
      <details class="sh-all"><summary>All ${int(a.n)} as listed by DSB</summary><ul>${[...list].sort((p, q) => (p.address || "").localeCompare(q.address || "", "nb"))
        .map((r) => `<li><button class="link" data-shelter-open="${esc(r.id)}">${esc(r.address || `room ${r.room}`)}</button> · ${r.places == null ? "places not stated" : `${int(r.places)} places`}</li>`).join("")}</ul></details>
      <p class="muted small">Public shelters serve anyone nearby. The figures show registered capacity. For current availability, follow the authorities' instructions. Most of Norway's shelter places are in private shelters, outside this register.</p>
      <div class="chips"><button class="chip" data-shelter-show="${esc(city.id)}">Show public shelters on the map</button>${guide}</div>${src}` }];
  }
  app.addCitySections?.((city) => muniSection(city));

  // one delegated handler for buttons in panels, the Council and cards
  document.addEventListener("click", (e) => {
    const o = e.target.closest("[data-shelter-open]");
    if (o && data) {
      const r = data.byId.get(o.dataset.shelterOpen);
      if (!r) return;
      show(true);
      app.flyTo(r.x, r.y, Math.max(app.cam.scale, 60 / app.w.grid.R));
      openCard(r);
      return;
    }
    const b = e.target.closest("[data-shelter-show],[data-shelter-pedia]");
    if (!b) return;
    if (b.hasAttribute("data-shelter-pedia")) { app.pedia?.open(PAGE); return; }
    show(true);
    const id = b.dataset.shelterShow;
    const list = id && data?.byMuni.get(id);
    if (list?.length) {
      const xs = list.map((r) => r.x), ys = list.map((r) => r.y);
      const pad = 2.5;
      const narrow = app.isMobile?.();
      app.fitBounds(Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad,
        { maxScale: 90 / app.w.grid.R, padRight: narrow ? 24 : 420, padBottom: narrow ? 300 : 24 });
    }
  });

  // ---- Council (Resilience advisor) ---------------------------------------------------------------------------------
  function councilNotes(c, r, obs) {
    if (!data) return [];
    const src = `DSB public shelter register, extracted ${data.source.extracted}`;
    const btn = (id) => `<button class="chip" data-shelter-show="${esc(id || "")}">Show public shelters</button>`;
    if (c) {
      if (c.country !== "NO") return [obs(`Public shelter data is <b>unavailable</b> for ${COUNTRY[c.country]}.`, { source: "coverage note" })];
      const a = data.munis[c.id];
      if (!a) return [obs(`DSB's register lists no public shelter in ${esc(c.name)}. The register covers public shelters; private shelters and other protective spaces are outside its coverage.`, { source: src })];
      return [obs(`DSB's register lists <b>${int(a.n)} public shelter${a.n === 1 ? "" : "s"}</b> in ${esc(c.name)} with <b>${int(a.places)}</b> registered places. Public shelters serve whoever is nearby; private shelters are not published, so this is part of the municipality's shelter provision, not all of it. ${btn(c.id)}`, { source: src })];
    }
    if (r) {
      if (r.country !== "NO") return [obs(`Public shelter data is <b>unavailable</b> for ${COUNTRY[r.country]}.`, { source: "coverage note" })];
      const a = data.regions[r.fips];
      const total = app.data.cities.filter((x) => x.states[0] === r.fips).length;
      if (!a) return [obs(`DSB's register lists no public shelter in ${esc(r.name)}.`, { source: src })];
      return [obs(`${esc(r.name)}: <b>${int(a.n)}</b> public shelters with <b>${int(a.places)}</b> registered places, in ${a.munis} of ${total} municipalities. The register holds public shelters only. ${btn("")}`, { source: src })];
    }
    const t = data.totals;
    return [obs(`Norway: DSB's register lists <b>${int(t.shelters)} public shelters</b> with <b>${int(t.places)}</b> registered places, in ${t.munis_with} of ${t.munis_no} municipalities. DSB puts Norway's total at about 20,000 shelters with room for about 2.5 million people, most of them private and not published. Public shelter data is unavailable for Sweden and Denmark. ${btn("")}`,
      { source: `${src}; national total from DSB's guidance page` })];
  }

  // ---- Almanac ------------------------------------------------------------------------------------------------------
  const PAGE = "Civil preparedness — Public shelters";
  app.pedia?.addPage?.(PAGE, () => {
    if (!data) return `<h2>${esc(PAGE)}</h2><p>Loading…</p>`;
    const s = data.source, t = data.totals;
    return `<h2><span>${esc(PAGE)}</span></h2>
      <p><b>What public shelters are.</b> Permanent rooms built to protect the population from the effects of armed conflict. In Norway, public shelters (<i>offentlige tilfluktsrom</i>) are for anyone in the area; they are built and maintained by the municipality, mostly in towns and larger built-up areas, and may be used for other purposes in peacetime. DSB says they must be cleared and made ready within 72 hours when required. Private shelters are for the people connected to a building (housing, schools, workplaces) and hold most of Norway's roughly 2.5 million shelter places.</p>
      <p><b>Public shelter register.</b> Every record of DSB's public register (${int(t.shelters)} shelters, ${int(t.places)} registered places, extracted ${esc(s.extracted)}), at its published position, transformed from ETRS89 into this map's projection. Far out, shelters are summarised by county and municipality; closer in, records that would overlap share one symbol with a count. Symbols use the published coordinates. The shield and doorway represent public shelters.</p>
      <p><b>Registered places</b> show how many people the shelter is designed to hold, as listed by DSB. Anyone nearby can use a public shelter when the authorities open it. The register does not show current access or readiness.</p>
      <p><b>Current shelter information.</b> DSB and local authorities provide instructions about shelter use. This register covers public shelters only.</p>
      <p><b>Municipality.</b> ${esc(data.rules.municipality)} ${t.assigned_nearest} record(s) were assigned this way.</p>
      <p><b>Sweden and Denmark.</b> Public shelter data is unavailable. Sweden: ${esc(data.coverage.SE.reason)} Denmark: ${esc(data.coverage.DK.reason)}</p>
      <p class="sc-note">${esc(EMERGENCY)}</p>
      <h4>Sources</h4>
      <ul><li><a href="${esc(s.dataset_url)}" target="_blank" rel="noopener">${esc(s.dataset)}</a> — ${esc(s.authority)}, ${esc(s.license)}. ${esc(s.attribution)}</li>
      <li>Retrieved ${esc((s.retrieved || "").slice(0, 10))} from the WFS (<code>${esc(s.request)}</code>), ${int(s.number_matched)} features matched; SHA-256 ${esc((s.sha256 || "").slice(0, 12))}…</li>
      <li><a href="${esc(s.guidance_url)}" target="_blank" rel="noopener">DSB: Verdt å vite om tilfluktsrom</a> (guidance; national totals)</li>
      <li><a href="${esc(s.official_map_url)}" target="_blank" rel="noopener">DSB's official public shelter map</a></li></ul>`;
  });

  // ---- data -------------------------------------------------------------------------------------------------------
  if (app.data.shelters !== undefined) setData(app.data.shelters);
  else app.loadData("shelters").then(setData, (err) => console.warn("shelters failed to load", err));

  app.shelters = {
    get data() { return data; }, get on() { return on; }, show, items, openCard, openGroup, closeCard, councilNotes,
    tier, symbolPx, page: PAGE,
  };
}
