// Helper for tests/test_maps.py: runs web/js/util/geo.js and web/js/app/maps.js in Node on the shipped data and prints
// JSON (projection round trips, the URLs built for representative places, and the answers to invalid input).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { projectionFrom, mapToLonLat, lonLatToMap } from "../web/js/util/geo.js";
import * as M from "../web/js/app/maps.js";
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (n) => JSON.parse(readFileSync(join(ROOT, "web/data", `${n}.json`), "utf8"));
const world = read("world"), cities = read("cities"), wonders = read("wonders"), infra = read("infrastructure"), up = read("uplinks");
const pts = JSON.parse(readFileSync(0, "utf8") || "[]");
const proj = projectionFrom(world);
M.initMaps(world);
const grid = { R: world.grid.radius, cx: (i) => { const c = world.grid.cols, r = (i / c) | 0; return Math.sqrt(3) * world.grid.radius * ((i % c) + 0.5 * (r & 1)); }, cy: (i) => 1.5 * world.grid.radius * ((i / world.grid.cols) | 0) };
const city = (id) => cities.find((c) => c.id === id);
const munis = new Map(read("munis").features.map((f) => [f.id, f])); // bbox in map km, as the browser decodes it
const muniFeature = (id) => munis.get(id) || null;
const out = {
  inverse: pts.map(([x, y]) => { const g = mapToLonLat(proj, x, y); const b = lonLatToMap(proj, g.lon, g.lat); return [g.lon, g.lat, b.x, b.y]; }),
  targets: {
    muni_stranda: M.municipalityTarget(city("NO-1525"), { grid, muniFeature }), muni_kiruna: M.municipalityTarget(city("SE-2584"), { grid, muniFeature }),
    muni_copenhagen: M.municipalityTarget(city("DK-101"), { grid, muniFeature }), muni_frederiksberg: M.municipalityTarget(city("DK-147"), { grid, muniFeature }),
    town_copenhagen: M.settlementTarget(city("DK-101")), town_stockholm: M.settlementTarget(city("SE-0180")), town_tromso: M.settlementTarget(city("NO-5501")),
    town_none: M.settlementTarget(cities.find((c) => c.anchor === "grid-peak")),
    muni_frederiksberg_hexes: M.municipalityTarget(city("DK-147"), { grid }),
    region_more: M.regionTarget("Møre og Romsdal", cities.filter((c) => c.states?.[0] === "NO-15"), { grid }),
    park: M.wonderTarget(wonders.wonders.find((w) => w.kind === "natural" && w.metrics?.area_km2)),
    landmark: M.wonderTarget(wonders.wonders.find((w) => w.id === "whs-55")),
    campus: M.wonderTarget(wonders.wonders.find((w) => w.kind === "university")),
    airport_cph: M.airportTarget(infra.airports.find((a) => a.id === "EKCH")),
    airport_arn: M.airportTarget(infra.airports.find((a) => a.iata === "ARN")),
    airport_osl: M.airportTarget(infra.airports.find((a) => a.iata === "OSL")),
    port_bergen: M.portTarget(infra.ports.find((p) => p.id === "NO_0NOBGO")),
    cam_published: M.cameraTarget(up.cameras.find((c) => c.pos === "published")),
    cam_place: M.cameraTarget(up.cameras.find((c) => c.pos === "place")),
  },
  sources: {
    park: wonders.wonders.find((w) => w.kind === "natural" && w.metrics?.area_km2),
    airports: Object.fromEntries(["EKCH", "ESSA", "ENGM"].map((id) => [id, infra.airports.find((a) => a.id === id)])),
    port_bergen: infra.ports.find((p) => p.id === "NO_0NOBGO"),
    cam_published: up.cameras.find((c) => c.pos === "published"), cam_place: up.cameras.find((c) => c.pos === "place"),
  },
  invalid: [
    M.mapsUrl({ lat: NaN, lon: 10 }), M.mapsUrl({ lat: 91, lon: 10 }), M.mapsUrl({ lat: 60, lon: 181 }), M.mapsUrl({ lat: 0, lon: 0 }),
    M.mapsUrl({}), M.mapsUrl({ lat: "60", lon: "10" }), M.mapsUrl({ lat: null, lon: 10 }), M.mapsUrl({ lat: 60, lon: Infinity }),
  ],
  zoomClamp: [M.mapsUrl({ lat: 60, lon: 10, zoom: 99 }), M.mapsUrl({ lat: 60, lon: 10, zoom: -4 }), M.mapsUrl({ lat: 60, lon: 10, zoom: NaN })],
  noProjection: (M.initMaps({}), M.airportTarget({ x: 10, y: 10, name: "x" })),
  link: (M.initMaps(world), M.mapsLink(M.cameraTarget(up.cameras[0]))),
  linkNone: M.mapsLink(null) + M.mapsLink({ lat: NaN, lon: 1 }),
  escaped: M.mapsLink({ lat: 60, lon: 10, zoom: 12, what: `"><img src=x onerror=alert(1)>` }),
};
for (const [k, t] of Object.entries(out.targets)) if (t) t.url = M.mapsUrl(t);
process.stdout.write(JSON.stringify(out));
