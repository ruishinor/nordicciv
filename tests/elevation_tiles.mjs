import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Camera } from "../web/js/camera.js";
import { parseHash, formatHash } from "../web/js/app/urlstate.js";
import { ElevationTiles, validateTerrainIndex, decodeElevation, triangleHeight } from "../web/js/render/elevation-tiles.js";
import { buildSurfaceMesh, surfaceHeight, intersectSurface, MAX_SURFACE_VERTICES } from "../web/js/render/terrain-surface.js";

const root = new URL("../web/terrain/", import.meta.url);
const doc = JSON.parse(readFileSync(new URL("index.json", root)));
const projection = JSON.parse(readFileSync(new URL("../web/data/world.json", import.meta.url))).projection;
const bytes = t => { const b = readFileSync(new URL(t.path, root)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength); };
function loaded() {
  const field = new ElevationTiles(projection, null);
  field.index = doc; field.descriptors = new Map(doc.tiles.map(t => [t.key, t])); field.level = 2;
  for (const t of doc.tiles) field.cache.set(t.key, { ...t, data: decodeElevation(bytes(t), t, doc.levels[t.level].samples) });
  field.wanted.add(doc.tiles[0].key);
  return field;
}

test("manifest rejects a foreign projection, paths, duplicate keys and oversized tiles", () => {
  assert.equal(validateTerrainIndex(doc, projection), doc);
  for (const change of [d => d.projection.x0_km++, d => d.tiles[0].path = "../data/world.json",
    d => d.tiles.push(d.tiles[0]), d => d.tiles[0].bytes++]) {
    const bad = structuredClone(doc); change(bad); assert.throws(() => validateTerrainIndex(bad, projection));
  }
  const t = doc.tiles[0]; assert.throws(() => decodeElevation(new ArrayBuffer(2), t, 11));
  const bad = bytes(t); new DataView(bad).setInt16(0, -32768, true);
  assert.throws(() => decodeElevation(bad, t, 11));
});

test("fine tiles contain additional measured height variation and continuous shared edges", () => {
  const field = loaded(), fallback = () => 100;
  for (const r of doc.regions) {
    const [x0, y0, x1, y1] = r.bounds, x = (x0 + x1) / 2, y = (y0 + y1) / 2 + 0.13;
    assert.ok(Math.abs(field.sample(x - 1e-8, y, fallback) - field.sample(x + 1e-8, y, fallback)) < 0.001);
    const fine = field.sample(x + 0.63, y, fallback);
    field.level = 0; const coarse = field.sample(x + 0.63, y, fallback); field.level = 2;
    assert.notEqual(fine, coarse, r.id);
    // Remove the right-hand fine tile: The fine left edge must meet its parent, without a crack.
    const k = `2-${Math.floor(x / 3.84)}-${Math.floor(y / 3.84)}`;
    const removed = field.cache.get(k); field.cache.delete(k);
    assert.ok(Math.abs(field.sample(x - 1e-8, y, fallback) - field.sample(x + 1e-8, y, fallback)) < 0.001);
    field.cache.set(k, removed);
  }
});

test("rectangular meshes, normals and triangle picking use the same heights", () => {
  const field = loaded(), b = doc.regions[1].bounds;
  const vp = {x0:b[0]+5,y0:b[1]+5,x1:b[0]+7,y1:b[1]+6.2,s:720};
  const mesh = buildSurfaceMesh(field, () => 100, vp, 35);
  assert.ok(mesh.vertices <= MAX_SURFACE_VERTICES);
  assert.notEqual(mesh.cols, mesh.rows);
  assert.ok(mesh.positions.every(Number.isFinite)); assert.ok(mesh.shades.every(Number.isFinite));
  const cam = new Camera(2000, 3000); cam.resize(1440, 900); cam.scale = 720; cam.setPitch(35);
  cam.elevationAt = (x, y) => surfaceHeight(mesh, x, y);
  cam.surfaceRay = (x, y, k) => intersectSurface(mesh, x, y, k);
  cam.x = (vp.x0 + vp.x1)/2; cam.y = (vp.y0 + vp.y1)/2;
  for (let sx = 300; sx <= 1100; sx += 200) for (let sy = 100; sy < 800; sy += 100) {
    const world = cam.toWorld(sx, sy), screen = cam.toScreenSurface(...world);
    assert.ok(Math.hypot(screen[0] - sx, screen[1] - sy) < 0.02, `${sx},${sy}`);
  }
});

test("steep and occluded terrain picks the nearest triangle instead of iterating away", () => {
  const mesh = { x0:0, y0:0, x1:1, y1:4, step:1, cols:2, rows:5,
    heights: new Float32Array([0,0, 3000,3000, 0,0, 3000,3000, 0,0]) };
  const hit = intersectSurface(mesh, 0.5, 0.5, 0.001);
  assert.ok(hit > 3 && hit < 4, `Front-most intersection: ${hit}`);
  assert.ok(Math.abs(hit - surfaceHeight(mesh, 0.5, hit)*0.001 - 0.5) < 1e-9);
  assert.equal(triangleHeight(new Float32Array([0,0, 10,10, 20,20]), 2, 0.5, 1.5), 15);
});

test("close camera URLs preserve sub-metre positions and old links still parse", () => {
  const at = [600.123456, 1400.345678, 11.123456];
  const restored = parseHash(formatHash({at})).at;
  assert.ok(Math.abs(at[0]-restored[0]) < 0.0001 && Math.abs(at[1]-restored[1]) < 0.0001);
  assert.deepEqual(parseHash("#city=NO-0301&at=600,1400,4").at, [600,1400,4]);
});

test("request concurrency, eviction, cancellation and failure retries stay bounded", async () => {
  let active = 0, peak = 0;
  const fetcher = async (url, {signal}) => {
    active++; peak = Math.max(peak, active);
    await new Promise(r => setTimeout(r, 2)); active--;
    if (signal.aborted) throw new Error("Aborted");
    const t = doc.tiles.find(t => url.endsWith(t.path));
    return {ok:true,arrayBuffer:async()=>bytes(t)};
  };
  const field = new ElevationTiles(projection, null, {fetcher, limits:{entries:12,bytes:450000,requests:2}});
  field.index = doc; field.descriptors = new Map(doc.tiles.map(t => [t.key,t]));
  const settled = async () => { for (let i=0;i<300 && field.stats().pending;i++) await new Promise(r=>setTimeout(r,3)); assert.equal(field.stats().pending,0); };
  for (const region of [...doc.regions, ...doc.regions]) {
    const b=region.bounds;
    field.update({x0:b[0]+3,y0:b[1]+3,x1:b[0]+8,y1:b[1]+8,s:720},24); await settled();
    assert.ok(field.bytes <= 450000); assert.ok(field.cache.size <= 12);
  }
  assert.ok(peak <= 2); assert.ok(field.evictions > 0);
  field.fetcher = async () => { throw new Error("Unavailable"); };
  field.cache.clear(); field.bytes=0;
  const b=doc.regions[0].bounds;
  field.update({x0:b[0]+3,y0:b[1]+3,x1:b[0]+4,y1:b[1]+4,s:720}); await settled();
  assert.ok(field.failed.size > 0);
  assert.equal(field.sample(b[0]+3.5,b[1]+3.5,()=>123),123);
  field.dispose(); assert.equal(field.bytes,0); assert.equal(field.cache.size,0);
});
