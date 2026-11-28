import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  localToUtc, positionFromParameters, solarDay, solarParameters, solarPhase, solarPosition, zonedParts,
} from "../web/js/util/solar.js";

// NASA/JPL Horizons, DE441, https://ssd-api.jpl.nasa.gov/doc/horizons.html.
// COMMAND=10, CENTER=coord@399, COORD_TYPE=GEODETIC, SITE_COORD=lon,lat,0,
// QUANTITIES=4, APPARENT=AIRLESS, TIME_TYPE=UT, STEP_SIZE='1 min'. Query from
// local midnight through the following midnight, in UTC. Position rows are
// [UTC, azimuth, elevation]. Event times are linearly interpolated between the
// reference elevations bracketing each fixed threshold and rounded to seconds.
// Daylight is the sum of the elapsed intervals above -0.833° within that day.
const fixtures = JSON.parse(readFileSync(new URL("./fixtures/solar_horizons.json", import.meta.url), "utf8"));
const thresholds = { sunrise: -0.833, civil: -6, nautical: -12, astronomical: -18 };
const circularError = (a, b) => Math.abs((a - b + 540) % 360 - 180);
const asIso = (d) => d?.toISOString() ?? null;
const near = (actual, expected, tolerance, name) => {
  assert.ok(Math.abs(actual - expected) <= tolerance,
    `${name}: got ${actual}, expected ${expected} ± ${tolerance}`);
};

test("geometric elevation and azimuth agree with Horizons airless coordinates", (t) => {
  let maxElevation = 0, maxAzimuth = 0, samples = 0;
  for (const { place, lat, lon, positions } of fixtures) {
    for (const [utc, azimuth, elevation] of positions) {
      const label = `${place} ${utc}`;
      const p = solarPosition(utc, lat, lon);
      near(p.elevation, elevation, 0.02, `${label} elevation (°)`);
      near(circularError(p.azimuth, azimuth), 0, 0.02, `${label} azimuth (°)`);
      assert.ok(p.azimuth >= 0 && p.azimuth < 360, label);
      maxElevation = Math.max(maxElevation, Math.abs(p.elevation - elevation));
      maxAzimuth = Math.max(maxAzimuth, circularError(p.azimuth, azimuth));
      samples++;
    }
  }
  t.diagnostic(`${samples} positions. Maximum error: elevation ${maxElevation.toFixed(4)}°, azimuth ${maxAzimuth.toFixed(4)}°.`);
});

test("rise, set, twilight and elapsed daylight agree with Horizons crossings", (t) => {
  const maxEvent = { ordinary: 0, grazing: 0 };
  const maxDaylight = { ordinary: 0, grazing: 0 };
  let eventCount = 0;
  for (const { place, lat, lon, date, zone, events, daylight, grazing } of fixtures) {
    const label = `${place} ${date}`;
    const day = solarDay(date, lat, lon, zone);
    near(day.daylightMinutes, daylight, grazing ? 2.5 : 0.5, `${label} daylight (min)`);
    const bucket = grazing ? "grazing" : "ordinary";
    maxDaylight[bucket] = Math.max(maxDaylight[bucket], Math.abs(day.daylightMinutes - daylight));
    for (const [level, expected] of Object.entries(events)) {
      const actual = day.levels[level];
      const crossings = Array.isArray(expected) ? expected : [];
      assert.equal(actual.state, crossings.length ? "crosses" : expected, `${label} ${level}`);
      assert.deepEqual(actual.events.map(({ kind }) => kind), crossings.map(([kind]) => kind), `${label} ${level} order`);
      for (const [i, [kind, utc]] of crossings.entries()) {
        const { time } = actual.events[i];
        const error = (+time - Date.parse(utc)) / 1000;
        const eventBucket = grazing && level === "sunrise" ? "grazing" : "ordinary";
        near(error, 0, eventBucket === "grazing" ? 75 : 15, `${label} ${level} ${kind} (s)`);
        maxEvent[eventBucket] = Math.max(maxEvent[eventBucket], Math.abs(error));
        assert.ok(+time >= +day.start && +time < +day.end, `${label} event outside the local day`);
        near(solarPosition(time, lat, lon).elevation, thresholds[level], 0.001, `${label} ${level} root (°)`);
        eventCount++;
      }
      for (const key of ["rise", "set"])
        assert.equal(actual[key], actual.events.find(({ kind }) => kind === key)?.time ?? null, `${label} ${level} ${key}`);
    }
    assert.equal(day.sunrise, day.levels.sunrise.rise, label);
    assert.equal(day.sunset, day.levels.sunrise.set, label);
  }
  t.diagnostic(`${fixtures.length} days and ${eventCount} events. Maximum event error: ${maxEvent.ordinary.toFixed(1)} s ordinary, ${maxEvent.grazing.toFixed(1)} s grazing.`);
  t.diagnostic(`Maximum daylight error: ${maxDaylight.ordinary.toFixed(2)} min ordinary, ${maxDaylight.grazing.toFixed(2)} min grazing.`);
});

