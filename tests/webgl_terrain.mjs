import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { Camera } from "../web/js/camera.js";
import { makeGrid } from "../web/js/hex.js";
import {
  buildTerrainMesh, projectTerrainPoint, TERRAIN_LAYER_TYPES, terrainElevationAt, WebGLTerrainRenderer,
} from "../web/js/render/webgl-terrain.js";

function smallWorld() {
  const raw = { grid: { radius: 6, cols: 3, rows: 2 }, elev: [100, 700, 900, 1200, 400, 800] };
  return {
    raw, grid: makeGrid(raw.grid), water: [0, 0, 1, 0, 0, 0],
    terrainColors: Array.from({ length: 6 }, () => [100, 140, 80]),
  };
}

test("terrain mesh uses source elevations and omits water cells", () => {
  const world = smallWorld();
  const mesh = buildTerrainMesh(world);
  assert.equal(mesh.cells, 5);
  assert.equal(mesh.hexRadiusKm, 6);
  assert.equal(mesh.vertices, 35);
  assert.equal(mesh.triangles, 30);
  assert.equal(mesh.indices.length, mesh.triangles * 3);
  assert.equal(mesh.shades.length, mesh.vertices);
  assert.ok(mesh.shades.every((shade) => shade >= 0.75 && shade <= 1.2));
  assert.ok(Math.abs(mesh.positions[2] - 0.1) < 1e-7);
  assert.ok(mesh.positions.some((value, i) => i % 3 === 2 && value > 0.7));
});

test("terrain mesh rejects incomplete or non-finite elevation input", () => {
  const world = smallWorld();
  assert.throws(() => buildTerrainMesh({ ...world, raw: { elev: [1] } }), TypeError);
  world.raw.elev[0] = NaN;
  assert.throws(() => buildTerrainMesh(world), /not finite/);
});

test("terrain surface interpolation uses neighboring elevation samples", () => {
  const world = smallWorld();
  const cell = 4;
  assert.equal(terrainElevationAt(world, world.grid.cx(cell), world.grid.cy(cell)), world.raw.elev[cell]);
  const [dx, dy] = world.grid.corners[0];
  const point = [world.grid.cx(cell) + dx * 0.25, world.grid.cy(cell) + dy * 0.25];
  assert.notEqual(terrainElevationAt(world, ...point), world.raw.elev[cell]);
});

test("shipped world elevations produce one mesh sample per land hex", () => {
  const raw = JSON.parse(readFileSync(new URL("../web/data/world.json", import.meta.url), "utf8"));
  const world = {
    raw, grid: makeGrid(raw.grid), water: raw.water, terrainColors: [],
  };
  const mesh = buildTerrainMesh(world);
  const landCells = raw.water.filter((water) => !water).length;
  assert.equal(mesh.cells, landCells);
  assert.equal(mesh.triangles, landCells * 6);
  assert.equal(mesh.hexRadiusKm, raw.grid.radius);
  assert.ok(mesh.positions.some((value, i) => i % 3 === 2 && value > 0.5));
});

test("camera pitch preserves screen-to-world round trips and zoom anchors", () => {
  const cam = new Camera(1000, 800);
  cam.resize(800, 600);
  cam.x = 420;
  cam.y = 310;
  cam.scale = 4;
  assert.equal(cam.maxScale, 12);
  assert.equal(cam.setPitch(28), 28);
  assert.ok(Math.abs(cam.yScale - 4 * Math.cos(28 * Math.PI / 180)) < 1e-12);
  cam.elevationAt = (x, y) => 1000 + x * 0.1 + y * 0.2;
  cam.verticalExaggeration = 2;
  const point = [480, 360];
  const screen = cam.toScreenSurface(...point);
  const world = cam.toWorld(...screen);
  assert.ok(Math.abs(world[0] - point[0]) < 1e-10);
  assert.ok(Math.abs(world[1] - point[1]) < 1e-10);
  const center = cam.centerAt(point[0], point[1], 230, 160, 6);
  const centered = new Camera(1000, 800);
  centered.resize(800, 600);
  centered.scale = 6;
  centered.setPitch(28);
  centered.elevationAt = cam.elevationAt;
  centered.verticalExaggeration = 2;
  centered.x = center[0];
  centered.y = center[1];
  const anchored = centered.toScreenSurface(...point);
  assert.ok(Math.abs(anchored[0] - 230) < 1e-10);
  assert.ok(Math.abs(anchored[1] - 160) < 1e-10);
  const anchor = [185, 140];
  const before = cam.toWorld(...anchor);
  cam.zoomAt(...anchor, 1.5);
  const after = cam.toWorld(...anchor);
  assert.ok(Math.abs(before[0] - after[0]) < 1e-10);
  assert.ok(Math.abs(before[1] - after[1]) < 1e-10);
  assert.equal(cam.setPitch(90), 45);
  assert.throws(() => cam.setPitch(Infinity), TypeError);
});

