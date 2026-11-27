# Methodology and indicator definitions

## Geography

| Item | Definition |
|---|---|
| Projection | Lambert azimuthal equal-area, centre 63°N 15°E, GRS80, km (`pipeline/core/geo.py`). Equal-area so every hex is 93.5 km²; centred on Scandinavia so the North Cape is not sheared as in EPSG:3035. |
| Grid | Pointy-top hexes, radius 6 km (10.4 km across the flats), odd-r offset layout; 40,828 cells (173 × 236), 9,005 Scandinavian land hexes. |
| Land / water | CORINE Land Cover 2018 on the 1 km grid: land = classes 1–39. A hex is land when land covers ≥ 42% of its area, or ≥ 30% with ≥ 4 land neighbours (narrow sounds, skerries). Lake when inland water classes (511/512) outweigh sea. |
| Sea depth | Natural Earth bathymetry polygons (200, 1000, 2000, 3000 m): depth *classes*, not soundings. Coast = next to land or shallower than 200 m. |
| Relief | From the ~94 EU-DEM 1 km cells: peaks = highest cell ≥ 1,600 m and std ≥ 180 m; mountains = std ≥ 150 m or mean ≥ 850 m; hills = std ≥ 55 m. |
| Land cover | Largest CORINE group among the hex's land cells; urban and glacier win at ≥ 30%. `pct.*` shares are whole percent of land cells. |
| Municipality of a hex | Every 1 km cell goes to the municipality polygon containing its centre (cells in the coastal fringe of the simplified polygons, but inside the national border, go to the nearest polygon). The hex takes the municipality with most land cells. |
| Hex population (derived) | Σ over municipalities of official population × (that municipality's GEOSTAT 2018 grid population in the hex ÷ its total grid population); land-cell weights where a municipality has no grid population. Exact municipal totals; the split within a municipality is an estimate. |

## Statistics and harmonisation

| Item | Norway | Sweden | Denmark |
|---|---|---|---|
| Population (1 Jan 2008–2026) | SSB 07459, aggregated series for 2024 municipalities | SCB TAB628 (31 Dec of previous year) | DST FOLK1A (1st quarter) |
| Age 0–19 / 20–64 / 65+ | SSB 07459 grouping | SCB TAB5557, 5-year groups summed | DST FOLK1A single years summed |
| Land area | SSB 09280 (land) | SCB TAB628 | DST ARE207 (total area) |
| Jobs by place of work, 2024 | SSB 07984 (Q4, 15–74) | SCB TAB3204 (Nov, 15–74, BAS) | DST RAS501 (end Nov, DB25) |
| Income (experimental) | 06944 median household income after tax | TAB4840 median net income 20+ | INDKP101 average disposable income |
| Regional GDP 2023 | 09391 GVA basic prices, 2020–23 counties; shelf extra-regio | TAB3138 GRDP by län | NRHP GDP by landsdel |

**Industry groups.** NACE Rev. 2 sections grouped to the finest level all three publish: A · B–C · D–E · F · G · H · I
· J · K · L–N · O · P · Q · R–U · unknown. Denmark's DB25 (NACE Rev. 2.1) codes are mapped back (2.1 L→K, M/N/O→L–N,
P→O, Q→P, R86–88→Q, S/T/U→R–U, K61–63→J). Finer detail where published (Norway and Denmark: B mining incl. oil & gas).

**Currencies.** Euro at Eurostat annual average rates 2023 (ert_bil_eur_a); PPS via Eurostat GDP PPPs (prc_ppp_ind).

**Suppression and noise.** SSB suppresses small cells (shown as part of "unknown", the group marked ≥). From 2025 SCB adds
small random noise (cell key method), so Swedish parts may not sum exactly.

## Yields

| Yield | Real-world measure | Unit | Resolution |
|---|---|---|---|
| Food | jobs in A | jobs | municipality |
| Production | jobs in B, C, F | jobs | municipality |
| Gold | GDP 2023 (Norway: GVA), € | euro | region; municipality = estimate (region × share of jobs) |
| Science | jobs in J and L–N | jobs | municipality |
| Culture | jobs in R–U | jobs | municipality |
| Welfare | jobs in P and Q | jobs | municipality |

**Specialisation.** Location quotient LQ = (jobs in group / all jobs)ₘ ÷ (same share for NO+SE+DK). Listed when LQ ≥ 1.5
and ≥ 250 jobs; city type = the highest such LQ, else "Diversified".

## Lenses

| Lens | Definition | Resolution |
|---|---|---|
| Population density | hex population (2026) ÷ hex area | derived |
| Population change 2016–26 | municipal | municipality |
| Aged 65+, aged 0–19 | share of residents 2026 | municipality |
| GDP per person (PPS) | regional GDP 2023 ÷ average 2023 population, PPS | region |
| Jobs per 100 residents | jobs at place of work 2024 ÷ population 2026 × 100 | municipality |
| Industry / primary / ICT / tourism / public admin jobs | share of municipal jobs in B–C, A, J, I, O | municipality |
| Specialisation | city type (categorical) | municipality |
| Income vs national | income ÷ national figure of the same statistic (experimental) | municipality |
| Time to hospital / primary school | GISCO 1 km road travel time, population-weighted over the hex | hex |
| Reachable population | people reachable within 90 min by road (EC road performance grid), population-weighted | hex |
| Distance to a large town | straight line to the nearest municipality of 50,000+ | hex |
| Elevation, tree cover, farmland, land cover | EU-DEM, Copernicus TCD 2018, CORINE 2018 | hex |
| New built-up land 1990–2018 | 1 km cells that became artificial in CORINE | hex |

## Advisors

Observations are deterministic templates filled from the loaded data (ranks, shares, correlations, sums), each with its
source. Resilience is shown as separate indicators (growth, ageing, jobs ratio, employment concentration HHI,
largest-industry share, isolation) — deliberately not a composite score.

## Validation (`python -m pipeline check`)

Hex population vs municipal totals (rounding only); municipal sums vs national tables (≤ 0.05%; Christiansø and SCB noise
explain the residuals); jobs vs national totals (≤ 1%); 745 municipalities on 2024 boundaries; banners on land and within
25 km of reference coordinates for 12 cities; null-not-zero for missing growth; every lens has a source, unit and
resolution; every source has a licence and files. Current report: `docs/CHECK_REPORT.txt`.
