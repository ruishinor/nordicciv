# Detailed terrain preview

The standard Canvas map stays on by default. To try the WebGL terrain preview, open the app with `?renderer=webgl`.
Add `&pitch=25` to tilt the camera; pitch is limited to 0–45 degrees. If WebGL 2 is unavailable or the context is
lost, the app returns to the standard map.

The preview builds a triangle mesh from the elevation values already in `web/data/world.json`: one height per hex,
with a 6 km hex radius. The displayed vertical scale is exaggerated 2.5×. It uses no new elevation downloads. The
mesh interpolates between those samples, but that does not add geographic detail. Existing relief and land-cover
artwork stays underneath the lightly shaded mesh, so close zooms can show its finer visual detail. The 1 km and
0.5 km relief images are shaded land-cover artwork, not elevation surfaces. Higher-resolution terrain tiles remain
future work.

The WebGL surface is drawn into the existing cached map. Municipality and regional borders, coastlines, city markers,
resource icons and selection outlines follow the sampled surface. City banners, navigation, lenses and the minimap
keep their existing paths. Statistical lenses use the Canvas renderer so their colours remain unchanged. The feature
flag raises the camera limit from the normal 12 to 48 screen pixels per km; the standard map keeps its existing limit.
Rivers and state labels still use the flat map projection.

`window.__app.terrain.registerLayer({id, type, draw})` accepts future WebGL layers with one of these types:
`elevation`, `vegetation`, `buildings`, `agriculture` or `infrastructure`. The draw callback receives the WebGL
context and a frame with the world data, view and a map-coordinate projection helper. This is an interface only;
the preview does not add finer elevation, trees, buildings, fields or transport features.

Run the focused checks with `python -m unittest discover -s tests -p test_webgl_terrain.py`. The visual capture script
includes `53-webgl-terrain-pitch`:
`python tests/visual_states.py BASE_URL OUT_DIR 53-webgl-terrain-pitch`.

The browser journey also checks failed WebGL initialization and a lost runtime context. `window.__app.terrain.stats()`
reports buffer upload time, CPU-side WebGL submission time and Canvas composition time separately. GPU time is reported
only when the browser supports `EXT_disjoint_timer_query_webgl2`; `gpuMedianMs` stays `null` when no GPU samples are
available.
