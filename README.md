# NordicCiv — Scandinavia as a strategy game, built from real data

Norway, Sweden and Denmark drawn like a turn-based 4X strategy map. Every hex, municipality, yield, resource and
wonder comes from public data — EU-DEM and CORINE on a 1 km grid, the municipal statistics of Statistics Norway,
Statistics Sweden and Statistics Denmark, Eurostat, the Norwegian Offshore Directorate, the Geological Survey of Sweden,
Natural Earth and Wikidata — and every number says what it measures, where it came from and at what resolution.

It is a visualiser, not a game: open your hometown, then wander off into Norwegian hydropower, Swedish mining towns,
Danish farmland or the Øresund.

## What's in it

- **The map.** 40,828 equal-area hexes (9,005 of them Scandinavian land) (10.4 km across, 93.5 km² each) in a Lambert equal-area projection centred on
  63°N 15°E. Each hex summarises ~94 one-kilometre cells: relief from EU-DEM, land cover from CORINE 2018 (conifer taiga,
  fjell heath, bare rock, glaciers, mires, farmland, towns), tree cover from Copernicus, water and sea depth classes.
  Rivers, lakes and region borders; Finland, Russia and Germany under fog for context.
- **Cities = municipalities.** All 745 municipalities (357 NO, 290 SE, 98 DK; 2024 boundaries) are cities, with banners
  on their main settlement and six yields:
  Food (agriculture/forestry/fishing jobs), Production (mining, manufacturing, construction), Gold (GDP), Science (ICT and
  professional services), Culture (arts, recreation, other services) and — distinctly Nordic — **Welfare** (education,
  health and social work). City types come from location quotients against the three countries combined.
- **Municipality panel.** Population and growth 2008–2026, age structure, density, jobs per resident, income relative to
  the national level, specialisations, jobs by 14 harmonised industries, resources/wonders/ports/airports in the
  municipality, similar-sized peers, sources.
- **Regions.** 15 fylker, 21 län, 5 Danish regions, with yields, ranks, land-cover mix and largest municipalities.
- **Resources.** 687 sites: hydropower, pumped storage, nuclear, wind (onshore/offshore), solar, thermal plants
  (installed MW — never presented as generation), 101 producing oil and gas fields with production, Swedish metal and
  industrial-mineral mines.
- **Infrastructure.** Motorways, major roads, railways and ferry routes (Natural Earth, as map art), 145 ports by goods
  handled and 59 airports by passengers (Eurostat 2024).
- **Wonders by rule.** All 32 UNESCO World Heritage Sites, national parks ≥ 1,000 km², large/old universities, bridges
  ≥ 6 km and tunnels ≥ 11 km.
- **22 lenses** in four groups (people, economy, welfare & access, land), each labelled hex / municipality / region /
  derived, with a histogram legend you can brush.
- **The Council.** Eight advisors (geography, population, economy, industry, energy, infrastructure, environment,
  resilience) whose observations are computed deterministically from the data on the map, each with its source and a
  "show on map" action. Plus **Compare** (up to four municipalities), **Explorer** (filter, sort, scatter with
  correlation, CSV export) and a **Timeline** lens for population change between any two years 2008–2026.
- **Almanac.** About, yields, regions, methodology, terrain, lenses, resources, wonders, limitations and every source with
  URL, SHA-256, size and retrieval date.

## Quick start

The built data is included, so serving `web/` is all it takes:

```bash
python -m pipeline serve            # http://127.0.0.1:8765  (or any static server on web/)
```

`web/` is a self-contained static site (plain ES modules + Canvas 2D, no framework, no build step, no runtime APIs).

## Rebuilding the data

Python 3.11+ with `numpy pyproj shapely pyarrow scipy` (`pip install -r requirements.txt`).

```bash
python -m pipeline fetch            # download every source into data/raw/<source>/ with a provenance manifest
python -m pipeline process          # raw → data/interim/<source>.json
python -m pipeline build            # interim → web/data/*.json
python -m pipeline check            # validation report (exit 1 on FAIL); writes docs/CHECK_REPORT.txt
python -m unittest discover -s tests
python tests/smoke_browser.py       # real-browser user journeys (Playwright, site served on :8765)
python -m pipeline all              # fetch + process + build + check
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
  check.py   acceptance checks: reconciliation with national totals, placement, null≠0, provenance
web/          the static app (engine adapted from usaciv; ext/nordic adds the Council, Compare, Explorer, Timeline, ferries)
docs/         METHODOLOGY, SOURCES, LIMITATIONS (with decision log), DATA_CONTRACTS, CHECK_REPORT
tests/        unit tests (geometry, projection, JSON-stat, harmonisation, built data) and browser journeys
tools/        relay.js and bridge.py (browser relay), preview.py, shot.py
```

The data engine knows nothing about the game presentation: `web/data/*.json` is a documented, machine-readable
export (see `docs/DATA_CONTRACTS.md`) that the Explore/Analyze modes consume, and that a future Simulate mode or another
interface can consume too. A simulation would add its own files and must never overwrite observed values.

## Reading the map honestly

- Yields are names for real figures (see the Almanac). Jobs are counted where people work (Nov/Q4 2024).
- Gold below the region level is an estimate (regional GDP × share of jobs), always shown with ≈. Norway's regional
  GDP is value added at basic prices and excludes the continental shelf (≈ €104 bn in 2023).
- Hex population is a dasymetric estimate; municipal totals are exact. Municipal and regional lenses say so in the legend.
- Missing stays missing: null, "–" or "no data", never 0. Suppressed components make a value a lower bound (≥).
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
