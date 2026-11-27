# Visual evidence: before (v0.2.0) and after (v0.3.0)

Captured by `tests/visual_states.py` against v0.2.0 (git tag `v0.2.0`) and v0.3.0, with identical viewports (1440×900
desktop, 390×844 mobile, device pixel ratio 1), camera centres, zooms, selections and lenses. The one-time first-run hint
is suppressed in every state except 22, so the frames compare the map. `before/` and `after/` hold the frames,
`compare/` the side-by-side pairs (before left, after right). The after frames use `?detail=full`: the capture machine
renders without a GPU, where the map would otherwise drop to its reduced illustration detail (see VERIFICATION).

No baseline was approved automatically: these frames are evidence for review, not regression thresholds.

| State | What changed (v0.2 → v0.3) |
|---|---|
| 01 overview | The Scandinavian interior is no longer muted as "foreign" (v0.2 bug); colours richer, foreign land still muted |
| 02 regional south | Ranges as connected masses (form shading + crests); farmland tones in Denmark, Skåne, Mälardalen |
| 03 Bergen profile | "What stands out" first in the inspector; ranks are competition ranks or possible-rank intervals |
| 04 Kiruna + Council | Same layout; ranks and intervals follow the single convention |
| 05 western Norway | Crest snow instead of whitened plateaus; deeper fjord valleys |
| 06 Bergen coast (close) | Illustrated ground: broadleaf and conifer crowns, scree, fields, rooftops; no isolated sprites |
| 07 Frederiksberg | Built-up land illustrated as rooftops and streets around the capital |
| 08 / 09 / 10 lenses | Unchanged analysis view (no illustrations under a lens) |
| 11 Lofoten, 12 Stockholm | Sea shadow under the land; archipelago coast still from 1 km cells (documented limitation) |
| 13 / 14 mobile | Same navigation; Discover in the top bar (icon only on phones) |
| 15 Jotunheimen | Connected massifs, snow on crests, valleys in blue-violet shadow |
| 16 Skåne farmland (close) | Field patchwork with hedgerows instead of flat yellow and single barn sprites |
| 17 Småland forest (close) | Continuous conifer canopy instead of scattered tree clumps |
| 18 northern Scandes | Ranges continuous across the border |
| 19 Jutland | Farmland patchwork, heath and plantations distinguishable |
| 20 Telemark (very close) | Heath and scree on the plateau, forest on the slopes, smooth lake shores (was 1 km stair steps) |
| 21 mobile Lofoten | Illustrated ground at phone size |
| 22 first run (after only) | Three-line hint: click a municipality, lenses, Discover |
| 23 Røst (after only) | "What stands out": fastest-shrinking and smallest by area, with neighbours and map links |
| 24 Discover (after only) | A computed fact with its definition, the place selected and its lens applied |

Timings for the same states are in `before/timings.json` and `after/timings.json`; the scripted performance comparison
is in `docs/perf/`.

## v0.4: public shelters (`v04/`)

`v04/before` is v0.3.0 and `v04/after` v0.4.0 at the same cameras (`tests/visual_states.py`, states 25–31; v0.3 cannot
show the shelter states, so its frames show the same view without them). States 01–24 were captured again on v0.4 and
compared pixel by pixel with `after/` (v0.3): every frame within JPEG noise (≤ 0.08% of pixels), except 14 (and the other
frames that show a specialisation badge), where the badge background is lighter for contrast (WCAG AA; a latent v0.3
defect the accessibility journey hit on some Discover facts). No baseline was approved automatically.

| State | What it shows |
|---|---|
| 25 overview, layer off | Default: unchanged map, no shelter symbols |
| 26 regional, layer on | One symbol per municipality, counts on tabs; restrained next to banners and sites |
| 27 local Oslo | Records at their own positions; overlapping ones share a group symbol |
| 28 selected | Card: address as published, registered places, municipality, room, identifier, meaning, emergency note, DSB links, source |
| 29 Society tab | Count, registered places, largest, full list, caveats, "show on map" |
| 30 lens | Registered places in bands; "none" its own class; Sweden and Denmark no data |
| 31 mobile | Card as a bottom sheet |
| 14 mobile Tromsø | Type badge with higher contrast |

## v0.5: camera uplinks (`v05/`)

`v05/after` is v0.5.0 (states 32–39 of `tests/visual_states.py`); `v05/before` and `v05/compare` hold v0.4.0 at the
same cameras for the regional and local states (v0.4 has no uplinks, so its frames show the map the symbols sit on).
With the layer off, states 01, 02, 11, 25 and 27 were captured on v0.4.0 and v0.5.0 and are pixel-identical (0 pixels
differ); state 32 (layer on, whole of Scandinavia) differs from 01 only in the Map-menu counter (31 pixels): the layer
draws nothing at that scale.

| State | What it shows |
|---|---|
| 32 overview, layer on | Nothing drawn at the scale of the whole of Scandinavia (suppressed below 4.5 px per hex) |
| 33 regional south | Small spyglass-on-lookout symbols and count tabs, under the resource medallions, sites and banners |
| 34 western Norway | Region view: coastal and fjord uplinks among hydropower and wind symbols |
| 35 Lofoten (local) | Individual uplinks at their positions; Reine/Hamnøy still share one symbol at this scale |
| 36 Reinefjorden selected | The card: category, name, location, provider and host, kind of position, 'Open uplink' and 'Open in Maps', no-live note |
| 37 Stranda panel | Overview: "The real place" (Open in Maps, Open the town in Maps) above the camera uplinks section |
| 38 under a lens | Symbols fade under the population-density lens and stay above the choropleth, below the sites |
| 39 phone card | Åreskutan: the card as a bottom sheet with both actions visible |


## v0.5: opening screen and Open in Maps (`v05/after`, states 40–46)

States 01–35 and 38 were captured on `main` before this change (ea7e6f3) and after it: all 33 that do not show a
camera card or a municipality's Overview are pixel-identical (0 pixels differ). 36, 37 and 39 differ only by the new
links. States 40–42 are taken while the start-up is held on `world.json` (40, 41) or `world.json` answers 404 (42).

| State | What it shows |
|---|---|
| 40 opening, desktop | Compass emblem, NORDICCIV, "Explore Scandinavia", progress line (indeterminate: the held file's size is not yet known), status line, version |
| 41 opening, phone | The same on 390 × 844, everything on screen |
| 42 opening failed | "The map data is missing", plain explanation, "Try again" (focused), details for developers |
| 43 Bergen panel | Overview · The real place: "Open in Maps" (municipality) and "Open the city in Maps" |
| 44 Bergen sites | Economy · resources, wonders & hubs: Bryggen, University of Bergen, Flesland, port — each with Open in Maps |
| 45 Møre og Romsdal | Region panel: Open in Maps (landscape overview of the county) |
| 46 phone, Stranda | The panel as a bottom sheet with both map links |

The screen recording (opening on a slow network, then Open in Maps for Stranda, Copenhagen Airport and a camera uplink,
with Google's actual landing pages captured in a real browser) is not kept in the repository because it contains Google
Maps imagery; it was handed over with the pull request.
