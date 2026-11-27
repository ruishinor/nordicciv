# NordicCiv — Scandinavia as a strategy game, built from real data

**Version 0.5.0** (see `VERSION`, `docs/VERIFICATION.md` for release test results, `docs/LEDGER.md` for the
requirement-by-requirement status).

Norway, Sweden and Denmark drawn like a turn-based 4X strategy map. Every hex, municipality, yield, resource and
wonder comes from public data — EU-DEM and CORINE on a 1 km grid, the municipal statistics of Statistics Norway,
Statistics Sweden and Statistics Denmark, Eurostat, the Norwegian Offshore Directorate, the Geological Survey of Sweden,
Natural Earth and Wikidata — and every number says what it measures, where it came from and at what resolution.

Explore your hometown, see what stands out, compare it with nearby municipalities,
press **Discover** for a surprising fact about a real place, or wander off into Norwegian hydropower, Swedish mining
towns, Danish farmland or the Øresund.

## What's in it

- **The map.** A continuous painted landscape — CORINE land cover, Copernicus tree cover and a multidirectional EU-DEM
  hillshade on a 0.5 km image, coasts from the municipal polygons, a sea from Natural Earth depth bands — with 40,828
  equal-area hexes (93.5 km² each; 9,005 Scandinavian land) as the unit of terrain statistics, in a Lambert equal-area
  projection centred on 63°N 15°E. Ranges are shaded as connected masses under one north-west light, and closer in the
  ground is illustrated — tree crowns, field patchwork, scree, mire, heath, rooftops — through the 1 km land-cover masks
  (illustrations show what covers each square kilometre, not where a real tree or house stands). Every municipality also has its own polygon for selection, borders and municipal lenses, so small ones
  (Frederiksberg, Solna, Utsira, Røst …) are fully represented. Finland, Russia and Germany under fog for context.
- **Cities = municipalities.** All 745 municipalities (357 NO, 290 SE, 98 DK; 2024 boundaries) are cities, with banners
  on their main settlement and six yields:
  Food (agriculture/forestry/fishing jobs), Production (mining, manufacturing, construction), Gold (GDP), Science (ICT and
  professional services), Culture (arts, recreation, other services) and — distinctly Nordic — **Welfare** (education,
  health and social work). City types come from location quotients against the three countries combined.
- **Municipality panel** — Overview (yields with what each measures, rank or rank interval, largest
  industry vs strongest specialisation, actions: compare with neighbours, similar municipalities, where else this
  industry concentrates, ask the Council), Economy (output estimate and method, specialisations, jobs by 14 industries,
  sites), Society (population chart with boundary breaks, age, density, income relative to the national reference),
  Sources (data status per value, tables) and Daylight (local sun and daylight times).
- **Daylight.** Open **Daylight** to see where the sun is up, where there is twilight and where it is dark.
  Use the current time or choose a date and local time. Pick a municipality to see its sunrise, sunset, and
  daylight hours, including midnight sun and polar night. **Turn off** brings back the usual map colours.
  The light depends on the sun's position. The painted terrain relief keeps its fixed shading.
  Times are calculated at the municipality's map location for a clear, level horizon.
- **Regions.** 15 fylker, 21 län, 5 Danish regions, with yields, ranks, land-cover mix and largest municipalities.
- **Resources.** 687 sites: hydropower, pumped storage, nuclear, wind (onshore/offshore), solar, thermal plants
  (installed MW — never presented as generation), 101 producing oil and gas fields with production, Swedish metal and
  industrial-mineral mines.
- **Infrastructure.** Motorways, major roads, railways and ferry routes (Natural Earth, as map art), 145 ports by goods
  handled and 59 airports by passengers (Eurostat 2024).
- **Public shelters (v0.4, Norway).** All 555 public civil-defence shelters in DSB's register (296,937 registered places;
  NLOD 1.0), as an optional layer in the Map menu: summarised by county and municipality far out, every record at its
  published position closer in, a card per shelter, a section in the municipality panel's Society tab, notes from the
  Council's Resilience advisor, an Almanac page and a lens. Public shelters only (private shelters are not published);
  DSB lists the number of places in each shelter. Data for Sweden and Denmark is not available here.
  In an emergency, follow the authorities' instructions.
