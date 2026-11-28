import { terrainGrain } from "./landscape.js";
// Continuous landscape and administrative geometry for the static map (NC-V01–V03, NC-T04).
//
//  * relief: a shaded-relief land-cover image painted by the pipeline (pipeline/build/relief.py) from the same 1 km
//    evidence as the hexes: L0 = one image at 1 km/px, L1 = 512-px tiles at 0.5 km/px loaded only when zoomed in,
//    gray = hillshade without colour for Analyze mode. The sea is transparent so the water art shows through.
//  * munis: municipal polygons (pipeline/build/munis.py) for borders, selection, hit-testing and municipal
//    choropleths, at three simplification levels.
//  * coast: shore lines traced from the relief land mask, stroked at close zoom for a crisp edge.
//
// Everything here is optional: before the files arrive (or if they are missing) the map draws as hex tiles.

import { initIllustration, drawIllustration, ILLUSTRATE_MIN } from "./illustrate.js";

let state = null; // {index, L0, gray, tiles: Map(key -> {img, ok}), munis, coast, invalidate}
const tileKey = (x, y) => `${x}_${y}`;

export function initRelief(loadJSON, invalidate) {
  if (state) return state;
  state = { index: null, L0: null, gray: null, tiles: new Map(), munis: null, coast: null, invalidate, ready: false };
  loadJSON("relief/index", true).then((idx) => {
    if (!idx) return;
    state.index = idx;
    initIllustration(idx, invalidate);
    const l0 = idx.levels.find((l) => l.id === "L0");
    state.L0 = loadImage(`data/${l0.path}`, () => { state.ready = true; invalidate(); });
    if (idx.gray) state.gray = loadImage(`data/${idx.gray.path}`, invalidate);
    if (idx.sea) state.sea = loadImage(`data/${idx.sea.path}`, invalidate);
  }).catch((e) => console.warn("relief unavailable", e));
  loadJSON("munis", true).then((m) => { if (m) { state.munis = decodeMunis(m); invalidate(); } });
  loadJSON("coast", true).then((c) => { if (c) { state.coast = decodeLines(c); invalidate(); } });
  loadJSON("borders", true).then((b) => {
    if (!b) return;
    state.borders = { country: decodeLines({ lines: b.country, scale: b.scale }), region: decodeLines({ lines: b.region, scale: b.scale }),
      municipality: decodeLines({ lines: b.municipality, scale: b.scale }) };
    invalidate();
  });
  return state;
}

function loadImage(src, onload) {
  const img = new Image();
  img.decoding = "async";
  img.onload = () => { img._ok = true; onload?.(); };
  img.onerror = () => { img._ok = false; };
  img.src = src;
  return img;
}

export const reliefReady = () => !!(state && state.ready && state.L0?._ok);
export const seaReady = () => !!(state?.sea?._ok);

/** The continuous sea (Natural Earth depth bands), in world units; replaces the hex water tiles under the relief. */
export function drawSea(ctx) {
  if (!seaReady()) return false;
  const m = state.index.sea;
  ctx.save();
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(state.sea, 0, 0, m.size[0] * m.km_per_px, m.size[1] * m.km_per_px);
  ctx.restore();
  return true;
}
export const reliefState = () => state;

