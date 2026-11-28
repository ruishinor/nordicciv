// Illustration layer for the World style (NC-V06).
//
// The relief image carries colour, light and form; close in, it can only interpolate its 0.5–1 km evidence and reads
// soft. This layer paints illustrative ground cover over it: tree crowns where CORINE says forest, a patchwork of
// fields on farmland, scree on bare rock, tufts and pools on mires, low scrub on heath. Each pattern is drawn through
// that class's 1 km mask (relief/cover tiles from pipeline/build/relief.py), so it shows WHAT covers the ground, never
// WHERE a real tree or field is. Patterns are anchored to the map (no swimming while panning) and regenerated per
// zoom bucket so they stay crisp; one light source (north-west) as the relief and the buildings.
//
// Composition per class (one reusable screen-size layer): clear → draw the class's mask tiles (alpha = cover) →
// source-in fill with the class pattern → draw the layer onto the relief. No per-tile destination-in (that would
// erase the other tiles).

const CLASSES = [
  // order = painting order: flat ground first, trees last (they stand on everything)
  // tier 1 = drawn on slow (software-rendered) machines; tier 2 = full detail; tier 0 (no illustrations) when even
// tier 1 takes more than ~200 ms per redraw
  { key: "farm", pack: "A", ch: 2, lo: 0.30, hi: 0.62, tier: 1 },
  { key: "heath", pack: "B", ch: 2, lo: 0.35, hi: 0.75, tier: 2 },
  { key: "wet", pack: "B", ch: 1, lo: 0.30, hi: 0.65, tier: 2 },
  { key: "rock", pack: "B", ch: 0, lo: 0.25, hi: 0.60, tier: 2 },
  { key: "broadleaf", pack: "A", ch: 1, lo: 0.22, hi: 0.50, tier: 2 },
  { key: "conifer", pack: "A", ch: 0, lo: 0.22, hi: 0.50, tier: 1 },
  { key: "urban", pack: "C", ch: 0, lo: 0.30, hi: 0.60, tier: 1 },
];
const PACKS = ["A", "B", "C"];
const MAX_TILES = 8; // decoded tiles kept (6 class masks of 512² each)
export const ILLUSTRATE_MIN = 2.2; // device px per km where the layer starts to fade in

let S = null; // {index, tiles: Map(key -> {A, B, masks}), invalidate}

export function initIllustration(index, invalidate) {
  if (!index?.cover) return;
  S = { cover: index.cover, have: new Set(index.cover.tiles.map(([x, y]) => `${x}_${y}`)), tiles: new Map(), invalidate };
  // paint the pattern tiles ahead of time, one per idle moment, so the first close zoom does not pay for them
  const keys = CLASSES.map((c) => c.key);
  const warm = () => { const k = keys.shift(); if (k) { pattern(k); if (keys.length) later(warm); } };
  setTimeout(() => later(warm), 2500);
}

function loadImg(src, cb) {
  const im = new Image();
  im.decoding = "async";
  im.onload = () => { im._ok = true; cb(); };
  im.onerror = () => { im._ok = false; };
  im.src = src;
  return im;
}

const smooth = (lo, hi, v) => { const t = Math.min(1, Math.max(0, (v - lo) / (hi - lo))); return t * t * (3 - 2 * t); };

/** Split a tile's packed mask images into one alpha canvas per class, in small steps scheduled when the browser is idle
 *  (one pack read or one class per step, ~5–15 ms each), so decoding never blocks a frame for long. The tile is drawn
 *  only when all its classes are ready, and the map is redrawn once per finished tile. */
