// "Open in Maps": hand a selected place over to an external map service (Google Maps for now), as an ordinary link the
// user chooses to follow. One module builds every such link, so the coordinates, zoom and URL format are decided once.
//
// Nothing is loaded from the map service here: no script, tile, key or embed. The URL is built locally from NordicCiv's
// own data, carries only a position and a zoom (no app state, no search text, no user data), and opens in a new tab or
// the Maps app (target=_blank, no opener, no referrer). Google's cross-platform Maps URLs:
// https://developers.google.com/maps/documentation/urls/get-started
//
// Two behaviours, chosen per kind of place:
//   view — map_action=map: an unmarked satellite view centred on the place at a zoom that suits its size. For areas
//          (municipalities, regions, national parks) and for positions that only say "around here" (a port placed at
//          its town, a camera placed at the place it is named after).
//   pin  — search with a coordinate query: Google drops a marker on the exact point. For things that sit at a precise,
//          published spot and are easier to find with a marker (an airport, a university).
//
// Positions are always the feature's true geographical position (its own lon/lat, or its true map position converted
// with util/geo.js) — never a symbol nudged aside on screen, the viewport centre or a polygon centroid presented as a
// town. A municipality opens on its whole extent; its main settlement is a separate link at town scale.
import { esc } from "../format.js";
import { projectionFrom, mapToLonLat } from "../util/geo.js";

export const MAPS_LABEL = "Open in Maps";
const VIEW_BASE = "https://www.google.com/maps/@";
const PIN_BASE = "https://www.google.com/maps/search/";
// Fixed zoom levels (Google: 0 world … 21 buildings) for point-like places, by what is worth seeing around them.
export const ZOOM = { viewpoint: 16, landmark: 15, campus: 16, place: 14, town: 13, city: 12, port: 13 };
const GOOGLE_M_PER_PX = 156543.03392; // ground metres per 256-px-tile pixel at zoom 0 on the equator

let proj = null;
/** Give the module the map projection (world.json); needed for places that only have map coordinates. */
export function initMaps(world) { proj = projectionFrom(world); return !!proj; }

export function validLatLon(lat, lon) {
  return Number.isFinite(lat) && Number.isFinite(lon) && Math.abs(lat) <= 90 && Math.abs(lon) <= 180 && !(lat === 0 && lon === 0);
}
const fix = (v) => String(Math.round(v * 1e5) / 1e5); // 5 decimals ≈ 1 m

/** The external URL for {lat, lon, zoom, pin}; null when the position is missing or invalid. */
export function mapsUrl({ lat, lon, zoom = 15, pin = false } = {}) {
  if (!validLatLon(lat, lon)) return null;
  const ll = `${fix(lat)},${fix(lon)}`; // latitude first; URLSearchParams encodes the comma as %2C
  if (pin) return `${PIN_BASE}?${new URLSearchParams({ api: "1", query: ll })}`;
  const z = Number.isFinite(zoom) ? Math.max(0, Math.min(21, Math.round(zoom))) : 15;
  return `${VIEW_BASE}?${new URLSearchParams({ api: "1", map_action: "map", center: ll, zoom: String(z), basemap: "satellite" })}`;
}

/** Zoom at which a span of `km` (the larger side of an area) fits about `px` CSS pixels at latitude `lat`. */
export function zoomForSpan(lat, km, { px = 640, min = 5, max = 15 } = {}) {
  if (!Number.isFinite(km) || km <= 0 || !Number.isFinite(lat)) return max;
  const z = Math.floor(Math.log2((GOOGLE_M_PER_PX * Math.cos((lat * Math.PI) / 180) * px) / (km * 1000)));
  return Math.max(min, Math.min(max, z));
}

/** A map position (km) as WGS84, or null. */
export function lonLatOf(x, y) { return mapToLonLat(proj, x, y); }

