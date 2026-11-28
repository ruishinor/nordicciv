# NordicCiv roadmap handoff — 28 November 2026

Stopped at the owner's explicit request to prepare a handoff due to usage limits. The roadmap is incomplete. Nothing was merged into main, released or deployed.

## Resume here

Canonical repository: `C:/00 DEV/In Progress/NordicCiv-Repository`.

Working tree for this task: `C:/Users/alex_/Documents/Codex/2026-11-28/nordicciv-autonomous-roadmap-completion-and-release/candidate`.

Branch: `integration/roadmap-2026-11-28`. This is a linked worktree of the canonical repository, not a replacement repository. Use its Git history. Use one agent.

Python: `C:/00 DEV/In Progress/NordicCiv-Repository/.venv/Scripts/python.exe` (Python 3.14). Set `PYTHONUTF8=1` and preferably `PYTHONUNBUFFERED=1` for commands. Browser and dependencies are installed; axe-core is under `tests/.node`. The validation script now accepts `-Python` for this worktree.

The canonical checkout remains on local main `e41e3bd`, behind fetched `origin/main` `249fce8`. Its pre-existing modified `docs/CHECK_REPORT_SOURCE.txt` was deliberately preserved. Do not stage it on main or overwrite it as task cleanup.

## Reconciliation and completed changes

- `origin/main` `249fce8` already contains PRs #1–9, including climate normals, glacier/environment history, connected discovery, daylight, Windows source-check changes and CORINE history. No recreation was needed.
- PR #10 (NVE) and #11 (Norwegian commuting, based on #10) remain open. Their history is included through the Scandinavian commuting merge.
- `796f8d5`: merged `feature/scandinavian-commuting` `02366bf`, including `feature/norwegian-commuting` `b3e13c9` and `feature/nve-environment-maps` `d9dc2fa`.
- `49a06b2`: completed SE/DK municipality panels, incoming/outgoing schematic lines, national definitions, registry and builder integration, built/source checks and desktop/mobile commuting journeys. Datasets: NO 357 municipalities / 2,981 directed pairs; SE 290 / 4,268; DK 98 / 3,066. Threshold 25 employed people. Danish ambiguous zero/suppressed cells stay excluded. SE/DK raw packets exactly reproduce the shipped files. GitHub built workflow for this revision passed: run 46121428699.
- `e4ab796`: merged `feature/scandinavian-shelter-overview` `8fe3e84`, preserving its Swedish aggregates and Danish inventory, both CSS additions and data contracts.
- `26a000a`: merged `feature/discover-saved-places` `13ad409`, including direct navigation `76074eb`.
- `7a4aab2`: merged `feature/seasonal-daylight-aurora` `a42dec9`.
- `ea76518`: merged `feature/close-zoom-detail` `d798e74`; reconciled browser IDs: 51 NVE, 52–53 commuting desktop/phone, 54–55 close zoom desktop/phone. Preserved failure recovery from that branch. Converted old Playwright string predicates to function predicates for CSP compatibility. Added a main guard so importing the smoke runner does not execute the full suite.
- `d63aafb`: corrected mobile saved-place test navigation (close municipality before opening mobile Discover; reopen municipality before checking removed state); added explicit Python selection and UTF-8 to Windows validation. At handoff preparation, GitHub run 46122286314 was still running for this revision.

The final handoff checkpoint adds this document, retained results and the unfinished transport modules described below. Its commit is the branch HEAD after this document is committed; use `git log -1` for the exact revision.

## Validation and limits

`docs/recovery/2026-11-28-roadmap/` retains the actual unit/browser JSON, validation logs, focused-check notes, selected screenshots, and the small new transport source cache with its manifest. The JSON identifies the candidate it tested; it does not certify later code.

- Full local unit suite: 75 passed, 0 failed/errors/skips.
- Full combined built check: 154 pass, 9 notes, 0 warnings/failures; source checking intentionally not part of built mode.
- Full combined browser run: 55 passed, 1 failed, 0 skipped/missing; candidate unchanged during run. Only journey 50 failed. The final correction subsequently passed focused discovery journeys on desktop and phone. Full validation still needs to run on the final combined candidate.
- Accessibility journey passed with axe installed. Close zoom passed on desktop and high-DPI phone. Bergen screenshots were visually inspected: artwork remains stylised, with coarse terrain and some repeated patterns; no claim of surveyed trees/buildings or high-resolution geography.
- No final performance comparison or full representative visual review was completed. No release-mode success is claimed.
- Source-mode attempt: 196 pass, 6 failures. Four missing manifest entries were subsequently restored by merging only hash-verified entries from recovery; `pipeline process ssb regional_accounts --strict` then passed. Those fixes have not yet received another full source check.
- The source-mode shelter comparison found 555 cached and 555 shipped records but 1,110 differing IDs/records. Diagnose whether the recovered DSB snapshot changed identifiers/contents before any update. Do not weaken the comparison.

## Preserved raw sources

All recovered files remain locally under `candidate/data/raw/` (ignored by Git). Original local raw files were copied, not moved or overwritten. Recovered manifest entries were combined only after checking their downloaded file hashes.

