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

## Suppression and ranks (v0.2, convention fixed in v0.3)

A Norwegian industry group with suppressed components is a lower bound. Because each municipality's total jobs is
published unsuppressed, the suppressed cells together add at most the unallocated remainder (total − published groups),
which gives an upper bound (`yields_hi`) for each yield that contains a suppressed group. Sweden publishes no suppressed
cells, but SCB's disclosure method means its totals need not equal the sum of components (≤ 1% here); Denmark's add up.

**One ranking convention** (`pipeline/build/ranking.py`, mirrored in `web/js/stats.js`, both tested against
`tests/fixtures/ranking_cases.json`):
- *comparison population*: the areas being ranked (all municipalities, all regions, or a filtered list such as one
  country or "5,000+ residents") that have a value; unavailable values are never ranked and never counted in "of N";
- *exact rank*: competition ranking, 1 = largest, rank = 1 + number of areas with a larger value, so equal values share
  a rank; lists show tied areas by name, then id;
- *possible-rank interval* where values are lower bounds: best = 1 + #(others' lower bound > this upper bound), worst =
  1 + #(others' upper bound > this lower bound). It is exact for the stated bounds (both ends are reachable, checked by
  brute force in the tests) and always contains the rank of the published figures. The bounds themselves are
  conservative: they ignore the agencies' disclosure thresholds and the national totals the suppressed cells must add up
  to — using those would come close to re-identifying cells the agency chose to suppress — so the true range can be
  narrower. An interval covering at least half the areas is shown as "rank uncertain".

v0.2 mixed two conventions (exact ranks by sorted position with ties broken by population; intervals by strict
inequalities), which left 157 of 2,969 published intervals not containing their own rank.

## Economic output (v0.2; classification and fallback corrected in v0.3)

Regional totals are kept as published (Norway GVA at basic prices by 2020–23 county, excluding the continental shelf;
Sweden GRDP at market prices by län; Denmark GDP by landsdel; euro at Eurostat 2023 average rates). Municipal estimates
share each total by a sector-weighted key: Σ industry value added × the municipality's share of the region's jobs in
that industry (SSB 11713; Eurostat nama_10r_3gva A*10), real estate (incl. imputed rents) by residents, value added the
agency does not break down by total jobs. Σ municipal estimates = published regional totals (to €0.1 m). The
Scandinavian sum is labelled "combined regional output (mixed concepts, not harmonised GDP)".

- *Classification (v0.3)*: professional and business services (M–N) are keyed by M–N jobs only. v0.2 keyed them by the
  combined L–N group although real estate (L) is already allocated by residents. Sweden (SCB L and M+N) and Denmark
  (DB25 section M = real estate) publish real-estate jobs separately, so they are removed. Norway's municipal table joins
  real estate with professional services (NACE 68–75): there M (69–75) is keyed by 68–75 jobs — an approximation — and
  N (77–82) by 77–82 jobs. Effect against v0.2: 28 Swedish and Danish estimates move by more than 1% (largest Fanø,
  −6.25%), 10 Norwegian ones (largest Tydal, −3.9%); every regional total is unchanged.
- *Missing denominator (v0.3)*: value added in an industry where no municipality of the region has a mapped job is
  shared by total jobs and reported in `nation.gdp_fallbacks` (only Oslo: NOK 45 m of agriculture, forestry and fishing,
  0.005% of Oslo's value added, whose NACE A jobs are suppressed). It is never dropped.
- *Sensitivity* (`nation.gdp_sensitivity`, shown in the Almanac): median / 95th-percentile / largest change of the 745
  estimates under alternative keys — v0.2 classification 0.15% / 1.0% / 6.7%; real estate by jobs instead of residents
  1.6% / 8.6% / 20%; total jobs only (no industry weighting) 5.6% / 27% / 78%.

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
  six neighbours (v0.2; v0.3 replaces the pieces with the illustration layer, below). Analyze mode multiplies lens
  colours by a gray hillshade, clipped to land.

## Boundary adjustments that are not breaks (v0.3)

SSB's classification (KLASS 131) records a 1 January 2026 adjustment from Indre Østfold to Nordre Follo and Vestby. The
decisions describe two small areas (about 565 decares with eight property units by Slemmestadveien; the Loska cabin
area, about 17 cabins). SSB's table 07459 counts each year on that year's boundaries (its own notes document earlier
small transfers as not harmonised) and has no note for 2026; the three 2025→26 changes (+1.0%, +1.1%, +1.6%) are close to
each municipality's previous year. The years stay comparable; each municipality carries a note (`pop_adjustments`) with
the sources, and SSB's own table notes are shown for 28 other municipalities. Change size alone never creates or removes
a break.

## World style and illustrations (v0.3)

The relief adds shading at the scale of ranges (2 km) to the detail shading and lifts crests, so ranges read as
connected masses; one north-west light (as the buildings) with warm highlights and blue-violet shadows; snow on crests
above a latitude-dependent line; slow illustrative crop tones on farmland. Lakes are smoothed from a signed distance
field with the same total area as before (13,900 vs 12,800 km² painted on land). The three countries are recognised from
Natural Earth (the 1 km grid's country code is empty for most unpopulated cells, which in v0.2 muted much of the
Scandinavian mountains as if they were foreign land). Closer in, the browser paints trees, fields, scree, mire, heath
and rooftops through 1 km CORINE class masks: they show what covers each square kilometre, not where any tree, field or
house is. The analysis view (any lens) shows no illustrations.

## Discovery (v0.3)

"What stands out" lists a municipality's figures in the top or bottom 5% of the municipalities that have them (growth,
density, 65+ share, jobs per 100 residents, distance to a larger municipality for places under 50,000, land area) and a
strongest specialisation from ×2.5, each with its value, rank, definition and its neighbours in that ranking.
"Discover" shows one of 18 facts computed the same way (single extremes, with the population filter in the sentence).

## Validation (`python -m pipeline check --mode built|source|release`)

Modes: **built** (shipped files only), **source** (independent reconciliation with the original downloads, values
checked by status, and cache verification), **release** (also unit and browser evidence for this exact candidate — app,
data, assets, tests and pipeline by SHA-256 — with every mandatory journey passing, and accepted key totals). A skipped,
missing or stale check is never a pass. See docs/VERIFICATION.md for the results of this release.


Hex population vs municipal totals (rounding only); municipal sums vs national tables (≤ 0.05%; Christiansø and SCB noise
explain the residuals); jobs vs national totals (≤ 1%); 745 municipalities on 2024 boundaries; banners on land and within
25 km of reference coordinates for 12 cities; null-not-zero for missing growth; every lens has a source, unit and
resolution; every source has a licence and files. Current report: `docs/CHECK_REPORT.txt`.