/** A view target over a map-km bounding box [x0, y0, x1, y1]: centred on the box, zoomed to fit it. */
export function extentTarget(bbox, { min = 5, max = 14, pad = 1.15 } = {}) {
  if (!bbox || bbox.some((v) => !Number.isFinite(v))) return null;
  const c = lonLatOf((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2);
  if (!c) return null;
  const span = Math.max(bbox[2] - bbox[0], (bbox[3] - bbox[1]) * 1.4) * pad; // screens are wider than tall
  return { lat: c.lat, lon: c.lon, zoom: zoomForSpan(c.lat, Math.max(span, 1), { min, max }) };
}

/**
 * The link itself (HTML), or "" when there is no valid position. target = {lat, lon, zoom?, pin?, what}; `what` says
 * what will open, for the tooltip and screen readers ("Satellite view of …").
 */
export function mapsLink(target, { label = MAPS_LABEL, cls = "chip maps-open", id = "" } = {}) {
  const href = target ? mapsUrl(target) : null;
  if (!href) return "";
  const what = target.what || (target.pin ? "This place" : "Satellite view");
  const title = `${what} in Google Maps (opens in a new tab)`;
  return `<a class="${esc(cls)}" href="${esc(href)}" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer"
    data-maps-out="${esc(id || target.kind || "")}" title="${esc(title)}" aria-label="${esc(`${label}: ${what} (opens Google Maps in a new tab)`)}">${esc(label)} <span aria-hidden="true">↗</span></a>`;
}

// ---- targets: one per kind of place -----------------------------------------------------------------------------
const span = (xs) => Math.max(...xs) - Math.min(...xs);

/** A municipality as an area: its polygon's extent (once loaded), else its hexes'. Never presented as a town. */
export function municipalityTarget(city, { grid, muniFeature } = {}) {
  let bbox = muniFeature?.(city.id)?.bbox || null;
  if (!bbox && grid && city.footprint?.length) {
    const xs = city.footprint.map((i) => grid.cx(i)), ys = city.footprint.map((i) => grid.cy(i));
    const r = grid.R;
    bbox = [Math.min(...xs) - r, Math.min(...ys) - r, Math.max(...xs) + r, Math.max(...ys) + r];
  }
  const t = extentTarget(bbox, { min: 8, max: 14 });
  return t && { ...t, kind: "municipality", what: `Satellite view of the municipality of ${city.name}` };
}

/** A municipality's main settlement (a named place), at town or city scale; null where the banner sits on a population peak. */
export function settlementTarget(city) {
  if (!city.place || !/^euronym/.test(city.anchor || "")) return null;
  const zoom = city.population >= 150000 ? ZOOM.city : ZOOM.town;
  const name = city.place.split("/")[0];
  return { lat: city.lat, lon: city.lon, zoom, kind: "settlement", what: `Satellite view of ${name}` };
}

/** A region (county, län, region) as a landscape overview over its municipalities' extent. */
export function regionTarget(name, cities, { grid } = {}) {
  const xs = [], ys = [];
  for (const c of cities) for (const i of c.footprint || []) { xs.push(grid.cx(i)); ys.push(grid.cy(i)); }
  if (!xs.length) return null;
  const r = grid.R;
  const t = extentTarget([Math.min(...xs) - r, Math.min(...ys) - r, Math.max(...xs) + r, Math.max(...ys) + r], { min: 5, max: 10, pad: 1.05 });
  return t && { ...t, kind: "region", what: `Satellite view of ${name}` };
}

/** A camera uplink: a close view where the provider publishes the position; the place it is named after otherwise. */
export function cameraTarget(c) {
  if (c.pos === "place") return { lat: c.lat, lon: c.lon, zoom: ZOOM.place, kind: "camera", what: `Satellite view around ${c.place?.label || c.name} (the camera's exact spot is not published)` };
  return { lat: c.lat, lon: c.lon, zoom: ZOOM.viewpoint, kind: "camera", what: `Satellite view of the camera's location, ${c.name}` };
}

/** A wonder (wonders.json): national parks and natural sites by area, campuses with a marker, landmarks close up. */
export function wonderTarget(wd) {
  const mt = wd.metrics || {};
  if (wd.kind === "natural") {
    const km = Number.isFinite(mt.area_km2) && mt.area_km2 > 0 ? Math.sqrt(mt.area_km2) * 1.6 : 30;
    return { lat: wd.lat, lon: wd.lon, zoom: zoomForSpan(wd.lat, km, { min: 8, max: 13 }), kind: "park", what: `Satellite view of ${wd.name}` };
  }
  if (wd.kind === "university") return { lat: wd.lat, lon: wd.lon, pin: true, kind: "campus", what: `${wd.name}, marked on the map` };
  return { lat: wd.lat, lon: wd.lon, zoom: ZOOM.landmark, kind: "landmark", what: `Satellite view of ${wd.name}` };
}

/** An airport (positions from OurAirports, in map km): marked. */
export function airportTarget(a) {
  const g = lonLatOf(a.x, a.y);
  return g && { ...g, pin: true, kind: "airport", what: `${a.name}, marked on the map` };
}

/** A port (placed at its town in the data, not at a quay): a town-scale view, no marker. */
export function portTarget(p) {
  const g = lonLatOf(p.x, p.y);
  return g && { ...g, zoom: ZOOM.port, kind: "port", what: `Satellite view of the port town ${p.short || p.name}` };
}