const OCC = 32; // occupancy grid per tile and class (16 km blocks): classes absent from the view are skipped
const queue = [];
let pumping = false;
function schedule(t) { queue.push(t); if (!pumping) { pumping = true; later(pump); } }
const later = (fn) => (typeof requestIdleCallback === "function" ? requestIdleCallback(fn, { timeout: 120 }) : setTimeout(() => fn(null), 16));
function pump(deadline) {
  const until = performance.now() + (deadline?.timeRemaining ? Math.max(4, Math.min(12, deadline.timeRemaining())) : 8);
  while (queue.length && performance.now() < until) {
    const t = queue[0];
    if (!step(t)) { queue.shift(); if (t.masks) S.invalidate(); }
  }
  if (queue.length) later(pump);
  else pumping = false;
}
// one unit of work; returns false when the tile is complete
function step(t) {
  const N = S.cover.tile_px;
  t.src ||= {};
  t.done ||= {};
  for (const p of PACKS) {
    if (t.src[p]) continue;
    const c = document.createElement("canvas");
    c.width = c.height = N;
    const g = c.getContext("2d", { willReadFrequently: true });
    g.drawImage(t[p], 0, 0);
    t.src[p] = g.getImageData(0, 0, N, N).data;
    t[p] = null; // the decoded image is no longer needed
    return true;
  }
  const cl = CLASSES.find((x) => !t.done[x.key]);
  if (!cl) {
    t.masks = t.done;
    t.src = null;
    return false;
  }
  const c = document.createElement("canvas");
  c.width = c.height = N;
  const g = c.getContext("2d");
  const id = g.createImageData(N, N);
  const d = t.src[cl.pack], o = id.data;
  const lut = cl.lut || (cl.lut = (() => { const l = new Uint8ClampedArray(256); for (let v = 0; v < 256; v++) l[v] = 255 * smooth(cl.lo, cl.hi, v / 255); return l; })());
  const B = OCC, bs = N / B, occ = new Uint8Array(B * B);
  for (let i = 3, j = cl.ch, p = 0; i < o.length; i += 4, j += 4, p++) {
    const a = lut[d[j]];
    o[i] = a;
    if (a > 8) occ[((p / N / bs) | 0) * B + (((p % N) / bs) | 0)] = 1;
  }
  g.putImageData(id, 0, 0);
  c.occ = occ;
  t.done[cl.key] = c;
  return true;
}

function tile(tx, ty) {
  const k = `${tx}_${ty}`;
  if (!S.have.has(k)) return null;
  let t = S.tiles.get(k);
  if (t) { S.tiles.delete(k); S.tiles.set(k, t); return t.masks ? t : null; } // LRU: most recent last
  t = { masks: null };
  const done = () => { if (PACKS.every((p) => t[p]?._ok) && !t.masks && !t.queued) { t.queued = true; schedule(t); } };
  const path = (p) => `data/${S.cover.path.replace("{k}", p).replace("{x}", tx).replace("{y}", ty)}`;
  for (const p of PACKS) t[p] = loadImg(path(p), done);
  S.tiles.set(k, t);
  while (S.tiles.size > MAX_TILES) S.tiles.delete(S.tiles.keys().next().value);
  return null;
}

// ---- patterns ---------------------------------------------------------------------------------------------------
// Deterministic, seamless patterns. At close zoom the artwork keeps a fixed map scale instead of shrinking
// as the camera zooms. Repaint the same artwork at a higher raster density for crisp edges on high-DPI screens.
const PAT = 256;
const cache = new Map();
let season = "off";
const SEASONAL_CLASSES = new Set(["farm", "broadleaf", "conifer"]);
export function seasonForMonth(month) {
  if (!Number.isInteger(month) || month < 1 || month > 12) return "off";
  return month <= 2 || month === 12 ? "winter" : month <= 5 ? "spring" : month <= 8 ? "summer" : "autumn";
}
export function setIllustrationSeason(value) {
  if (!["off", "spring", "summer", "autumn", "winter"].includes(value) || value === season) return false;
  season = value;
  return true;
}
export const illustrationSeason = () => season;
export function seasonalPatternKey(key, raster, value = season) {
  return key + ":" + raster + ":" + (SEASONAL_CLASSES.has(key) ? value : "off");
}
const PATTERN_BUDGET = 12e6; // at most ~48 MB of pattern canvas pixels
let cachedPixels = 0;

