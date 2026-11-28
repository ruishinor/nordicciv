import test from "node:test";
import assert from "node:assert/strict";
import { Camera } from "../web/js/camera.js";
import { illustrationPatternSpec, seasonForMonth, seasonalPatternKey, setIllustrationSeason, illustrationSeason } from "../web/js/render/art/illustrate.js";

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

test("seasonal artwork is optional and cache keys distinguish changed covers", () => {
  assert.equal(illustrationSeason(), "off");
  assert.deepEqual([2,3,6,9,12].map(seasonForMonth), ["winter","spring","summer","autumn","winter"]);
  assert.equal(seasonForMonth(13), "off");
  assert.equal(setIllustrationSeason("winter"), true);
  assert.equal(setIllustrationSeason("winter"), false);
  assert.notEqual(seasonalPatternKey("farm", 2), seasonalPatternKey("farm", 2, "summer"));
  assert.equal(seasonalPatternKey("rock", 2), seasonalPatternKey("rock", 2, "summer"));
  assert.equal(setIllustrationSeason("invalid"), false);
  assert.equal(illustrationSeason(), "winter");
  assert.equal(setIllustrationSeason("off"), true);
});

import { woodlandPoints, fieldParcels, terrainGrain } from "../web/js/render/art/landscape.js";

test("landscape geometry is deterministic, irregular and periodic", () => {
  const p=woodlandPoints(384,12.5,2401);
  assert.deepEqual(p,woodlandPoints(384,12.5,2401));
  assert.ok(p.length>300 && p.length<1200);
  assert.ok(p.every(([x,y,s])=>x>=0&&x<384&&y>=0&&y<384&&s>0));
  assert.ok(new Set(p.map(a=>Math.round(a[2]*100))).size>40);
  const fields=fieldParcels(512,7177);
  assert.equal(fields.length,90);
  assert.ok(fields.every(f=>f.poly.length>=3&&f.poly.flat().every(Number.isFinite)));
  const area=poly=>Math.abs(poly.reduce((sum,p,i)=>{const q=poly[(i+1)%poly.length];return sum+p[0]*q[1]-q[0]*p[1];},0))/2;
  assert.ok(Math.abs(fields.reduce((sum,f)=>sum+area(f.poly),0)-512*512)<1e-5);
  const grain=terrainGrain(128);
  assert.deepEqual(grain,terrainGrain(128));
  assert.equal(grain.length,128*128*4);
  assert.ok(grain.every((v,i)=>i%4===3?v===255:v>60&&v<196));
});
