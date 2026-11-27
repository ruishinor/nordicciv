# Verification record — NordicCiv 0.4.0 (public shelters)

Executed on the build machine (Linux, 2 CPUs, Python 3.13, headless Chrome with a software GPU, SwiftShader). The
0.3.0 record follows unchanged below this section.

## Gates (run on the working tree, then again by `python -m pipeline release` on the staged copy)

| Gate | Outcome |
|---|---|
| Unit tests | 37 run, 0 failed, 0 skipped (6 new: fixture parse with missing vs zero and lat/lon order; identity; positions; municipal association; aggregates and coverage; lens bands) |
| Browser journeys | 27 mandatory (0–26) PASS; 22–26 are new: layer default/tiers/no overlaps/true positions, selection card and Escape, Society tab (incl. "none" and "not integrated" wording, keyboard list), Council/Almanac/lens, phone |
| `check` (built / source) | built: 111 pass, 7 note, 0 fail; source adds an independent regular-expression re-read of the WFS answer (555 records, 0 differ, numberMatched 555) |
| Release run | the staged run's own results are in `RELEASE_EVIDENCE/` and `RELEASE_MANIFEST.json` inside the package |

Defect found on the way: the accessibility journey (21) failed on some Discover facts because the specialisation badge
had dark text on mid-tone colours (contrast 3.7–4.0:1). Latent in v0.3 (the fact shown is random); fixed by lightening
the badge background (≥ 7:1). The mutation-tested release gates of v0.3 are unchanged.

## Data integrity (public shelters)

