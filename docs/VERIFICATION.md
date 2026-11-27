# Verification record — NordicCiv 0.2.0

Everything below was executed for this release on the build machine (Linux, 2 CPUs, Python 3.13.18, headless Chrome
153 with a software GPU). "Independently reproduced" means recomputed in this release from the original downloads;
"historical" means taken from the earlier audit and only reconciled here.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `python -m unittest discover -s tests` | 28 tests, all pass (history rules, sector allocation, cache integrity, registry re-invocation, shipped-data fixtures) |
| `python tests/smoke_browser.py` | 20 journeys pass, 0 fail, 0 skipped (`tests/results/browser.json`, data hash `c68ec9d6f244…`) |
| `python -m pipeline check --mode built` | pass (run by every guarded build and by the release package check) |
| `python -m pipeline check --mode release` | 113 pass, 19 note, 0 warn, 0 skipped, 0 fail (`docs/CHECK_REPORT.txt`) |
| `python -m pipeline verify-cache` (inside the release check) | 1,003 / 1,003 cached downloads match SHA-256, size and request identity |
| `python tests/visual_states.py` | 14 states captured for v0.1 and v0.2 (`docs/visual/`) |
| `python tests/perf.py` | before/after, unthrottled and 4× CPU (`docs/perf/`) |
| Adversarial build test | a build that corrupts `cities.json` and then fails restores the previous file (SHA-256 unchanged) |

Not run: the CI workflow (`.github/workflows/validate.yml`) has not been executed on GitHub — there is no remote
repository. No live deployment was made beyond the private artifact link.

## Evidence and statistical reconciliation

- **Original evidence:** all 25 files of the supplied evidence archive match the SHA-256 recorded in the v0.1 build and
  the files in `data/raw` (independently reproduced).
- **Zero observations (NC-T01):** 64 municipality-years / 6 municipalities reported as 0 by SSB 07459 reproduced exactly;
  now `null` with status "boundary". No zero population remains (check `history: no municipality-year …`).
- **National series (NC-T02):** Scandinavia 19,395,889 (2008), 20,772,253 (2016), 22,258,532 (2026); +7.16 % 2016–26;
  Norway +7.93 % — recomputed from the raw national tables, matching the audit. Norway, every year 2008–2026:
  Σ municipalities + SSB's "divided municipalities and unknown" bucket = national total exactly.
- **Boundary breaks:** 9 municipalities with recorded breaks (Narvik, Hábmer–Hamarøy, Orkland, Heim, Hitra — R1;
  Ålesund/Haram — R2; Tønsberg, Sandefjord — R3 from SSB KLASS 131). Ålesund's 2023→2024 fall (67,520 → 58,509) is now
  a change of territory, not a decline. 14 unexplained one-year changes above 6 % are listed and shown as cautions.
- **Suppression (NC-T06):** 310 Norwegian municipalities with partial groups, 307 with a partial yield, 1,073 partial
  group values, 882 with lower bound 0 — reproduced exactly. Groups + suppressed remainder = total jobs in all 745.
- **Economic output (NC-T07):** combined €1,225.58 bn and continental shelf €104.1 bn reproduced; Σ municipal estimates =
  all 43 published regional totals (worst €47.8 k, from €0.1 m rounding of the stored totals).
- **Current totals:** municipal sums equal the published 2026 totals for Norway; Sweden −9 (SCB noise), Denmark −92
  (residents without a municipality).

## Geography

- Every one of the 745 municipalities has its own polygon (3,643 rings, 113,805 vertices); fixtures Frederiksberg, Solna,
  Sundbyberg, Haugesund, Utsira, Røst, Værøy, Rælingen and Randaberg are selectable (Frederiksberg by a real click in
  the browser, although it owns no hex).
- Banner positions of 12 reference towns within 25 km of their coordinates.

## Performance (laboratory, `docs/perf/`)

| Measure | v0.1 | v0.2 | v0.1 at 4× CPU | v0.2 at 4× CPU |
|---|---|---|---|---|
| Data ready (ms) | 1,041 | 1,018 | 3,648 | 3,398 |
| Relief ready (ms) | — | 1,227 | — | 6,141 |
| LCP (ms) / CLS | 84 / 0.091 | 112 / 0.079 | 184 / 0.091 | 200 / 0.079 |
| Pan: median / p95 frame (ms) | 16.7 / 16.8 | 16.7 / 16.8 | 16.7 / 49.9 | 16.7 / 49.9 |
| Zoom: p95 frame (ms), frames > 50 ms | 233 / 15 | 50 / 5 | 817 / 14 | 233 / 20 |
| Lens switch to next frame (ms, cached) | 151 | 134 | 740 | 562 |
| Municipality click (Event Timing max) | < 16 ms | < 16 ms | 56 ms | 32 ms |
| JS heap (MB) | 35 | 58 | 32 | 55 |

Targets met unthrottled (60 fps panning, lens change < 300 ms, selection < 150 ms, CLS < 0.1). At 4× CPU the lens change
(≈ 0.56 s) misses the 300 ms target and the relief image arrives after ≈ 6 s (hex tiles show until then). LCP is a
canvas-dominated page metric; field data (real users) have not been collected.

## Accessibility

axe-core 4.14.1 (WCAG 2 A/AA, 2.1 AA, 2.2 AA) on the map, an open inspector, the Council and the Timeline: no violations
of any impact. Manually verified in the journeys: keyboard tab navigation in the inspector (arrow keys), `/` to search,
Escape to close, reduced-motion flights, labelled mobile navigation, no horizontal page scroll at 390 px. Not done:
screen-reader testing with NVDA/VoiceOver; the map canvas itself is not accessible beyond its description, search and
the panel/Explorer tables that carry every statistic.

## Security and publication

Static site; Content-Security-Policy restricts scripts, styles, images and connections to the site's own origin (the
mobile journey runs with the policy enforced and records no violation). No third-party runtime requests, telemetry or
storage beyond two `localStorage` preferences (overview scope, existing UI settings). Data inserted into HTML passes
through `esc()`. The release package is scanned for private keys and tokens (none found) and excludes `data/raw`,
caches, local tooling and `tests/.node`. Not done: a dependency vulnerability scan (the site has no runtime dependencies;
the Python build dependencies are pinned in `requirements-lock.txt`).