/** Draw the colour relief (explore) or the gray hillshade (analyze) into ctx, which is in world units (km). */
export function drawRelief(ctx, vp, { gray = false } = {}) {
  if (!reliefReady()) return false;
  const idx = state.index;
  const l0 = idx.levels[0];
  ctx.save();
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
  if (gray) {
    if (!state.gray?._ok) { ctx.restore(); return false; }
    const [w0, h0] = idx.gray.size;
    ctx.drawImage(state.gray, 0, 0, w0 * idx.gray.km_per_px, h0 * idx.gray.km_per_px);
    ctx.restore();
    return true;
  }
  const devPerKm = vp.s * vp.dpr;
  const [w0, h0] = l0.size;
  // L0 always underneath (no holes while tiles load); L1 on top once one L0 pixel spans more than ~1.3 device px
  ctx.drawImage(state.L0, 0, 0, w0 * l0.km_per_px, h0 * l0.km_per_px);
  const l1 = idx.levels[1];
  if (l1 && devPerKm * l0.km_per_px > 1.3) {
    const span = l1.tile_px * l1.km_per_px;
    const tx0 = Math.floor(vp.x0 / span), tx1 = Math.floor(vp.x1 / span);
    const ty0 = Math.floor(vp.y0 / span), ty1 = Math.floor(vp.y1 / span);
    const have = state.tilesSet || (state.tilesSet = new Set(l1.tiles.map(([x, y]) => tileKey(x, y))));
    for (let ty = ty0; ty <= ty1; ty++) {
      for (let tx = tx0; tx <= tx1; tx++) {
        const k = tileKey(tx, ty);
        if (!have.has(k)) continue;
        let t = state.tiles.get(k);
        if (!t) {
          t = loadImage(`data/${l1.path.replace("{x}", tx).replace("{y}", ty)}`, state.invalidate);
          state.tiles.set(k, t);
        }
        if (t._ok) {
          // overlap by a fraction of a pixel so tile seams never show
          const e = 0.5 * l1.km_per_px / l1.tile_px;
          ctx.drawImage(t, tx * span - e, ty * span - e, span + 2 * e, span + 2 * e);
        }
      }
    }
  }
  ctx.restore();
  return true;
}

// ---- close-zoom ground texture ------------------------------------------------------------------------------------
// Below 1 km the relief image only interpolates, so close in it reads soft. A neutral grain (canopy speckle and fine
// noise around mid-grey) is blended over the land with soft-light, anchored to the map so it never swims while
// panning, at a scale chosen per zoom bucket so its grain stays at a few device pixels. It carries no information.
let grain = null;
function grainCanvas() {
  if (grain) return grain;
  const N=256,c=document.createElement("canvas");
  c.width=c.height=N;
  const g=c.getContext("2d"),id=g.createImageData(N,N);
  id.data.set(terrainGrain(N));
  g.putImageData(id,0,0);
  grain=c;
  return c;
}

let texLayer = null, grainLayer = null;
const sized = (c, cv) => {
  if (!c || c.width !== cv.width || c.height !== cv.height) { c = document.createElement("canvas"); c.width = cv.width; c.height = cv.height; }
  return c;
};
/** Explore-mode relief with the close-zoom grain; falls back to the plain image when zoomed out.
 *  Composition (each step one drawImage, because a destination-in per tile would erase the other tiles):
 *  1. relief (L0 + L1 tiles) → texLayer;  2. grain pattern → grainLayer, clipped to texLayer's alpha;
 *  3. grainLayer soft-light onto texLayer;  4. texLayer onto the map. */
export function drawReliefTextured(ctx, vp) {
  const devPerKm = vp.s * vp.dpr;
  if (devPerKm < ILLUSTRATE_MIN || typeof DOMMatrix === "undefined") return drawRelief(ctx, vp);
  const cv = ctx.canvas;
  texLayer = sized(texLayer, cv);
  const L = texLayer.getContext("2d");
  L.setTransform(1, 0, 0, 1, 0, 0);
  L.globalCompositeOperation = "source-over";
  L.globalAlpha = 1;
  L.clearRect(0, 0, texLayer.width, texLayer.height);
  L.setTransform(ctx.getTransform());
  if (!drawRelief(L, vp)) return false;
  if (devPerKm >= 3.5) {
    grainLayer = sized(grainLayer, cv);
    const G = grainLayer.getContext("2d");
    G.setTransform(1, 0, 0, 1, 0, 0);
    G.globalCompositeOperation = "source-over";
    G.clearRect(0, 0, grainLayer.width, grainLayer.height);
    G.setTransform(ctx.getTransform());
    // pattern scale: one grain pixel ≈ 1.3 device px, quantised to powers of two (no swimming between renders)
    const kmPerPx = Math.pow(2, Math.round(Math.log2(1.3 / devPerKm)));
    const pat = G.createPattern(grainCanvas(), "repeat");
    pat.setTransform(new DOMMatrix([kmPerPx, 0, 0, kmPerPx, 0, 0]));
    G.fillStyle = pat;
    G.fillRect(vp.x0, vp.y0, vp.x1 - vp.x0, vp.y1 - vp.y0);
    G.setTransform(1, 0, 0, 1, 0, 0);
    G.globalCompositeOperation = "destination-in";
    G.drawImage(texLayer, 0, 0);
    L.setTransform(1, 0, 0, 1, 0, 0);
    L.globalCompositeOperation = "soft-light";
    L.globalAlpha = Math.min(0.6, (devPerKm - 3.5) / 8 + 0.25);
    L.drawImage(grainLayer, 0, 0);
    L.globalAlpha = 1;
    L.globalCompositeOperation = "source-over";
    L.setTransform(ctx.getTransform());
  }
  // illustrative ground cover (World style): trees, fields, scree, mires, heath through the 1 km cover masks
  drawIllustration(L, vp, devPerKm);
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.drawImage(texLayer, 0, 0);
  ctx.restore();
  return true;
}

