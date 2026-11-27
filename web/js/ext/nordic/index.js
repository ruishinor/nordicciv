// NordicCiv extension: the Council (advisors with evidence-based observations), Compare, Explorer (table, scatter,
// CSV export) and a Timeline lens built from the population series. Deterministic: no external API at runtime.
// Every observation is computed from the loaded data and names its source; nothing is generated text from a model.
import { esc, int, compact, money, pct, popShort } from "../../format.js";
import { icon } from "../../ui/icon.js";

const COUNTRY = { NO: "Norway", SE: "Sweden", DK: "Denmark" };
const FLAG = { NO: "🇳🇴", SE: "🇸🇪", DK: "🇩🇰" };
const fin = Number.isFinite;
const sgn = (g, d = 1) => (fin(g) ? `${g >= 0 ? "+" : "−"}${Math.abs(g * 100).toFixed(d)}%` : "–");
const sum = (a) => a.reduce((p, q) => p + (fin(q) ? q : 0), 0);
const median = (a) => { const v = a.filter(fin).sort((x, y) => x - y); return v.length ? v[Math.floor(v.length / 2)] : null; };

const ADVISORS = [
  { id: "geography", name: "Geography", emoji: "🧭", color: "#7fb3d5" },
  { id: "people", name: "Population & society", emoji: "👥", color: "#e8dcc0" },
  { id: "economy", name: "Economy", emoji: "🪙", color: "#e6c14a" },
  { id: "industry", name: "Industry", emoji: "⚙️", color: "#d98b3a" },
  { id: "energy", name: "Energy", emoji: "⚡", color: "#4aa3df" },
  { id: "infrastructure", name: "Infrastructure", emoji: "🛣️", color: "#c9a06a" },
  { id: "environment", name: "Environment", emoji: "🌲", color: "#5a8a3a" },
  { id: "resilience", name: "Resilience", emoji: "🛡️", color: "#e5707a" },
];

const COLUMNS = [
  { key: "population", label: "Population 2026", fmt: int, get: (c) => c.population },
  { key: "growth", label: "Change 2016–26", fmt: (v) => sgn(v), get: (c) => c.growth },
  { key: "density", label: "Residents / km²", fmt: (v) => (v < 10 ? v.toFixed(1) : int(v)), get: (c) => c.density },
  { key: "land_km2", label: "Land km²", fmt: int, get: (c) => c.land_km2 },
  { key: "share_65plus", label: "Aged 65+", fmt: (v) => pct(v), get: (c) => c.share_65plus },
  { key: "share_0_19", label: "Aged 0–19", fmt: (v) => pct(v), get: (c) => c.share_0_19 },
  { key: "jobs_total", label: "Jobs (place of work)", fmt: int, get: (c) => c.jobs_total },
  { key: "jobs_per_100", label: "Jobs per 100 residents", fmt: (v) => v.toFixed(0), get: (c) => c.jobs_per_100 },
  { key: "food", label: "Food (jobs)", fmt: int, get: (c) => c.yields?.food },
  { key: "production", label: "Production (jobs)", fmt: int, get: (c) => c.yields?.production },
  { key: "science", label: "Science (jobs)", fmt: int, get: (c) => c.yields?.science },
  { key: "culture", label: "Culture (jobs)", fmt: int, get: (c) => c.yields?.culture },
  { key: "welfare", label: "Welfare (jobs)", fmt: int, get: (c) => c.yields?.welfare },
  { key: "gdp", label: "GDP ≈ (€, est.)", fmt: (v) => money(v), get: (c) => c.gdp },
  { key: "gdp_pp", label: "GDP ≈ per resident (€)", fmt: (v) => "€" + int(v), get: (c) => (c.gdp && c.population ? c.gdp / c.population : null) },
  { key: "income_index", label: "Income vs national (exp.)", fmt: (v) => Math.round(v * 100) + "%", get: (c) => c.income_index },
  { key: "nearest_bigger_km", label: "Km to larger municipality", fmt: (v) => v.toFixed(0), get: (c) => c.nearest_bigger_km },
];
const colByKey = new Map(COLUMNS.map((c) => [c.key, c]));