Sibling `../artifacts/` retains downloaded workflow artifacts and logs:

- `source-recovery`: run 46094165346, artifact `missing-source-recovery`; 46 files match original published hashes, 10 differ, none unavailable. Read `recovery-report.json` for the exact files. Do not silently replace published provenance with these changed snapshots.
- `nordic-commuting`: run 46098700396, artifact `nordic-commuting-source-and-generated`.
- `norway-commuting`: run 46094123547, artifact `commuting-source-and-generated`.
- `nve`: run 46094102071, artifact `nve-environment-source-and-generated`.
- `close-zoom` and `saved-places`: failed-head browser artifacts retained for diagnosis.

The Swedish shelter acquisition workflow did not retain a raw artifact; only the municipal aggregate and its hash/provenance were committed. Its tool downloads without caching; this remains a source-reproducibility gap. No individual Swedish shelter records were published by this session.

## Transport draft — not shipped

New unregistered modules: `pipeline/sources/transport.py`, `pipeline/build/transport.py`.

They reuse the recovered source research and ordinary cache/provenance contract. Eight official metadata/data files were acquired for 2024 (FLYV33, FLYV34, SKIB31, SKIB32). A processor smoke check produced 40 observations; the draft output is preserved under recovery, not web/data. Units are rounded thousands converted to passenger movements or tonnes. Zero/suppression is omitted, never interpreted as verified absence. Domestic flights are directed airport pairs; international flights are airport-to-country and must not get a fictional foreign airport or map line. Ferry totals combine directions. Læsø uses an explicitly labelled municipality centre because the existing port layer lacks its endpoint.

Remaining work: independent parser/contract tests (missing/duplicate/invalid cells, units, direction), confirm endpoint municipality corrections and coordinate meaning, source-registry and builder registration, built/source gates, generate only transport JSON and its catalogue entry, add a shared optional map layer and panel with category filtering/period/units/direction/source notes, desktop/mobile journeys, Discover links. No transport UI exists yet. Do not present this draft as delivered functionality.

## Cross-border research — not implemented

- Region Skåne report, Table 1, page 2: https://utveckling.skane.se/siteassets/publikationer/2026-rapport-oresundspendling.pdf — observed via web reader. 2024: Sweden to eastern Denmark 20,998; Denmark to Skåne 910; other Sweden 343; other Denmark 897. Keep regional resolution. Direct pipeline download returned HTTP 403; no PDF source bytes/hash were acquired. Prefer an official accessible dataset or retain a clearly reviewed transcription with source documentation; do not invent a cache hash.
- Nordic Statistics COMP53 queried successfully: https://pxweb.nordicstatistics.org/api/v1/en/Nordic%20Statistics/Nordic%20Indicators%20for%20our%20Vision%202030/Area%202%20A%20competitive%20Nordic%20region/COMP53.px . Latest year in metadata: 2023. Reporting DK 1,391, SE 20,038. These differ from the newer Skåne report's historical series. Do not combine or silently harmonise them. Metadata and response retained in recovery. This indicator covers Øresund only.
- SSB article: https://www.ssb.no/arbeid-og-lonn/sysselsetting/artikler/flest-grensependlere-fra-stromstad — November 2023, nonresident employees aged 15–74 with Swedish background; about 13,000 nationally. Its municipality distributions include estimated assignments for missing addresses (about 20%). No exact OD table was acquired. Do not turn its percentages or approximate totals into precise municipality flows.

## Remaining roadmap at the original recovery checkpoint (see updates below)

1. Keep this checkpoint; inspect current remote head and CI first. Do not repeat successful old runs because historical failures are visible.
2. Finish transport as above; commit/push the smallest tested usable deliverable.
3. Implement published cross-border observations at their actual regional/national resolution; investigate the precise Norway–Sweden source before drawing OD lines.
4. Extend existing Discover journeys with the new domestic commuting and transport observations. Existing saved places and direct navigation are reconciled, not replaced.
5. Implement seasonal landscape artwork. Current merged branch provides season/time presets, darkness calculations and an external NOAA aurora forecast reference, but no seasonal forest/farm/winter palette changes. Reuse `render/art/illustrate.js` masks and bounded pattern cache. Make illustration explicit and optional; no simulated live snow/weather claims.
6. Review close zoom across fjords, islands, Swedish forests/towns, Danish fields and cities; compare performance with baseline. Current max zoom/raster/cache upgrade is merged, but further official geographic detail acquisition and full visual assessment are not done.
7. Reconcile shelter source/registry/Almanac/lens language and reproducibility. Swedish aggregate code can assign a point to the nearest outline within 1,500 m; expose that qualification in UI, which currently says only municipality boundaries. The Norway-only individual map/lens remains distinct from SE/DK aggregate categories.
8. Environmental baseline already includes climate normals, CORINE changes, glacier history and NVE southeast flood pilot. Further Swedish/Danish hazards remain optional source-led expansion, not completed in this session.
9. Resolve source validation findings, then run `scripts/validate.ps1 -Mode built -Browser -Port 8767 -Python <configured-python>`, source mode, `tests/visual_states.py`, `tests/perf.py`, and candidate-bound release validation. Batch related fixes before expensive reruns. Do not claim release readiness while sources or candidate evidence fail.
10. Prepare/update the integration draft PR. No merge to main, release promotion or deployment is authorized.