- **Camera uplinks (v0.5).** 196 public webcams their operators publish — towns, mountains, fjords, coasts, islands,
  ski resorts, weather stations — as an optional layer in the Map menu (off by default; hidden at the scale of the whole
  of Scandinavia). Selecting one opens a small card with **Open uplink**, to the provider's own page in
  a new tab. NordicCiv loads nothing from the providers — no pictures, players, scripts or cookies — and never claims a
  camera is live. Reviewed from CamStreamer, Panomax, WebcamCollections, SkylineWebcams and operators' pages; road and
  people-facing cameras excluded. Municipality panels list their uplinks; Discover visits some of them.
- **Opening screen and Open in Maps (v0.5).** A NordicCiv title card (compass emblem, title, version, a progress line
  and status that follow the real start-up) shows only until the first map is drawn. Municipalities, their main
  settlements, regions, landmarks, national parks, airports, ports and camera uplinks offer "Open in Maps": the real
  place in Google Maps, in a new tab, from each feature's own position (no key, embed or tracking; NordicCiv keeps its view).
- **Wonders by rule.** All 32 UNESCO World Heritage Sites, national parks ≥ 1,000 km², large/old universities, bridges
  ≥ 6 km and tunnels ≥ 11 km.
- **23 lenses** in four groups (people, economy, welfare & access, land), each labelled hex / municipality / region /
  derived, with a histogram legend you can brush.
- **The Council.** Eight advisors (geography, population, economy, industry, energy, infrastructure, environment,
  resilience) who highlight local and regional figures, with sources and a
  "show on map" action. Plus **Compare** (up to four municipalities), **Explorer** (filter, sort, scatter with
  correlation, CSV export) and a **Timeline** lens for population change between any two years 2008–2026.
- **Almanac.** About, yields, regions, methodology, terrain, lenses, resources, wonders, limitations and every source with
  URL, SHA-256, size and retrieval date.

## Quick start

The built data is included, so serving `web/` is all it takes:

```bash
python -m pipeline serve            # http://127.0.0.1:8765  (or any static server on web/)
```

Windows (PowerShell 5.1 or 7):

```powershell
.\scripts\setup.ps1                 # .venv + requirements   (-Locked: exact release versions; -Browser: test browser + axe)
.\scripts\serve.ps1                 # http://127.0.0.1:8765
.\scripts\validate.ps1 -Mode built  # unit tests + built-data gates   (-Mode source / release, -Browser)
.\scripts\release.ps1               # staged candidate → gates → package verified → promoted to dist\release\
```

`web/` is a self-contained static site (plain ES modules + Canvas 2D, no framework, no build step, no runtime APIs).

## Rebuilding the data

Python 3.11+ (`pip install -r requirements.txt`; release data were built with `requirements-lock.txt`).

```bash
python -m pipeline fetch            # download every source into data/raw/<source>/ with a provenance manifest
python -m pipeline verify-cache     # every cached download vs its manifest (SHA-256, size, request identity)
python -m pipeline process --strict # raw → data/interim/<source>.json (a missing source is an error)
python -m pipeline build            # interim → web/data/*.json; validated, and restored if anything fails
python -m pipeline check --mode built|source|release   # gates; reports in docs/CHECK_REPORT*.txt
python -m unittest discover -s tests
python tests/smoke_browser.py       # 43 real-browser journeys (0–42) (site served on :8765); writes tests/results/browser.json
python tests/visual_states.py URL OUT   # the 46 standard screenshots at fixed cameras (visual regression)
python tests/perf.py OUT.json now=URL   # laboratory performance (frame times, LCP, CLS, lens switch)
python -m pipeline release          # stage, gate (unit, browser and data checks for this candidate), package, verify, promote
python -m pipeline all              # fetch + process (strict) + build
```

**Blocked networks and the relay.** On a normal internet connection `fetch` downloads everything directly. In sandboxes
that only allow package registries, unreachable requests are queued in `data/relay/pending.json`; any browser can run
them with `tools/relay.js` (the SSB, SCB, DST, Eurostat, Wikidata, Sodir and SGU APIs all allow it), and
`python -m pipeline relay-ingest FILE` stores the answers in the cache exactly as a direct download would, marked
`"via": "browser-relay"` in the manifest. The URLs and query bodies are the same either way; they live in
`pipeline/sources/`.

