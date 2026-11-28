// Bounded, same-origin elevation tiles. These assets are separate from municipal statistics.
import { physicalLodForWidth, terrainLevelForWidth } from "./surface-contract.js";

export const TILE_LIMITS = Object.freeze({ entries: 96, bytes: 8 * 1024 * 1024, requests: 4 });
const smooth = (t) => { t = Math.min(1, Math.max(0, t)); return t * t * (3 - 2 * t); };
const key = (level, x, y) => `${level}-${x}-${y}`;

export function validateTerrainIndex(doc, projection) {
  if (doc?.version !== 1 || doc.tileSpanKm !== 3.84 || doc.heightUnitM !== 0.25 ||
      JSON.stringify(doc.projection) !== JSON.stringify(projection) || !Array.isArray(doc.tiles) ||
      doc.tiles.length > 4096 || !Array.isArray(doc.regions) || doc.regions.length > 32 ||
      JSON.stringify(doc.levels?.map(l => [l.id, l.stepKm, l.samples])) !== JSON.stringify([[0, 0.48, 11], [1, 0.12, 35], [2, 0.03, 131]])) {
    throw new Error("Unsupported terrain index or map projection");
  }
  const seen = new Set();
  for (const t of doc.tiles) {
    const n = doc.levels[t.level]?.samples;
    if (!Number.isInteger(t.x) || !Number.isInteger(t.y) || t.x < 0 || t.y < 0 || t.x > 1000 || t.y > 1000 ||
        !n || t.key !== key(t.level, t.x, t.y) || seen.has(t.key) ||
        t.bytes !== n * n * 2 || !/^[a-f0-9]{64}$/.test(t.sha256) ||
        t.path !== `tiles/${t.key}-${t.sha256.slice(0, 12)}.bin`) throw new Error("Invalid terrain tile record");
    seen.add(t.key);
  }
  for (const r of doc.regions) {
    if (!Array.isArray(r.bounds) || r.bounds.length !== 4 || !r.bounds.every(Number.isFinite) ||
        !(r.bounds[2] > r.bounds[0] && r.bounds[3] > r.bounds[1])) throw new Error("Invalid terrain coverage");
  }
  return doc;
}

export function decodeElevation(buffer, descriptor, samples) {
  if (buffer.byteLength !== descriptor.bytes) throw new Error("Incomplete elevation tile");
  const view = new DataView(buffer), data = new Int16Array(samples * samples);
  for (let i = 0; i < data.length; i++) {
    const value = view.getInt16(i * 2, true);
    if (value < -800 || value > 16000) throw new Error("Invalid elevation sample");
    data[i] = value;
  }
  return data;
}

// The same triangle diagonal as the GPU mesh, including at tile boundaries.
export function triangleHeight(a, n, u, v) {
  const x = Math.min(n - 2, Math.max(0, Math.floor(u))), y = Math.min(a.length / n - 2, Math.max(0, Math.floor(v)));
  const fx = Math.min(1, Math.max(0, u - x)), fy = Math.min(1, Math.max(0, v - y));
  const i = y * n + x, h00 = a[i], h10 = a[i + 1], h01 = a[i + n], h11 = a[i + n + 1];
  return fx + fy <= 1 ? h00 + fx * (h10 - h00) + fy * (h01 - h00) :
    h11 + (1 - fx) * (h01 - h11) + (1 - fy) * (h10 - h11);
}

export class ElevationTiles {
  constructor(projection, onChange, { fetcher = globalThis.fetch?.bind(globalThis), limits = TILE_LIMITS } = {}) {
    this.projection = projection; this.onChange = onChange; this.fetcher = fetcher; this.limits = limits;
    this.index = null; this.descriptors = new Map(); this.cache = new Map(); this.running = new Map();
    this.failed = new Map(); this.wanted = new Set(); this.queue = []; this.bytes = 0; this.peakBytes = 0;
    this.revision = 0; this.disposed = false; this.error = null; this.level = -1; this.widthKm = Infinity; this.evictions = 0;
  }

  async init() {
    this.indexController = new AbortController();
    const timeout = setTimeout(() => this.indexController.abort(), 15000);
    try {
      const response = await this.fetcher("terrain/index.json", { signal: this.indexController.signal });
      if (!response.ok) throw new Error(`Terrain index: HTTP ${response.status}`);
      const doc = validateTerrainIndex(await response.json(), this.projection);
      if (this.disposed) return;
      this.index = doc;
      this.descriptors = new Map(doc.tiles.map(t => [t.key, t]));
      this.revision++; this.onChange?.();
    } catch (e) {
      if (!this.disposed) { this.error = "Detailed terrain could not load. Showing the existing elevation."; this.onChange?.(); }
    } finally { clearTimeout(timeout); }
  }

