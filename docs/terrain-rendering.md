# Detailed terrain preview

The standard Canvas map stays on by default. To try the WebGL terrain preview, open the app with `?renderer=webgl`.
Add `&pitch=25` to tilt the camera; pitch is limited to 0–45 degrees. If WebGL 2 is unavailable or the context is
lost, the app returns to the standard map.

The map uses the same Nordic LAEA coordinates in Canvas and WebGL. The broad fallback surface uses the elevation
values already in `web/data/world.json`: one height per hex, with a 6 km hex radius. It is lightly shaded and keeps
the existing relief image and its land-cover artwork visible underneath.

In the Oslo–Lillestrøm, Aurland and Herning pilots, Copernicus GLO-30 elevation tiles add 480 m, 120 m and 30 m
samples. They are surface-model heights, including vegetation and buildings, in metres above EGM2008; they are not
bare-earth lidar. The terrain overlay is translucent, and the 1 km cover masks remain visible beneath it. Those
masks show land-cover classes and illustrative patterns, not the position of individual trees or buildings. The
surface tint also keeps the existing land-cover mix from each 6 km hex; the 30 m height samples do not increase the
resolution of that colour information.

Terrain detail follows the visible map width: wider than 100 km uses the fallback; at 100 km the 480 m tiles are
available, at 30 km the 120 m level is used, and at 10 km the 30 m source level is selected. At 2 km and closer the
same 30 m source is the finest available; zooming further does not add source detail. The mesh is capped at 100,000
vertices: in a 1440 × 900 view it draws at 60 m spacing at 10 km and 30 m at 2 km. The actual mesh spacing is
reported in terrain stats. Missing or failed fine tiles blend to a loaded coarser tile and then to the existing hex
elevations. Coverage fades at pilot and tile edges, and water cells are excluded from the detailed surface.

The WebGL surface is drawn into the existing cached map. Municipality and regional borders, coastlines, city markers,
resource icons and selection outlines follow the sampled surface. At close zoom, settlement markers remain visible as
small legacy map symbols at their settlement coordinates, with an 18 CSS-pixel radius cap; water locations are skipped
and symbols do not grow with the camera. Vegetation artwork stays under the translucent surface. City banners,
navigation, lenses and the minimap keep their existing paths.
Statistical lenses use the Canvas renderer so their colours remain unchanged. The optional renderer supports a
viewport as narrow as about 2 km on desktop or phone; the standard map keeps its existing zoom limit. Rivers and
state labels still use the flat map projection.

Terrain layers registered with `window.__app.terrain.registerLayer({id, type, draw})` receive a shared `frame.surface`
contract (version 1). Its `sample(x, y)` returns elevation in metres, usable tile coverage from 0 to 1, and whether
the location is water or outside the mapped world. `project(x, y, elevationM)` returns WebGL clip coordinates using
the same camera and vertical scale as terrain picking; if height is omitted, it uses the sampled surface height.
Horizontal coordinates are kilometres in the existing Nordic LAEA map frame. The frame also reports the physical
surface LOD (`overview`, `regional`, `local`, `neighbourhood` or `close`) based on visible widths of 100, 30, 10 and
2 km. Existing `frame.project`, view, pitch and world fields remain available for registered layers.

`window.__app.terrain.registerLayer({id, type, draw})` accepts future WebGL layers with one of these types:
`elevation`, `vegetation`, `buildings`, `agriculture` or `infrastructure`. This is an interface only; the preview
does not add individual trees, buildings, fields or transport features.

Run the focused checks with `python -m unittest discover -s tests -p test_webgl_terrain.py`. The visual capture script
includes `53-webgl-terrain-pitch`:
`python tests/visual_states.py BASE_URL OUT_DIR 53-webgl-terrain-pitch`.

The browser journey also checks failed WebGL initialization and a lost runtime context. `window.__app.terrain.stats()`
reports buffer upload time, CPU-side WebGL submission time and Canvas composition time separately. GPU time is reported
only when the browser supports `EXT_disjoint_timer_query_webgl2`; `gpuMedianMs` stays `null` when no GPU samples are
available.
