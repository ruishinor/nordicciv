// Map coordinates ⇄ WGS84 longitude/latitude, for the few places that need real-world positions (the external map
// hand-off, app/maps.js). The map is the Lambert azimuthal equal-area projection named in world.json
// ("+proj=laea +lat_0=63 +lon_0=15 +ellps=GRS80 +units=km"), shifted so x grows east from x0_km and y grows south
// from y1_km (km, y down). Ellipsoidal formulas from Snyder, "Map Projections — A Working Manual" (1987), pp. 187–190;
// tests/test_maps.py checks them against pyproj. ETRS89 and WGS84 differ by well under a metre here.

const A = 6378137; // GRS80 semi-major axis (m)
const F = 1 / 298.257222101;
const E2 = 2 * F - F * F;
const E = Math.sqrt(E2);
const RAD = Math.PI / 180;

const qOf = (sinPhi) =>
  (1 - E2) * (sinPhi / (1 - E2 * sinPhi * sinPhi) - (1 / (2 * E)) * Math.log((1 - E * sinPhi) / (1 + E * sinPhi)));
const QP = qOf(1);

/** Parse the projection block of world.json into what the formulas need; null if it is not the expected LAEA. */
export function projectionFrom(world) {
  const p = world?.projection || world?.raw?.projection;
  if (!p || typeof p.proj4 !== "string" || !/\+proj=laea\b/.test(p.proj4) || !/\+ellps=GRS80\b/.test(p.proj4)) return null;
  const num = (k) => { const m = p.proj4.match(new RegExp(`\\+${k}=(-?[\\d.]+)`)); return m ? +m[1] : 0; };
  const lat0 = num("lat_0") * RAD, lon0 = num("lon_0") * RAD;
  const units = /\+units=km\b/.test(p.proj4) ? 1000 : 1;
  if (!Number.isFinite(p.x0_km) || !Number.isFinite(p.y1_km)) return null;
  const sinB1 = qOf(Math.sin(lat0)) / QP;
  const b1 = Math.asin(sinB1);
  const Rq = A * Math.sqrt(QP / 2);
  const m1 = Math.cos(lat0) / Math.sqrt(1 - E2 * Math.sin(lat0) ** 2);
  const D = (A * m1) / (Rq * Math.cos(b1));
  return { lat0, lon0, b1, Rq, D, x0: p.x0_km * 1000, y1: p.y1_km * 1000, units };
}

/** Map position (km, y down) → {lon, lat} in degrees, or null. */
export function mapToLonLat(proj, x, y) {
  if (!proj || !Number.isFinite(x) || !Number.isFinite(y)) return null;
  const X = x * 1000 + proj.x0; // projected metres
  const Y = proj.y1 - y * 1000;
  const { b1, Rq, D, lon0 } = proj;
  const rho = Math.hypot(X / D, D * Y);
  if (rho < 1e-9) return { lon: lon0 / RAD, lat: proj.lat0 / RAD };
  const ce = 2 * Math.asin(Math.min(1, rho / (2 * Rq)));
  const beta = Math.asin(Math.cos(ce) * Math.sin(b1) + (D * Y * Math.sin(ce) * Math.cos(b1)) / rho);
  const lon = lon0 + Math.atan2(X * Math.sin(ce), D * rho * Math.cos(b1) * Math.cos(ce) - D * D * Y * Math.sin(b1) * Math.sin(ce));
  const e4 = E2 * E2, e6 = e4 * E2;
  const lat = beta + (E2 / 3 + (31 * e4) / 180 + (517 * e6) / 5040) * Math.sin(2 * beta)
    + ((23 * e4) / 360 + (251 * e6) / 3780) * Math.sin(4 * beta) + ((761 * e6) / 45360) * Math.sin(6 * beta);
  return { lon: lon / RAD, lat: lat / RAD };
}

/** {lon, lat} in degrees → map position {x, y} (km, y down), or null. */
export function lonLatToMap(proj, lon, lat) {
  if (!proj || !Number.isFinite(lon) || !Number.isFinite(lat)) return null;
  const { b1, Rq, D, lon0 } = proj;
  const beta = Math.asin(qOf(Math.sin(lat * RAD)) / QP);
  const dl = lon * RAD - lon0;
  const B = Rq * Math.sqrt(2 / (1 + Math.sin(b1) * Math.sin(beta) + Math.cos(b1) * Math.cos(beta) * Math.cos(dl)));
  const X = B * D * Math.cos(beta) * Math.sin(dl);
  const Y = (B / D) * (Math.cos(b1) * Math.sin(beta) - Math.sin(b1) * Math.cos(beta) * Math.cos(dl));
  return { x: (X - proj.x0) / 1000, y: (proj.y1 - Y) / 1000 };
}
