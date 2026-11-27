# Visual evidence: before (v0.1) and after (v0.2)

Captured by `tests/visual_states.py` against the v0.1 baseline (git tag `v0.1-baseline`) and v0.2, with identical
viewports (1440×900 desktop, 390×844 mobile, device pixel ratio 1), camera centres, zooms, selections and lenses.
`before/` and `after/` hold the single frames, `compare/` the side-by-side pairs.

| State | What changed |
|---|---|
| 01 overview | One continuous landscape (relief, land cover, sea depth bands) instead of hex tiles; national borders from polygons |
| 02 regional south | Mountain ranges and valleys from the hillshade; mountain pieces only on summits |
| 03 Bergen profile | Inspector in tabs; yields name their measure; rank intervals; Bergen's polygon outlined |
| 04 Kiruna + Council | Council at ~25 % width; advisor statements computed, with sources |
| 05 western Norway | Fjords, glaciers and plateaux continuous; the carpet of mountain sprites removed |
| 06 Bergen coast (close) | 1 km blocks gone: polygon coast, painted lakes, smooth sea |
| 07 Frederiksberg | Selectable by its own polygon although it owns no hex |
| 08 specialisation | Municipal polygons coloured (every municipality its own value), clipped to the coast |
| 09 population density | Hex lens clipped to land and shaded by relief |
| 10 growth, Øresund | Municipal choropleth; grey = not comparable, never zero |
| 11 Lofoten | Islands and sounds from polygons; no hex staircase in the sea |
| 12 Stockholm archipelago | Coast from smoothed 1 km cells (the skerries merge: a documented limitation) |
| 13/14 mobile | Labelled navigation bar (Explore, Lenses, Council, Almanac); Tromsø sheet leaves the town visible |

Timings for the same states are in `before/timings.json` and `after/timings.json`; the scripted performance
comparison is in `docs/perf/`.
