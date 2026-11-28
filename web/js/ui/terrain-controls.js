import { projectionFrom, lonLatToMap } from "../util/geo.js";

export function installTerrainControls(app, renderer, host) {
  if (!host) return;
  host.removeAttribute("role");
  host.innerHTML = `<details id="terrain-options"><summary>Terrain pilot</summary>
    <p id="terrain-description" role="status"></p>
    <label for="terrain-place">Visit a pilot area</label>
    <select id="terrain-place"><option value="">Choose a place</option><option value="oslo">Oslo</option>
      <option value="lillestrom">Lillestrøm</option><option value="aurland">Aurland mountains</option><option value="herning">Herning</option></select>
    <label for="terrain-pitch">Camera tilt</label><input id="terrain-pitch" type="range" min="0" max="45" step="1">
    <p>Heights include vegetation and buildings. Landscape colours follow height and slope.</p>
    <button id="terrain-retry" type="button" hidden>Retry elevation</button>
    <a href="terrain/sources.html" target="_blank" rel="noopener">Elevation sources and coverage</a>
    <a href="?renderer=canvas">Standard map</a></details>`;
  const pitch = host.querySelector("#terrain-pitch"), description = host.querySelector("#terrain-description");
  pitch.value = app.cam.pitch;
  pitch.addEventListener("input", () => app.setPitch(Number(pitch.value)));
  host.querySelector("#terrain-retry").addEventListener("click", () => {
    renderer.tiles.failed.clear();
    if (renderer.tiles.error) { renderer.tiles.error = null; void renderer.tiles.init(); }
    app.invalidate();
  });
  const places = { oslo: [10.7522, 59.9139], lillestrom: [11.0492, 59.9559], aurland: [7.236, 60.909], herning: [8.973, 56.139] };
  host.querySelector("#terrain-place").addEventListener("change", e => {
    const ll = places[e.target.value];
    if (!ll) return;
    const point = lonLatToMap(projectionFrom(app.w), ...ll);
    app.setLens(null); app.flyTo(point.x, point.y, app.cam.maxScale, 750);
  });
  host.querySelector('a[href="?renderer=canvas"]').addEventListener("click", e => {
    app.hash.flush(); e.currentTarget.href = `?renderer=canvas${location.hash}`;
  });
  const update = () => {
    const s = renderer.stats(), t = s.tiles;
    if (!s.available) return;
    host.querySelector("#terrain-retry").hidden = !(t?.error || t?.failed);
    pitch.value = app.cam.pitch;
    const text = t?.error || (t?.failed ? "Some elevation tiles could not load. Coarser terrain is shown." :
      t?.pending ? "Loading elevation. Coarser terrain is shown while tiles arrive." :
        s.detailVertices ? `Elevation grid: ${s.detailSpacingM} m. Vertical scale: 1×.` :
          "Outside the close-up coverage. Showing the existing hex elevations.");
    if (description.textContent !== text) description.textContent = text;
  };
  app.on("camera", update);
  const previous = renderer.tiles.onChange;
  renderer.tiles.onChange = () => { previous?.(); update(); };
  host.querySelector("details").addEventListener("toggle", update);
  update();
}
