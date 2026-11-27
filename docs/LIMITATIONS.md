# Limitations, unavailable data and decisions

## Not (yet) included — nothing is substituted in their place

- **Geographies:** Finland, Iceland, Åland, the Faroes, Greenland, Svalbard. The pipeline is built for them (country
  registry, frame, sources per publisher); Finland needs Statistics Finland tables and municipal boundaries.
- **Norwegian mines** (NGU mineral resources service was not reachable from the build environment), **Danish North Sea
  fields** (no open field-level dataset found), **fisheries landings and aquaculture** (Fiskeridirektoratet), **wind
  turbines below 50 MW**, **electricity generation per plant** (only installed capacity per plant; national generation by
  source from Eurostat), **freight flows**, **natural hazards** (NVE, MSB, Beredskabsstyrelsen), **climate normals**,
  **housing prices**, **education attainment** and **healthcare provider locations**.
- **Cross-border commuting** (e.g. Øresund): no harmonised municipal flow table was integrated; the Council says so.

## Civil preparedness: public shelters (v0.4)

- **Norway only, public shelters only.** Private shelters (most of Norway's ~2.5 million places, per DSB) are not
  published and not shown. Sweden and Denmark: not integrated (missing coverage, not zero; see METHODOLOGY).
- **Registered places are not availability.** Nothing in the register says whether a shelter is open, ready, inspected
  or accessible; the app says so on every card and section.
- **Snapshot.** Extracted 2026-11-27. Shelters added, removed or moved since are not reflected until the source is
  fetched again (the Beredskap101 snapshot from mid-2026 already differs by one removed room and one moved position).
- **Simplified boundaries.** Four records are assigned to the nearest municipality outline (≤ 110 m).
- **Not an emergency service.** The app is educational. In an emergency, follow current instructions from the
  authorities; DSB's own map is linked from every card.

## Camera uplinks (v0.5)

- **A reviewed selection, not a census.** 196 cameras (Norway 80, Sweden 108, Denmark 8). Many public webcams exist
  that are not here: road and traffic cameras by policy; others because no provider listing with a stable page and a
  position was found, or they were not reviewed yet. A municipality with no uplink is not one without cameras.
- **Denmark is thin.** Few intentionally public landscape webcams with stable pages were found; five of eight are
  weather-station cameras.
- **Listed is not live.** Cameras go offline, move or change what they show; the app never claims a camera works, and a
  page check (2026-11-27) concerns the page, not the stream. Checks older than 120 days drop the camera at the next build.
- **Positions.** Published positions are the providers' (a few owners round theirs); 21 page-only cameras stand at the
  place they show, not at the camera. Ten coastal cameras are assigned to the nearest municipality outline (≤ 882 m).
- **The provider's page is a third-party site** with its own cookies, advertising and terms; NordicCiv sends no
  referrer and opens it in a separate tab, but cannot vouch for it.

## Opening screen and Open in Maps (v0.5)

- **Progress is only as fine as the server allows.** Byte progress needs `Content-Length` without compression; behind a
  compressing server the line counts whole files (seven) and is indeterminate until every file has started.
- **"Open in Maps" hands over to Google.** Google's pages have their own cookies, consent screens and terms (in Norway a
  consent page comes first, then the requested view). NordicCiv sends a position and a zoom only, no referrer, and
  cannot control what Google shows. Only Google Maps is offered so far.
- **Positions are only as good as the data.** Ports are placed at their town, 21 camera uplinks at the place they show,
  and settlement points are the EuroGeographics name positions; zoom levels are chosen so the place is in view, not to
  frame any particular building.

## Known caveats

- **Below 1 km the landscape only interpolates.** The relief image is painted from 1 km CORINE, EU-DEM and tree-cover
  cells; class boundaries are blended over about one cell and wobbled by a fixed noise field, and the grain seen close
  in is texture. The illustrations (trees, fields, scree, mire, heath, rooftops) show the class of each square kilometre,
  never a real tree, field or building; crop and roof colours are illustrative. Very close in (≥ 15 px per km) the base
  image is visibly soft between illustrated areas. Coasts are finer only where polygons exist (Norway and Denmark); Swedish and Finnish shores, including
  the Stockholm archipelago, follow 1 km cells and merge small skerries into larger shapes.