/** Logical pattern scale uses CSS pixels so phones and desktops show the same landscape at the same map zoom. */
export function illustrationPatternSpec(cssPerKm, devPerKm) {
  const kmPerPx = Math.max(0.125, 2 ** Math.round(Math.log2(0.75 / cssPerKm)));
  const raster = Math.min(4, Math.max(1, Math.ceil(kmPerPx * devPerKm)));
  return { kmPerPx, raster };
}
function rng(seed) { let s = seed >>> 0 || 1; return () => ((s = (s * 16807) % 2147483647) / 2147483647); }
function canvas(N = PAT, raster = 1) {
  const c = document.createElement("canvas");
  c.width = c.height = N * raster;
  c.getContext("2d").setTransform(raster, 0, 0, raster, 0, 0);
  return c;
}
// draw fn at (x, y) and its wrapped copies so the tile is seamless
function wrapDraw(N, x, y, r, fn) {
  for (const dx of [-N, 0, N]) for (const dy of [-N, 0, N]) {
    const X = x + dx, Y = y + dy;
    if (X + r < 0 || X - r > N || Y + r < 0 || Y - r > N) continue;
    fn(X, Y);
  }
}

function conifer(raster = 1, appearance = "off") {
  const c = canvas(PAT, raster), g = c.getContext("2d"), r = rng(2401);
  const pts = [];
  for (let gy = 0; gy < 18; gy++) for (let gx = 0; gx < 18; gx++) pts.push([(gx + 0.15 + r() * 0.7) * PAT / 18, (gy + 0.1 + r() * 0.8) * PAT / 18, 0.75 + r() * 0.5, r()]);
  pts.sort((a, b) => a[1] - b[1]);
  for (const [x, y, s, v] of pts) wrapDraw(PAT, x, y, 14, (X, Y) => {
    const h = 13 * s, w = 5.2 * s;
    g.fillStyle = "rgba(10,22,18,0.30)"; // ground shadow to the south-east
    g.beginPath(); g.ellipse(X + 2.2 * s, Y + 0.6, w * 0.9, 1.8 * s, 0, 0, 2 * Math.PI); g.fill();
    g.fillStyle = "rgba(85,65,44,0.9)";
    g.fillRect(X - 0.48 * s, Y - 3 * s, 0.96 * s, 3.7 * s);
    const dark = `rgb(${24 + v * 10},${58 + v * 16},${40 + v * 10})`, lit = `rgb(${58 + v * 16},${104 + v * 20},${62 + v * 12})`;
    for (let k = 0; k < 3; k++) { // three tiers, shadowed east half
      const ty = Y - h * (0.18 + 0.27 * k), tw = w * (1 - 0.24 * k), th = h * 0.46;
      g.fillStyle = dark;
      g.beginPath(); g.moveTo(X, ty - th); g.lineTo(X + tw, ty); g.lineTo(X - tw, ty); g.closePath(); g.fill();
      g.fillStyle = appearance === "winter" ? "rgb(151,178,181)" : lit;
      g.beginPath(); g.moveTo(X, ty - th); g.lineTo(X - tw * 0.15, ty); g.lineTo(X - tw, ty); g.closePath(); g.fill();
      // Small branch highlights become visible as the same tree is enlarged.
      g.strokeStyle = appearance === "winter" ? "rgba(228,239,241,0.7)" : "rgba(174,196,126,0.28)"; g.lineWidth = 0.45 * s;
      g.beginPath(); g.moveTo(X - 0.18 * tw, ty - th * 0.45); g.lineTo(X - tw * 0.68, ty - th * 0.09); g.stroke();
    }
  });
  return c;
}