  update(vp, pitch = 0) {
    if (!this.index || this.disposed) return;
    this.widthKm = Number.isFinite(vp.widthKm) ? vp.widthKm :
      (Number.isFinite(vp.cssW) && vp.s > 0 ? vp.cssW / vp.s : Infinity);
    this.level = terrainLevelForWidth(this.widthKm);
    const span = this.index.tileSpanKm;
    const yPad = 4 * Math.tan(pitch * Math.PI / 180);
    const desired = [];
    if (this.level >= 0 && vp.s >= 8) for (const t of this.descriptors.values()) {
      if (t.level > this.level || (t.x + 1) * span < vp.x0 || t.x * span > vp.x1 ||
          (t.y + 1) * span < vp.y0 - 0.2 || t.y * span > vp.y1 + yPad) continue;
      desired.push(t);
    }
    const cx = (vp.x0 + vp.x1) / (2 * span), cy = (vp.y0 + vp.y1) / (2 * span);
    // Parents arrive first. Near tiles are preferred if a very wide viewport exceeds the cap.
    desired.sort((a, b) => a.level - b.level || Math.hypot(a.x - cx, a.y - cy) - Math.hypot(b.x - cx, b.y - cy));
    this.wanted = new Set(desired.slice(0, this.limits.entries).map(t => t.key));
    for (const [id, controller] of this.running) if (!this.wanted.has(id)) controller.abort();
    for (const id of this.wanted) if (this.cache.has(id)) {
      const tile = this.cache.get(id); this.cache.delete(id); this.cache.set(id, tile);
    }
    this.queue = desired.filter(t => this.wanted.has(t.key) && !this.cache.has(t.key) && !this.running.has(t.key) &&
      (this.failed.get(t.key) || 0) < Date.now());
    this.pump();
  }

  pump() {
    while (!this.disposed && this.running.size < this.limits.requests && this.queue.length) {
      const t = this.queue.shift();
      if (!this.wanted.has(t.key)) continue;
      const controller = new AbortController();
      this.running.set(t.key, controller);
      void this.load(t, controller);
    }
  }

  async load(t, controller) {
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const digest = btoa(String.fromCharCode(...t.sha256.match(/../g).map(s => parseInt(s, 16))));
      const response = await this.fetcher(`terrain/${t.path}`, { signal: controller.signal, integrity: `sha256-${digest}` });
      if (!response.ok) throw new Error(`Elevation tile: HTTP ${response.status}`);
      const data = decodeElevation(await response.arrayBuffer(), t, this.index.levels[t.level].samples);
      if (this.disposed || controller.signal.aborted || !this.wanted.has(t.key)) return;
      while (this.cache.size >= this.limits.entries || this.bytes + data.byteLength > this.limits.bytes) {
        const victim = [...this.cache.keys()].find(id => !this.wanted.has(id));
        if (!victim) return;
        this.bytes -= this.cache.get(victim).data.byteLength; this.cache.delete(victim); this.evictions++;
      }
      this.cache.set(t.key, { ...t, data }); this.bytes += data.byteLength;
      this.peakBytes = Math.max(this.peakBytes, this.bytes); this.failed.delete(t.key); this.revision++;
      this.onChange?.();
    } catch (e) {
      if (!this.disposed && this.wanted.has(t.key)) { this.failed.set(t.key, Date.now() + 30000); this.onChange?.(); }
    } finally {
      clearTimeout(timeout); this.running.delete(t.key); this.pump();
    }
  }

  regionCoverage(x, y) {
    let weight = 0;
    for (const r of this.index?.regions || []) {
      const [x0, y0, x1, y1] = r.bounds;
      weight = Math.max(weight, smooth(Math.min(x - x0, y - y0, x1 - x, y1 - y) / 0.96));
    }
    return weight;
  }

  sampleAt(x, y, fallback) {
    const span = this.index?.tileSpanKm || 3.84, tx = Math.floor(x / span), ty = Math.floor(y / span);
    const dx = x - tx * span, dy = y - ty * span;
    let height = fallback(x, y);
    let coverage = 0;
    for (let level = 0; level <= this.level; level++) {
      const tile = this.cache.get(key(level, tx, ty));
      if (!tile) continue;
      const spec = this.index.levels[level];
      const h = triangleHeight(tile.data, spec.samples, dx / spec.stepKm + 1, dy / spec.stepKm + 1) * 0.25;
      let weight = this.regionCoverage(x, y);
      // Fade into the parent at a missing neighbour. One continuous viewport grid prevents T-junctions.
      for (const [nx, ny, distance] of [[tx - 1, ty, dx], [tx + 1, ty, span - dx], [tx, ty - 1, dy], [tx, ty + 1, span - dy]]) {
        if (!this.cache.has(key(level, nx, ny))) weight = Math.min(weight, smooth(distance / 0.48));
      }
      if (weight <= 0) continue;
      height += (h - height) * weight;
      coverage += (1 - coverage) * weight;
    }
    return { elevationM: height, coverage };
  }

  sample(x, y, fallback) { return this.sampleAt(x, y, fallback).elevationM; }

  coverage(x, y) { return this.sampleAt(x, y, () => 0).coverage; }

  dispose() {
    this.disposed = true; this.indexController?.abort();
    for (const controller of this.running.values()) controller.abort();
    this.queue = []; this.wanted.clear(); this.cache.clear(); this.bytes = 0;
  }

  stats() {
    return { entries: this.cache.size, bytes: this.bytes, peakBytes: this.peakBytes, pending: this.running.size + this.queue.length,
      requests: this.running.size, failed: this.failed.size, level: this.level,
      spacingM: this.level < 0 ? null : [480, 120, 30][this.level], widthKm: this.widthKm,
      physicalLod: physicalLodForWidth(this.widthKm),
      loadedByLevel: [0, 1, 2].map(l => [...this.cache.values()].filter(t => t.level === l).length),
      limits: this.limits, evictions: this.evictions, error: this.error };
  }
}