- 555 of 555 features the WFS reports as matched; DSB lokalId unique and well-formed; room numbers unique.
- 296,937 registered places; 1 record registered with 0 places (kept as 0); none unstated.
- Positions: transformed back to the published ETRS89 coordinates within 0.7 m; 522 on Norwegian land hexes, 33 on
  coastal hexes the 9.7 km grid counts as sea (inside or ≤ 1.5 km from their municipality's outline).
- Municipalities: 551 inside an outline, 4 assigned to the nearest (19, 35, 36, 110 m); 135 of 357 municipalities have
  at least one public shelter; county and national totals equal the sums of their records.
- Reconciliation with Beredskap101's snapshot: identical except one removed room and one position 173 m apart.

## Five review perspectives (developer reviews, not user evidence)

1. **Data integrity.** No inferred facilities, no merged private data, missing ≠ zero, SE/DK "not integrated", every
   number traceable to the cached answer. Found and fixed: a municipality whose shelters sum to 0 places would have
   fallen into the "no public shelter" lens class; it now cannot.
2. **Responsible information.** Card, section, Council and Almanac say that registered places are not availability or
   readiness, that private shelters are missing, and to follow the authorities in an emergency; no ranking, ratio or
   score exists to misread. Only the fields DSB publishes are shown (no layouts, access or condition).
3. **Visual identity.** One symbol family with the sites (ink outline, gold rim, top-left light, shadow); restrained at
   small scales; no pins, red or animation; grouping instead of displacement. Judged native in states 26–28 and 31 —
   by the developer only.
4. **Accessibility.** Card: labelled region, live, close button, Escape; Society tab lists every shelter as buttons, so
   nothing is reachable only through the canvas; badge contrast defect fixed (above). axe journey 21 passes.
5. **Performance.** Static layer drawn into the cached map; items cached per zoom bucket; no network requests at runtime
   beyond one 122 kB JSON (≈ 25 kB compressed) after the first frame.

## Performance (`docs/perf/v03_v04_desktop.json`; 3 alternating runs, unthrottled, software GPU)

| Measure | v0.3.0 | v0.4.0, shelters off | v0.4.0, shelters on |
|---|---|---|---|
| Data ready, median / worst | 911 / 939 ms | 888 / 904 ms | 988 / 1,022 ms |
| Pan frames, median / worst | 16.7 / 100 ms | 16.7 / 117 ms | 16.7 / 117 ms |
| Zoom frames, p95 (worst run) / long frames | 50 ms / 26 | 50 ms / 23 | 50 ms / 23 |
| Close pan, worst | 233 ms | 233 ms | 250 ms |
| Lens switch, median / worst | 150 / 250 ms | 134 / 200 ms | 125 / 321 ms |
| Settled redraw: overview / regional / close (median) | 43 / 50 / 191 ms | 44 / 45 / 183 ms | 51 / 44 / 184 ms |

Read: with the layer off v0.4 matches v0.3 within run-to-run noise; with it on, the far overview redraw is ~7 ms slower
and data readiness ~100 ms later (the extra file); everything else within noise. Not measured: a 4×-throttled CPU and
a real phone for this release. The keyboard list in the Society tab was added after this benchmark (no rendering change).

# Verification record — NordicCiv 0.3.0 (previous release)

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
| Responsiveness, accessibility, performance | illustrated redraw cost on a software GPU (first measured at 270 ms against 70 ms): occupancy skipping, mask decoding in idle steps, pre-painted patterns, adaptive detail (full → reduced → off), `?detail=off`; the benchmark tour first ran under a lens and measured no illustration — corrected and rerun | settled redraws in illustrated views still ~1.9× v0.2 on software rendering; more long frames while zooming |
| Software and release assurance | candidate identity, browser verification of served files, evidence lifecycle, staged promotion, four test false positives, build backup removed from git, Pillow 12.3.0 → 13.0.0 (42 known CVEs; relief output byte-identical) | CI not executed remotely |

## Performance (laboratory, `docs/perf/v02_v03_*.json`)

Same scripted session on v0.2.0 and v0.3.0, 3 runs each with the build order alternated, headless Chrome with a
software GPU (SwiftShader), 1440×900. Values are median / 95th percentile / worst over all samples. A "settled redraw"
is the full map redraw at a view whose tiles are already decoded — what happens once after every pan or zoom stops;
frames during movement reuse the cached image. Unthrottled = this machine; 4× = the CPU slowed four times.

| Measure | v0.2.0 | v0.3.0 | v0.2.0 at 4× | v0.3.0 at 4× |
|---|---|---|---|---|
| Data ready (ms, median) | 985 | 911 | 3,503 | 4,694 |
| Relief ready (ms, median / worst) | 1,453 / 1,508 | 1,495 / 1,602 | 5,889 / 12,418 | 7,144 / 7,682 |
| LCP (ms, median; returning visitor) | 84 | 64 | 252 | 216 |
| Pan frames (ms) | 16.7 / 16.8 / 83 | 16.7 / 16.8 / 83 | 16.7 / 50 / 650 | 16.7 / 50 / 417 |
| Zoom frames (ms); frames > 50 ms | 16.7 / 33 / 117; 12 | 16.7 / 50 / 133; 24 | 16.7 / 267 / 650; 64 | 16.7 / 367 / 500; 71 |
| Close-zoom pan frames (ms) | 16.7 / 16.8 / 117 | 16.7 / 16.8 / 217 | 16.7 / 50 / 550 | 16.7 / 50 / 767 |
| Settled redraw, overview / regional | 42 / 55 | 44 / 44 | 245 / 308 | 242 / 222 |
| Settled redraw, mid (illustrated in v0.3) | 50 / 87 / 92 | 128 / 191 / 214 | 334 / 569 / 660 | 273 / 469 / 482 |
| Settled redraw, close | 96 / 123 / 175 | 181 / 227 / 238 | 494 / 805 / 821 | 446 / 577 / 580 |
| Settled redraw, very close | 91 / 124 / 125 | 166 / 221 / 240 | 461 / 577 / 579 | 410 / 614 / 656 |
| Lens switch to next frame (ms) | 122 / 223 / 223 | 120 / 208 / 208 | 608 / 1,283 / 1,283 | 608 / 837 / 837 |
| Municipality click (Event Timing max, ms) | ≤ 16–32 | ≤ 16 | 40–72 | 32–48 |
| JS heap (MB, median) | 56 | 60 | 37 | 38 |

Reading: panning and lens switching are unchanged. The illustrated views cost about 80–90 ms more per settled redraw
on this software-rendered machine (reduced detail, 3 classes, chosen automatically); zooming produces about twice as
many frames over 50 ms. At 4× CPU the first illustrated redraw took 260–530 ms, after which the map switched the
illustrations off for the session and later redraws were no slower than v0.2. Mask decoding runs in idle steps (no
long task) and the decoded masks hold up to 8 tiles × 7 classes of 1 MB canvases. Machines with a GPU were not
measured; the illustration layer is a handful of full-screen GPU composites there. Data-ready and relief-ready at 4×
vary by several seconds between runs in both builds.

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
