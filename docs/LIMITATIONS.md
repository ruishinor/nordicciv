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

- Roads, railways and ferries are Natural Earth 1:10m line work: generalised and incomplete, drawn as map art.
- Regional GDP: Norway publishes value added at basic prices on the 2020–23 counties; Sweden and Denmark publish GDP.
  Cross-country Gold comparisons understate Norway by roughly the size of product taxes, and exclude the continental
  shelf. Municipal GDP is an estimate assuming equal output per job within a region.
- Income uses three different national statistics and is shown only relative to each country's level (experimental).
- University wonders rely on Wikidata types and student counts; the University of Copenhagen was not returned by the
  typed query at retrieval and is therefore missing; several institutions have no recorded count.
- The GEOSTAT 2021 grid in the tiled mirror over-counted Norway by ~12% against SSB's total, so the 2018 grid is used
  only as spatial weights; Denmark's 2018 grid under-counts by ~5% — irrelevant for weights within municipalities.
- CORINE assigns one class per 1 km cell: small fields, villages and lakes disappear into their surroundings; fjords
  narrower than a hex read as coast; Bornholm and small islands are represented by the hexes that pass the land rule.
- Five Norwegian municipalities created by splits in 2024 have no 2016 population and no growth value.
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
