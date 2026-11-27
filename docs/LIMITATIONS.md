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

## Known caveats

- **Below 1 km the landscape only interpolates.** The relief image is painted from 1 km CORINE, EU-DEM and tree-cover
  cells; class boundaries are blended over about one cell and wobbled by a fixed noise field, and the grain seen close
  in is texture. Coasts are finer only where polygons exist (Norway and Denmark); Swedish and Finnish shores, including
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
  interval rather than an exact rank (the interval can be wide, e.g. Oslo's farm/fish jobs).
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
