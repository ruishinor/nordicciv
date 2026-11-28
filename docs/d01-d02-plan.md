# Close-up terrain pilot

Baseline: `2488c94`, the merged WebGL preview in PR #14. The canonical checkout has an uncommitted source report, so development uses an isolated checkout of GitHub main.

## Architecture decision

Canvas remains the default strategic renderer and the renderer for statistical lenses. Adding more Canvas illustrations would not supply elevation, correct pitched picking or an efficient route to instanced objects. A second map engine would duplicate the existing projection, camera and selection interfaces. Extend the existing optional WebGL 2 component instead, using the current Lambert equal-area map coordinates. Keep the existing layer registration interface for future objects.

The pilot adds independent elevation assets under `web/terrain/`. Municipal statistics, identifiers and their source caches stay unchanged. A bounded build reads only source windows covering Oslo–Lillestrøm, Aurland and Herning. Copernicus GLO-30 supplies a roughly 30 m surface model, including vegetation and buildings. The output grid must not be described as a bare-earth lidar survey. Heights are in metres above EGM2008. The source licence and required notices travel with the generated tiles.

## Acceptance criteria

- The ordinary Canvas map and existing journeys continue to pass.
- The optional terrain view reaches a viewport about 2 km across on desktop and phone, with new elevation samples at closer scales.
- The three pilot areas have measured heights, separate coarse/intermediate/fine tile levels and documented source coverage, spacing, checksums and redistribution terms.
- A continuous mesh has shared edge samples, stable lighting and no cracks when tiles arrive or a level changes. Missing, corrupt or slow tiles leave a coarser surface visible.
- Camera projection, surface picking, zoom anchors, pitch, minimap, navigation and shared URLs agree at close scales. Statistical lenses retain their data and selection.
- The loader limits requests, decoded storage and GPU buffers, and releases obsolete work. Repeated travel does not grow the terrain cache without limit.
- Fixed geographical cameras compare the baseline and candidate at common scales and at a 2 km viewport. Record redraw/frame timings, tile storage, renderer information and the limits of the measurements.
- Unit tests, built-data checks and the complete browser workflow pass on the integrated revision. New terrain source checks run against the bounded source cache. No nationwide rebuild is needed.

## Delivery sequence

1. Preserve the baseline and camera captures. Check source access and licensing.
2. Build and validate bounded terrain assets, then commit a recoverable data checkpoint.
3. Add continuous geometry, loading, shared transformations and close navigation. Test seams, missing tiles and steep terrain picking.
4. Run fixed-camera visual and performance checks, then the existing full applicable workflow. Review failures before integration.
5. Push the development branch, verify GitHub checks and merge with an expected-head guard. Stop before buildings, vegetation or infrastructure expansion.

Rollback: Disable the optional WebGL URL flag to use the existing Canvas view. Git checkpoints preserve the baseline and each implementation stage.
