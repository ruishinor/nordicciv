# NordicCiv — requirements and evidence ledger

Status: ✅ done and verified · 🟡 done, verification pending or partial · ⏳ open · ➖ out of scope. "Evidence" names the
check, test or file that verifies the item. v0.4 items first; the v0.3 and v0.2 tables follow unchanged.

## v0.4 — civil preparedness: public shelters

| ID | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| NC-S01 | Investigate references: DSB map, Beredskap101, dataset, WFS, guidance (schema, CRS, updates, licence) | ✅ | WFS 2.0 `app:Tilfluktsrom` (lokalId, romnr, plasser, adresse, posisjon; EPSG:4258 default), NLOD 1.0, updated "as needed" (data.norge.no modified 2026-11-25; extraction 2026-11-27); Beredskap101 repo read (static snapshot, no acquisition code) | METHODOLOGY "Civil preparedness"; SOURCES v0.4 |
| NC-S02 | Official public shelters in the pipeline and source registry, with provenance | ✅ | `pipeline/sources/shelters.py` (`dsb_shelters`), `pipeline/build/shelters.py` → `web/data/shelters.json`; manifest with URL, SHA-256, retrieval | checks `shelters:*`, `source: every shelter record … equals the cached WFS answer`; unit `ParseTest` |
| NC-S03 | Public only; nothing inferred; missing ≠ zero | ✅ | only the public dataset; null for an unstated capacity, 0 kept as 0; SE/DK `not_integrated` | unit `ParseTest`, `test_lens_bands`; check coverage |
| NC-S04 | Coordinate transformation validated; records never moved | ✅ | PROJ EPSG:4258 → map LAEA; grouping instead of displacement | check round-trip (worst 0.7 m); unit `test_positions_are_the_published_ones`; journey 22 (singles exactly at their position, no overlaps) |
| NC-S05 | Municipal association from the existing polygons | ✅ | point in polygon; 4 shore records to the nearest outline (19–110 m, kept); > 1.5 km fails the build | unit `test_municipality_contains_record_or_is_nearest_within_limit`; check |
| NC-S06 | Original, native symbol | 🟡 (visual judgement; no user test) | shield with arched doorway in the site style (ink outline, gold rim, top-left light, ground shadow); group = stacked shield + count tab; Map-menu icon `c-shelter` | `docs/visual/v04/` (states 25–31) |
| NC-S07 | Scale-dependent rendering | ✅ | county → municipality → record tiers; greedy grouping + merge pass; off by default | journey 22 |
| NC-S08 | Card, Society tab, Council, Almanac | ✅ | card (places, municipality, room, id, meaning, emergency note, DSB links, source); Society section (count, places, largest, full keyboard list, show on map, caveats); Resilience advisor notes; Almanac page | journeys 23–25 |
| NC-S09 | Analytical view without scores or coverage ratios | ✅ | lens `shelter_places` (5 bands, "not a preparedness score", SE/DK no data, "none" its own class) | journey 25; check lens |
| NC-S10 | Sweden and Denmark investigated | ✅ (not integrated) | coverage reasons in data, card, panel, Council, Almanac | METHODOLOGY |
| NC-S11 | Responsible information | ✅ | emergency note on card, section, Almanac; no availability, readiness or vulnerability claims | journeys 23–25 |
| NC-S12 | Performance with layer on/off | 🟡 | static layer in the cached map; per-zoom item cache | `docs/perf/v03_v04_desktop.json`, VERIFICATION |
| NC-S13 | Mobile | ✅ | card as a bottom sheet above the nav | journey 26; state 31 |
| NC-S14 | Existing behaviour preserved | ✅ | journeys 0–21 unchanged and passing; states 01–24 pixel-compared with v0.3 (≤ 0.08% JPEG noise, except the type badge contrast fix) | VERIFICATION |

## v0.3