test("polar days and nights retain distinct horizon and twilight states", () => {
  const tromso = (date) => solarDay(date, 69.6492, 18.9553, "Europe/Oslo");
  const summer = tromso("2024-06-20");
  assert.equal(summer.condition, "midnight-sun");
  assert.equal(summer.daylightMinutes, 1440);
  assert.equal(summer.sunrise, null);
  assert.equal(summer.sunset, null);
  const winter = tromso("2024-12-21");
  assert.equal(winter.condition, "polar-night");
  assert.equal(winter.daylightMinutes, 0);
  assert.equal(winter.sunrise, null);
  assert.equal(winter.sunset, null);
  assert.equal(winter.levels.civil.state, "crosses");
  assert.ok(winter.levels.civil.minutesAbove > 0);
  assert.equal(tromso("2024-05-17").condition, "ordinary");
  assert.equal(tromso("2024-05-18").condition, "midnight-sun");
  assert.equal(tromso("2024-07-25").condition, "midnight-sun");
  assert.equal(tromso("2024-07-26").condition, "ordinary");
  for (const [h, phase] of [
    [-0.833, "daylight"], [-0.834, "civil twilight"], [-6, "civil twilight"],
    [-6.001, "nautical twilight"], [-12, "nautical twilight"], [-12.001, "astronomical twilight"],
    [-18, "astronomical twilight"], [-18.001, "night"],
  ]) assert.equal(solarPhase(h), phase);
});

test("IANA time zones resolve spring gaps and both autumn occurrences", () => {
  for (const zone of ["Europe/Oslo", "Europe/Stockholm", "Europe/Copenhagen"]) {
    const spring = localToUtc("2024-03-31", "02:30", zone);
    assert.deepEqual(spring, { status: "nonexistent", date: null, alternatives: [] });
    const fall = localToUtc("2024-10-27", "02:30", zone);
    assert.equal(fall.status, "ambiguous");
    assert.deepEqual(fall.alternatives.map(asIso), ["2024-10-27T00:30:00.000Z", "2024-10-27T01:30:00.000Z"]);
    assert.equal(asIso(fall.date), asIso(fall.alternatives[0]));
    const later = localToUtc("2024-10-27", "02:30", zone, { disambiguation: "later" });
    assert.equal(asIso(later.date), asIso(fall.alternatives[1]));
    assert.equal(zonedParts(later.date, zone).time, "02:30");
    assert.equal(asIso(localToUtc("2024-02-29", "12:00", zone).date), "2024-02-29T11:00:00.000Z");
  }
});

test("local days use elapsed duration and handle a skipped midnight or date", () => {
  for (const [date, zone, start, end, minutes, localSunrise] of [
    ["2024-03-31", "Europe/Oslo", "2024-03-30T23:00:00.000Z", "2024-03-31T22:00:00.000Z", 1380, "06:44"],
    ["2024-10-27", "Europe/Stockholm", "2024-10-26T22:00:00.000Z", "2024-10-27T23:00:00.000Z", 1500, "06:55"],
    ["2018-11-04", "America/Sao_Paulo", "2018-11-04T03:00:00.000Z", "2018-11-05T02:00:00.000Z", 1380],
    ["2011-12-29", "Pacific/Apia", "2011-12-29T10:00:00.000Z", "2011-12-30T10:00:00.000Z", 1440],
  ]) {
    const f = fixtures.find((x) => x.date === date);
    const day = solarDay(date, f?.lat ?? 0, f?.lon ?? 0, zone);
    assert.deepEqual([asIso(day.start), asIso(day.end), day.dayMinutes], [start, end, minutes]);
    if (localSunrise) assert.equal(zonedParts(day.sunrise, zone).time, localSunrise);
  }
  assert.throws(() => solarDay("2011-12-30", -13.8, -171.75, "Pacific/Apia"), RangeError);
});