function broadleaf(raster = 1, appearance = "off") {
  const c = canvas(PAT, raster), g = c.getContext("2d"), r = rng(911);
  const pts = [];
  for (let gy = 0; gy < 15; gy++) for (let gx = 0; gx < 15; gx++) pts.push([(gx + 0.1 + r() * 0.8) * PAT / 15, (gy + 0.1 + r() * 0.8) * PAT / 15, 0.8 + r() * 0.45, r()]);
  pts.sort((a, b) => a[1] - b[1]);
  for (const [x, y, s, v] of pts) wrapDraw(PAT, x, y, 14, (X, Y) => {
    const R = 7 * s;
    g.fillStyle = "rgba(12,24,10,0.28)";
    g.beginPath(); g.ellipse(X + 2.5 * s, Y + R * 0.55, R * 0.95, R * 0.38, 0, 0, 2 * Math.PI); g.fill();
    if (appearance === "winter") {
      g.strokeStyle = "rgba(79,66,55,0.85)"; g.lineWidth = 0.9 * s;
      g.beginPath(); g.moveTo(X, Y + R * .55); g.lineTo(X, Y - R * .4);
      for (let j = 0; j < 6; j++) {
        const a = j * Math.PI / 3 + v;
        g.moveTo(X, Y); g.lineTo(X + Math.cos(a) * R * .55, Y + Math.sin(a) * R * .48);
        g.lineTo(X + Math.cos(a + .18) * R * .9, Y + Math.sin(a + .18) * R * .8);
      }
      g.stroke(); return;
    }
    const gr = g.createRadialGradient(X - R * 0.38, Y - R * 0.45, R * 0.1, X, Y - R * 0.1, R * 1.05);
    gr.addColorStop(0, appearance === "autumn" ? "rgb(230,170,71)" : appearance === "spring" ? "rgb(185,210,115)" : `rgb(${150 + v * 20},${178 + v * 14},${86 + v * 10})`);
    gr.addColorStop(0.55, appearance === "autumn" ? "rgb(171,97,35)" : appearance === "spring" ? "rgb(111,157,72)" : `rgb(${84 + v * 18},${128 + v * 16},${52 + v * 8})`);
    gr.addColorStop(1, appearance === "autumn" ? "rgb(93,52,29)" : appearance === "spring" ? "rgb(52,99,43)" : `rgb(${40 + v * 8},${76 + v * 10},${34 + v * 6})`);
    g.fillStyle = gr;
    g.beginPath();
    for (let k = 0; k <= 7; k++) { // a lumpy crown
      const a = (k / 7) * 2 * Math.PI, rr = R * (0.86 + 0.14 * Math.sin(k * 2.3 + v * 6));
      const px = X + Math.cos(a) * rr, py = Y - R * 0.1 + Math.sin(a) * rr * 0.9;
      k ? g.lineTo(px, py) : g.moveTo(px, py);
    }
    g.closePath(); g.fill();
    // Soft crown lobes, in a common light direction rather than a flat green disc.
    for (let j = 0; j < 3; j++) {
      const a = j * 2.1 + v * 3;
      g.fillStyle = j === 0 ? "rgba(202,212,122,0.24)" : "rgba(36,73,36,0.18)";
      g.beginPath(); g.ellipse(X + Math.cos(a) * R * 0.33, Y - R * 0.18 + Math.sin(a) * R * 0.29,
        R * 0.31, R * 0.25, a, 0, 2 * Math.PI); g.fill();
    }
  });
  return c;
}

