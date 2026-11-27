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

## Population history and territorial comparability (v0.2)

Municipal series are published on today's boundaries where the agency can sum former units (SSB codelist
`agg_KommSummer`; Sweden and Denmark had no municipal reforms in 2008–2026). `pipeline/build/history.py` classifies every
municipality-year from evidence:

- **R1 source zero.** SSB publishes 0 persons for a code it cannot reconstruct (Narvik, Hábmer–Hamarøy, Orkland, Heim,
  Hitra 2008–2019; Haram 2020–2023 — 64 municipality-years). These become `null` with status "boundary".
- **R2 absorbed unit.** Where a municipality's R1 block is matched (±10 %) by jumps of another municipality's series at
  both ends, that municipality describes a larger territory in those years (Ålesund 2020–23 includes Haram).
- **R3 divided municipality.** SSB's classification 131 records old units split between new ones; a receiving
  municipality whose change in that year departs from the national change by more than 1.5 points gets a break
  (Tønsberg and Sandefjord, 2017, part of Stokke).

Two years are comparable only when both are observed on the same territory code. Growth, rankings, the Timeline, the
map's change lens and exports all use that rule (`web/js/stats.js`). Remaining one-year changes above 6 % are shown as
cautions, not altered. Independent check: for every year 2008–2026, Norway's municipalities plus SSB's "divided
municipalities and unknown" bucket equal SSB's national total exactly.

**Totals.** Scandinavia and each country use the agencies' national series (SSB 07459 country, SCB TAB628 "00", DST
FOLK1A "000"): 19,395,889 (2008), 20,772,253 (2016), 22,258,532 (2026); +7.16 % 2016–26 (Norway +7.93 %). Norwegian
counties use SSB 07459 on the 2024 counties where the county existed; otherwise the sum of member municipalities if all
are comparable (transfers wholly inside the county do not break the sum); otherwise "not available" with coverage.

## Suppression (v0.2)

A Norwegian industry group with suppressed components is a lower bound. Because each municipality's total jobs is
published unsuppressed, the suppressed cells together add at most the unallocated remainder, which gives an upper bound
(`yields_hi`). Ranks become intervals `[best, worst]`: best = 1 + number of municipalities whose lower bound exceeds this
upper bound; worst = 1 + number whose upper bound exceeds this lower bound. National Norwegian yields come from SSB's
national table (no suppression), so the overview bar is exact.

## Economic output (v0.2)

Regional totals are kept as published (Norway GVA at basic prices by 2020–23 county, excluding the continental shelf;
Sweden GRDP at market prices by län; Denmark GDP by landsdel; euro at Eurostat 2023 average rates). Municipal estimates
share each total by a sector-weighted key: Σ industry value added × the municipality's share of the region's jobs in
that industry (SSB 11713; Eurostat nama_10r_3gva A*10), real estate (incl. imputed rents) by residents, value added the
agency suppresses by total jobs. Σ municipal estimates = published regional totals (to €0.1 m). The Scandinavian sum is
labelled "combined regional output (mixed concepts, not harmonised GDP)".

## Geography layers (v0.2)

- **Hexes** (6 km radius) remain the unit of terrain statistics and hex lenses.
- **Municipal polygons** (`munis.json`, three simplification levels) carry selection, hit-testing (even–odd, so enclaves
  such as Frederiksberg work), the selected outline, municipal borders and municipal choropleths (`lenses[].muni_values`).
- **Borders** (`borders.json`) are polygon boundaries minus the coastline (land union incl. Natural Earth Finland,
  Russia, Germany), so only real land borders are stroked.
- **Relief** (`relief/`): a continuous image in the map frame — CORINE colour, Copernicus tree-cover tone,
  multidirectional EU-DEM hillshade (×3), high-alpine tint above an elevation falling from ~1,500 m at 60° N to ~800 m at
  70° N, lakes painted in; coast from municipal polygons in Norway and Denmark and smoothed 1 km cells elsewhere; sea from
  Natural Earth bathymetry bands. Mountain pieces stand only on summit hexes (highest 1 km cell ≥ 1,000 m and above all
  six neighbours). Analyze mode multiplies lens colours by a gray hillshade, clipped to land.

## Validation (`python -m pipeline check --mode built|source|release`)

Modes: **built** (shipped files only), **source** (independent reconciliation with the original downloads and cache
verification), **release** (also browser journeys on the same data hash and accepted key totals). A skipped check is
never a pass. See docs/VERIFICATION.md for the results of this release.


Hex population vs municipal totals (rounding only); municipal sums vs national tables (≤ 0.05%; Christiansø and SCB noise
explain the residuals); jobs vs national totals (≤ 1%); 745 municipalities on 2024 boundaries; banners on land and within
25 km of reference coordinates for 12 cities; null-not-zero for missing growth; every lens has a source, unit and
resolution; every source has a licence and files. Current report: `docs/CHECK_REPORT.txt`.
