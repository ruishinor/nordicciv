import { triangleHeight } from "./elevation-tiles.js";

export const MAX_SURFACE_VERTICES = 100000;

export function surfaceHeight(mesh, x, y) {
  if (!mesh || x < mesh.x0 || y < mesh.y0 || x > mesh.x1 || y > mesh.y1) return null;
  return triangleHeight(mesh.heights, mesh.cols, (x - mesh.x0) / mesh.step, (y - mesh.y0) / mesh.step);
}

// Intersect an orthographic camera ray with the exact triangle strips sent to WebGL.
// Search from the viewer (south/high elevation) so hidden rear slopes cannot win selection.
export function intersectSurface(mesh, x, groundY, heightScale) {
  if (!mesh || x < mesh.x0 || x >= mesh.x1 || !heightScale) return null;
  const u = (x - mesh.x0) / mesh.step, fx = u - Math.floor(u);
  let upper = Math.min(mesh.y1, groundY + 4000 * heightScale);
  const lower = Math.max(mesh.y0, groundY - 200 * heightScale);
  const f = (y) => y - surfaceHeight(mesh, x, y) * heightScale - groundY;
  let fu = f(upper);
  // A ray crosses each row boundary and then the cell's diagonal, both linear segments.
  for (let row = Math.min(mesh.rows - 2, Math.floor((upper - mesh.y0) / mesh.step)); row >= 0; row--) {
    const base = mesh.y0 + row * mesh.step;
    for (const y of [base + (1 - fx) * mesh.step, base]) {
      const next = Math.max(lower, y);
      if (next >= upper) continue;
      const fl = f(next);
      if (fu >= 0 && fl <= 0) return upper + (next - upper) * fu / (fu - fl || 1);
      upper = next; fu = fl;
      if (next <= lower) return null;
    }
  }
  return null;
}

export function buildSurfaceMesh(tiles, fallback, vp, pitch, exaggeration = 1) {
  if (!tiles.index || vp.s < 8 || !tiles.wanted.size) return null;
  let step = [0.48, 0.12, 0.03][tiles.level];
  const pad = 4 * exaggeration * Math.tan(pitch * Math.PI / 180);
  let x0, y0, cols, rows;
  do {
    x0 = Math.floor(vp.x0 / step) * step;
    y0 = Math.floor((vp.y0 - 0.2) / step) * step;
    cols = Math.ceil((vp.x1 - x0) / step) + 1;
    rows = Math.ceil((vp.y1 + pad - y0) / step) + 1;
    if (cols * rows <= MAX_SURFACE_VERTICES) break;
    step *= 2;
  } while (true);
  const n = cols * rows;
  const heights = new Float32Array(n), coverage = new Float32Array(n);
  // Extra ring keeps lighting identical on neighbouring viewport meshes.
  const ring = new Float32Array((cols + 2) * (rows + 2));
  for (let r = -1; r <= rows; r++) for (let c = -1; c <= cols; c++) {
    ring[(r + 1) * (cols + 2) + c + 1] = tiles.sample(x0 + c * step, y0 + r * step, fallback);
  }
  const positions = new Float32Array(n * 3), colors = new Uint8Array(n * 3), shades = new Float32Array(n);
  const indices = new Uint32Array((cols - 1) * (rows - 1) * 6);
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
    const i = r * cols + c, k = (r + 1) * (cols + 2) + c + 1, h = ring[k];
    heights[i] = h;
    positions.set([c * step, r * step, h / 1000], i * 3);
    coverage[i] = tiles.coverage(x0 + c * step, y0 + r * step);
    const gx = (ring[k + 1] - ring[k - 1]) / (step * 2000);
    const gy = (ring[k + cols + 2] - ring[k - cols - 2]) / (step * 2000);
    const length = Math.hypot(gx * exaggeration, gy * exaggeration, 1);
    const light = Math.max(0, (gx * 0.45 * exaggeration + gy * 0.55 * exaggeration + 0.704) / length);
    shades[i] = 0.48 + 0.57 * light;
    const rock = Math.min(1, Math.max(Math.hypot(gx, gy) * 0.8, (h - 700) / 800));
    const snow = Math.min(1, Math.max(0, (h - 1550) / 450));
    const grass = [120, 145, 92], stone = [155, 153, 138], ice = [222, 229, 225];
    for (let j = 0; j < 3; j++) colors[i * 3 + j] = h <= 0 ? [38, 92, 138][j] :
      (grass[j] * (1 - rock) + stone[j] * rock) * (1 - snow) + ice[j] * snow;
    if (c < cols - 1 && r < rows - 1) {
      const at = (r * (cols - 1) + c) * 6;
      indices.set([i, i + cols, i + 1, i + 1, i + cols, i + cols + 1], at);
    }
  }
  return { positions, colors, shades, coverage, indices, heights, cols, rows, step, x0, y0,
    x1: x0 + (cols - 1) * step, y1: y0 + (rows - 1) * step, vertices: n, triangles: indices.length / 3 };
}
