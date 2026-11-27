// Solar geometry: NOAA's Meeus equations, evaluated at each UTC instant.
// Original implementation of published equations, not copied calculator code.
// https://gml.noaa.gov/grad/solcalc/calcdetails.html
// Sunrise = centre at -0.833 degrees (standard refraction + solar radius).
// This models an unobstructed sea-level horizon, not terrain or weather.
const RAD = Math.PI / 180, DAY = 86400000, MINUTE = 60000;
const sin = (x) => Math.sin(x * RAD), cos = (x) => Math.cos(x * RAD);
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const mod = (v, n) => ((v % n) + n) % n;
export const SOLAR_LIMITS = Object.freeze({ sunrise: -0.833, civil: -6, nautical: -12, astronomical: -18 });
export const SOLAR_YEARS = Object.freeze({ min: 1800, max: 2100 });

function instant(value) {
  const ms = value instanceof Date ? value.getTime() : typeof value === "number" ? value : Date.parse(value);
  if (!Number.isFinite(ms)) throw new RangeError("Choose a valid date and time.");
  const year = new Date(ms).getUTCFullYear();
  if (year < SOLAR_YEARS.min || year > SOLAR_YEARS.max) throw new RangeError("Choose a year from 1800 to 2100.");
  return ms;
}

function coordinates(lat, lon) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180)
    throw new RangeError("Invalid geographical coordinates.");
}

/** Reusable parameters for one UTC instant; useful when drawing many locations. */
export function solarParameters(value) {
  const ms = instant(value);
  const t = (ms / DAY + 2440587.5 - 2451545) / 36525;
  const L = mod(280.46646 + t * (36000.76983 + 0.0003032 * t), 360);
  const M = 357.52911 + t * (35999.05029 - 0.0001537 * t);
  const e = 0.016708634 - t * (0.000042037 + 0.0000001267 * t);
  const C = sin(M) * (1.914602 - t * (0.004817 + 0.000014 * t))
    + sin(2 * M) * (0.019993 - 0.000101 * t) + sin(3 * M) * 0.000289;
  const omega = 125.04 - 1934.136 * t;
  const lambda = L + C - 0.00569 - 0.00478 * sin(omega);
  const epsilon = 23 + (26 + (21.448 - t * (46.815 + t * (0.00059 - t * 0.001813))) / 60) / 60 + 0.00256 * cos(omega);
  const declination = Math.asin(sin(epsilon) * sin(lambda)) / RAD;
  const y = Math.tan(epsilon * RAD / 2) ** 2;
  const equationMinutes = 4 / RAD * (y * sin(2 * L) - 2 * e * sin(M) + 4 * e * y * sin(M) * cos(2 * L)
    - 0.5 * y * y * sin(4 * L) - 1.25 * e * e * sin(2 * M));
  return { ms, declination, equationMinutes, utcMinutes: mod(ms, DAY) / MINUTE };
}

/** Geometric elevation and clockwise-from-north azimuth, in degrees. */
export function positionFromParameters(p, lat, lon) {
  coordinates(lat, lon);
  const hourAngle = mod(p.utcMinutes + p.equationMinutes + 4 * lon, 1440) / 4 - 180;
  const elevation = Math.asin(clamp(sin(lat) * sin(p.declination) + cos(lat) * cos(p.declination) * cos(hourAngle), -1, 1)) / RAD;
  const azimuth = mod(Math.atan2(sin(hourAngle), cos(hourAngle) * sin(lat) - Math.tan(p.declination * RAD) * cos(lat)) / RAD + 180, 360);
  return { elevation, azimuth, declination: p.declination, phase: solarPhase(elevation) };
}

export function solarPosition(value, lat, lon) { return positionFromParameters(solarParameters(value), lat, lon); }
export function solarPhase(elevation) {
  if (elevation >= SOLAR_LIMITS.sunrise) return "daylight";
  if (elevation >= -6) return "civil twilight";
  if (elevation >= -12) return "nautical twilight";
  if (elevation >= -18) return "astronomical twilight";
  return "night";
}

/** Smooth overlay opacity; capped to keep the landscape legible. */
export function illumination(elevation) {
  const x = clamp((4 - elevation) / 22, 0, 1);
  return 0.60 * x * x * (3 - 2 * x);
}

export function zoneForCountry(country) {
  return ({ NO: "Europe/Oslo", SE: "Europe/Stockholm", DK: "Europe/Copenhagen" })[country] || "Europe/Oslo";
}