test("pitched terrain projection and hit testing stay aligned across scales, heights and map positions", () => {
  const world = smallWorld();
  const cam = new Camera(1000, 800);
  cam.resize(800, 600);
  cam.maxScale = 48;
  cam.minScale = 0.1;
  cam.verticalExaggeration = 2.5;
  cam.elevationAt = (x, y) => terrainElevationAt(world, x, y);
  const cells = [0, 1, 3, 4, 5];

  for (const scale of [0.5, 4, 12, 28, 48]) {
    for (const pitch of [0, 14, 30, 45]) {
      cam.scale = scale;
      cam.setPitch(pitch);
      for (const cell of cells) {
        const point = [world.grid.cx(cell), world.grid.cy(cell)];
        cam.x = point[0] - 3;
        cam.y = point[1] + 2;
        const screen = cam.toScreenSurface(...point);
        const hit = cam.toWorld(...screen);
        assert.ok(Math.abs(hit[0] - point[0]) < 1e-7, `x round trip: ${scale}px/km, ${pitch}° pitch, cell ${cell}`);
        assert.ok(Math.abs(hit[1] - point[1]) < 1e-5, `y round trip: ${scale}px/km, ${pitch}° pitch, cell ${cell}`);

        const view = {
          ...cam.view(),
          s: scale,
          yScale: cam.yScale,
          cssW: cam.w,
          cssH: cam.h,
        };
        const elevation = terrainElevationAt(world, ...point);
        const projected = projectTerrainPoint(view, ...point, elevation, pitch);
        assert.ok(Math.abs((projected[0] + 1) * cam.w / 2 - screen[0]) < 1e-7,
          `projected x: ${scale}px/km, ${pitch}° pitch, cell ${cell}`);
        assert.ok(Math.abs((1 - projected[1]) * cam.h / 2 - screen[1]) < 1e-7,
          `projected y: ${scale}px/km, ${pitch}° pitch, cell ${cell}`);
      }
    }
  }
});

test("pitched render bounds stay rectangular even over unequal elevations", () => {
  const cam = new Camera(1000, 800);
  cam.resize(800, 600);
  cam.x = 420;
  cam.y = 310;
  cam.scale = 48;
  cam.setPitch(45);
  cam.verticalExaggeration = 2.5;
  cam.elevationAt = (x, y) => 1000 + x + y;
  const {x0, y0, x1, y1} = cam.view();
  for (const [actual, expected] of [
    [cam.toScreen(x0, y0), [0, 0]], [cam.toScreen(x1, y1), [cam.w, cam.h]],
  ]) {
    assert.ok(Math.abs(actual[0] - expected[0]) < 1e-8);
    assert.ok(Math.abs(actual[1] - expected[1]) < 1e-8);
  }
  assert.notEqual(cam.toWorld(0, 0)[1], y0);
});

test("terrain projection shares the pitched camera's ground coordinates", () => {
  const cam = new Camera(1000, 800);
  cam.resize(800, 600);
  cam.x = 420;
  cam.y = 310;
  cam.scale = 4;
  cam.setPitch(30);
  const [x, y] = cam.toScreen(480, 360);
  const bounds = cam.view();
  const view = { ...bounds, s: 4, yScale: cam.yScale, cssW: 800, cssH: 600 };
  const projected = projectTerrainPoint(view, 480, 360);
  assert.ok(Math.abs((projected[0] + 1) * 400 - x) < 1e-10);
  assert.ok(Math.abs((1 - projected[1]) * 300 - y) < 1e-10);
  assert.ok(projectTerrainPoint(view, 480, 360, 1000, 30)[1] > projected[1]);
});

test("renderer reports unavailable WebGL cleanly and defines future terrain layer types", () => {
  const previous = globalThis.document;
  globalThis.document = { createElement: () => ({ getContext: () => null }) };
  try {
    const renderer = new WebGLTerrainRenderer(smallWorld());
    assert.equal(renderer.available, false);
    assert.match(renderer.error.message, /WebGL 2/);
    assert.throws(() => renderer.registerLayer({ id: "trees", type: "vegetation", draw() {} }), /active WebGL 2/);
  } finally {
    if (previous === undefined) delete globalThis.document;
    else globalThis.document = previous;
  }
  assert.deepEqual(TERRAIN_LAYER_TYPES, ["elevation", "vegetation", "buildings", "agriculture", "infrastructure"]);
});
