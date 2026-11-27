# Verification record — NordicCiv 0.3.0

Executed for this release on the build machine (Linux, 2 CPUs, Python 3.13, headless Chrome with a software GPU,
SwiftShader). "Reproduced" means recomputed here from the original downloads or the shipped data. The v0.2.0 record is
in the `v0.2.0` tag.

## Gates on the release candidate

The release command (`python -m pipeline release`) copies the candidate into `dist/.staging/`, checks that the copy has
the same content identity, runs the gates on that copy, packages and verifies it there, and only then promotes it to
`dist/release/` (the previous release moves to `dist/previous/`). Its output is summarised in the delivery note and in
`RELEASE_MANIFEST.json` inside the package.

| Gate | Outcome on the final candidate |
|---|---|
| Unit tests (`tests/run_unit.py`) | 31 run, 0 failed, 0 errors, 0 skipped — incl. the JavaScript ranking parity test (Node) |
| Browser journeys (`tests/smoke_browser.py`) | 22 mandatory journeys (0–21) PASS, 0 skipped; journey 0 fetched all 161 app and data files through the browser and matched every SHA-256 |
| `check --mode release` | 121 pass, 20 note, 0 warn, 0 skipped, 0 fail (`docs/CHECK_REPORT.txt`) |
| Cache | 1,003 / 1,003 downloads match SHA-256, size and request identity |
| Package | extracted copy: every file's SHA-256 equals the manifest, same candidate id, built-data check PASS, no secrets found |

**The gates themselves were tested** (each mutation must fail): browser evidence for another candidate, evidence listing
no journey 16, a skipped journey, a `browser.running.json` left by an interrupted run, no browser evidence, an
incomplete run, a skipped unit test, and evidence carrying only a data hash all FAIL. An interrupted browser run
(stopped after 12 s) left no `browser.json`. Source reconciliation: a mismatched value labelled "boundary" FAILS; a
boundary year relabelled "observed" FAILS. Four test assertions were corrected: journey 18 passed through an `or` on the
navigation labels alone (fixing it exposed that the labels are upper-cased by CSS — the comparison is now
case-insensitive); journey 16 did not assert that Escape closes the panel; journey 13 now asserts the rank labels; and
journey 7 the number of advisors. The summary baseline is no longer created automatically in release mode.

Not run: the CI workflow on GitHub (no remote repository, none created); a real-user test (`docs/USER_TEST_SCRIPT.md`).

## Statistical corrections (reproduced)

- **Ranking:** the audit's 157 inconsistent intervals among 2,969 were reproduced (food 128, culture 29: exact ranks were
  sorted positions with ties broken by population, intervals used strict inequalities). After: one convention, 2,969
  intervals, 0 inconsistent, re-derived independently in the check; 6 hand-calculated fixtures and a brute-force test
  that every interval end is attainable; Python and browser implementations agree on the fixtures.
- **Suppression remainder:** 309 Norwegian municipalities with suppressed groups have a positive remainder, 1 has 0; no
  negative remainder; unsuppressed Norwegian and Danish groups add up exactly; Swedish totals differ from the sum of
  components by at most 0.92% in both directions, as SCB's TAB3204 note says its disclosure method allows.
- **Output allocation:** v0.2 → v0.3 changes 28 Swedish and Danish estimates by more than 1%, largest Fanø −6.25%
  (matching the audit), and 10 Norwegian ones (largest Tydal −3.9%); every regional total unchanged (largest difference
  €0.0001 m). Missing denominator: Oslo NOK 45 m (agriculture etc.) now shared by total jobs and reported.
- **Indre Østfold 2026:** checked against KLASS 131, the ministry decision and Vestby municipality; comparable (see
  Methodology). SSB's own table notes are now shown on 28 municipalities.
- **v0.2 visual-data defect found and fixed:** the 1 km grid's country code is empty for 1.25 million land cells, so
  v0.2 muted most unpopulated Scandinavian land as foreign; the three countries now come from Natural Earth.
- Preserved: population, history, employment and output values other than the allocation change above; the accepted
  key totals (release check) are unchanged.

## Five review perspectives (developer reviews, not user evidence)

| Perspective | Findings corrected in this release | Open |
|---|---|---|
| Statistical and geographical | ranking conventions; remainder checks; output classification and fallback; "remote" fact for Copenhagen (distance to Oslo) restricted to places under 50,000; "youngest population" for a low 65+ share and "job magnet" for 62 jobs per 100 reworded; Nordic land mask | bounds stay conservative by design |
| Visual and game identity | isolated sprites removed over the relief; ranges as connected masses; lakes no longer 1 km stair steps (same area); heath and scree glyphs enlarged to be visible; greens toned down; polygonal shore strokes smoothed | soft base between illustrations at very close zoom; Russia edge in hexes; archipelago coasts from 1 km cells |
| Product discovery, new users | first-run hint covered the Council (now under all panels, dismissed by use); Discover unreachable on phones (now in the bottom bar); a discovery showed the wrong definition; the Almanac button was cut off at 1440 px | no real-user test yet |
| Responsiveness, accessibility, performance | illustrated redraw cost on a software GPU (see below): occupancy skipping, mask decoding in idle steps, pre-painted patterns, adaptive detail, `?detail=off` | more long frames while zooming on software rendering |
| Software and release assurance | candidate identity, browser verification of served files, evidence lifecycle, staged promotion, four test false positives, build backup removed from git, Pillow 12.3.0 → 13.0.0 (42 known CVEs; relief output byte-identical) | CI not executed remotely |

## Performance (laboratory, `docs/perf/v02_v03_*.json`)

PERF_TABLE

## Accessibility

axe-core 4.14.1 (WCAG 2 A/AA, 2.1 AA, 2.2 AA) on the map, an open inspector, the Council, the Timeline, the first-run
hint and a Discover card: no serious or critical violations. Keyboard: tab arrows, `/` search, Escape closes (asserted).
The illustrations are decorative; every statement they support is in the panels, Explorer and Almanac, and
`?detail=off` removes them. Not done: screen-reader testing (NVDA/VoiceOver).

## Security and publication

Static site; Content-Security-Policy limits scripts, styles, images and connections to the site's own origin, and
journey 0 confirms every resource the page loaded is a file of the candidate. Storage: three `localStorage` preferences
(overview scope, lens shortcuts, first-run hint seen). Dependencies: `pip-audit` on `requirements-lock.txt` finds no
known vulnerabilities after the Pillow upgrade (the site itself has no runtime dependencies; axe-core is a test tool,
not audited). The package excludes `data/raw`, caches, `tests/.node` and test results, and is scanned for keys and tokens.
No credentials are used or stored; nothing was published or deployed.