## How it works

```
pipeline/
  core/      fetch (cache + manifest + relay), source contract, Nordic equal-area projection and vectorised hex lookup,
             JSON-stat reader, atomic JSON IO, hexgrid (shared with web/js/hex.js)
  sources/   one class per publisher: files() to download, process() to tidy JSON (no hexes, no UI)
  build/     world (hexes, terrain, water, municipalities, dasymetric population), regions (cities, regions, nation,
             yields, GDP), resources, infrastructure, wonders, lenses, catalog (Almanac bibliography)
  build/     … also history (observation status, boundary breaks), gva (sector-weighted output keys), munis (polygons,
             borders), relief (landscape and sea images, shore lines), shelters, uplinks (camera uplinks)
  catalogue/ reviewed selections tracked in git: camera_uplinks.json (+ page checks, tools/verify_uplinks.js)
  check.py   validation gates in three modes; candidate.py content identity of a release candidate; release.py stages,
             verifies and only then promotes a release (dist/release/, previous in dist/previous/)
web/          the static app (engine adapted from usaciv; ext/nordic adds the Council, Compare, Explorer, Timeline, ferries;
              ext/explore adds Discover and the first-run hint)
docs/         METHODOLOGY, SOURCES, LIMITATIONS (with decision log), DATA_CONTRACTS, CHECK_REPORT
tests/        unit tests, browser walkthroughs, screenshots,
              performance script, ranking fixtures shared by Python and JavaScript
scripts/      PowerShell (setup, serve, validate, release) and validate.sh
.github/      CI: built-data gates, unit tests and browser journeys on every push
tools/        relay.js and bridge.py (browser relay), preview.py, shot.py
```

The data engine knows nothing about the game presentation: `web/data/*.json` is a documented, machine-readable
export (see `docs/DATA_CONTRACTS.md`) that the Explore/Analyze modes consume, and that a future Simulate mode or another
interface can consume too. A simulation would add its own files and must never overwrite observed values.

## Map data and definitions

- Yields group employment by industry alongside economic output (see the Almanac). Jobs are counted where people work (Nov/Q4 2024).
- Gold is economic output in each agency's own concept (Norway GVA at basic prices, Sweden and Denmark GDP); the
  Scandinavian sum is "combined regional output", not harmonised GDP. Below the region it is an estimate (sector-weighted
  share of the region's output), always shown with ≈. Norway's continental shelf (≈ €104 bn in 2023) is outside every
  region.
- Population changes are only compared on the same territory: years a municipality could not be reconstructed are "not
  available", and national and county totals are the agencies' own series.
- Hex population is a dasymetric estimate; municipal totals are exact. Municipal and regional lenses say so in the legend.
- Unavailable figures appear as “–” or “no data”. A lower bound (≥) includes the published parts of a partly withheld total.
- Resources and wonders are selected by published thresholds and rules, listed in the Almanac and in the data files.

## Credits and licences

Code: MIT (see `LICENSE`). The map engine (renderer, terrain art, banners, lenses UI, Almanac framework) is adapted from
**Andrej Karpathy's usaciv** (MIT, © 2026 Andrej Karpathy; licence in `docs/USACIV-LICENSE`). The Scandinavian data
pipeline, panels, Council, Compare, Explorer and Timeline are new.

Data keeps its own licences (details in `docs/SOURCES.md` and the in-app Almanac): Statistics Norway (NLOD / CC BY 4.0),
Statistics Sweden (CC0), Statistics Denmark (CC BY 4.0), Eurostat (CC BY 4.0), Copernicus/EEA and Eurostat GISCO grids
(free reuse with attribution; © EuroGeographics for boundaries), Kartverket (CC BY 4.0), Sodir (NLOD), SGU (CC0),
Natural Earth (public domain), OurAirports (public domain), Wikidata (CC0), powerplantmatching (CC BY 4.0).
Not affiliated with any game publisher; all art is drawn in code.