const formatters = new Map();
export function zonedParts(value, timeZone) {
  let fmt = formatters.get(timeZone);
  if (!fmt) {
    fmt = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
    formatters.set(timeZone, fmt);
  }
  const parts = Object.fromEntries(fmt.formatToParts(new Date(instant(value))).filter((p) => p.type !== "literal").map((p) => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}`, second: +parts.second,
    year: +parts.year, month: +parts.month, day: +parts.day, hour: +parts.hour, minute: +parts.minute };
}

function parseLocal(date, time = "00:00") {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) throw new RangeError("Choose a valid date and time.");
  const [y, m, d] = date.split("-").map(Number), [h, n] = time.split(":").map(Number);
  const ms = Date.UTC(y, m - 1, d, h, n);
  if (y < 1800 || y > 2100 || m < 1 || m > 12 || d < 1 || h > 23 || n > 59 || new Date(ms).toISOString().slice(0, 10) !== date)
    throw new RangeError("Choose a valid date from 1800 to 2100.");
  return ms;
}

/** Resolve a wall-clock time without assuming the browser's timezone.
 * A skipped spring time has no instant. A repeated autumn time returns both
 * instants and chooses the earlier one unless disambiguation is "later".
 */
export function localToUtc(date, time, timeZone, { disambiguation = "earlier" } = {}) {
  const target = parseLocal(date, time), offsets = new Set();
  for (let hours = -36; hours <= 36; hours += 12) {
    const ms = target + hours * 3600000;
    const p = zonedParts(ms, timeZone);
    offsets.add(Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - ms);
  }
  const alternatives = [...offsets].map((offset) => target - offset).filter((ms) => {
    const p = zonedParts(ms, timeZone);
    return p.date === date && p.time === time;
  }).sort((a, b) => a - b).map((ms) => new Date(ms));
  return { status: alternatives.length === 0 ? "nonexistent" : alternatives.length > 1 ? "ambiguous" : "exact",
    date: alternatives.length ? alternatives[disambiguation === "later" ? alternatives.length - 1 : 0] : null, alternatives };
}

function nextDate(date) { return new Date(parseLocal(date) + DAY).toISOString().slice(0, 10); }
function bisect(fn, a, b) {
  const positive = fn(a) >= 0;
  while (b - a > 250) {
    const m = (a + b) / 2;
    if ((fn(m) >= 0) === positive) a = m; else b = m;
  }
  return Math.round((a + b) / 2);
}
function extremum(fn, a, b, maximum) {
  while (b - a > 250) {
    const l = a + (b - a) / 3, r = b - (b - a) / 3;
    if ((fn(l) < fn(r)) === maximum) a = l; else b = r;
  }
  return (a + b) / 2;
}

/** Crossings within the selected local calendar day; no fictional polar events.
 * Durations use elapsed time, including 23/25-hour clock-change days.
 */
export function solarDay(date, lat, lon, timeZone) {
  coordinates(lat, lon);
  parseLocal(date);
  const start = +localToUtc(date, "00:00", timeZone).date;
  const end = +localToUtc(nextDate(date), "00:00", timeZone).date;
  const elevation = (ms) => solarPosition(ms, lat, lon).elevation;
  const points = [];
  for (let ms = start; ms < end; ms += 30 * MINUTE) points.push({ ms, e: elevation(ms) });
  points.push({ ms: end, e: elevation(end) });
  // Include solar extrema explicitly, so a short day/night near the polar
  // boundary cannot disappear between fixed-interval samples.
  const critical = [];
  for (let i = 1; i < points.length - 1; i++) {
    const a = points[i - 1], p = points[i], b = points[i + 1];
    const max = p.e > a.e && p.e > b.e, min = p.e < a.e && p.e < b.e;
    if (max || min) { const ms = extremum(elevation, a.ms, b.ms, max); critical.push({ ms, e: elevation(ms) }); }
  }
  points.push(...critical); points.sort((a, b) => a.ms - b.ms);
  const levels = {};
  for (const [key, threshold] of Object.entries(SOLAR_LIMITS)) {
    const events = [];
    for (let i = 1; i < points.length; i++) {
      const a = points[i - 1], b = points[i];
      if ((a.e >= threshold) !== (b.e >= threshold)) {
        const ms = bisect((t) => elevation(t) - threshold, a.ms, b.ms);
        if (ms < end) events.push({ kind: b.e > a.e ? "rise" : "set", time: new Date(ms) });
      }
    }
    let above = points[0].e >= threshold, cursor = start, duration = 0;
    for (const event of events) {
      if (above) duration += +event.time - cursor;
      above = event.kind === "rise"; cursor = +event.time;
    }
    if (above) duration += end - cursor;
    levels[key] = { rise: events.find((e) => e.kind === "rise")?.time || null,
      set: events.find((e) => e.kind === "set")?.time || null, events, minutesAbove: duration / MINUTE,
      state: !events.length ? above ? "always-above" : "always-below" : "crosses" };
  }
  return { date, timeZone, start: new Date(start), end: new Date(end), dayMinutes: (end - start) / MINUTE,
    sunrise: levels.sunrise.rise, sunset: levels.sunrise.set, daylightMinutes: levels.sunrise.minutesAbove,
    condition: levels.sunrise.state === "always-above" ? "midnight-sun" : levels.sunrise.state === "always-below" ? "polar-night" : "ordinary",
    levels, minElevation: Math.min(...points.map((p) => p.e)), maxElevation: Math.max(...points.map((p) => p.e)) };
}