export function install(app) {
  const { cities, nation } = app.data;
  const states = app.data.states || [];
  const w = app.w;
  const byId = new Map(cities.map((c) => [c.id, c]));
  const compareSet = [];
  let tab = "advisors";
  let advisor = "geography";
  let context = null; // {kind: "city", city} | {kind: "state", index}
  let explorer = { country: "", region: "", sort: "population", desc: true, cols: ["population", "growth", "density", "share_65plus", "jobs_per_100", "gdp_pp"], x: "density", y: "share_65plus", q: "" };
  let dockEl = null;

  // ---- derived indexes ---------------------------------------------------------------------------------------------
  const hexesOf = new Map(); // municipality id -> [cells]
  const cnt = w.raw.counties;
  for (let i = 0; i < w.raw.owner.length; i++) {
    const m = w.raw.county[i];
    if (m >= 0 && w.raw.owner[i] >= 0) {
      const id = cnt[m].geoid;
      if (!hexesOf.has(id)) hexesOf.set(id, []);
      hexesOf.get(id).push(i);
    }
  }
  const lens = (id) => app.data.lenses?.lenses?.find((l) => l.id === id);
  const rankOf = (list, get, item, desc = true) => {
    const v = list.map(get).filter(fin).sort((a, b) => (desc ? b - a : a - b));
    const x = get(item);
    return fin(x) ? v.indexOf(x) + 1 : null;
  };
  const totals = nation.nation;

  // ---- UI shell ------------------------------------------------------------------------------------------------------
  const btn = app.ui.addTopButton({ id: "council", icon: "🏛️", label: "Council", title: "Advisors, comparison and data explorer (C)", onClick: () => toggle() });

  function toggle(open) {
    const want = open ?? !(app.ui.isDockOpen?.("left"));
    if (!want) { app.ui.undock("left"); dockEl = null; app.setHighlight(null); return; }
    dockEl = app.ui.dock("left", { width: Math.min(460, Math.max(340, innerWidth * 0.32)), label: "Council" });
    const st = app.state;
    if (st?.selectedCity) context = { kind: "city", city: st.selectedCity };
    else if (st?.selectedState != null) context = { kind: "state", index: st.selectedState };
    render();
  }
  addEventListener("keydown", (e) => {
    if (e.target.closest?.("input, textarea, select")) return;
    if (e.key === "c" && !e.metaKey && !e.ctrlKey && !e.altKey) toggle();
  });
  app.on("select", (s) => {
    context = s && s.kind ? s : null;
    if (dockEl && tab === "advisors") render();
  });
  app.on("compare", (e) => {
    if (e?.add && !compareSet.includes(e.add)) compareSet.push(e.add);
    while (compareSet.length > 4) compareSet.shift();
    tab = "compare";
    toggle(true);
  });

  function render() {
    if (!dockEl) return;
    dockEl.innerHTML = `<div class="nc">
      <div class="nc-head"><h2>Council of Scandinavia</h2><button class="icon-btn nc-close" aria-label="Close the council">${icon("close", "✕", { size: 13 })}</button></div>
      <div class="nc-tabs" role="tablist">${[["advisors", "Advisors"], ["compare", `Compare${compareSet.length ? ` (${compareSet.length})` : ""}`], ["explorer", "Explorer"], ["timeline", "Timeline"]]
        .map(([id, l]) => `<button role="tab" data-tab="${id}" aria-selected="${tab === id}">${l}</button>`).join("")}</div>
      <div class="nc-body">${tab === "advisors" ? advisorsHtml() : tab === "compare" ? compareHtml() : tab === "explorer" ? explorerHtml() : timelineHtml()}</div></div>`;
    dockEl.querySelector(".nc-close").onclick = () => toggle(false);
    dockEl.querySelectorAll("[data-tab]").forEach((b) => (b.onclick = () => { tab = b.dataset.tab; render(); }));
    wire();
  }

  // ---- shared actions ----------------------------------------------------------------------------------------------
  function wire() {
    dockEl.querySelectorAll("[data-adv]").forEach((b) => (b.onclick = () => { advisor = b.dataset.adv; render(); }));
    dockEl.querySelectorAll("[data-lens]").forEach((b) => (b.onclick = () => app.setLens(b.dataset.lens)));
    dockEl.querySelectorAll("[data-city]").forEach((b) => (b.onclick = () => app.selectCity(b.dataset.city)));
    dockEl.querySelectorAll("[data-hl]").forEach((b) => (b.onclick = () => highlightIds(b.dataset.hl.split(","))));
    dockEl.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { compareSet.splice(compareSet.indexOf(b.dataset.rm), 1); render(); }));
    const add = dockEl.querySelector("#nc-add");
    if (add) {
      add.oninput = () => {
        const q = norm(add.value);
        const list = dockEl.querySelector("#nc-add-list");
        const hits = q.length < 2 ? [] : cities.filter((c) => norm(c.name).startsWith(q) || norm(c.place || "").startsWith(q)).slice(0, 6);
        list.innerHTML = hits.map((c) => `<button class="chip" data-addc="${esc(c.id)}">${FLAG[c.country]} ${esc(c.name)}</button>`).join("");
        list.querySelectorAll("[data-addc]").forEach((b) => (b.onclick = () => { if (!compareSet.includes(b.dataset.addc)) compareSet.push(b.dataset.addc); while (compareSet.length > 4) compareSet.shift(); render(); }));
      };
    }
    const ex = dockEl.querySelector(".nc-explorer");
    if (ex) wireExplorer(ex);
    const tl = dockEl.querySelector(".nc-timeline");
    if (tl) wireTimeline(tl);
  }
  function highlightIds(ids) {
    const cells = new Set();
    for (const id of ids) for (const c of hexesOf.get(id) || []) cells.add(c);
    const h = { cells, cities: new Set(ids), dimOthers: true, color: "#ffe08a" };
    app.setHighlight(h);
    const b = app.highlightBounds(h);
    if (b) app.fitBounds(b.x0, b.y0, b.x1, b.y1, { maxScale: 3 });
  }
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const cityLink = (c) => `<button class="link" data-city="${esc(c.id)}">${FLAG[c.country] || ""} ${esc(c.name)}</button>`;
  const obs = (text, { evidence = "", lensId = null, hl = null, source = "" } = {}) => `<div class="obs"><p>${text}</p>
    <div class="obs-foot">${evidence ? `<span class="muted">${evidence}</span>` : ""}${source ? `<span class="src">${esc(source)}</span>` : ""}
    ${lensId && lens(lensId) ? `<button class="chip" data-lens="${lensId}">Show lens: ${esc(lens(lensId).name)}</button>` : ""}
    ${hl ? `<button class="chip" data-hl="${esc(hl.join(","))}">Highlight on map</button>` : ""}</div></div>`;

  // ---- advisors ----------------------------------------------------------------------------------------------------
  function advisorsHtml() {
    const a = ADVISORS.find((x) => x.id === advisor);
    const subject = context?.kind === "city" ? context.city : null;
    const region = context?.kind === "state" ? states[context.index] : null;
    const scope = subject ? `${FLAG[subject.country]} ${esc(subject.name)}` : region ? esc(region.name) : "All of Scandinavia";
    let items = [];
    try { items = OBS[advisor](subject, region); } catch (e) { console.error(e); items = [`<p class="muted">Could not compute (${esc(e.message)}).</p>`]; }
    return `<div class="adv-row">${ADVISORS.map((x) => `<button class="adv ${x.id === advisor ? "on" : ""}" data-adv="${x.id}" title="${esc(x.name)}" style="--c:${x.color}"><span>${x.emoji}</span><small>${esc(x.name.split(" ")[0])}</small></button>`).join("")}</div>
      <h3 class="adv-title" style="color:${a.color}">${a.emoji} ${esc(a.name)} advisor <span class="muted">· ${scope}</span></h3>
      <p class="muted small">${subject || region ? "Observations about your selection. Close the panel to hear about Scandinavia as a whole." : "Select a municipality or region on the map for local observations."}
      Every statement is computed from the data on this map; sources are named under each.</p>
      ${items.join("")}`;
  }

  const OBS = {
    geography(c, r) {
      const out = [];
      if (c) {
        const hx = hexesOf.get(c.id) || [];
        const elevs = hx.map((i) => w.raw.elev[i]);
        const maxE = Math.max(...hx.map((i) => w.raw.elev_max?.[i] ?? 0), 0);
        const areaRank = rankOf(cities, (x) => x.land_km2, c);
        const dens = c.density, sDens = totals.density;
        out.push(obs(`${cityLink(c)} covers <b>${int(c.land_km2)} km²</b> (#${areaRank} of ${cities.length} by area) with <b>${int(c.population)}</b> residents —
          ${fin(dens) ? `${dens < 10 ? dens.toFixed(1) : int(dens)} per km², ${dens > sDens ? `${(dens / sDens).toFixed(1)}× denser` : `${(sDens / dens).toFixed(dens > sDens / 10 ? 1 : 0)}× sparser`} than Scandinavia as a whole (${sDens.toFixed(0)}/km²)` : ""}.`,
          { lensId: "density", hl: [c.id], source: "SSB/SCB/DST population and area" }));
        if (hx.length) {
          const pctOf = (k) => sum(hx.map((i) => w.raw.pct?.[k]?.[i])) / hx.length / 100;
          const land = [["forest", "forest"], ["heath", "treeless fjell heath"], ["bare", "bare rock"], ["crop", "farmland"], ["wetland", "mire"], ["ice", "glacier"], ["developed", "built-up land"]]
            .map(([k, l]) => [l, pctOf(k)]).filter(([, v]) => v >= 0.08).sort((x, y) => y[1] - x[1]);
          out.push(obs(`Its ${hx.length} hexes average <b>${int(sum(elevs) / elevs.length)} m</b> above sea level, rising to <b>${int(maxE)} m</b> (highest 1 km cell).
            The land is ${land.map(([l, v]) => `${Math.round(v * 100)}% ${l}`).join(", ") || "mixed"}.`, { lensId: "elevation", source: "EU-DEM, CORINE Land Cover 2018 (1 km)" }));
        }
        if (c.nearest_bigger_km) {
          const big = cities.filter((x) => x.population > c.population).map((x) => [x, Math.hypot(x.x - c.x, x.y - c.y)]).sort((a, b) => a[1] - b[1])[0];
          out.push(obs(`The nearest municipality with more people is ${cityLink(big[0])}, <b>${Math.round(big[1])} km</b> away in a straight line${big[1] > 100 ? " — a long way in Scandinavian terms, which makes this a regional centre by necessity" : ""}.`,
            { lensId: "remoteness", source: "municipal main settlements (Euronym)" }));
        }
        return out;
      }
      // Scandinavia-wide
      const north = cities.filter((x) => x.lat >= 63);
      const nPop = sum(north.map((x) => x.population)), nLand = sum(north.map((x) => x.land_km2));
      const big = [...cities].sort((a, b) => b.land_km2 - a.land_km2).slice(0, 5);
      out.push(obs(`Municipalities whose main town lies north of 63°N hold <b>${pct(nLand / totals.land_km2, 0)}</b> of Scandinavia's land but only <b>${pct(nPop / totals.population, 0)}</b> of its people.
        The five largest by area — ${big.map(cityLink).join(", ")} — together cover ${int(sum(big.map((x) => x.land_km2)))} km² with ${int(sum(big.map((x) => x.population)))} residents.`,
        { lensId: "density", hl: big.map((x) => x.id), source: "SSB/SCB/DST population and land area" }));
      const coastal = cities.filter((c) => (hexesOf.get(c.id) || []).some((i) => { for (let d = 0; d < 6; d++) { const j = w.grid.neighbour(i, d); if (j >= 0 && w.water[j] && w.water[j] !== 3) return true; } return false; }));
      out.push(obs(`<b>${coastal.length}</b> of ${cities.length} municipalities touch the sea on this map, and they are home to <b>${pct(sum(coastal.map((c) => c.population)) / totals.population, 0)}</b> of Scandinavians: the coast, not the interior, is where people live.`,
        { hl: coastal.map((c) => c.id), source: "hex coastline from CORINE; population registers" }));
      const ice = sum(w.raw.pct?.ice?.map((v, i) => (w.raw.owner[i] >= 0 ? v : 0)) || []) / 100 * (w.grid.R ** 2 * 2.598);
      out.push(obs(`Glaciers cover about <b>${int(ice)} km²</b> of mainland Scandinavia on the 1 km CORINE grid — Jostedalsbreen, Svartisen and Folgefonna are the largest bodies, all in Norway.`,
        { lensId: "cover", source: "CORINE Land Cover 2018 (class 335)" }));
      return out;
    },
    people(c, r) {
      const out = [];
      const sel = c ? [c] : r ? cities.filter((x) => x.states[0] === r.fips) : cities;
      if (c) {
        const cn = nation.countries[c.country];
        out.push(obs(`${cityLink(c)} ${fin(c.growth) ? `${c.growth >= 0 ? "grew" : "shrank"} by <b>${sgn(c.growth)}</b> between 2016 and 2026, against ${sgn(cn.growth)} for ${COUNTRY[c.country]}` : "has no comparable 2016 figure"}.
          ${fin(c.share_65plus) ? `<b>${pct(c.share_65plus, 0)}</b> of residents are 65 or older (${COUNTRY[c.country]}: ${pct(cn.share_65plus, 0)}).` : ""}`,
          { lensId: "growth", source: "SSB 07459, SCB TAB628/TAB5557, DST FOLK1A" }));
        if (fin(c.jobs_per_100)) out.push(obs(c.jobs_per_100 >= 55
          ? `With <b>${Math.round(c.jobs_per_100)} jobs per 100 residents</b>, ${esc(c.name)} is a commuting centre: more people work here than its working-age residents alone could fill.`
          : c.jobs_per_100 <= 30 ? `Only <b>${Math.round(c.jobs_per_100)} jobs per 100 residents</b> are located in ${esc(c.name)}: many residents commute out or are outside the labour force.`
          : `${esc(c.name)} has <b>${Math.round(c.jobs_per_100)} jobs per 100 residents</b>, close to the Scandinavian level (${Math.round(100 * totals.jobs_total / totals.population)}).`,
          { lensId: "jobs_ratio", source: "jobs at place of work 2024 ÷ population 2026" }));
        return out;
      }
      const grow = sel.filter((x) => fin(x.growth) && x.population >= 5000).sort((a, b) => b.growth - a.growth);
      const shrinking = sel.filter((x) => fin(x.growth) && x.growth < 0);
      out.push(obs(`${r ? esc(r.name) : "Scandinavia"} ${r ? `has ${int(r.population)} residents (${sgn(r.growth)} since 2016)` : `has ${int(totals.population)} residents, ${sgn(totals.growth)} since 2016`}.
        <b>${shrinking.length}</b> of ${sel.length} municipalities shrank. Fastest growing (5,000+ residents): ${grow.slice(0, 3).map((x) => `${cityLink(x)} ${sgn(x.growth)}`).join(", ")};
        fastest shrinking: ${grow.slice(-3).reverse().map((x) => `${cityLink(x)} ${sgn(x.growth)}`).join(", ")}.`,
        { lensId: "growth", hl: shrinking.map((x) => x.id), source: "national population registers" }));
      const old = sel.filter((x) => fin(x.share_65plus)).sort((a, b) => b.share_65plus - a.share_65plus);
      const corr = pearson(sel.map((x) => x.share_65plus), sel.map((x) => x.growth));
      out.push(obs(`Ageing is uneven: the oldest municipalities (${old.slice(0, 3).map((x) => `${cityLink(x)} ${pct(x.share_65plus, 0)}`).join(", ")}) have up to twice the share of 65+ of the youngest (${old.slice(-2).map((x) => `${cityLink(x)} ${pct(x.share_65plus, 0)}`).join(", ")}).
        Across these municipalities the share of 65+ and population growth are correlated at <b>r = ${fin(corr) ? corr.toFixed(2) : "–"}</b>: places that lose people also grow older.`,
        { lensId: "ageing", source: "population by age, 2026" }));
      const caps = ["NO-0301", "SE-0180", "DK-101"].map((id) => byId.get(id));
      if (!r) out.push(obs(`The three capitals — ${caps.map(cityLink).join(", ")} — are home to ${pct(sum(caps.map((x) => x.population)) / totals.population, 0)} of Scandinavians but host ${pct(sum(caps.map((x) => x.jobs_total)) / totals.jobs_total, 0)} of the jobs.`,
        { hl: caps.map((x) => x.id), source: "population 2026, jobs 2024" }));
      return out;
    },
    economy(c, r) {
      const out = [];
      const pps = lens("gdp_pc");
      if (c) {
        const v = c.hexValue ?? null;
        const i0 = (hexesOf.get(c.id) || [])[0];
        const regPps = pps && i0 != null ? pps.values[i0] : null;
        out.push(obs(`${cityLink(c)}'s Gold (GDP) is about <b>${money(c.gdp)}</b> — an estimate: ${esc(c.gdp_region_name || c.gdp_region)}'s ${c.gdp_year} GDP shared by jobs. Its region produces
          <b>${fin(regPps) ? int(regPps) : "–"} PPS per resident</b> (EU-27 purchasing power).`, { lensId: "gdp_pc", source: "SSB 09391, SCB TAB3138, DST NRHP; Eurostat PPPs" }));
        if (fin(c.income_index)) out.push(obs(`Incomes are <b>${Math.round(c.income_index * 100)}%</b> of the ${COUNTRY[c.country]} level (${int(c.income)} ${c.income_currency}; ${c.country === "NO" ? "median household income after tax" : c.country === "SE" ? "median net income, 20+" : "average disposable income per person"}, 2024).`,
          { lensId: "income", source: "experimental: compare within a country" }));
        return out;
      }
      if (pps) {
        const vals = new Map();
        cities.forEach((x) => { const i0 = (hexesOf.get(x.id) || [])[0]; if (i0 != null && fin(pps.values[i0])) vals.set(x.gdp_region_name || x.gdp_region, pps.values[i0]); });
        const sorted = [...vals.entries()].sort((a, b) => b[1] - a[1]);
        out.push(obs(`Regional GDP per resident ranges from <b>${int(sorted[0][1])} PPS</b> (${esc(sorted[0][0])}) to <b>${int(sorted.at(-1)[1])} PPS</b> (${esc(sorted.at(-1)[0])}) — a ${(sorted[0][1] / sorted.at(-1)[1]).toFixed(1)}× gap, largely the pull of capital regions on head offices and high-value services.`,
          { lensId: "gdp_pc", source: "regional accounts 2023 ÷ population; Eurostat PPPs" }));
      }
      out.push(obs(`${esc(nation.extra_regio.note)}`, { source: "SSB 09391 (extra-regio)" }));
      const types = {};
      cities.forEach((x) => (types[x.type.label] = (types[x.type.label] || 0) + 1));
      out.push(obs(`By their strongest specialisation, Scandinavia's municipalities divide into ${Object.entries(types).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k, v]) => `${v} ${esc(k.toLowerCase())}`).join(", ")} …`,
        { lensId: "specialisation", source: "location quotients, jobs 2024" }));
      return out;
    },
    industry(c, r) {
      const out = [];
      if (c) {
        if (c.specialisations?.length) {
          out.push(obs(`${cityLink(c)} specialises in ${c.specialisations.map((s) => `<b>${esc(s.label.toLowerCase())}</b> (×${s.lq.toFixed(1)}, ${compact(s.jobs)} jobs)`).join(", ")}: these industries hold a much larger share of local jobs than across Scandinavia.`,
            { lensId: "specialisation", source: "location quotients vs NO+SE+DK" }));
        } else out.push(obs(`${cityLink(c)} has no industry group with a location quotient above 1.5 and 250+ jobs: its economy mirrors the Scandinavian mix.`, { lensId: "specialisation" }));
        const d = c.jobs_detail || {};
        if (fin(d.B) && d.B > 200) out.push(obs(`<b>${int(d.B)}</b> jobs here are in mining and quarrying — in Norway and Denmark that includes oil and gas extraction (${pct(d.B / c.jobs_total, 1)} of local jobs).`, { source: c.country === "NO" ? "SSB 07984" : "DST RAS501" }));
        const mines = (app.data.resources?.items || []).filter((it) => it.cbsa === c.id && (it.type === "metal_mine" || it.type === "industrial_mineral"));
        if (mines.length) out.push(obs(`Mines in ${esc(c.name)} (SGU): ${mines.slice(0, 5).map((m) => `<b>${esc(m.name)}</b> — ${esc(m.detail)}`).join("; ")}. Sweden publishes mining jobs together with manufacturing, so they sit inside the B–C group above.`,
          { source: "SGU mineral resources database" }));
        const top = Object.entries(c.jobs).filter(([k]) => k !== "X").sort((a, b) => b[1] - a[1])[0];
        out.push(obs(`The largest employer group is <b>${esc(nation.industries[top[0]].toLowerCase())}</b> with ${int(top[1])} jobs (${pct(top[1] / c.jobs_total, 0)}).`, { source: "jobs at place of work, 2024" }));
        return out;
      }
      const conc = (g) => [...cities].filter((x) => x.jobs_total > 2000).sort((a, b) => (b.lq?.[g] || 0) - (a.lq?.[g] || 0)).slice(0, 4);
      out.push(obs(`Industrial towns: the highest concentrations of mining & manufacturing jobs (2,000+ jobs) are in ${conc("BC").map((x) => `${cityLink(x)} ×${x.lq.BC.toFixed(1)}`).join(", ")}.`,
        { lensId: "share_BC", hl: conc("BC").map((x) => x.id), source: "jobs 2024, NACE B–C" }));
      const big = (g) => [...cities].filter((x) => x.jobs_total > 15000).sort((a, b) => (b.lq?.[g] || 0) - (a.lq?.[g] || 0)).slice(0, 4);
      out.push(obs(`Knowledge economies: ICT jobs concentrate in ${conc("J").map((x) => `${cityLink(x)} ×${x.lq.J.toFixed(1)}`).join(", ")}. Among municipalities with 15,000+ jobs, education (schools and universities) weighs most in ${big("P").map((x) => `${cityLink(x)} ×${x.lq.P.toFixed(1)}`).join(", ")}.`,
        { lensId: "share_J", hl: conc("J").map((x) => x.id), source: "jobs 2024, NACE J and P" }));
      const petro = cities.filter((x) => fin(x.jobs_detail?.B) && x.jobs_detail.B > 1500).sort((a, b) => b.jobs_detail.B - a.jobs_detail.B);
      if (petro.length) out.push(obs(`Oil, gas and mining employment (NACE B, published separately in Norway and Denmark) clusters in ${petro.slice(0, 5).map((x) => `${cityLink(x)} ${compact(x.jobs_detail.B)}`).join(", ")} — the onshore half of the North Sea economy.`,
        { hl: petro.map((x) => x.id), source: "SSB 07984, DST RAS501" }));
      return out;
    },
    energy(c, r) {
      const out = [];
      const res = app.data.resources;
      if (!res) return [`<p class="muted">Resources are still loading…</p>`];
      const types = new Map(res.types.map((t) => [t.id, t]));
      const inArea = (it) => (c ? it.cbsa === c.id : r ? it.state === r.fips : true);
      const items = res.items.filter(inArea);
      const cap = (t) => sum(items.filter((it) => it.type === t).map((it) => it.value));
      const el = nation.electricity;
      if (!c && !r && el) {
        const rows = ["NO", "SE", "DK"].map((cc) => {
          const d = el.countries[cc];
          const share = (k) => (d[k] ? d[k] / d.Total : 0);
          return `<b>${COUNTRY[cc]}</b> ${int(d.Total / 1000)} TWh: hydro ${pct(share("Hydro"), 0)}, wind ${pct(share("Wind"), 0)}${d.Nuclear ? `, nuclear ${pct(share("Nuclear"), 0)}` : ""}, fossil ${pct(share("Fossil"), 0)}`;
        });
        out.push(obs(`Three very different power systems (${el.year}, gross production): ${rows.join("; ")}.`, { source: el.source }));
        out.push(obs(`On the map: ${res.summary.national.hydro.count} hydropower stations ≥ 50 MW (${int(res.summary.national.hydro.value)} MW), ${res.summary.national.nuclear.count} nuclear sites (${int(res.summary.national.nuclear.value)} MW), ${res.summary.national.wind.count} onshore and ${res.summary.national.offshore_wind.count} offshore wind farms. Capacity is not production: hydro reservoirs and wind run below full output most of the year.`,
          { source: "powerplantmatching (installed capacity)" }));
      }
      const scope = c ? cityLink(c) : r ? esc(r.name) : "Scandinavia";
      const lines = ["hydro", "pumped", "nuclear", "wind", "offshore_wind", "solar", "thermal"].map((t) => [t, cap(t), items.filter((it) => it.type === t)]).filter(([, v]) => v > 0);
      if (c || r) {
        out.push(lines.length
          ? obs(`${scope} hosts ${lines.map(([t, v, its]) => `<b>${int(v)} MW</b> of ${esc(types.get(t).name.toLowerCase())}${its.length > 1 ? ` (${its.length} sites)` : ` (${esc(its[0].name)})`}`).join(", ")}.`,
            { source: "powerplantmatching; thresholds in the Almanac" })
          : obs(`No mapped power plant (above the per-type thresholds) stands in ${scope}.`, { source: "powerplantmatching" }));
        if (c && !lines.length) {
          const reg = states.find((x) => x.fips === c.states[0]);
          const ri = res.items.filter((it) => it.state === c.states[0]);
          const rl = ["hydro", "nuclear", "wind", "offshore_wind", "thermal"].map((t) => [t, sum(ri.filter((it) => it.type === t).map((it) => it.value))]).filter(([, v]) => v > 0);
          if (rl.length) out.push(obs(`Its region, ${esc(reg?.name || "")}, hosts ${rl.map(([t, v]) => `${int(v)} MW of ${esc(types.get(t).name.toLowerCase())}`).join(", ")}.`, { source: "powerplantmatching (installed capacity)" }));
        }
        const fields = items.filter((it) => it.type === "oil_gas");
        if (fields.length) out.push(obs(`${fields.length} producing oil/gas fields: ${fields.slice(0, 4).map((f) => `${esc(f.name)} ${f.value} M Sm³ o.e.`).join(", ")}.`, { source: "Sodir FactPages" }));
      } else {
        const fields = res.items.filter((it) => it.type === "oil_gas" && fin(it.value)).sort((a, b) => b.value - a.value);
        out.push(obs(`${fields.length} producing fields on the Norwegian shelf delivered <b>${sum(fields.map((f) => f.value)).toFixed(0)} million Sm³ oil equivalents</b> in ${res.production_year}; the two largest, ${esc(fields[0].name)} and ${esc(fields[1].name)}, account for ${pct((fields[0].value + fields[1].value) / sum(fields.map((f) => f.value)), 0)}.`,
          { source: "Sodir FactPages, field production" }));
      }
      return out;
    },
    infrastructure(c, r) {
      const out = [];
      const inf = app.data.infrastructure;
      const hosp = lens("hospital");
      const sel = c ? [c] : r ? cities.filter((x) => x.states[0] === r.fips) : cities;
      const cellsOf = sel.flatMap((x) => hexesOf.get(x.id) || []);
      if (hosp) {
        let far = 0, tot = 0;
        for (const i of cellsOf) { const p = w.raw.pop?.[i] || 0; const v = hosp.values[i]; if (fin(v)) { tot += p; if (v > 30) far += p; } }
        out.push(obs(`An estimated <b>${pct(tot ? far / tot : null, 1)}</b> of residents ${c ? `of ${cityLink(c)}` : r ? `of ${esc(r.name)}` : "of Scandinavia"} live where the average drive to the nearest hospital exceeds 30 minutes.`,
          { lensId: "hospital", source: "GISCO 1 km accessibility × dasymetric hex population (estimate)" }));
      }
      if (inf) {
        const inSel = (o) => (c ? o.county === c.id : r ? o.state === r.fips : true);
        const ap = inf.airports.filter(inSel).filter((a) => a.passengers).sort((a, b) => b.passengers - a.passengers);
        const pt = inf.ports.filter(inSel).sort((a, b) => b.tonnes - a.tonnes);
        if (ap.length) out.push(obs(`Airports: ${ap.slice(0, 4).map((a) => `${esc(a.name)} <b>${compact(a.passengers)}</b>`).join(", ")} passengers (2024).`, { source: "Eurostat avia_paoa" }));
        if (pt.length) out.push(obs(`Ports: ${pt.slice(0, 4).map((p) => `${esc(p.short || p.name)} <b>${compact(p.tonnes)} t</b>`).join(", ")} of goods handled (2024).`, { source: "Eurostat mar_go_aa" }));
        if (!c && !r) {
          const links = (app.data.wonders?.wonders || []).filter((x) => x.rule === "fixed_link");
          out.push(obs(`Geography is expensive to cross: ${links.length} fixed links of record length — ${links.slice(0, 4).map((l) => `${esc(l.name)} (${l.metrics.length_km} km)`).join(", ")} — and ${inf.ferries.length} mapped ferry routes stitch fjords, sounds and islands together. The Øresund Bridge ties Copenhagen and Malmö into one labour market.`,
            { source: "Wikidata lengths; Natural Earth ferries" }));
        }
      }
      return out;
    },
    environment(c, r) {
      const out = [];
      const sel = c ? [c] : r ? cities.filter((x) => x.states[0] === r.fips) : cities;
      const cells = sel.flatMap((x) => hexesOf.get(x.id) || []);
      const avg = (k) => sum(cells.map((i) => w.raw.pct?.[k]?.[i])) / Math.max(1, cells.length) / 100;
      const tcd = sum(cells.map((i) => w.raw.tcd?.[i])) / Math.max(1, cells.filter((i) => fin(w.raw.tcd?.[i])).length);
      out.push(obs(`${c ? cityLink(c) : r ? esc(r.name) : "Scandinavia"}: forest ${pct(avg("forest"), 0)}, farmland ${pct(avg("crop") + avg("pasture"), 0)}, fjell heath and bare rock ${pct(avg("heath") + avg("bare"), 0)}, mires ${pct(avg("wetland"), 0)}, built-up ${pct(avg("developed"), 1)}; mean tree cover density ${fin(tcd) ? tcd.toFixed(0) : "–"}%.`,
        { lensId: "cover", source: "CORINE 2018, Copernicus TCD 2018 (1 km)" }));
      const ug = lens("urban_growth");
      if (ug) {
        const n = sum(cells.map((i) => ug.values[i]));
        out.push(obs(`Between 1990 and 2018 about <b>${int(n)}</b> one-kilometre cells ${c ? "here" : "in this area"} turned into built-up, industrial or transport land on the CORINE grid.`, { lensId: "urban_growth", source: "CORINE 1990 and 2018" }));
      }
      const parks = (app.data.wonders?.wonders || []).filter((x) => x.rule === "national_park" && (c ? x.county === c.id : r ? x.state === r.fips : true));
      if (parks.length) out.push(obs(`Large national parks: ${parks.map((p) => `${esc(p.short)} (${int(p.metrics.area_km2)} km²)`).join(", ")}.`, { source: "Wikidata areas; rule ≥ 1,000 km²" }));
      return out;
    },
    resilience(c, r) {
      const sel = c ? [c] : r ? cities.filter((x) => x.states[0] === r.fips) : cities;
      const one = sel.length === 1 ? sel[0] : null;
      const hhi = (x) => { const t = x.jobs_total; return t ? sum(Object.entries(x.jobs).filter(([k]) => k !== "X").map(([, v]) => (v / t) ** 2)) : null; };
      const rows = [
        ["Population change 2016–26", (x) => x.growth, sgn, "lower = more strain on services per resident"],
        ["Aged 65+", (x) => x.share_65plus, (v) => pct(v), "care demand"],
        ["Jobs per 100 residents", (x) => x.jobs_per_100, (v) => v.toFixed(0), "local labour market"],
        ["Employment concentration (HHI)", hhi, (v) => v.toFixed(3), "higher = more dependent on few industries"],
        ["Largest industry share", (x) => { const t = x.jobs_total; const m = Math.max(...Object.entries(x.jobs).filter(([k]) => k !== "X").map(([, v]) => v)); return t ? m / t : null; }, (v) => pct(v, 0), "single-industry exposure"],
        ["Km to a larger municipality", (x) => x.nearest_bigger_km, (v) => v.toFixed(0), "isolation"],
      ];
      const table = `<table class="nc-table"><tr><th>Indicator</th><th>${one ? esc(one.name) : "Median"}</th><th>Scandinavian median</th><th>Reads as</th></tr>
        ${rows.map(([l, g, f, note]) => { const v = one ? g(one) : median(sel.map(g)); const m = median(cities.map(g)); return `<tr><td>${l}</td><td><b>${fin(v) ? f(v) : "–"}</b></td><td>${fin(m) ? f(m) : "–"}</td><td class="muted">${note}</td></tr>`; }).join("")}</table>`;
      const out = [`<div class="obs"><p>Resilience is shown as separate, measurable indicators — deliberately <b>not</b> a single score, because the trade-offs between them are political, not statistical.</p>${table}
        <div class="obs-foot"><span class="src">population registers 2016–2026; jobs 2024</span></div></div>`];
      if (!one) {
        const exposed = sel.filter((x) => x.jobs_total > 1000).map((x) => [x, hhi(x)]).sort((a, b) => b[1] - a[1]).slice(0, 5);
        out.push(obs(`Most concentrated local economies (1,000+ jobs): ${exposed.map(([x, h]) => `${cityLink(x)} (${esc(x.type.label.toLowerCase())})`).join(", ")}. A downturn in one industry would hit these hardest.`,
          { hl: exposed.map(([x]) => x.id), source: "Herfindahl index of job shares across 14 industry groups" }));
      }
      return out;
    },
  };

  // ---- compare -----------------------------------------------------------------------------------------------------
  function compareHtml() {
    const list = compareSet.map((id) => byId.get(id)).filter(Boolean);
    const keys = ["population", "growth", "density", "land_km2", "share_65plus", "share_0_19", "jobs_total", "jobs_per_100", "production", "science", "welfare", "gdp_pp", "income_index", "nearest_bigger_km"];
    const table = list.length ? `<div class="nc-scroll"><table class="nc-table cmp-table"><tr><th></th>${list.map((c) => `<th>${cityLink(c)}<button class="x" data-rm="${esc(c.id)}" aria-label="Remove ${esc(c.name)}">✕</button></th>`).join("")}</tr>
      <tr><td>Type</td>${list.map((c) => `<td><span class="ctype" style="--c:${c.type.color}">${esc(c.type.label)}</span></td>`).join("")}</tr>
      ${keys.map((k) => { const col = colByKey.get(k); const vals = list.map((c) => col.get(c)); const max = Math.max(...vals.filter(fin)); return `<tr><td>${esc(col.label)}</td>${vals.map((v) => `<td class="${fin(v) && v === max && list.length > 1 ? "best" : ""}">${fin(v) ? col.fmt(v) : "–"}</td>`).join("")}</tr>`; }).join("")}
      </table></div><button class="chip" data-hl="${list.map((c) => c.id).join(",")}">Highlight on map</button>
      <p class="muted small">Income is relative to each country's own statistic; GDP per resident is an estimate (regional GDP shared by jobs).</p>`
      : `<p class="muted">Add municipalities with the box below, or with <i>Compare ⇄</i> in a municipality's panel.</p>`;
    return `${table}<div class="nc-add"><input id="nc-add" type="search" placeholder="Add a municipality…" autocomplete="off"><div id="nc-add-list" class="chips"></div></div>`;
  }

  // ---- explorer ----------------------------------------------------------------------------------------------------
  function filtered() {
    let list = cities;
    if (explorer.country) list = list.filter((c) => c.country === explorer.country);
    if (explorer.region) list = list.filter((c) => c.states[0] === explorer.region);
    if (explorer.q) { const q = norm(explorer.q); list = list.filter((c) => norm(c.name).includes(q)); }
    const col = colByKey.get(explorer.sort);
    return [...list].sort((a, b) => {
      const va = col.get(a), vb = col.get(b);
      if (!fin(va)) return 1;
      if (!fin(vb)) return -1;
      return explorer.desc ? vb - va : va - vb;
    });
  }
  function explorerHtml() {
    const list = filtered();
    const regionOpts = states.filter((s) => !explorer.country || s.country === explorer.country).map((s) => `<option value="${esc(s.fips)}" ${explorer.region === s.fips ? "selected" : ""}>${esc(s.name)}</option>`).join("");
    const colOpts = (sel) => COLUMNS.map((c) => `<option value="${c.key}" ${sel === c.key ? "selected" : ""}>${esc(c.label)}</option>`).join("");
    return `<div class="nc-explorer">
      <div class="nc-filters">
        <select data-f="country"><option value="">All three countries</option>${["NO", "SE", "DK"].map((cc) => `<option value="${cc}" ${explorer.country === cc ? "selected" : ""}>${COUNTRY[cc]}</option>`).join("")}</select>
        <select data-f="region"><option value="">All regions</option>${regionOpts}</select>
        <input data-f="q" type="search" placeholder="Filter by name" value="${esc(explorer.q)}">
      </div>
      <h4>Scatter</h4>
      <div class="nc-filters"><label>x <select data-f="x">${colOpts(explorer.x)}</select></label><label>y <select data-f="y">${colOpts(explorer.y)}</select></label></div>
      ${scatter(list)}
      <h4>${list.length} municipalities <button class="chip" data-act="hl">Highlight on map</button> <button class="chip" data-act="csv">Download CSV</button> <button class="chip" data-act="copy">Copy CSV</button></h4>
      <div class="nc-filters"><label>Columns <select data-f="addcol"><option value="">+ add column</option>${colOpts("")}</select></label></div>
      <div class="nc-scroll"><table class="nc-table ex-table"><tr><th>Municipality</th>${explorer.cols.map((k) => `<th class="sortable ${explorer.sort === k ? "on" : ""}" data-sort="${k}">${esc(colByKey.get(k).label)}${explorer.sort === k ? (explorer.desc ? " ▼" : " ▲") : ""} <button class="x" data-dropcol="${k}" aria-label="Remove column">✕</button></th>`).join("")}</tr>
      ${list.slice(0, 120).map((c) => `<tr><td>${cityLink(c)}</td>${explorer.cols.map((k) => { const v = colByKey.get(k).get(c); return `<td>${fin(v) ? colByKey.get(k).fmt(v) : "–"}</td>`; }).join("")}</tr>`).join("")}
      </table></div>${list.length > 120 ? `<p class="muted small">Showing 120 of ${list.length}; the CSV has all rows.</p>` : ""}
      <p class="muted small">Sources: SSB, SCB, Statistics Denmark (population 2026, jobs 2024); GDP estimate from regional accounts 2023. The CSV carries the same notes.</p></div>`;
  }
  function scatter(list) {
    const X = colByKey.get(explorer.x), Y = colByKey.get(explorer.y);
    const pts = list.map((c) => [X.get(c), Y.get(c), c]).filter(([a, b]) => fin(a) && fin(b));
    if (pts.length < 3) return `<p class="muted">Not enough data.</p>`;
    const logx = explorer.x === "density" || explorer.x === "population" || explorer.x === "land_km2" || explorer.x === "jobs_total";
    const tx = (v) => (logx ? Math.log10(Math.max(v, 0.1)) : v);
    const xs = pts.map((p) => tx(p[0])), ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const W = 400, H = 220, P = 30;
    const sx = (v) => P + ((tx(v) - x0) / (x1 - x0 || 1)) * (W - P - 8), sy = (v) => H - P - ((v - y0) / (y1 - y0 || 1)) * (H - P - 8);
    const col = { NO: "#e0745a", SE: "#5aa8e6", DK: "#e6c14a" };
    const r = pearson(pts.map((p) => tx(p[0])), ys);
    return `<svg class="nc-scatter" viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Scatter of ${esc(Y.label)} against ${esc(X.label)}">
      <line x1="${P}" y1="${H - P}" x2="${W - 4}" y2="${H - P}" stroke="#55606b"/><line x1="${P}" y1="6" x2="${P}" y2="${H - P}" stroke="#55606b"/>
      ${pts.map(([a, b, c]) => `<circle cx="${sx(a).toFixed(1)}" cy="${sy(b).toFixed(1)}" r="${c.population > 2e5 ? 4.5 : 2.6}" fill="${col[c.country]}" fill-opacity=".75" data-city="${esc(c.id)}"><title>${esc(c.name)}: ${X.fmt(a)}, ${Y.fmt(b)}</title></circle>`).join("")}
      <text x="${W - 4}" y="${H - 8}" text-anchor="end" font-size="11" fill="#9aa4b0">${esc(X.label)}${logx ? " (log)" : ""} →</text>
      <text x="${P + 4}" y="14" font-size="11" fill="#9aa4b0">↑ ${esc(Y.label)}</text>
      <text x="${W - 4}" y="14" text-anchor="end" font-size="11" fill="#c9a45c">r = ${fin(r) ? r.toFixed(2) : "–"}</text></svg>
      <p class="muted small">🇳🇴 orange · 🇸🇪 blue · 🇩🇰 yellow. Correlation is not causation; click a dot to open it.</p>`;
  }
  function wireExplorer(ex) {
    ex.querySelectorAll("[data-f]").forEach((el) => {
      el.onchange = el.oninput = () => {
        const f = el.dataset.f;
        if (f === "addcol") { if (el.value && !explorer.cols.includes(el.value)) explorer.cols.push(el.value); }
        else { explorer[f] = el.value; if (f === "country") explorer.region = ""; }
        if (f === "q" && el.type === "search") { clearTimeout(wireExplorer.t); wireExplorer.t = setTimeout(render, 250); return; }
        render();
      };
    });
    ex.querySelectorAll("[data-sort]").forEach((th) => (th.onclick = (e) => {
      if (e.target.closest("[data-dropcol]")) return;
      if (explorer.sort === th.dataset.sort) explorer.desc = !explorer.desc; else { explorer.sort = th.dataset.sort; explorer.desc = true; }
      render();
    }));
    ex.querySelectorAll("[data-dropcol]").forEach((b) => (b.onclick = () => { explorer.cols = explorer.cols.filter((k) => k !== b.dataset.dropcol); if (!explorer.cols.includes(explorer.sort)) explorer.sort = explorer.cols[0] || "population"; render(); }));
    ex.querySelector('[data-act="hl"]').onclick = () => highlightIds(filtered().map((c) => c.id));
    ex.querySelector('[data-act="csv"]').onclick = () => downloadCsv(filtered());
    ex.querySelector('[data-act="copy"]').onclick = async (e) => {
      try { await navigator.clipboard.writeText(csvText(filtered())); e.target.textContent = "Copied ✓"; }
      catch { e.target.textContent = "Copy blocked here"; }
    };
  }
  function downloadCsv(list) {
    const blob = new Blob([csvText(list)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "nordicciv-municipalities.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }
  function csvText(list) {
    const cols = COLUMNS;
    const q = (s) => `"${String(s ?? "").replace(/"/g, '""')}"`;
    const lines = [
      `# NordicCiv municipal data export (${new Date().toISOString().slice(0, 10)})`,
      `# Population: 1 January 2026 (SSB 07459, SCB TAB628, DST FOLK1A). Jobs: place of work, Nov/Q4 2024 (SSB 07984, SCB TAB3204, DST RAS501).`,
      `# GDP: regional accounts 2023 apportioned by jobs (estimate). Income index: experimental, relative to the same statistic nationally.`,
      `# Licences: NLOD/CC BY 4.0 (SSB), CC0 (SCB), CC BY 4.0 (DST, Eurostat). Empty = not available (never zero).`,
      ["id", "name", "country", "region", "type", ...cols.map((c) => c.label)].map(q).join(","),
      ...list.map((c) => [c.id, c.name, c.country, c.states[0], c.type.label, ...cols.map((col) => { const v = col.get(c); return fin(v) ? +v.toPrecision(8) : ""; })].map(q).join(",")),
    ];
    return lines.join("\n");
  }

  // ---- timeline: a population-change lens between any two years --------------------------------------------------
  let tl = { a: 2008, b: 2026 };
  function timelineHtml() {
    const yrs = Object.keys(cities[0].pop_series).map(Number);
    const opt = (sel) => yrs.map((y) => `<option ${y === sel ? "selected" : ""}>${y}</option>`).join("");
    const pa = sum(cities.map((c) => c.pop_series[tl.a])), pb = sum(cities.map((c) => c.pop_series[tl.b]));
    const comp = cities.filter((c) => fin(c.pop_series[tl.a]) && fin(c.pop_series[tl.b]));
    const ch = comp.map((c) => [c, c.pop_series[tl.b] / c.pop_series[tl.a] - 1]).sort((a, b) => b[1] - a[1]);
    return `<div class="nc-timeline">
      <p>Population on 1 January, every year since ${yrs[0]}, on today's municipal borders. Pick two years to colour the map by the change between them.</p>
      <div class="nc-filters"><label>From <select data-y="a">${opt(tl.a)}</select></label><label>to <select data-y="b">${opt(tl.b)}</select></label>
      <button class="chip" data-act="apply">Show on map</button></div>
      <p><b>${int(pa)}</b> → <b>${int(pb)}</b> residents (${sgn(pb / pa - 1)}) across the ${comp.length} municipalities with both years${comp.length < cities.length ? ` (${cities.length - comp.length} lack an early figure after boundary splits)` : ""}.</p>
      <p>Grew most: ${ch.slice(0, 4).map(([c, g]) => `${cityLink(c)} ${sgn(g)}`).join(", ")}<br>Shrank most: ${ch.slice(-4).reverse().map(([c, g]) => `${cityLink(c)} ${sgn(g)}`).join(", ")}</p>
      <p class="muted small">Sources: SSB 07459 (aggregated series for 2024 municipalities), SCB TAB628 (31 December of the previous year), DST FOLK1A (1st quarter).</p></div>`;
  }
  function wireTimeline(el) {
    el.querySelectorAll("[data-y]").forEach((s) => (s.onchange = () => { tl[s.dataset.y] = +s.value; render(); }));
    el.querySelector('[data-act="apply"]').onclick = () => {
      const n = w.raw.owner.length;
      const vals = new Array(n).fill(null);
      for (const c of cities) {
        const a = c.pop_series[tl.a], b = c.pop_series[tl.b];
        if (!fin(a) || !fin(b) || a <= 0) continue;
        for (const i of hexesOf.get(c.id) || []) vals[i] = b / a - 1;
      }
      const span = Math.max(0.05, Math.min(0.4, Math.abs(tl.b - tl.a) * 0.012));
      app.setLens({
        id: null, name: `Population change ${tl.a}–${tl.b}`, emoji: "📈", icon: "l-growth", group: "people", unit: "% change", format: "pct",
        scale: "linear", domain: [-span, span], ramp: ["#b2443a", "#e08a5a", "#f3e6b0", "#7fbf8f", "#2f8f6f"], higher_is: "neutral",
        resolution: "municipality", source: "ssb, scb, dst", description: `Change in residents between 1 January ${tl.a} and 1 January ${tl.b}, current municipal borders.`,
        note: "One value per municipality, repeated on each of its hexes.", values: vals,
      });
    };
  }

  function pearson(a, b) {
    const p = a.map((x, i) => [x, b[i]]).filter(([x, y]) => fin(x) && fin(y));
    if (p.length < 3) return null;
    const mx = sum(p.map((q) => q[0])) / p.length, my = sum(p.map((q) => q[1])) / p.length;
    let sxy = 0, sxx = 0, syy = 0;
    for (const [x, y] of p) { sxy += (x - mx) * (y - my); sxx += (x - mx) ** 2; syy += (y - my) ** 2; }
    return sxy / Math.sqrt(sxx * syy);
  }
  // ---- ferry routes: a static layer (Natural Earth 1:10m), dashed sea lanes -----------------------------------------
  let ferriesOn = true;
  let ferryPaths = null;
  const ferryLayer = {
    id: "ferries", z: 55, minRpx: 2.5,
    visible: () => ferriesOn && !!app.data.infrastructure?.ferries?.length,
    sig: () => `${ferriesOn ? 1 : 0}|${app.data.infrastructure ? 1 : 0}`,
    draw(ctx, vp, _w, o) {
      if (!ferryPaths) ferryPaths = app.data.infrastructure.ferries.map((f) => {
        const p = new Path2D();
        for (let k = 0; k < f.pts.length; k += 2) (k ? p.lineTo(f.pts[k], f.pts[k + 1]) : p.moveTo(f.pts[k], f.pts[k + 1]));
        return { p, f };
      });
      const s = vp.s;
      const wpx = Math.max(1, Math.min(2.4, o.Rpx / 8));
      ctx.save();
      ctx.lineCap = "round";
      for (const { p, f } of ferryPaths) {
        ctx.setLineDash([]);
        ctx.strokeStyle = "rgba(10,25,40,.45)";
        ctx.lineWidth = (wpx + 1.6) / s;
        ctx.stroke(p);
        ctx.setLineDash([5 / s, 4 / s]);
        ctx.strokeStyle = f.seasonal ? "rgba(220,235,245,.55)" : "rgba(240,248,255,.85)";
        ctx.lineWidth = wpx / s;
        ctx.stroke(p);
      }
      ctx.restore();
    },
  };
  app.registerStaticLayer(ferryLayer);
  app.ui.addMapToggle?.({ id: "ferries", label: "Ferries", icon: "t-port", title: "Ferry routes (Natural Earth 1:10m; a selection, not every ferry)", default: true,
    get: () => ferriesOn, set: (v) => { ferriesOn = !!v; app.invalidate?.(); app.requestDraw(); } });
  app.on("data", (e) => { if (e?.name === "infrastructure") { ferryPaths = null; app.invalidate?.(); } });

  // ---- 1 km coastline detail: fjords, sounds, small lakes and skerries finer than a hex (detail.json, lazy) -------
  let detail = null, detailLoading = false;
  const COVER_COL = new Map((w.raw.tables?.cover || []).map((c) => [c.id, c.color]));
  const detailLayer = {
    id: "detail-1km", z: 25, minRpx: 7,
    visible: () => true,
    sig: () => (detail ? "d1" : "d0"),
    draw(ctx, vp, _w, o) {
      if (!detail) {
        if (!detailLoading) {
          detailLoading = true;
          app.loadData("detail").then((d) => { detail = d; app.invalidate?.(); }, () => {});
        }
        return;
      }
      const s = 1.08; // a cell is 1 km; slight overlap closes seams between neighbours
      const pad = 2;
      const inView = (x, y) => x > vp.x0 - pad && x < vp.x1 + pad && y > vp.y0 - pad && y < vp.y1 + pad;
      const fill = (arr, step, color) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        for (let k = 0; k < arr.length; k += step) {
          const x = arr[k] / 2, y = arr[k + 1] / 2;
          if (inView(x, y)) ctx.rect(x - s / 2, y - s / 2, s, s);
        }
        ctx.fill();
      };
      ctx.save();
      fill(detail.sea, 2, "rgba(48,112,156,0.96)");
      fill(detail.lake, 2, "rgba(62,132,180,0.96)");
      // land cells in water hexes, coloured by their land-cover group
      const byCol = new Map();
      for (let k = 0; k < detail.land.length; k += 3) {
        const x = detail.land[k] / 2, y = detail.land[k + 1] / 2;
        if (!inView(x, y)) continue;
        const col = COVER_COL.get(detail.land[k + 2]) || "#8f9a58";
        if (!byCol.has(col)) byCol.set(col, []);
        byCol.get(col).push(x, y);
      }
      for (const [col, pts] of byCol) {
        ctx.fillStyle = col;
        ctx.beginPath();
        for (let k = 0; k < pts.length; k += 2) ctx.rect(pts[k] - s / 2, pts[k + 1] - s / 2, s, s);
        ctx.fill();
      }
      ctx.restore();
    },
  };
  app.registerStaticLayer(detailLayer);

  app.nordic = { toggle, OBS, compareSet, downloadCsv };
}