test("invalid inputs are rejected and ISO instants are independent of host time zone", () => {
  for (const invalid of [
    "2024-02-30", "2024-02-30T12:00Z", "2024-03-31T24:00Z", "2023-02-29T12:00+01:00",
    "2024-03-20T12:00", "2024-03-20T12:00+26:00", undefined, null, NaN, Infinity, 1e16, new Date(NaN),
  ]) assert.throws(() => solarPosition(invalid, 60, 10), RangeError, String(invalid));
  for (const invalid of ["2023-02-29", "2024-04-31", "2024-13-01", "2024-04-00", "2024-4-01"])
    assert.throws(() => solarDay(invalid, 60, 10, "Europe/Oslo"), RangeError, invalid);
  assert.throws(() => localToUtc("2024-03-20", "14:60", "Europe/Oslo"), RangeError);
  assert.throws(() => localToUtc("2024-03-20", "14:00", "Invalid/Zone"), RangeError);
  assert.throws(() => solarDay("2024-03-20", 60, 10), RangeError);
  assert.throws(() => solarDay("2024-03-20", 91, 10, "Europe/Oslo"), RangeError);
  assert.throws(() => solarPosition("2024-03-20", 60, -181), RangeError);
  const iso = "2024-03-20T00:00:00.000Z";
  const expected = solarPosition(iso, 60, 10);
  for (const equivalent of ["2024-03-20", "2024-03-20T01:00+01:00", new Date(iso), Date.parse(iso)])
    assert.deepEqual(solarPosition(equivalent, 60, 10), expected);
});

test("UTC instant and local day ranges include both boundary years", () => {
  for (const utc of ["1800-01-01T00:00:00Z", "2100-12-31T23:59:59.999Z"])
    assert.ok(Number.isFinite(solarPosition(utc, 60, 10).elevation));
  for (const utc of ["1799-12-31T23:59:59.999Z", "2101-01-01T00:00:00Z"])
    assert.throws(() => solarPosition(utc, 60, 10), RangeError);
  const first = solarDay("1800-01-01", 60, 10, "Europe/Oslo");
  assert.equal(first.start.getUTCFullYear(), 1799);
  assert.equal(first.dayMinutes, 1440);
  assert.equal(zonedParts(first.start, first.timeZone).date, "1800-01-01");
  assert.equal(+localToUtc("1800-01-01", "00:00", first.timeZone).date, +first.start);
  const last = solarDay("2100-12-31", 60, 10, "UTC");
  assert.equal(asIso(last.end), "2101-01-01T00:00:00.000Z");
  assert.equal(last.dayMinutes, 1440);
  for (const day of [first, last]) assert.ok(day.daylightMinutes > 0 && day.daylightMinutes < day.dayMinutes);
  for (const date of ["1799-12-31", "2101-01-01"])
    assert.throws(() => solarDay(date, 60, 10, "UTC"), RangeError);
});

test("position remains finite at the poles, zenith and wrap of longitude", () => {
  const p = solarParameters("2024-06-20T12:00Z");
  for (const lat of [-90, -66.5, 0, 66.5, 90]) {
    const east = positionFromParameters(p, lat, 180), west = positionFromParameters(p, lat, -180);
    for (const h of [east, west]) {
      assert.ok(h.elevation >= -90 && h.elevation <= 90);
      assert.ok(h.azimuth >= 0 && h.azimuth < 360);
    }
    near(east.elevation, west.elevation, 1e-10, "wrapped elevation");
    near(circularError(east.azimuth, west.azimuth), 0, 1e-10, "wrapped azimuth");
  }
  const lon = (720 - p.utcMinutes - p.equationMinutes) / 4;
  for (const lat of [p.declination, p.declination - 1e-8, p.declination + 1e-8]) {
    const h = positionFromParameters(p, lat, lon);
    near(h.elevation, 90, 2e-6, "elevation near zenith");
    assert.ok(h.azimuth >= 0 && h.azimuth < 360);
  }
});
