# Living world recovery — 2026-11-28

Recovery checkpoint only. Development was interrupted by a usage limit; the owner subsequently requested preservation and a stop. No feature completion or release readiness is claimed. Do not resume without a new instruction.

## Git and preserved work

- Recovery branch: `recovery/living-connected-world-2026-11-28`.
- Original development branch: `codex/living-connected-world`. Accepted baseline inspected: `ea7e6f300a81f018f4511c9d7cfb722b2ddfd7c7` (v0.5.0).
- Before interruption, development fast-forwarded to `d028d1a62371c6a2ad40938d8c8d1015834ef16a`, the existing completed opening/maps branch from PR #3. That integration predates recovery; nothing was merged during recovery. PR #3 was open at last inspection. PR #2 contains separate language cleanup; preserve it. Neither PR was merged by this session.
- Main checkout is `work/nordicciv` relative to the chat workspace. All three agents shared it; no separate agent worktrees. `work/baseline` is a clean detached worktree at `ea7e6f3`. An older clean local repository, `NordicCiv-Repository`, was inspected at `0faba82` and left untouched.
- Three untracked files recovered unchanged: `web/js/util/solar.js`, `pipeline/sources/connections.py`, `pipeline/sources/climate.py`. These are unfinished, unregistered, untested modules. No production dataset was generated or modified; no UI extension, builder, or new test was completed.
- `docs/recovery/2026-11-28/research/` contains the metadata-fetch script and six downloaded public table metadata responses. The script originally wrote to a sibling `connection_research` directory; it is preserved as research, not an integrated pipeline command.
- `docs/recovery/2026-11-28/baseline/` contains 39 screenshots and timing JSON from the unchanged baseline. `baseline-perf.json` contains one completed baseline laboratory run (1440×900, unthrottled, Chromium 159). These captures have not been visually reviewed; there is no after/before comparison. They do not validate the new modules.
- Local originals remain under `work/connection_research`, `work/evidence`; the isolated Python 3.12 environment remains under `work/venv`. Virtual environment and bytecode are intentionally not committed.

## Decisions and source leads

Astronomy: dependency-free NOAA/Meeus equations; sunrise threshold −0.833°, twilight −6/−12/−18°; IANA local-day boundaries and explicit repeated/skipped local times. `solar.js` implements parameters, positions, daily crossings, duration, phase and illumination helpers. Independent numerical verification is still required, especially extrema near polar transitions, date-range edges and DST. Planned optional layer uses existing cached static layer z=45, leaving labels and borders above it. Reuse PR #3's existing `projectionFrom` / `mapToLonLat` in `web/js/util/geo.js`.

- Algorithm reference: https://gml.noaa.gov/grad/solcalc/calcdetails.html
- Independent reference intended: USNO; no saved reference results found.

Connections: proposed `connections.json` contract contains source metadata, nodes, directed or undirected flows, period, unit, status and coverage. Draft queries only 2024, selects municipal commuting pairs with at least 25 employed people, excludes self-flows, selects five international ferry routes and Danish domestic airport pairs. These are registered employment relationships or annual passenger/freight movements, not live trips. Route totals combine directions; commuting and aviation preserve direction. Parser, identifiers, suppression, exact query compatibility and unit conversions still need verification. Source/license claims in draft code are provisional until checked against publisher terms; metadata alone is not numerical validation.

- SSB 03321: https://www.ssb.no/en/statbank/table/03321/ ; metadata https://data.ssb.no/api/pxwebapi/v2/tables/03321/metadata?lang=en
- SCB TAB1830: https://statistikdatabasen.scb.se/api/v2/tables/TAB1830/metadata?lang=en
- DST metadata: https://api.statbank.dk/v1/tableinfo/PEND100?format=JSON&lang=en ; same endpoint for `SKIB32`, `SKIB31`, `FLYV33` (all six responses saved).
- Cross-border commuting and observed rail flows remain unimplemented; no equivalent coverage established. Do not infer flows from infrastructure or employment balances.

Climate: draft selects 48 WMO station files for monthly temperature and precipitation, 1991–2020, from national submissions in NCEI archive 6.6. Planned profiles show nearby station and distance, never an exact municipal average. Parser handles missing values, units and year counts, withholding counts below 24. No downloaded station CSVs, built climate data or tests were found. Archive filenames and licensing statements in code still need independent confirmation.

- https://www.ncei.noaa.gov/products/wmo-climate-normals
- https://www.ncei.noaa.gov/data/oceans/archive/arc0216/0253808/6.6/data/0-data/Region-6-WMO-Normals-9120/
- Existing `urban_growth` lens and Environment advisor already compare CORINE 1990/2018: reuse, do not invent annual history.

Contextual references researched, not implemented:

- https://github.com/eu-cdse/copernicus-browser documents `zoom`, `lat`, `lng`, `datasetId=S2_L2A_CDAS`, `layerId=1_TRUE_COLOR`, `date=latest`; verify actual destination behavior before shipping. https://documentation.dataspace.copernicus.eu/Applications/Browser.html describes account requirements.
- https://developer.yr.no/featured-products/forecast/ documents forecast API coordinates, not yet a verified public forecast-page deep link. https://hjelp.yr.no/hc/en-us/articles/19559480708508-Weather-modules-from-Yr describes coordinate-based widgets; do not introduce embedding/polling merely for outbound references.
- https://github.com/simplifaisoul/osiris and https://osirisai.live/ were inspected as functional references only. No OSIRIS code/assets copied.

## Remaining implementation and blockers

1. Review and test these drafts before registration; obtain bounded raw data through existing cache/provenance workflow, then add builders and contracts. Preserve all existing generated data.
2. Implement optional daylight controls/rendering/profiles and a Connections layer/inspector with filtering and source details. Use existing extension API, hash, cached layers and city sections. A matching `addStateSections` hook was proposed but not written.
3. Implement station climate profiles and environmental context; investigate defensible hazards, seasonal treatments and aurora references. Integrate existing historical land cover with Timeline/Environment advisor.
4. Add weather/Earth-observation references through existing map-handoff conventions, and connected Discover journeys/context navigation. No bookmarks/history work completed.
5. Add focused numerical/data/browser tests, inspect desktop/mobile visuals and accessibility under CSP, benchmark against preserved baseline, complete the requested five substantive review perspectives, then reconcile parallel work and prepare one coherent PR when authorized to resume.
6. Historical raw caches are absent from this checkout (`data/` did not exist). The older local source folder had only some source cache directories, not a verified complete cache. Full source-backed release remains unresolved. Existing PR #3 reports its staged release stopped for missing historical caches; this session did not reproduce that validation.

Runtime notes: `python` resolves to an unusable Windows Store shim; use `work/venv/Scripts/python.exe`. Declared repository dependencies were installed there. Official source networking required sandbox escalation. No dependencies were changed in the repository. Recovery performs preservation checks only: no dataset regeneration, research rerun, feature validation suite, deployment or release promotion.