- **Swedish municipal polygons** are a simplified Valmyndigheten file that, in archipelagos, includes water (Vaxholm's
  polygon is ~2× its land area). They are used for selection, borders and choropleths, not for areas or the coast.
- **Unrecorded boundary adjustments.** Breaks are recorded only from evidence: SSB's zeros, the absorbed-unit
  arithmetic and SSB's classification of divided municipalities. Twelve municipalities show a one-year change above 6 %
  with no recorded change (e.g. Stad +6.3 % in 2020, which may be the transfer of Bryggja); their panels say so and the
  validation report lists them, but their growth figures are not suppressed.
- **Regional population before 2018 for Trøndelag** is not available: SSB has no county series before the county existed
  and three of its municipalities cannot be reconstructed for those years (coverage of today's population: 94 %).
- **Municipal economic output** is still an estimate: sector-weighted allocation assumes equal output per job within an
  industry and region, uses 2023 industry value added (SSB 11713 for Norway, Eurostat nama_10r_3gva for Sweden and
  Denmark) and counts output where people work.
- **Suppressed cells (Norway).** 310 municipalities have at least one industry group with suppressed components; values
  are lower bounds with an upper bound from the unallocated total, and 745 municipalities have at least one rank
  interval rather than an exact rank. Most of these intervals are one place wide and come from a single municipality:
  Oslo's agriculture, forestry and fishing jobs are suppressed with a remainder of 4,372 jobs that could, as far as the
  published table shows, all be in that group. The bounds deliberately ignore national totals (see Methodology).
- **Norway's output key for professional services** uses NACE 68–75 jobs, which include real estate; SSB publishes no
  finer municipal split. Sweden and Denmark use M–N jobs only.
- **Rendering cost of the illustrations.** Without a GPU (software rendering) a settled redraw in an illustrated view
  takes about twice as long as in v0.2 (≈ 180 ms instead of ≈ 95 ms close in); the map drops to reduced detail, and on
  very slow machines turns the illustrations off for the session. `?detail=off` turns them off; `?detail=full` keeps
  them. GPU machines were not measured.
- **Discovery facts** are single extremes under a stated filter; small municipalities dominate ratios, so most facts use
  a 5,000-resident threshold. They describe, they do not explain.
- Roads, railways and ferries are Natural Earth 1:10m line work: generalised and incomplete, drawn as map art.
- Regional output: Norway publishes value added at basic prices on the 2020–23 counties; Sweden and Denmark publish GDP.
  The Scandinavian total (€1,225.6 bn) is therefore labelled "combined regional output, not harmonised GDP"; Norway is
  understated by roughly product taxes and excludes the continental shelf (€104.1 bn, shown separately).
- Income uses three different national statistics (median household income after tax; median net income 20+; average
  disposable income) and is shown only relative to each country's own figure, nominal, without price or PPP adjustment.
- University wonders rely on Wikidata types and student counts; the University of Copenhagen was not returned by the
  typed query at retrieval and is therefore missing; several institutions have no recorded count.
- The GEOSTAT 2021 grid in the tiled mirror over-counted Norway by ~12% against SSB's total, so the 2018 grid is used
  only as spatial weights; Denmark's 2018 grid under-counts by ~5% — irrelevant for weights within municipalities.
- CORINE assigns one class per 1 km cell: small fields, villages and lakes disappear into their surroundings; fjords
  narrower than a hex read as coast; Bornholm and small islands are represented by the hexes that pass the land rule.
- Seven Norwegian municipalities have no comparable 2016–26 growth figure (Narvik, Hábmer–Hamarøy, Orkland, Heim and
  Hitra: not reconstructable before 2020; Tønsberg and Sandefjord: part of Stokke moved in 2017).
- Swedish municipal boundaries come from a simplified (2%) Valmyndigheten file; they assign 1 km cells correctly away
  from borders, approximately along them.

## Decisions log

1. **Reuse usaciv's engine** (MIT): renderer, terrain art, banners, lenses UI and Almanac framework were adapted; US
   extensions (City View, US advisors, military, trade) were removed. Data pipeline written new.
2. **Municipality = city.** It is the unit of local government and of all three agencies' statistics, so yields are
   measured, not apportioned (except Gold).
3. **Jobs at place of work, reference November/Q4 2024** in all three countries (the latest year all three publish).
4. **Equal-area projection centred on Scandinavia** instead of EPSG:3035, so the north is neither enlarged nor sheared.
5. **Hex radius 6 km** (93.5 km² hexes): fine enough for fjord coasts and municipal shapes, ~41k cells for smooth Canvas.
6. **Dasymetric hex population** with the 2018 grid as weights (see above), preserving official municipal totals.
7. **Wonders by rule only** (UNESCO, park area, university size/age, fixed-link length); no hand-picked list.
8. **Relay for blocked hosts:** statistics APIs were fetched through a browser relay with the identical URLs; manifests
   record it. A normal machine downloads directly.
9. **No composite resilience score**; separate indicators instead.
10. **Lens values packed** to Scandinavian land hexes only (the browser expands them) to keep downloads small.
11. **Population history (v0.2).** Source zeros are "not available", never 0; comparisons only within one territory;
    national and county totals from published series. A heuristic for unrecorded boundary adjustments (paired opposite
    changes) was tried and rejected because it also flagged ordinary demographic changes in Sweden.
12. **Continuous relief instead of a new renderer (v0.2).** The landscape is one pre-painted image (two levels, tiles
    loaded on demand) inside the existing Canvas 2D renderer. Measured zoom p95 frame time fell from 233 to 50 ms;
    WebGL/MapLibre migration was not justified by the measurements.
13. **Municipal polygons beside the hexes (v0.2).** Hexes stay the statistical unit for terrain lenses; municipal lenses,
    selection, borders and hit-testing use the polygons, so municipalities that own no hex are fully represented.
14. **Sector-weighted output allocation (v0.2)** replaces the plain job share; regional totals are unchanged.
15. **One ranking convention (v0.3)**: competition ranks, possible-rank intervals from each area's own bounds; national
    totals are not used to narrow suppressed cells.
16. **World style inside Canvas 2D (v0.3).** Illustrations are drawn through 1 km class masks with one reusable layer per
    class; no WebGL migration (measurements in docs/VERIFICATION.md). Per-hex terrain sprites remain only in the hex-tile
    fallback, so the World view has no rows of isolated sprites. A separate "Atlas" or "Strategic" style was not added:
    the analysis view (any lens over the gray relief) is the legible alternative, and a third style would double the
    visual baselines to maintain.
17. **Indre Østfold 2026** stays comparable (two small areas, no visible effect), with the adjustment noted.
18. **Release candidates** are identified by content hash and verified in a staging folder before promotion; the last
    known-good release stays in `dist/release/` until then (previous release kept in `dist/previous/`).

19. **Public shelters (v0.4) as an optional infrastructure layer, not a workspace.** One Map-menu switch (off by default),
    a card, a Society-tab section, Council notes under Resilience, an Almanac page and one lens; no new top-bar button,
    no score. Grouping instead of displacement, so no symbol stands anywhere a record is not.
20. **Camera uplinks (v0.5) as links, not a viewer.** One Map-menu switch (off by default), a card whose one link to the camera is "Open uplink" (plus "Open in Maps"),
    a short Overview section where a municipality has uplinks, Discover entries and an Almanac page; no media panel,
    monitoring workspace or new top-level navigation. Road and traffic cameras excluded on principle. Reviewed include
    lists instead of whole provider catalogues, so a provider's new cameras never appear unreviewed. OSIRIS studied,
    nothing imported (licence of its generated lists unclear, positions unreliable).
21. **Opening screen and Open in Maps (v0.5) kept small.** The opening screen borrows OSIRIS's
    structure (identity, emblem, version, progress line, changing status, automatic hand-over) in NordicCiv's own art,
    bound to the real start-up with no minimum duration. "Open in Maps" is a link in the existing inspectors (municipality
    and region panels, the site list, the camera card) rather than a navigation tool; Google Maps first because its
    cross-platform URLs need no key and open the app on phones. Two behaviours (unmarked view / pin) chosen per kind of
    place; no links for energy, military or shelter sites.
