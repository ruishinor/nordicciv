# Data contracts (web/data)

All files are plain JSON written by `python -m pipeline build`. Missing values are `null` (never 0). Map coordinates are
km in the Nordic LAEA frame described in `world.json.projection` (x right, y down).

| File | Shape (main keys) |
|---|---|
| `world.json` | `grid {radius, cols, rows}`, `width`, `height`, `projection {proj4, x0_km, y1_km}`; per-cell arrays: `owner` (−1 water, −2 foreign land, ≥0 index into `states`), `county` (index into `counties` = municipalities, −1 none), `elev` (m; water: depth class), `elev_max`, `water` (0 land, 1 ocean, 2 coast, 3 lake), `relief` (0–3), `cover` (id in `tables.cover`), `pct {forest, crop, pasture, grass, shrub, wetland, developed, heath, bare, ice}` (% of land cells), `tcd` (% tree cover), `pop` / `pop_2016` (dasymetric estimates); `tables {water, relief, cover, notes}`, `states` (regions: `{fips, abbr, name, short, country}`), `countries`, `counties` (`{geoid, name, region}`), `rivers [{name, rank, pts}]`, `lakes`, `seas`. |
| `cities.json` | one record per municipality, sorted by banner prominence: `id` (NO-0301…), `name`, `full`, `country`, `states [region id]`, `capital`, `place`/`anchor` (main settlement and how it was found), `x`, `y`, `lon`, `lat`, `cell`, `population`, `pop_series {year: n}`, `growth`, `growth_years`, `land_km2`, `density`, `age`, `share_65plus`, `share_0_19`, `jobs {group: n}`, `jobs_detail`, `jobs_partial`, `jobs_total`, `jobs_per_100`, `yields {food, production, gold, science, culture, welfare}`, `yields_partial`, `yields_estimated`, `gdp`, `gdp_year`, `gdp_region(_name)`, `income`, `income_currency`, `income_index`, `lq`, `specialisations [{group, lq, jobs, label, partial}]`, `type {label, color, group, rule}`, `footprint [cells]`, `regional_centre`, `prominence`, `nearest_bigger_km`, `ranks`, `peers`. |
| `states.json` | one per region (same order as `world.states`): sums of its municipalities plus `land` cover shares, `hexes`, `ranks`. |
| `nation.json` | `nation` (Scandinavian totals), `countries {NO, SE, DK}`, `yields` (definitions), `industries`, `lq_rule`, `extra_regio`, `fx`, `ppp`, `electricity`, `banner_floors`, vintages. |
| `lenses.json` | `groups`, `lenses [{id, group, name, unit, format, scale, domain, ramp, higher_is, source, resolution, description, note, categories?, values}]`; `packed: "owned"` → `values[k]` belongs to the k-th cell with `owner ≥ 0`. |
| `resources.json` | `types [{id, name, category, unit, source, description}]`, `items [{type, name, x, y, cell, value, detail, country, state, cbsa (municipality id)}]`, `summary`. |
| `infrastructure.json` | `roads [[a, b, class, name]]`, `rail [[a, b, tier]]` (hex links), `ferries [{name, pts, seasonal}]`, `ports [...]`, `airports [...]`, `rules`, `vintage`. |
| `wonders.json` | `rules [{id, kind, text}]`, `wonders [{id, name, kind, category, rule, rank, motif, metrics, x, y, cell, county, state}]`. |
| `sources.json` | the source registry with licence, publisher, description and every downloaded file (URL, SHA-256, bytes, retrieval time, via). |
| `climate.json` | WMO `period` and `archive_version`, source and licence, `stations [{id, country, name, lat, lon, elevation_m, temperature_c[12], precipitation_mm[12], annual_temperature_c, annual_precipitation_mm, temperature_years[13], precipitation_years[13], source_url, sha256, retrieved}]`. Year counts follow Jan–Dec and then annual. Each value belongs to one station. |