// ---- municipal polygons --------------------------------------------------------------------------------------
function decodeRing(arr, scale) {
  const n = arr.length / 2;
  const out = new Float32Array(arr.length);
  let x = 0, y = 0;
  for (let k = 0; k < n; k++) {
    x += arr[2 * k];
    y += arr[2 * k + 1];
    out[2 * k] = x * scale;
    out[2 * k + 1] = y * scale;
  }
  return out;
}

function decodeMunis(m) {
  const feats = m.features.map((f) => ({
    id: f.id, bbox: f.bbox, label: f.label, area: f.area_km2,
    levels: [f.rings, f.r1, f.r2].map((rs) => (rs || []).map((r) => decodeRing(r, m.scale))),
    paths: [null, null, null],
  }));
  // a coarse bucket grid over bounding boxes for hit-testing
  const G = 40; // km
  const grid = new Map();
  feats.forEach((f, k) => {
    for (let gy = Math.floor(f.bbox[1] / G); gy <= Math.floor(f.bbox[3] / G); gy++)
      for (let gx = Math.floor(f.bbox[0] / G); gx <= Math.floor(f.bbox[2] / G); gx++) {
        const key = gx + "," + gy;
        if (!grid.has(key)) grid.set(key, []);
        grid.get(key).push(k);
      }
  });
  return { feats, byId: new Map(feats.map((f) => [f.id, f])), grid, G, levels: m.levels };
}

export const munisReady = () => !!state?.munis;
export const muniFeature = (id) => state?.munis?.byId.get(id) || null;
export const muniFeatures = () => state?.munis?.feats || [];

/** Simplification level for a zoom: tolerance must stay under about half a device pixel. */
export function muniLevel(devPerKm) {
  const lv = state?.munis?.levels || [0.08, 0.4, 1.6];
  for (let k = lv.length - 1; k >= 0; k--) if (lv[k] * devPerKm < 0.6) return k;
  return 0;
}

export function muniPath(f, level) {
  if (f.paths[level]) return f.paths[level];
  const p = new Path2D();
  for (const r of f.levels[level]) {
    p.moveTo(r[0], r[1]);
    for (let k = 2; k < r.length; k += 2) p.lineTo(r[k], r[k + 1]);
    p.closePath();
  }
  f.paths[level] = p;
  return p;
}

