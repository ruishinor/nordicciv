import test from "node:test";
import assert from "node:assert/strict";
import {seasonalLight, seasonInstant, AURORA_FORECAST} from "../web/js/ext/daylight/seasons.js";

test("Tromsø has summer midnight sun and winter polar night; Copenhagen has seasonal contrasts", () => {
  const north = seasonalLight(2026, 69.65, 18.96, "Europe/Oslo");
  const south = seasonalLight(2026, 55.68, 12.57, "Europe/Copenhagen");
  assert.equal(north.length, 4);
  assert.ok(north[1].daylight > 1439);
  assert.equal(north[1].darkness, 0);
  assert.equal(north[3].daylight, 0);
  assert.ok(north[3].darkness > south[3].darkness);
  assert.ok(south[1].daylight > south[3].daylight);
  for (const s of [...north, ...south]) assert.ok(s.daylight + s.darkness <= 1440.001);
  assert.deepEqual(seasonalLight(2101, 69.65, 18.96, "Europe/Oslo"), []);
});
test("season actions use local noon or midnight", () => {
  assert.equal(seasonInstant(2026,"summer","00:00","Europe/Oslo").toISOString(), "2026-06-20T22:00:00.000Z");
  assert.equal(seasonInstant(2026,"winter","12:00","Europe/Oslo").toISOString(), "2026-12-21T11:00:00.000Z");
  assert.equal(seasonInstant(2026,"invalid","12:00","Europe/Oslo"), null);
  assert.equal(seasonInstant(2026,"winter","06:00","Europe/Oslo"), null);
  assert.equal(new URL(AURORA_FORECAST).hostname, "www.spaceweather.gov");
});