## Continuation after recovery

- e08db6b integrated 40 Danish aviation and selected ferry observations, map and panels, filters, Discover and source checks.
- 3950385: local source validation passed (210 checks, zero failures/warnings/skips; 1,198 downloads). All 43 economic regions reconciled; 555 Norwegian shelter identifiers and source catalogue were updated without substantive record changes.
- Optional Daylight seasonal artwork uses existing masks and bounded cache. Swedish shelter wording now explains the 1.5 km assignment rule. New browser and unit assertions require validation.
- Nordic Statistics COMP53 reuse terms (https://nordicstatistics.org/about/) cover personal use, internal information and news media; public interactive redistribution is not clearly covered. Keep the recovered data local until permission or a reusable alternative is verified. COMP53 covers the Øresund region, not all Scandinavian commuting.
- Full candidate browser tests, representative visual/performance review, Swedish shelter source reproducibility and release gates remain outstanding.

## Owner-directed continuation

- 850d272 publishes the two attributed 2023 Øresund observations and adds six Discover journeys from the national commuting, transport and cross-border datasets. No municipal cross-border line is drawn. Owner approved publication of the two observations; no blanket reuse licence is asserted.
- Swedish shelter aggregator now supports private local snapshot caching and a read-only comparison. CI publishes only an aggregate comparison report, never the individual source records. A different archive hash with identical aggregates is not an exact reproduction of the original bytes. Exact original source bytes remain unavailable unless recovered separately.

## Validation and visual review — 28 November 2026

- GitHub validation run [46126739151](https://github.com/ruishinor/nordicciv/actions/runs/46126739151) at `fa05ace`: 84 unit tests and all 58 browser journeys passed. The browser checked 192 app/data files; none differed.
- Swedish shelter run [46126683317](https://github.com/ruishinor/nordicciv/actions/runs/46126683317): original SHA-256 reproduced exactly (`16f2d3c32a09f1eb521a7a735cfa60ce3d0307dac6b30791fdd5f318dd4cdc90`); 290 municipalities, 63,321 shelters, 6,751,759 places, no missing capacities, 3 nearest-outline assignments, no unassigned or ambiguous records. All municipal totals identical. This supersedes the earlier missing-source concern. Artifact `swedish-shelter-comparison`.
- Visual/performance run [46126736002](https://github.com/ruishinor/nordicciv/actions/runs/46126736002): baseline `249fce8`, candidate `fa05ace`. Reviewed all 12 screenshots (six paired views: Bergen, Vågan, Tingsryd, Skurup, Copenhagen and Värmdö on phone). All captures completed without errors. Max supported zoom increased from 6 to 12. Headless Chromium, one run per build. Median pan and close-pan frame interval 16.7 ms on both; close-pan p95 16.8 ms on both, worst 200 vs 216.7 ms. Common close-zoom warm redraw median 193.1 vs 196 ms; max zoom warm redraw 193.6 vs 88.3 ms (different zoom levels, not a like-for-like speedup). Zoom p95 33.4 vs 50 ms, worst 133.3 vs 100.1 ms. Repeated vegetation/field art and underlying terrain resolution are visible at maximum zoom; this is a stylised map. No device-wide performance claim. Artifact `close-zoom-review`.
- `4905103`: final functional correction chooses the transport category for each Discover journey, restores it from shared links, clears unrelated connection overlays for connection tours and tests navigation of all six new journeys on desktop and phone. Adds COMP53 to the data hash and checks the retained source cells in the pipeline. The pinned fixture matches the recovered source archive. The changes require their own CI pass.
- The raw source cache was already validated (1,198/1,198 files at `3950385`); do not export or reacquire it. The final release-mode check is performed in the candidate worktree against that cache. Reuse unit/browser results only when their full candidate ID matches the local files. Preserve the existing modified reports and untracked recovery directory; do not stage them unintentionally. After a successful release check, merge the consolidated PR when checks pass; confirm the production deployment. No production release yet.

## Close-zoom refinement after the release check

The owner supplied a successful local release report for `23d09ba`: 220 checks passed, 84 unit tests and all 58 browser journeys, all 1,198 raw downloads verified. Retain that revision as the known-good candidate. The follow-up artwork uses irregular, clustered forest stands and periodic field parcels, multi-scale ground grain, smaller close-range phone banners and a capped automatic high-DPI composition buffer. Full-detail mode retains native resolution. These changes do not alter the geographic source data, and the 12 million pattern-pixel cache cap is preserved. Recheck desktop and high-DPI phone rendering and compare against `23d09ba` at identical zooms. A real increase in terrain resolution requires finer elevation and land-cover inputs, not interpolation of the current 1 km grid.
