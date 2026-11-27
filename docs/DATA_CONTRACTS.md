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