| ID | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| NC-R01 | One ranking convention: exact ranks, ties, intervals, filtered populations, unavailable values | ✅ | `pipeline/build/ranking.py` (competition ranks, possible-rank intervals); `web/js/stats.js` `competitionRanks`, `rankIntervals`, `rankList`; leaderboards rank within the listed population; "of N" = areas with a value (`nation.rank_of`) | audit reproduced (157 of 2,969 inconsistent) → 0; check `ranking:*` (independent re-derivation); unit `RankingConventionTest` (6 hand cases + brute-force attainability + JS parity); journey 13 |
| NC-R02 | Suppression remainder compatible with totals and classification | ✅ | remainder = total − published groups, ≥ 0, only with a suppressed group, bounds only yields containing one; SE tolerance from SCB's disclosure method | check `suppression: remainders …` |
| NC-R03 | Source reconciliation by status (metadata cannot excuse mismatches) | ✅ | observed = equal and non-zero; boundary = source 0; missing = source empty | source check; mutation test (mismatch labelled "boundary" → FAIL) |
| NC-A01 | Release evidence bound to the exact candidate | ✅ | `pipeline/candidate.py` (app, data, tests, pipeline by SHA-256); journey 0 verifies every served file in the browser; unit and browser evidence carry the candidate id; evidence deleted at start, written only on completion; all mandatory journey ids required | gate mutation tests (stale, missing, skipped, interrupted, data-hash-only → FAIL) |
| NC-A02 | Staged package promotion | ✅ | `pipeline/release.py`: dist/.staging → gates → package → verify → promote to dist/release (previous → dist/previous); failures moved to dist/.failed | release run (VERIFICATION) |
| NC-A03 | Test correctness | ✅ | journey 18 OR → AND (then fixed the case-sensitive label comparison it exposed); 16 asserts the panel closes; 13 asserts rank labels; 7 asserts advisor count; summary baseline no longer auto-created | journeys 0–21 |
| NC-E01 | Output key: real estate vs business services | ✅ | M–N keyed by M–N jobs (SE, DK); NO 69–75 by 68–75 jobs (approximation), 77–82 by 77–82 | audit reproduced (28 SE/DK > 1%, max 6.25% Fanø); unit test |
| NC-E02 | Missing-denominator fallback | ✅ | shared by total jobs, reported in `nation.gdp_fallbacks` (Oslo NOK 45 m, A) | unit test; check `economy:*` |
| NC-E03 | Sensitivity comparison | ✅ | `nation.gdp_sensitivity`, Almanac table | METHODOLOGY |
| NC-H01 | KLASS 2026 Indre Østfold / Nordre Follo / Vestby | ✅ | sources show two small areas; series comparable; `pop_adjustments` notes; SSB's own table notes shown for 28 more | METHODOLOGY |
| NC-V06 | World identity: connected ranges, illustrated vegetation, agriculture, transitions, sharpness, settlements, light, depth | 🟡 (visual judgement; no user test yet) | two-scale shading and crests; painterly light; illustration layer through 1 km class masks (7 classes); built-up rooftops; no glyph sprites over the relief; SDF lakes; sea shadow; Nordic mask fix | `docs/visual/` before/after (24 states); journeys 0–21 |
| NC-X01 | "What stands out" + related municipalities, industries, history, lenses | ✅ | `web/js/explore.js`; panel section with definitions, map links, ranking neighbours | journey 21 |
| NC-X02 | Discover (surprising, supported facts) | ✅ | 18 computed facts, each flies to the place and colours the map | journey 21 |
| NC-X03 | Concise contextual onboarding | ✅ | three-line first-run hint under all panels, dismissed by use | journey 21 (incl. axe) |
| NC-P01 | Performance and memory, before/after | 🟡 (measured; illustrated redraws slower on software rendering) | chunked mask decoding in idle time; patterns pre-painted; perf script with runs, median/p95/worst, redraw tour, close pan | `docs/perf/` |
| NC-U01 | Real-user test | ⏳ | `docs/USER_TEST_SCRIPT.md` | not run (no participants) |

## v0.2

