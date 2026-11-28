import test from "node:test";
import assert from "node:assert/strict";
import { Camera } from "../web/js/camera.js";
import { illustrationPatternSpec } from "../web/js/render/art/illustrate.js";

test("close zoom is bounded and anchored", () => {
  const cam = new Camera(1800, 2200);
  cam.resize(1440, 900);
  cam.centerOn(900, 1100);
  cam.scale = 6;
  const point = cam.toWorld(740, 470);
  cam.zoomAt(740, 470, 10);
  assert.equal(cam.scale, 12);
  const next = cam.toWorld(740, 470);
  assert.ok(Math.abs(point[0] - next[0]) < 1e-9);
  assert.ok(Math.abs(point[1] - next[1]) < 1e-9);
  cam.zoomAt(740, 470, 0.5);
  assert.equal(cam.scale, 6);
});

test("close illustration holds map scale, increases raster density, and stays bounded", () => {
  assert.deepEqual(illustrationPatternSpec(6, 6), {kmPerPx: 0.125, raster: 1});
  assert.deepEqual(illustrationPatternSpec(12, 12), {kmPerPx: 0.125, raster: 2});
  assert.deepEqual(illustrationPatternSpec(12, 24), {kmPerPx: 0.125, raster: 3});
  assert.equal(illustrationPatternSpec(12, 36).raster, 4);
  assert.equal(illustrationPatternSpec(3, 3).kmPerPx, illustrationPatternSpec(3, 9).kmPerPx);
});
