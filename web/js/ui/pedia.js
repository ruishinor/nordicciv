// The Almanac: what every number means and exactly where it comes from.
import { resolveTables } from "../terrain.js";
import { esc } from "../format.js";
import { parseHex, luminance } from "../color.js";
import { icon, glyph } from "./icon.js";

const COVER_ICON = { forest_deciduous: "l-forest", forest_evergreen: "l-forest", forest_mixed: "l-forest", cropland: "l-farmland", pasture: "l-farmland", urban: "l-developed" };
// Glyph colour that reads on a resource medallion (dark on light faces such as nuclear yellow or silver).
const inkOn = (hex) => {
  try { return /^#[0-9a-f]{6}$/i.test(hex || "") && luminance(parseHex(hex)) > 0.4 ? "#1c1710" : "#f8f0d8"; } catch { return "#f8f0d8"; }
};
const CATEGORY = { energy: "Energy", mineral: "Minerals & petroleum", agri: "Agriculture" };

export function initPedia(data) {
  const modal = document.getElementById("pedia");
  const card = modal.querySelector(".modal-card");
  const nav = document.getElementById("pedia-nav");
  const body = document.getElementById("pedia-body");
  const srcName = (id) => data.sources?.find((s) => s.id === id)?.title || id || "";
  let restoreFocus = null;

  const h2 = (ic, fb, text) => `<h2>${icon(ic, fb, { size: 24 })}<span>${esc(text)}</span></h2>`;

  const pages = {
    "About this map": () => `
      ${h2("pedia", "📖", "About this map")}
      <p>This is the real Scandinavia — Norway, Sweden and Denmark — drawn like a strategy game. Nothing is invented:
      every tile, municipality and number comes from public data, listed under <i>Sources</i>, and every value says what it
      measures, where it comes from and at what resolution.</p>
      <h4>How it's built</h4>
      <p>The three countries are projected with a Lambert azimuthal equal-area projection centred on 63°N 15°E (so every hex
      covers the same ground area and the north is not stretched) and cut into ${data.world.grid.cols}×${data.world.grid.rows}
      hexes, ${(data.world.grid.radius * Math.sqrt(3)).toFixed(1)} km across (${(2.598 * data.world.grid.radius ** 2).toFixed(0)} km² each).
      Each hex summarises the ~94 one-kilometre cells of the European reference grids inside it: EU-DEM elevation,
      CORINE Land Cover 2018, Copenhagen tree-cover density and the GEOSTAT population grid.</p>
      <p><b>Cities are municipalities</b> (kommune / kommun): the basic unit of local government and of official statistics in
      all three countries. Their banners sit on the main settlement. Clicking any land hex opens the municipality it belongs to.</p>
      <h4>Reading it honestly</h4>
      <ul>
        <li>Yields are names for real figures (see <i>Yields</i>). Job counts are where people <i>work</i>.</li>
        <li>Statistics published for municipalities are never shown as if measured per hex: hex population is an estimate
        that spreads each municipality's official total over its 1 km population grid.</li>
        <li>Missing data stays missing (–, "no data"), never 0. Lower bounds are marked ≥, estimates ≈.</li>
        <li>Wonders and resources are selected by published rules, never by taste.</li>
      </ul>
      <h4>Controls</h4>
      <p>Drag or arrow keys / WASD to pan · scroll, +/– or double-click to zoom · click a hex or banner to open its municipality,
      a region chip to open the region · / or ⌘K to search · L to cycle lenses · R to show or hide resources · ? for all shortcuts.</p>
      <p class="muted">Built on the open-source engine of Andrej Karpathy's <a href="https://karpathy.ai/usaciv/" target="_blank" rel="noopener">usaciv</a>
      (MIT licence); the Scandinavian data pipeline, panels and advisors are new.</p>`,
    Yields: () => `
      ${h2("y-production", "⚙️", "Yields")}
      <p>Civilization's yields mapped onto real measures. Job-based yields count <i>jobs at the place of work</i> (November /
      4th quarter 2024: SSB table 07984, SCB TAB3204, DST RAS501), grouped into ${Object.keys(data.nation.industries || {}).length}
      industry groups that all three agencies publish (NACE Rev. 2 sections, with Denmark's NACE Rev. 2.1 data mapped back).</p>
      <table>${data.nation.yields.map((y) => `<tr><td class="ic" style="color:${esc(y.color)}">${glyph(y, 26)}</td><td><b style="color:${esc(y.color)}">${esc(y.label)}</b> = <i>${esc(y.measure || "")}</i><br>${esc(y.description)}</td></tr>`).join("")}</table>
      <p><b>What yields are not.</b> Five yields count employment. Agricultural jobs are not food production, industrial jobs
      are not industrial output, knowledge-sector jobs are not research output, culture jobs are not cultural value, and
      welfare jobs are not the quality or accessibility of welfare services. Workplace jobs are not the number of employed
      residents: commuters count where they work.</p>
      <h4>Gold: economic output</h4>
      <p>${esc(data.nation.gdp_label || "")}</p>
      <p>${esc(data.nation.gdp_allocation || "")} The method assumes equal output per job within an industry in a region; for a
      municipality the value is an estimate (≈), never an official statistic. Output is counted where people work, so a
      municipality that draws commuters shows high output per resident.</p>
      <p>${esc(data.nation.extra_regio?.note || "")}</p>
      ${sensitivityHtml(data.nation)}
      <h4>Specialisation (city types)</h4>
      <p>A municipality's type is its industry group with the highest <b>location quotient</b> — its share of local jobs ÷ the
      share in Norway, Sweden and Denmark combined — of at least ${data.nation.lq_rule?.min_lq} with at least ${data.nation.lq_rule?.min_jobs}
      jobs. Several groups can qualify; the panel lists them all. Sweden publishes mining together with manufacturing, so a
      Swedish mining town reads as "Industrial"; its mines appear as resources.</p>
      <h4>Suppressed values</h4>
      <p>Statistics Norway suppresses very small cells for confidentiality, and from 2025 Statistics Sweden adds small random
      noise to protect individuals. A yield with a suppressed component is shown as a lower bound (≥). Because the
      municipality's total jobs are published, the suppressed cells can add at most the unallocated remainder: the panel
      and CSV give that upper bound, and where it makes the order uncertain a rank is shown as an interval (#10–14).
      National figures for Norway come from SSB's national table, which has no suppression.</p>
      <h4>Ranks</h4>
      <p>${esc(data.nation.ranking || "")} The interval uses only each area's own published bounds; the bounds do not use the
      agencies' disclosure thresholds or national totals, so the true range can be narrower. "Rank uncertain" means the
      interval covers at least half of the areas (for example Oslo's agriculture jobs, which are suppressed).</p>
      <h4>Location quotients</h4>
      <p>A location quotient (×) compares an industry's share of local jobs with its share in the three countries combined;
      ×2 means twice as concentrated. It measures relative concentration only — not output, productivity, the largest
      industry or strategic importance — and small municipalities can reach high quotients with few jobs, so a
      specialisation needs at least ${data.nation.lq_rule?.min_jobs} jobs. The municipality panel shows the largest industry
      and the strongest specialisation side by side.</p>`,
    Regions: () => `
      ${h2("terrain", "🗺️", "Regions")}
      <p>Regions are Norway's 15 counties (fylker, 2024), Sweden's 21 counties (län) and Denmark's 5 regions. Their figures
      are sums of their municipalities. Ranks ("#3 of 41") compare all 41 regions; 1 is the largest.</p>
      <p>Regional GDP is published for Norwegian counties (on the 2020–2023 county map, as value added at basic prices),
      Swedish län and Danish landsdele (NUTS 3). It is converted to euro at Eurostat's ${data.nation.gdp_vintage?.match(/\d{4}/)?.[0] || ""}
      average exchange rates (NOK ${data.nation.fx?.NOK?.toFixed?.(3)}, SEK ${data.nation.fx?.SEK?.toFixed?.(3)}, DKK ${data.nation.fx?.DKK?.toFixed?.(3)} per euro)
      and, for per-person comparisons, to purchasing power standards with Eurostat GDP PPPs.</p>`,
    Methodology: () => `
      ${h2("pedia", "📖", "Methodology")}
      <h4>Pipeline</h4>
      <p>A reproducible Python pipeline downloads every source (with a manifest of URL, SHA-256, size and retrieval date),
      turns each into tidy interim data, and builds the files this page loads. The same commands rebuild the world when a
      source updates; the browser never calls an external API.</p>
      <h4>Harmonisation</h4>
      <ul>
        <li><b>Boundaries</b>: municipalities as of 2024–2026 (Norway's 357, Sweden's 290, Denmark's 98). Norway's series use
        SSB's aggregated series for today's municipalities. Where SSB could not reconstruct a municipality (it publishes 0),
        the years are shown as not available, never as zero population; where a municipality's series describes a
        different territory (Ålesund 2020–23 included Haram) or a part of a divided municipality moved (SSB's classification
        131), the years before the change are marked as another territory. Growth, rankings, the Timeline and exports only
        compare years on the same territory. Sweden and Denmark had no municipal reforms in the period.</li>
        <li><b>Totals over time</b>: Scandinavia and each country use the agencies' own national series, not sums of
        today's municipalities (which miss the residents of municipalities that cannot be reconstructed). Norwegian counties
        use SSB's county series where it exists, else the sum of comparable municipalities, else "not available".</li>
        <li><b>Reference dates</b>: population 1 January 2026 (Sweden's 31 December 2025 is the same moment); jobs November/Q4 2024
        in all three; GDP 2023; land cover 2018.</li>
        <li><b>Industries</b>: NACE sections grouped to the finest common level (L–N and R–U are joint groups because SSB and SCB
        publish them together).</li>
        <li><b>Currencies</b>: national currency → euro at Eurostat annual averages; PPS via Eurostat GDP PPPs.</li>
        <li><b>Income</b>: the three agencies publish different concepts (${esc(Object.values(data.nation.income_definitions || {}).join("; "))}),
        so income is shown only relative to the country's own figure for the same statistic. Values are nominal, not
        adjusted for prices or purchasing power; read them within one country.</li>
      </ul>
      <h4>Spatial allocation</h4>
      <p>Every 1 km grid cell is assigned to the municipality polygon containing its centre (cells in the coastal fringe
      outside simplified polygons go to the nearest municipality). A hex belongs to the municipality holding most of its land
      cells. Hex population = Σ municipality population × that municipality's share of GEOSTAT 2018 grid population falling in
      the hex; the sum over hexes equals the official total.</p>
      <h4>Geography: hexes, polygons and the landscape</h4>
      <p>Hexes are the unit of terrain statistics (93.5 km² each). Municipalities are drawn, selected and coloured from their
      own polygons (Kartverket, Valmyndigheten, DAGI), so a small municipality such as Frederiksberg, Solna or Utsira has
      its own territory even where it owns no hex. Municipal lenses colour polygons; hex lenses colour hexes.</p>
      <p>The landscape is one continuous image painted from the 1 km grids: CORINE land cover for colour, EU-DEM for a
      multidirectional hillshade (vertical exaggeration ×3), Copernicus tree-cover density for forest tone, and the municipal
      polygons for the Norwegian and Danish coast. Below 1 km it only interpolates; the fine grain that appears close in is
      texture, not data. Mountain pieces stand only on summits: hexes whose highest 1 km cell is above 1,000 m and higher
      than all six neighbours.</p>
      <h4>Validation</h4>
      <p><code>python -m pipeline check --mode built|source|release</code>. <i>built</i> checks the shipped files on their own;
      <i>source</i> reconciles them with the original downloads read independently (for example: for every year 2008–2026,
      Norway's municipalities plus SSB's "divided municipalities" bucket equal the national total) and verifies every
      cached download against its SHA-256 and request; <i>release</i> also requires the browser journeys to have passed on
      the same data files. A skipped check never counts as passed.</p>`,
    Terrain: () => {
      const t = data.w?.tables || resolveTables(data.world.tables);
      const hasCover = Array.isArray(data.world.cover);
      const row = (x) => `<tr><td class="nm">${x.color ? `<span class="swatch" style="background:${esc(x.color)}"></span>` : ""}${
        COVER_ICON[x.key] ? icon(COVER_ICON[x.key], "", { size: 15 }) + " " : ""}<b>${esc(x.name)}</b></td><td>${esc(x.rule || "")}</td></tr>`;
      return `
      ${h2("terrain", "🗺️", "Terrain")}
      <p>Each hex averages the EU-DEM 1 km cells inside it. Relief comes from the mean, maximum and roughness (standard
      deviation) of those cells; shading comes from elevation differences with neighbouring hexes, lit from the north-west.
      ${esc(data.world.tables?.notes?.water || "")}</p>
      <h4>${icon("l-forest", "🌲", { size: 16 })} Land cover</h4>
      ${hasCover
        ? `<p>The base colour of each hex is its dominant land-cover group: the largest group among the land samples inside it.
           Small symbols show the mix: trees scale with the forest share, and fields, reeds, shrubs and grass tufts mark farmland,
           wetland, scrub and grassland.</p>
           <table>${t.cover.filter((x) => x.id > 0).map(row).join("")}</table>`
        : `<p class="muted">This data build has no land-cover layer yet; land is coloured by elevation.</p>`}
      <h4>Relief</h4>
      <table>${t.relief.map(row).join("")}</table>
      <h4>${icon("r-hydro", "💧", { size: 16 })} Water</h4>
      <table>${t.water.filter((x) => x.id > 0).map(row).join("")}</table>
      <h4>Beyond the borders</h4>
      <p class="muted">Finland, Russia, Germany, Poland and the Baltic coast are drawn under a light fog for context and
      not mapped in detail (Finland, Iceland, the Faroes, Åland, Greenland and Svalbard are planned extensions).</p>`;
    },
    Lenses: () => `
      ${h2("layers", "▤", "Lenses")}
      <p>Lenses recolour the map by one measure (${esc(data.lenses.vintage)}). Each lens states its resolution: <b>hex</b>
      lenses aggregate the 1 km cells inside the hex; <b>municipality</b> and <b>region</b> lenses repeat one published value
      on every hex of the area; <b>derived</b> lenses are estimates (population spread over the 1 km grid). Grey means no data,
      which is never the same as zero.</p>
      <p>The legend shows how many hexes fall at each value. Hover or drag on it to show only that range on the map.</p>
      ${(data.lenses.groups || [{ id: null, name: "" }]).map((g) => {
        const ls = data.lenses.lenses.filter((l) => !g.id || l.group === g.id);
        if (!ls.length) return "";
        return `${g.name ? `<h3 class="grp">${icon(`g-${g.id}`, "", { size: 16 })} ${esc(g.name)}</h3>` : ""}${ls.map((l) => `
          <div class="lens-entry"><div class="le-ic">${glyph(l, 26)}</div><div>
          <h4>${esc(l.name)}</h4><p>${esc(l.description)}<br>
          <i class="le-ramp" style="background:linear-gradient(90deg, ${(l.ramp || []).map(esc).join(",")})"></i>
          <span class="muted">Scale: ${esc(l.scale)}, ${l.domain[0].toLocaleString()}–${l.domain[1].toLocaleString()} ${esc(l.unit)}${
            l.higher_is === "good" ? " · higher is better" : l.higher_is === "bad" ? " · higher is worse" : ""}${l.source ? " · " + esc(srcName(l.source)) : ""}</span></p></div></div>`).join("")}`;
      }).join("")}`,
    Resources: () => {
      const r = data.resources;
      if (!r?.types?.length) return `${h2("resources", "⛏️", "Resources")}<p class="muted">This data build has no resources layer.</p>`;
      const count = new Map();
      for (const it of r.items || []) count.set(it.type, (count.get(it.type) || 0) + 1);
      const cats = [...new Set(r.types.map((t) => t.category || "other"))];
      return `
      ${h2("resources", "⛏️", "Resources")}
      <p>Resources mark Scandinavia's power plants, oil &amp; gas fields and mines on the tiles where they are. Power plants
      show installed capacity (MW), never generation; fields show saleable production; mines show SGU's status.
      Only meaningful sites are shown: each type's threshold is in its description. When zoomed out, a hex shows its
      highest-ranked resource; zoom in to see more. Press <b>R</b> to show or hide them.</p>
      ${cats.map((c) => `<h4>${esc(CATEGORY[c] || c)}</h4><table class="res-table">
        <tr><th></th><th>Type</th><th>What counts</th><th>Sites</th></tr>
        ${r.types.filter((t) => (t.category || "other") === c).map((t) => `<tr>
          <td class="ic"><span class="res-ic" style="background:${esc(t.color || "#24384f")};color:${inkOn(t.color)}">${glyph(t, 20)}</span></td>
          <td class="nm"><b>${esc(t.name)}</b>${t.unit ? `<br><span class="muted">value in ${esc(t.unit)}</span>` : ""}</td>
          <td>${esc(t.description || "")}<br><span class="muted">Source: ${esc(srcName(t.source))}</span></td>
          <td class="num">${count.get(t.id) || 0}</td></tr>`).join("")}</table>`).join("")}`;
    },
    Wonders: () => {
      const wd = window.__app?.data?.wonders;
      if (!wd) return `${h2("w-landmark", "🏛️", "Wonders")}<p class="muted">Loading…</p>`;
      return `${h2("w-landmark", "🏛️", "Wonders")}
      <p>Wonders are landmarks chosen by published rules:</p>
      ${wd.rules.map((r) => `<h4>${esc(r.id.replace("_", " "))}</h4><p>${esc(r.text)}</p>
        <p class="muted">${wd.wonders.filter((x) => x.rule === r.id).map((x) => esc(x.name)).join(" · ")}</p>`).join("")}`;
    },
    Limitations: () => `
      ${h2("pedia", "📖", "Limitations")}
      <ul>
        <li>Finland, Iceland, Åland, the Faroes, Greenland and Svalbard are not yet mapped (the pipeline is built to add them).</li>
        <li>Norwegian mines (NGU), Danish North Sea fields, fisheries and aquaculture, wind turbines below 50 MW, electricity
        <i>generation</i> by plant, freight flows, hazards and climate are not yet included: their open services were not
        reachable from the build environment or need more work. Nothing is filled in their place.</li>
        <li>Roads, railways and ferries are Natural Earth 1:10m map art (generalised and incomplete), not a network model.</li>
        <li>GDP below the region level is an estimate (regional GDP × share of jobs). Norway's regional figures are value added
        at basic prices and exclude the continental shelf.</li>
        <li>University wonders use Wikidata student counts; some large universities have none recorded (the rule includes
        old universities without counts, but Wikidata typing can still miss an institution, e.g. the University of Copenhagen).</li>
        <li>CORINE assigns one class per 1 km cell, so small fields, towns and lakes can vanish into their surroundings; fjords
        narrower than a hex read as coast.</li>
      </ul>`,
    Sources: () => `
      ${h2("pedia", "📖", "Sources")}
      ${data.sources.map((s) => `
        <h4>${esc(s.title)}</h4>
        <p>${esc(s.description)}<br>
        <span class="muted">${esc(s.publisher)} · ${esc(s.license)}${s.vintage ? " · " + esc(s.vintage) : ""} ·
        <a href="${esc(s.homepage)}" target="_blank" rel="noopener">homepage</a></span></p>
        <p class="muted">${s.file_count || 0} file(s), ${((s.bytes || 0) / 1e6).toFixed(1)} MB${(s.files || []).some((f) => f.via === "browser-relay") ? " · some retrieved through a browser relay (same URLs; see README)" : ""}</p>
        <table>${(s.files || []).map((f) => `<tr><td><code>${esc(f.url)}</code></td><td class="muted" style="white-space:nowrap">${esc((f.retrieved || "").slice(0, 10))}<br>${((f.bytes || 0) / 1e6).toFixed(1)} MB</td></tr>`).join("")}</table>`).join("")}`,
  };

  const show = (name) => {
    if (!pages[name]) name = "About this map";
    body.innerHTML = pages[name]();
    body.scrollTop = 0;
    nav.querySelectorAll("button").forEach((b) => {
      const on = b.dataset.page === name;
      b.classList.toggle("active", on);
      b.setAttribute("aria-current", on ? "page" : "false");
    });
  };
  nav.innerHTML = `<div class="hd">Almanac</div>` + Object.keys(pages).map((p) => `<button data-page="${esc(p)}">${esc(p)}</button>`).join("");
  nav.onclick = (e) => {
    const b = e.target.closest("button[data-page]");
    if (b) show(b.dataset.page);
  };
  const close = () => {
    if (modal.hidden) return;
    modal.hidden = true;
    if (restoreFocus && document.contains(restoreFocus)) restoreFocus.focus();
    restoreFocus = null;
  };
  modal.onclick = (e) => {
    if (e.target === modal || e.target.closest("[data-close]")) close();
  };
  // Keep Tab inside the dialog.
  modal.addEventListener("keydown", (e) => {
    if (e.key !== "Tab") return;
    const f = [...card.querySelectorAll("button, a[href], [tabindex]:not([tabindex='-1'])")].filter((x) => x.offsetParent);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  return {
    open(page = "About this map") {
      if (modal.hidden) restoreFocus = document.activeElement;
      show(page);
      modal.hidden = false;
      (nav.querySelector("button.active") || card.querySelector("[data-close]"))?.focus();
    },
    close,
    get isOpen() {
      return !modal.hidden;
    },
  };
}

// How much municipal output estimates move under alternative allocation keys (computed in the build).
function sensitivityHtml(n) {
  const rows = (n.gdp_sensitivity || []).filter((r) => r.country === "all");
  if (!rows.length) return "";
  const p = (x) => `${(x * 100).toFixed(1)}%`;
  return `<p><b>How sensitive are the estimates?</b> The regional totals are fixed; only the split between municipalities
    depends on the method. Compared with the method used here, for the ${rows[0].n} municipalities:</p>
    <table class="small"><tr><th>Alternative key</th><th>median change</th><th>95th percentile</th><th>&gt; 5%</th><th>largest</th></tr>
    ${rows.map((r) => `<tr><td>${esc(r.alternative)}</td><td>${p(r.median_abs)}</td><td>${p(r.p95_abs)}</td><td>${r.over_5pct}</td><td>${p(r.max)} (${esc(r.max_name)})</td></tr>`).join("")}</table>
    <p class="muted small">Large differences under "total jobs only" are expected: that key gives every job in a region the same output.
    Real estate follows residents because its value added is mostly the rent of dwellings, owner-occupied ones included.</p>`;
}