function farm(raster = 1, appearance = "off") {
  const N = 512, c = canvas(N, raster), g = c.getContext("2d"), r = rng(7177);
  const crops = appearance === "winter" ? [[206,215,215],[181,194,191],[168,155,139],[221,225,221]] :
    appearance === "spring" ? [[137,174,91],[167,192,115],[156,132,96],[194,180,130]] :
    appearance === "autumn" ? [[184,141,79],[159,111,74],[207,177,104],[146,126,83]] :
    [[214,190,108],[176,186,92],[200,164,96],[226,210,150],[150,172,86],[188,150,104],[222,196,120]];
  // rows of fields of varying depth, each row split into fields of varying width (seamless in both directions)
  let y = 0;
  while (y < N) {
    const hgt = Math.min(N - y, 26 + Math.floor(r() * 46));
    let x = 0;
    const off = Math.floor(r() * 40);
    while (x < N) {
      const wd = Math.min(N - x, 30 + Math.floor(r() * 70));
      const col = crops[Math.floor(r() * crops.length)];
      const furrows = r() < 0.55, vert = r() < 0.5;
      for (const dx of [0, -N]) {
        const X = x + off + dx;
        g.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},0.62)`;
        g.fillRect(X, y, wd, hgt);
        if (furrows) { // furrows, identical in both wrapped copies
          g.strokeStyle = "rgba(90,80,40,0.25)"; g.lineWidth = 0.85;
          g.beginPath();
          for (let k = 3; k < (vert ? wd : hgt); k += 4) vert ? (g.moveTo(X + k, y + 2), g.lineTo(X + k, y + hgt - 2)) : (g.moveTo(X + 2, y + k), g.lineTo(X + wd - 2, y + k));
          g.stroke();
        }
        g.strokeStyle = "rgba(62,74,34,0.55)"; g.lineWidth = 1.6; // hedgerow
        if (wd > 2 && hgt > 2) g.strokeRect(X + 0.8, y + 0.8, wd - 1.6, hgt - 1.6);
        if (wd > 12 && hgt > 12) {
          g.strokeStyle = "rgba(246,226,164,0.28)"; g.lineWidth = 0.55;
          g.strokeRect(X + 3, y + 3, wd - 6, hgt - 6);
        }
      }
      x += wd;
    }
    y += hgt;
  }
  // scattered hedgerow trees
  for (let k = 0; k < 90; k++) {
    const x = r() * N, yy = r() * N, R = 2 + r() * 1.6;
    wrapDraw(N, x, yy, 4, (X, Y) => { g.fillStyle = "rgba(48,84,36,0.85)"; g.beginPath(); g.arc(X, Y, R, 0, 2 * Math.PI); g.fill();
      g.fillStyle = "rgba(120,160,70,0.8)"; g.beginPath(); g.arc(X - R * 0.35, Y - R * 0.35, R * 0.45, 0, 2 * Math.PI); g.fill(); });
  }
  return c;
}

function rock(raster = 1) {
  const c = canvas(PAT, raster), g = c.getContext("2d"), r = rng(3301);
  for (let k = 0; k < 120; k++) {
    const x = r() * PAT, y = r() * PAT, s = 3.2 + r() * 5, v = r();
    const off = [];
    for (let j = 0; j < 5; j++) { const a = (j / 5) * 2 * Math.PI + r() * 0.5; off.push([Math.cos(a) * s * (0.7 + r() * 0.5), Math.sin(a) * s * (0.55 + r() * 0.4)]); }
    wrapDraw(PAT, x, y, 14, (X, Y) => {
      const pts = off.map(([dx, dy]) => [X + dx, Y + dy]);
      g.fillStyle = `rgba(${96 + v * 40},${96 + v * 38},${98 + v * 36},0.75)`;
      g.beginPath(); pts.forEach(([px, py], j) => (j ? g.lineTo(px, py) : g.moveTo(px, py))); g.closePath(); g.fill();
      g.strokeStyle = "rgba(235,232,222,0.6)"; g.lineWidth = 1.2; // lit north-west edge
      g.beginPath(); g.moveTo(pts[2][0], pts[2][1]); g.lineTo(pts[3][0], pts[3][1]); g.stroke();
      g.strokeStyle = "rgba(30,32,44,0.45)"; // shadowed south-east edge
      g.beginPath(); g.moveTo(pts[0][0], pts[0][1]); g.lineTo(pts[4][0], pts[4][1]); g.stroke();
    });
  }
  g.strokeStyle = "rgba(40,40,52,0.28)"; g.lineWidth = 1; // cracks
  for (let k = 0; k < 40; k++) {
    let x = r() * PAT, y = r() * PAT;
    g.beginPath(); g.moveTo(x, y);
    for (let j = 0; j < 4; j++) { x += (r() - 0.3) * 9; y += (r() - 0.5) * 6; g.lineTo(x, y); }
    g.stroke();
  }
  return c;
}

function wet(raster = 1) {
  const c = canvas(PAT, raster), g = c.getContext("2d"), r = rng(5501);
  for (let k = 0; k < 70; k++) { // small pools
    const x = r() * PAT, y = r() * PAT, w = 3 + r() * 7;
    wrapDraw(PAT, x, y, 12, (X, Y) => {
      g.fillStyle = "rgba(70,118,140,0.75)"; g.beginPath(); g.ellipse(X, Y, w, w * 0.42, 0, 0, 2 * Math.PI); g.fill();
      g.strokeStyle = "rgba(200,226,226,0.6)"; g.lineWidth = 0.8; g.beginPath(); g.moveTo(X - w * 0.5, Y - 0.6); g.lineTo(X + w * 0.1, Y - 0.6); g.stroke();
    });
  }
  g.strokeStyle = "rgba(92,110,52,0.8)"; g.lineWidth = 1; // sedge tufts
  g.lineWidth = 1.3;
  for (let k = 0; k < 260; k++) {
    const x = r() * PAT, y = r() * PAT;
    wrapDraw(PAT, x, y, 6, (X, Y) => { g.beginPath(); g.moveTo(X - 3, Y - 4.5); g.lineTo(X, Y); g.lineTo(X + 0.7, Y - 6); g.moveTo(X, Y); g.lineTo(X + 3.6, Y - 3.8); g.stroke(); });
  }
  return c;
}

function heath(raster = 1) {
  const c = canvas(PAT, raster), g = c.getContext("2d"), r = rng(6607);
  for (let k = 0; k < 150; k++) {
    const x = r() * PAT, y = r() * PAT, s = 2.6 + r() * 3, v = r();
    wrapDraw(PAT, x, y, 10, (X, Y) => {
      g.fillStyle = `rgba(${110 + v * 40},${100 + v * 30},${60 + v * 20},0.7)`;
      g.beginPath(); g.ellipse(X, Y, s * 1.3, s * 0.8, 0, 0, 2 * Math.PI); g.fill();
      g.fillStyle = "rgba(220,200,140,0.45)"; g.beginPath(); g.arc(X - s * 0.4, Y - s * 0.3, s * 0.45, 0, 2 * Math.PI); g.fill();
    });
  }
  return c;
}

function urban(raster = 1) {
  const c = canvas(PAT, raster), g = c.getContext("2d"), r = rng(8803);
  g.strokeStyle = "rgba(226,220,204,0.55)"; g.lineWidth = 2.2; // streets
  for (let k = 0; k < 6; k++) {
    const y = (k + 0.5) * PAT / 6 + (r() - 0.5) * 8, x = (k + 0.3) * PAT / 6 + (r() - 0.5) * 8;
    g.beginPath(); g.moveTo(0, y); g.lineTo(PAT, y); g.stroke();
    g.beginPath(); g.moveTo(x, 0); g.lineTo(x, PAT); g.stroke();
  }
  const roofs = [[178, 86, 62], [150, 72, 58], [120, 116, 118], [92, 92, 104], [196, 112, 74], [168, 150, 128]];
  for (let k = 0; k < 230; k++) {
    const x = r() * PAT, y = r() * PAT, w = 5 + r() * 6, h = 4 + r() * 4, col = roofs[Math.floor(r() * roofs.length)];
    wrapDraw(PAT, x, y, 14, (X, Y) => {
      g.fillStyle = "rgba(20,20,30,0.35)"; g.fillRect(X + 1.4, Y + 1.4, w, h); // shadow south-east
      g.fillStyle = `rgb(${col[0]},${col[1]},${col[2]})`; g.fillRect(X, Y, w, h);
      g.fillStyle = "rgba(255,240,220,0.35)"; g.fillRect(X, Y, w, h * 0.45); // lit roof slope
      g.strokeStyle = "rgba(40,30,30,0.45)"; g.lineWidth = 0.7; g.beginPath(); g.moveTo(X, Y + h * 0.45); g.lineTo(X + w, Y + h * 0.45); g.stroke();
      if (w > 8) {
        g.fillStyle = "rgba(55,53,51,0.65)"; g.fillRect(X + w * 0.72, Y + h * 0.18, 1.1, 1.3);
        g.fillStyle = "rgba(240,225,195,0.5)"; g.fillRect(X + w * 0.72, Y + h * 0.18, 0.5, 0.8);
      }
    });
  }
  return c;
}

const MAKERS = { conifer, broadleaf, farm, rock, wet, heath, urban };
function pattern(key, raster = 1) {
  const id = seasonalPatternKey(key, raster);
  let c = cache.get(id);
  if (c) { cache.delete(id); cache.set(id, c); return c; }
  c = MAKERS[key](raster, SEASONAL_CLASSES.has(key) ? season : "off");
  const pixels = c.width * c.height;
  while (cache.size && cachedPixels + pixels > PATTERN_BUDGET) {
    const old = cache.keys().next().value, cv = cache.get(old);
    cachedPixels -= cv.width * cv.height;
    cache.delete(old);
  }
  cachedPixels += pixels;
  cache.set(id, c);
  return c;
}

// ---- drawing ----------------------------------------------------------------------------------------------------
let layer = null;

/** Paint the illustration over the relief in L (a screen-size canvas context whose transform is world → device). */
export function drawIllustration(L, vp, devPerKm) {
  if (!S || DETAIL === "off" || devPerKm < ILLUSTRATE_MIN || typeof DOMMatrix === "undefined") return false;
  // A costly regional view must not permanently disable detail when zooming into a much smaller area.
  const quality = vp.s > 6 ? closeQuality : regionalQuality;
  if (quality.tier === 0) return false;
  const fade = Math.min(1, (devPerKm - ILLUSTRATE_MIN) / 1.6);
  const span = S.cover.tile_px * S.cover.km_per_px;
  const tx0 = Math.floor(vp.x0 / span), tx1 = Math.floor(vp.x1 / span), ty0 = Math.floor(vp.y0 / span), ty1 = Math.floor(vp.y1 / span);
  const ready = [];
  for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) { const t = tile(tx, ty); if (t) ready.push([tx, ty, t]); }
  if (!ready.length) return false;
  const cv = L.canvas;
  if (!layer || layer.width !== cv.width || layer.height !== cv.height) { layer = document.createElement("canvas"); layer.width = cv.width; layer.height = cv.height; }
  const G = layer.getContext("2d");
  const T = L.getTransform();
  const { kmPerPx, raster } = illustrationPatternSpec(vp.s, devPerKm);
  const t0 = performance.now();
  const bk = span / OCC;
  let drawn = 0;
  for (const cl of CLASSES) {
    if (cl.tier > quality.tier) continue;
    // world bounding box of this class's occupied blocks inside the view; nothing to draw → skip the class
    let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
    for (const [tx, ty, t] of ready) {
      const occ = t.masks[cl.key].occ;
      const ox = tx * span, oy = ty * span;
      const i0 = Math.max(0, Math.floor((vp.x0 - ox) / bk)), i1 = Math.min(OCC - 1, Math.floor((vp.x1 - ox) / bk));
      const j0 = Math.max(0, Math.floor((vp.y0 - oy) / bk)), j1 = Math.min(OCC - 1, Math.floor((vp.y1 - oy) / bk));
      for (let j = j0; j <= j1; j++) for (let i = i0; i <= i1; i++) {
        if (!occ[j * OCC + i]) continue;
        bx0 = Math.min(bx0, ox + i * bk); by0 = Math.min(by0, oy + j * bk);
        bx1 = Math.max(bx1, ox + (i + 1) * bk); by1 = Math.max(by1, oy + (j + 1) * bk);
      }
    }
    bx0 = Math.max(bx0, vp.x0); by0 = Math.max(by0, vp.y0); bx1 = Math.min(bx1, vp.x1); by1 = Math.min(by1, vp.y1);
    if (!(bx1 > bx0 && by1 > by0)) continue;
    // the same box in device pixels (the transform is a scale and a translation)
    const rx = Math.max(0, Math.floor(T.a * bx0 + T.e)), ry = Math.max(0, Math.floor(T.d * by0 + T.f));
    const rw = Math.min(layer.width, Math.ceil(T.a * bx1 + T.e)) - rx, rh = Math.min(layer.height, Math.ceil(T.d * by1 + T.f)) - ry;
    if (rw <= 0 || rh <= 0) continue;
    G.setTransform(1, 0, 0, 1, 0, 0);
    G.globalCompositeOperation = "source-over";
    G.clearRect(rx, ry, rw, rh);
    G.save();
    G.beginPath();
    G.rect(rx, ry, rw, rh);
    G.clip();
    G.setTransform(T);
    G.imageSmoothingEnabled = true;
    const e = 0.5 * S.cover.km_per_px / S.cover.tile_px;
    for (const [tx, ty, t] of ready) {
      const x0 = tx * span, y0 = ty * span;
      if (x0 > bx1 || y0 > by1 || x0 + span < bx0 || y0 + span < by0) continue;
      G.drawImage(t.masks[cl.key], x0 - e, y0 - e, span + 2 * e, span + 2 * e);
    }
    G.globalCompositeOperation = "source-in";
    const p = G.createPattern(pattern(cl.key, raster), "repeat");
    const k = (cl.key === "farm" ? kmPerPx * 1.6 : kmPerPx) / raster; // same world size at every raster density
    p.setTransform(new DOMMatrix([k, 0, 0, k, 0, 0]));
    G.fillStyle = p;
    G.fillRect(bx0, by0, bx1 - bx0, by1 - by0);
    G.restore();
    L.save();
    L.setTransform(1, 0, 0, 1, 0, 0);
    L.globalAlpha = fade * (cl.key === "farm" ? 0.85 : 1);
    L.globalCompositeOperation = "source-atop"; // respect the relief land mask at coastlines and lakes
    L.drawImage(layer, rx, ry, rw, rh, rx, ry, rw, rh);
    L.restore();
    drawn++;
  }
  // adaptive detail: if illustrating takes too long on this machine (software rendering), draw only the main covers
  const ms = performance.now() - t0;
  quality.cost = quality.cost ? 0.6 * quality.cost + 0.4 * ms : ms;
  if (DETAIL !== "full") {
    if (quality.tier === 2 && quality.cost > 110) quality.tier = 1;
    else if (quality.tier === 1 && quality.cost < 35) quality.tier = 2;
    else if (quality.tier === 1 && quality.cost > 200) quality.tier = 0;
  }
  lastStats = { ms: Math.round(ms), classes: drawn, tier: quality.tier, zoom: vp.s, kmPerPx, raster, cachedPixels, season, at: Math.round(performance.now()) };
  return true;
}

// ?detail=full keeps every class (visual evidence, fast machines); ?detail=off turns the illustrations off
const DETAIL = (() => { try { return new URLSearchParams(location.search).get("detail"); } catch { return null; } })();
const regionalQuality = { tier: 2, cost: 0 }, closeQuality = { tier: 2, cost: 0 };
let lastStats = null;
export const illustrationState = () => S && { tiles: S.tiles.size, decoded: [...S.tiles.values()].filter((t) => t.masks).length, last: lastStats };
