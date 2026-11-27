# NordicCiv v0.2 — requirements and evidence ledger

Working ledger for the consolidation release. Status: ✅ done and verified · 🟡 done, verification pending · ⏳ open ·
➖ out of scope. "Evidence" names the check, test or file that verifies the item.

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