### Climate stations

The 48 station CSVs come from [WMO submissions in NOAA NCEI archive 0253808, version 6.6](https://www.ncei.noaa.gov/data/oceans/archive/arc0216/0253808/6.6/data/0-data/Region-6-WMO-Normals-9120/). The [archive record lists CC0 1.0](https://catalog.data.gov/dataset/wmo-climatological-standard-normals-for-1991-2020-ncei-accession-0253808). The app credits MET Norway, SMHI and DMI at each station. Temperature is parameter 5 (mean, °C) and precipitation is parameter 1 (monthly or annual total, mm). Annual values come from the annual field. Counts below 24 years hide the corresponding figure, and a blank count stays unknown.

Place profiles choose the closest sampled station in the same country within 100 km for each measurement. Distances start at the mapped settlement. Region panels use the largest municipality as a named reference. The map shows station locations.

To update this dataset alone, run `python -m pipeline fetch climate_normals`, `python -m pipeline process climate_normals --strict`, then `python -m pipeline build climate`.

## Added in v0.2

| File / field | Meaning |
|---|---|
| `cities[].pop_series` | population by year; `null` = not available (never 0) |
| `cities[].pop_terr` | territory code per year: `0` = today's boundaries, `k > 0` = another territory described in `pop_terr_notes[k]`, `null` = no value. Two years are comparable only with equal, non-null codes. |
| `cities[].pop_status` | years that are not plain observations: `"boundary"` (agency could not reconstruct), `"missing"` |
| `cities[].pop_breaks` | `[{rule R1/R2/R3, kind, years, related, terr, note, source}]` — the source and rule for each boundary break |
| `cities[].pop_review` | unexplained one-year changes above 6 % (`[{years, change}]`), shown as a caution |
| `cities[].growth`, `growth_note` | 2016–26 change on one territory, else `null` with the reason |
| `cities[].yields_hi`, `jobs_unallocated` | upper bounds for lower-bound yields; jobs in suppressed cells |
| `cities[].rank_range` | `{yield: [best, worst]}` where suppression makes the exact rank uncertain |
| `cities[].gdp_method`, `gdp_concept`, `gdp_jobshare` | `"sector"` or `"jobs"`; the regional accounting concept; the plain job-share alternative |
| `states[].pop_basis`, `pop_coverage` | per year `"published"` / `"sum"` / `null`, and the share of today's population that could be summed where not available |
| `nation.{nation,countries}.pop_series_source`, `population_published`, `yields_published` | agency national series and exact national yields |
| `nation.gdp_label`, `gdp_components`, `gdp_allocation`, `income_definitions` | what the economic figures are |
| `lenses[].muni_values` | one value per municipality id for municipal/regional lenses (polygon colouring) |
| `munis.json` | municipal polygons: `scale` (km per unit), `levels` (simplification, km), `features [{id, bbox, area_km2, label, rings, r1, r2}]`, rings delta-encoded |
| `borders.json` | internal borders without coastline: `country`, `region`, `municipality` line lists (delta-encoded) |
| `coast.json` | shore lines traced from the relief land mask |
| `relief/index.json` | relief image levels (`L0` 1 km whole image, `L1` 0.5 km tiles), `gray` (Analyze), `sea`, `hex_fallback` (land hexes with no 1 km data), `sha256` |

## Added in v0.5

| Field | Meaning |
|---|---|
| `uplinks.json → cameras[]` | `{id (provider prefix + provider key, stable), name (NordicCiv's short name), cat, provider, provider_name? (operator pages), url (https viewing page on the provider's host), lat, lon (WGS 84 as listed), x, y (map km), cell, muni, country, pos ("published" / "place"), place? {qid, label}, verified (page-check date), assigned? {method, distance_m}}` — nothing else: no stream, image or token fields (checked) |
| `uplinks.json → categories`, `providers` | category labels; provider name, home page and note |
| `uplinks.json → policy`, `meaning`, `sources` | inclusion/exclusion rules, position and duplicate rules, no-live-claim wording, page-check meaning, absence caveat; raw listing URLs with retrieval time and SHA-256; attribution; the OSIRIS reference note |
| `version.json` | `{version}`: the repository's `VERSION`, for the opening screen (`pipeline/build/version.py`; `check` fails if they differ) |
| `uplinks.json → munis{}`, `totals`, `left_out_unverified` | per municipality `n` and camera `ids`; totals by country, category and provider, place positions, nearest-outline assignments; cameras left out for a failed or stale page check |

## Added in v0.4

| File / field | Meaning |
|---|---|
| `shelters.json → source` | authority, dataset, licence (NLOD 1.0) and attribution, WFS request, DSB extraction date, retrieval time, SHA-256, `number_matched` |
| `shelters.json → coverage` | `{NO: integrated, SE/DK: not_integrated + reason}`: missing coverage is never zero |
| `shelters.json → meaning`, `rules` | the wording for capacity, public vs private, absence, residents; municipality and position rules |
| `shelters.json → shelters[]` | `{id (DSB lokalId), room, places (int ≥ 0, or null = not stated), address (as published), lat, lon (ETRS89), x, y (map km), cell, muni, assigned?: {method, distance_m}}` |
| `shelters.json → munis{}`, `regions{}` | per municipality / county: `n`, `places`, `zero`, `missing`, `anchor` (mean of members' true positions, for group symbols only) |
| `shelters.json → totals` | `shelters`, `places`, `munis_with`, `munis_no`, `assigned_nearest` |
| `lenses.json → shelter_places` | category lens, municipality resolution: 0 = no public shelter in the register, 1–4 = registered-place bands; SE/DK null |

## Changed or added in v0.3

| File / field | Meaning |
|---|---|
| `cities[].ranks`, `states[].ranks` | competition ranks (1 = largest, equal values share a rank) among the areas with a value (was: sorted position) |
| `cities[].rank_range`, `states[].rank_range` | possible-rank interval `[best, worst]` for the published bounds, only where `best ≠ worst`; always contains `ranks` |
| `states[].yields_hi`, `nation.*.yields_hi` | upper bounds summed from the members (members are independent) |
| `nation.rank_of` | `{municipalities: {key: n}, regions: {key: n}}` — the size of each comparison population ("of N") |
| `nation.ranking` | the ranking convention in one sentence (shown in the Almanac) |
| `cities[].jobs_detail.L`, `["68-75"]`, `["77-82"]` | real-estate jobs (SE, DK) and Norway's two L–N divisions, used by the output key |
| `cities[].pop_adjustments` | recorded boundary adjustments that are not breaks, and the agency's own table notes: `[{year, change, national, note, sources}]` |
| `nation.gdp_fallbacks` | per region, value added shared by total jobs because no municipality has a job in that industry (`value_added` in the source unit, `share_of_region`) |
| `nation.gdp_sensitivity` | per alternative key and country: `n`, `over_1pct`, `over_5pct`, `median_abs`, `p95_abs`, `max`, `max_name` |
| `relief/cover/{A,B,C}_{x}_{y}.webp`, `relief/index.json → cover` | 1 km land-cover masks for the illustration layer, 16 levels, three per image: A conifer, broadleaf, farmland; B rock, mire, heath; C built-up |

## Historical CORINE land cover

`lenses.json.land_history` contains the paired observation years (1990, 2018), pinned upstream revision, tile paths, Git blob IDs and SHA-256 hashes. `paired_cells` and each group's `gain` / `loss` arrays use the existing owned-hex packing. Forest classes are 23–25, agricultural classes 12–22. Net change is gain minus loss, null where no cell has both observations. Counts are 1 km cell classes, not polygon-based municipal areas. The builder checks all existing urban-growth values before writing new layers.
