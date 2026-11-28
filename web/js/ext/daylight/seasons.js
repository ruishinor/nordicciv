import { localToUtc, solarDay, SOLAR_YEARS } from "../../util/solar.js";

// Representative dates near the equinoxes and solstices, not their exact instants.
export const SEASON_DATES = Object.freeze([
  {id:"spring", label:"Spring", date:"03-20"},
  {id:"summer", label:"Summer", date:"06-21"},
  {id:"autumn", label:"Autumn", date:"09-22"},
  {id:"winter", label:"Winter", date:"12-21"},
].map(Object.freeze));
export const AURORA_FORECAST = "https://www.spaceweather.gov/products/aurora-30-minute-forecast";

function validYear(year) {
  return Number.isInteger(year) && year >= SOLAR_YEARS.min && year <= SOLAR_YEARS.max;
}
export function seasonalLight(year, lat, lon, zone) {
  if (!validYear(year)) return [];
  return SEASON_DATES.map(s => {
    const date = year + "-" + s.date;
    const d = solarDay(date, lat, lon, zone);
    return {id:s.id, label:s.label, date, daylight:d.daylightMinutes,
      darkness:Math.max(0, d.dayMinutes - d.levels.astronomical.minutesAbove)};
  });
}
export function seasonInstant(year, id, time, zone) {
  const season = SEASON_DATES.find(s => s.id === id);
  if (!validYear(year) || !season || !["12:00","00:00"].includes(time)) return null;
  return localToUtc(year + "-" + season.date, time, zone, {disambiguation:"earlier"}).date;
}
