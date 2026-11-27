# NordicCiv v0.2 — requirements and evidence ledger

Working ledger for the consolidation release. Status: ✅ done and verified · 🟡 done, verification pending · ⏳ open ·
➖ out of scope. "Evidence" names the check, test or file that verifies the item.

| ID | Requirement | Status | Implementation | Evidence |
|---|---|---|---|---|
| NC-T01 | Historical population observation integrity | ✅ | `pipeline/build/history.py` (R1 source-zero, R2 absorbed unit, R3 KLASS split); cities carry `pop_terr`, `pop_status`, `pop_breaks` | check `history:*`; source check "Σ municipalities + SSB divided bucket = national, every year" |
| NC-T02 | National/regional historical series, comparable cohorts | 🟡 | published national series (SSB/SCB/DST); counties from SSB 07459 agg_Fylker2024 or complete member sums with coverage | check `history: Scandinavia 2008/2016/2026`; Timeline UI pending |
| NC-T03 | Validation modes, independent reconciliation | ✅ | `pipeline/check.py` built / source / release | `docs/CHECK_REPORT_*.txt` |
| NC-T04 | Municipal geometry separate from hex ownership | 🟡 | `munis.json`, `borders.json`, polygon hit-testing, selection outline, municipal choropleth in Analyze mode | check `geometry:*`; browser test pending |
| NC-T05 | Municipality leaderboards (metro filter) | ⏳ | | |
| NC-T06 | Suppression propagation | 🟡 | `yields_hi`, `jobs_unallocated`, `rank_range` | check `suppression:*`; UI pending |
| NC-T07 | Economic comparability and estimation | 🟡 | `gva.py` sector-weighted allocation; `gdp_components`, `gdp_label`, `gdp_concept` | check `economy:*`; UI labels pending |
| NC-T08 | Income terminology | 🟡 | lens renamed "Income relative to national reference", neutral direction; `income_definitions` | UI pending |
| NC-T09 | Advisor interpretations | ⏳ | | |
| NC-T10 | Cache integrity | ✅ | `fetch.verify` (size, SHA-256, request fingerprint), `verify-cache` CLI | check `cache: 1003/1003` |
| NC-T11 | Accessibility and responsive controls | ⏳ | | |
| NC-T12 | Portable browser tests, CI | ⏳ | | |
| NC-T13 | Repeated registry invocation | ✅ | `_extra_sources()` | unit test pending |
| NC-V01 | Coastline rendering | 🟡 | relief raster coast (polygons NO/DK, CORINE elsewhere), coast lines, 1 km blocks disabled under relief | visual states 05/06/11/12 |
| NC-V02 | Terrain continuity and relief | 🟡 | multidirectional hillshade, summit-only mountain pieces | visual states 01/05 |
| NC-V03 | Integrated landscape art | 🟡 | painted CORINE palette, thinned clumps, close-zoom grain | visual states |
| NC-V04 | Rendering fluidity | ⏳ | | |
| NC-V05 | Extended geographic detail | 🟡 | L1 0.5 km tiles lazily loaded | |
| NC-F01/F02 | More countries / simulation | ➖ | | |

## Decisions
- R4 (paired opposite changes) rejected: flagged ordinary demographic changes in Sweden (no reforms there).
- Municipal output: sector-weighted keys keep each region's published total exactly (reconciled to €0.1 m).
- Relief image instead of a WebGL migration: one image draw per static render; hexes remain the statistical unit.