function inRing(r, x, y) {
  let inside = false;
  for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) {
    const xi = r[i], yi = r[i + 1], xj = r[j], yj = r[j + 1];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Municipality id at a map point (km), from the full-detail polygons; null if none. Even–odd over all rings, so
 *  holes (lakes, enclaves such as Frederiksberg inside Copenhagen) are respected. */
export function muniAt(x, y) {
  const M = state?.munis;
  if (!M) return null;
  const cand = M.grid.get(Math.floor(x / M.G) + "," + Math.floor(y / M.G)) || [];
  let best = null;
  for (const k of cand) {
    const f = M.feats[k];
    const b = f.bbox;
    if (x < b[0] || x > b[2] || y < b[1] || y > b[3]) continue;
    let inside = false;
    for (const r of f.levels[0]) if (inRing(r, x, y)) inside = !inside;
    if (inside && (!best || f.area < best.area)) best = f; // the smaller one wins if simplified rings overlap
  }
  return best ? best.id : null;
}

/** Nearest municipality within `tolKm` of a point (for taps on tiny islands); null if none. */
export function muniNear(x, y, tolKm) {
  const hit = muniAt(x, y);
  if (hit || !state?.munis) return hit;
  let best = null, bd = tolKm * tolKm;
  for (const f of state.munis.feats) {
    const b = f.bbox;
    if (x < b[0] - tolKm || x > b[2] + tolKm || y < b[1] - tolKm || y > b[3] + tolKm) continue;
    for (const r of f.levels[0]) {
      for (let i = 0; i < r.length; i += 2) {
        const d = (r[i] - x) ** 2 + (r[i + 1] - y) ** 2;
        if (d < bd) { bd = d; best = f.id; }
      }
    }
  }
  return best;
}

// ---- coast lines -----------------------------------------------------------------------------------------------
function decodeLines(c) {
  return c.lines.map((l) => {
    const r = decodeRing(l, c.scale);
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < r.length; i += 2) {
      x0 = Math.min(x0, r[i]); x1 = Math.max(x1, r[i]); y0 = Math.min(y0, r[i + 1]); y1 = Math.max(y1, r[i + 1]);
    }
    return { r, b: [x0, y0, x1, y1] };
  });
}

export const bordersReady = () => !!state?.borders;
export const fallbackHexes = () => {
  if (!state?.index) return null;
  return state.fallback || (state.fallback = new Set(state.index.hex_fallback || []));
};

/** Stroke border lines of one kind ("country" | "region" | "municipality") inside the viewport. */
export function drawBorderLines(ctx, vp, kind, { width, color, dash = null, surfaceY = null }) {
  const L = state?.borders?.[kind];
  if (!L) return;
  strokeLines(ctx, vp, L, width, color, dash, false, surfaceY);
}

/** Stroke the shore lines inside the viewport (world units). */
export function drawCoast(ctx, vp, { width, color, surfaceY = null }) {
  if (!state?.coast) return;
  strokeLines(ctx, vp, state.coast, width, color, null, true, surfaceY);
}

// smooth = curves through the midpoints of the traced segments (the shore traced from a 0.5 km raster would otherwise
// show its vertices as corners at close zoom)
function strokeLines(ctx, vp, lines, width, color, dash = null, smooth = false, surfaceY = null) {
  ctx.beginPath();
  for (const { r, b } of lines) {
    if (b[2] < vp.x0 || b[0] > vp.x1 || b[3] < vp.y0 || b[1] > vp.y1) continue;
    const n = r.length;
    if (!smooth || n < 6 || surfaceY) {
      ctx.moveTo(r[0], surfaceY ? surfaceY(r[0], r[1]) : r[1]);
      for (let k = 2; k < n; k += 2) {
        const x0 = r[k - 2], y0 = r[k - 1], x1 = r[k], y1 = r[k + 1];
        if (surfaceY && (Math.max(x0, x1) < vp.x0 || Math.min(x0, x1) > vp.x1 ||
            Math.max(y0, y1) < vp.y0 - 0.2 || Math.min(y0, y1) > vp.y1 + 4)) {
          ctx.moveTo(x1, surfaceY(x1, y1));
          continue;
        }
        const steps = surfaceY ? Math.ceil(Math.hypot(x1 - x0, y1 - y0) / Math.max(0.03, 3 / vp.s)) : 1;
        for (let j = 1; j <= steps; j++) {
          const x = x0 + (x1 - x0) * j / steps, y = y0 + (y1 - y0) * j / steps;
          ctx.lineTo(x, surfaceY ? surfaceY(x, y) : y);
        }
      }
      continue;
    }
    const closed = r[0] === r[n - 2] && r[1] === r[n - 1];
    if (closed) ctx.moveTo((r[n - 4] + r[0]) / 2, (r[n - 3] + r[1]) / 2);
    else ctx.moveTo(r[0], r[1]);
    for (let k = closed ? 0 : 2; k < n - 2; k += 2) ctx.quadraticCurveTo(r[k], r[k + 1], (r[k] + r[k + 2]) / 2, (r[k + 1] + r[k + 3]) / 2);
    if (!closed) ctx.lineTo(r[n - 2], r[n - 1]);
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.setLineDash(dash || []);
  ctx.stroke();
  ctx.setLineDash([]);
}