| ID | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| NC-T01 | Historical population observation integrity | ✅ | `pipeline/build/history.py` (R1 source-zero, R2 absorbed unit, R3 KLASS split); `pop_terr`, `pop_status`, `pop_breaks`, `pop_review` | check `history:*`; unit `HistoryClassificationTest`; journey 10 |
| NC-T02 | National/regional series, comparable cohorts, Timeline | ✅ | published national series; county series or complete member sums with coverage; `web/js/stats.js` comparability used by Timeline, lenses, panels, reports, Explorer, CSV | source check "Σ + divided bucket = national, every year"; journey 9 |
| NC-T03 | Validation modes, independent reconciliation | ✅ | `pipeline/check.py` built / source / release; skipped ≠ passed | `docs/CHECK_REPORT*.txt` |
| NC-T04 | Municipal geometry separate from hex ownership | ✅ | `munis.json`, `borders.json`, polygon hit-testing, outline, municipal choropleths (`muni_values`) | check `geometry:*`; journey 6 (Frederiksberg click) |
| NC-T05 | Municipality leaderboards | ✅ | explicit municipality ids replace the `metro` filter; deterministic ties; ≥ and ≈ ranks | journey 13 |
| NC-T06 | Suppression propagation | ✅ | `yields_hi`, `jobs_unallocated`, `rank_range`; ≥ in tiles, HUD, reports, Compare, CSV status columns | check `suppression:*`; unit tests; journey 11 |
| NC-T07 | Economic comparability and estimation | ✅ | `gva.py` sector-weighted keys; `gdp_label`, `gdp_components`, `gdp_concept`; HUD "Σ … combined regional output" | check `economy:*`; unit `SectorAllocationTest` |
| NC-T08 | Income terminology | ✅ | "Income relative to national reference", neutral ramp, definitions per country | panel, lens, Almanac |
| NC-T09 | Advisor interpretations | ✅ | correlation wording, computed ratios, commuting from employed residents, no causal or labour-market claims, absence ≠ evidence of absence | journey 7 (pattern scan) |
| NC-T10 | Cache integrity | ✅ | `fetch.verify` (size, SHA-256, request fingerprint); offline refuses unusable cache; atomic writes | check `cache: 1003/1003`; unit `CacheIntegrityTest` |
| NC-T11 | Accessibility and responsive controls | ✅ (automated + keyboard) | tabs with ARIA, labelled mobile nav, CSP-safe, reduced motion, touch targets | journeys 16–18; axe 0 violations; screen-reader test not done |
| NC-T12 | Portable browser tests, CI | ✅ (CI not executed remotely) | Playwright Chromium / `$NORDICCIV_CHROME` / platform paths; results file bound to data hash; `.github/workflows/validate.yml` | `tests/results/browser.json` |
| NC-T13 | Repeated registry invocation | ✅ | `_extra_sources()` | unit `RegistryTest` |
| NC-V01 | Coastline rendering | ✅ | polygon coast (NO, DK), smoothed CORINE elsewhere, bathymetry sea, coast lines; 1 km blocks off under relief | visual 06, 11, 12 |
| NC-V02 | Terrain continuity and relief | ✅ | multidirectional hillshade; summit-only mountain pieces | visual 01, 02, 05 |
| NC-V03 | Integrated landscape art | ✅ | CORINE palette, tree-cover tone, thinned clumps, close-zoom grain, Analyze mode over gray relief | visual 01–12 |
| NC-V04 | Rendering fluidity | ✅ | one image draw per static render; measured | `docs/perf/` (zoom p95 233 → 50 ms) |
| NC-V05 | Extended geographic detail | ✅ (to 0.5 km) | L1 tiles on demand; data finer than 1 km only in polygons | journey 19 |
| NC-F01/F02 | More countries / simulation | ➖ | out of scope for this release | |

## Decisions
- R4 (paired opposite changes) rejected: flagged ordinary demographic changes in Sweden (no reforms there).
- Municipal output: sector-weighted keys keep each region's published total exactly (reconciled to €0.1 m).
- Relief image instead of a WebGL migration: one image draw per static render; hexes remain the statistical unit.
