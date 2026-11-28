import { esc } from "../../format.js";
import { mapToLonLat, projectionFrom } from "../../util/geo.js";
import {
  SOLAR_YEARS, localToUtc, positionFromParameters, solarDay, solarParameters, zoneForCountry, zonedParts,
} from "../../util/solar.js";
import { icon } from "../../ui/icon.js";
import { daylightLayer } from "./light.js";
import { seasonForMonth, setIllustrationSeason } from "../../render/art/illustrate.js";
import { SEASON_DATES, seasonalLight, seasonInstant, AURORA_FORECAST } from "./seasons.js";

const COUNTRY = { NO: "Norway", SE: "Sweden", DK: "Denmark" };
const MINUTE = 60_000;
const currentMinute = () => Math.floor(Date.now() / MINUTE) * MINUTE;
const dateFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: "UTC", day: "numeric", month: "short", year: "numeric",
});
const timeFormats = new Map();

function localClock(ms, timeZone) {
  if (!timeFormats.has(timeZone)) {
    timeFormats.set(timeZone, new Intl.DateTimeFormat("en-GB", {
      timeZone, hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZoneName: "shortOffset",
    }));
  }
  return timeFormats.get(timeZone).format(ms).replace("GMT", "UTC");
}

function duration(minutes) {
  const total = Math.round(minutes);
  if (total === 0) return minutes > 0 ? "Less than 1 min" : "0 h";
  const h = Math.floor(total / 60), m = total % 60;
  return [h ? `${h} h` : "", m ? `${m} min` : ""].filter(Boolean).join(" ");
}

export function install(app) {
  const projection = projectionFrom(app.w);
  if (!projection) return;
  let mode = null, parameters = null, timer = 0, opener = null, lastDay = null;
  let layerRegistered = false;
  const referenceYear = Math.max(SOLAR_YEARS.min, Math.min(SOLAR_YEARS.max, new Date().getUTCFullYear()));
  const seasonCache = new Map();
  const selectedZone = () => zoneForCountry(app.state.selectedCity?.country);
  const panel = document.createElement("section");
  panel.id = "daylight-controls";
  panel.className = "panel daylight-panel";
  panel.hidden = true;
  panel.inert = document.getElementById("topbar").inert;
  panel.setAttribute("aria-labelledby", "daylight-title");
  panel.innerHTML = `
    <div class="daylight-head">
      <h2 id="daylight-title" tabindex="-1">Daylight</h2>
      <button type="button" class="chip" data-off>Turn off</button>
    </div>
    <p class="daylight-clock"><time></time><span data-zone class="muted"></span></p>
    <div class="daylight-modes" role="group" aria-label="Map time">
      <button type="button" class="btn" data-now>Now</button>
      <button type="button" class="btn" data-choose>Choose date and time</button>
    </div>
    <form hidden novalidate>
      <div class="daylight-fields">
        <label>Date<input name="date" type="date" required min="${SOLAR_YEARS.min}-01-01" max="${SOLAR_YEARS.max}-12-31"></label>
        <label>Time<input name="time" type="time" required></label>
      </div>
      <label class="daylight-occurrence" hidden>Which time?
        <select name="occurrence">
          <option value="">Choose an occurrence</option>
          <option value="earlier">First time</option>
          <option value="later">Second time</option>
        </select>
      </label>
      <p class="daylight-notice" role="status"></p>
      <button type="submit" class="chip">Apply time</button>
    </form>
    <ul class="daylight-key" aria-label="Map lighting">
      <li>Daylight</li><li>Twilight</li><li>Darkness</li>
    </ul>
    <details class="daylight-seasons">
      <summary>Explore the seasons</summary>
      <p class="muted small">Compare the same local time in different seasons (${referenceYear}).</p>
      <div class="chips">${SEASON_DATES.map(s => `<button type="button" class="chip" data-season="${s.id}">${s.label}</button>`).join("")}</div>
      <div class="chips"><button type="button" class="chip" data-season-hour="12:00">Noon</button><button type="button" class="chip" data-season-hour="00:00">Midnight</button></div>
      <label><input type="checkbox" data-season-art> Seasonal landscape artwork</label>
      <p class="muted small">Changes trees and fields as you zoom in. Illustrations, not current snow or weather.</p>
    </details>
    <p class="daylight-local muted">Pick a municipality for local times.</p>
    <button type="button" class="link daylight-local-link" hidden>See local times</button>`;
  document.body.append(panel);

  const find = (selector) => panel.querySelector(selector);
  const form = find("form");
  const { date, time, occurrence } = form.elements;
  const notice = find(".daylight-notice");
  const clock = find("time");
  const nowButton = find("[data-now]"), chooseButton = find("[data-choose]");
  const panelRoot = app.panels.element;
  const desktopButton = app.ui.addTopButton({
    id: "btn-daylight", icon: "☀", label: "Daylight", title: "Daylight", onClick: (_, button) => toggle(button),
  });
  const mobileButton = document.createElement("button");
  mobileButton.type = "button";
  mobileButton.id = "daylight-mobile";
  mobileButton.innerHTML = `<span aria-hidden="true">☀</span>Daylight`;
  const nav = document.getElementById("mobile-nav");
  nav.insertBefore(mobileButton, nav.querySelector('[data-mnav="council"]'));
  mobileButton.onclick = () => toggle(mobileButton);
  for (const button of [desktopButton, mobileButton]) {
    button.setAttribute("aria-controls", panel.id);
    button.setAttribute("aria-pressed", "false");
  }

  function citySummary(city) {
    if (!parameters) return '<p>See how daylight changes here through the year.</p><button type="button" class="chip" data-daylight-start>Turn on Daylight</button>';
    const point = Number.isFinite(city.lat) && Number.isFinite(city.lon) ? city : mapToLonLat(projection, city.x, city.y);
    if (!point) return "<p>Daylight times are unavailable for this municipality.</p>";
    const zone = zoneForCountry(city.country);
    const local = zonedParts(parameters.ms, zone);
    if (local.year < SOLAR_YEARS.min || local.year > SOLAR_YEARS.max)
      return "<p>Sunrise and sunset are unavailable for this local date.</p>";
    const key = `${city.id}|${local.date}`;
    if (lastDay?.key !== key) lastDay = { key, value: solarDay(local.date, point.lat, point.lon, zone) };
    const day = lastDay.value;
    const { phase } = positionFromParameters(parameters, point.lat, point.lon);
    const light = phase === "night" ? "Darkness" : phase[0].toUpperCase() + phase.slice(1);
    const polar = day.condition === "midnight-sun" ? "Midnight sun. The sun stays above the horizon all day."
      : day.condition === "polar-night" ? "Polar night. The sun stays below the horizon all day." : "";
    const times = (kind, label) => day.levels.sunrise.events.filter((event) => event.kind === kind)
      .map((event) => zonedParts(event.time, zone).time).join(", ") || `No ${label} today`;
    return `<p class="muted small"><time datetime="${local.date}">${dateFormat.format(Date.parse(local.date))}</time> · ${COUNTRY[city.country]} local time</p>
      <p class="daylight-phase"><b>${light}</b> at ${local.time}${polar ? `<br>${polar}` : ""}</p>
      <dl class="daylight-stats">
        <div><dt>Sunrise</dt><dd>${times("rise", "sunrise")}</dd></div>
        <div><dt>Sunset</dt><dd>${times("set", "sunset")}</dd></div>
        <div><dt>Daylight</dt><dd>${duration(day.daylightMinutes)}</dd></div>
      </dl>
      <p class="muted small">Times are for the municipality’s map location and a clear, level horizon.</p>`;
  }

  function seasonalSummary(city) {
    const point = Number.isFinite(city.lat) && Number.isFinite(city.lon) ? city : mapToLonLat(projection, city.x, city.y);
    if (!point) return "";
    const key = city.id;
    if (!seasonCache.has(key)) {
      if (seasonCache.size >= 64) seasonCache.delete(seasonCache.keys().next().value);
      seasonCache.set(key, seasonalLight(referenceYear, point.lat, point.lon, zoneForCountry(city.country)));
    }
    const rows = seasonCache.get(key);
    return `<p class="muted small">Four dates in ${referenceYear}, at the municipality’s map location.</p>
      <dl class="daylight-stats">${rows.map(r => `<div><dt>${r.label}<br><span class="muted small">${r.date}</span></dt>
        <dd>${duration(r.daylight)} daylight<br><span class="muted small">${duration(r.darkness)} astronomical darkness</span></dd></div>`).join("")}</dl>
      <p class="muted small">Astronomical darkness starts when the sun is 18° below the horizon.</p>
      <p>To see the northern lights, you also need clear skies and aurora activity.</p>
      <div class="chips"><a class="chip" href="${esc(AURORA_FORECAST)}" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">Aurora forecast (NOAA) ↗</a></div>`;
  }
  app.addCitySections((city) => [{
    tab: "Daylight", title: "Daylight", html: `<div data-daylight-city="${esc(city.id)}">${citySummary(city)}</div>`,
  }, {tab: "Daylight", title: "Daylight through the year", html: `<div data-seasonal-city>${seasonalSummary(city)}</div>`}]);
  panelRoot.addEventListener("click", (event) => {
    const button = event.target.closest("[data-daylight-start]");
    if (button && !mode) toggle(button);
  });

  function refreshCity() {
    const city = app.state.selectedCity;
    const box = panelRoot.querySelector("[data-daylight-city]");
    if (city && box?.dataset.daylightCity === city.id) box.innerHTML = citySummary(city);
  }

  function refreshArtwork() {
    const appearance = mode && parameters && find("[data-season-art]").checked
      ? seasonForMonth(zonedParts(parameters.ms, selectedZone()).month) : "off";
    if (setIllustrationSeason(appearance)) app.invalidate();
  }
  find("[data-season-art]").addEventListener("change", refreshArtwork);

  function refresh(fill = false) {
    refreshArtwork();
    const city = app.state.selectedCity;
    if (!parameters) { refreshCity(); return; }
    const zone = selectedZone();
    const local = zonedParts(parameters.ms, zone);
    find("[data-zone]").textContent = `${COUNTRY[city?.country] || "Norway"} local time`;
    clock.dateTime = new Date(parameters.ms).toISOString();
    clock.textContent = `${dateFormat.format(Date.parse(local.date))} · ${localClock(parameters.ms, zone)}`;
    if (fill) {
      date.value = local.date;
      time.value = local.time;
      clearNotice();
    }
    find(".daylight-local").hidden = !!city;
    find(".daylight-local-link").hidden = !city;
    refreshCity();
  }

  function clearNotice() {
    notice.textContent = "";
    occurrence.value = "";
    occurrence.parentElement.hidden = true;
  }

  function schedule() {
    clearTimeout(timer);
    if (mode !== "now" || document.hidden) return;
    timer = setTimeout(tick, MINUTE - Date.now() % MINUTE + 30);
  }
  function tick() {
    if (mode === "now" && !document.hidden) {
      const ms = currentMinute();
      if (parameters.ms !== ms) {
        parameters = solarParameters(ms);
        refresh();
        app.requestDraw();
      }
    }
    schedule();
  }
  function set(next, p, write = true) {
    if (!mode && !next) return;
    mode = next;
    parameters = p;
    if (mode && !layerRegistered) {
      app.registerStaticLayer(daylightLayer(projection, app.w.raw, () => parameters));
      layerRegistered = true;
    }
    panel.hidden = !mode;
    for (const button of [desktopButton, mobileButton]) button.setAttribute("aria-pressed", String(!!mode));
    nowButton.setAttribute("aria-pressed", String(mode === "now"));
    chooseButton.setAttribute("aria-pressed", String(mode === "manual"));
    form.hidden = mode !== "manual";
    refresh(true);
    schedule();
    app.requestDraw();
    if (write) app.hash.soon();
  }

  function turnOff(restoreFocus = false) {
    set(null, null);
    if (restoreFocus) {
      const target = [opener, panelRoot.querySelector("[data-daylight-start]"), desktopButton, mobileButton]
        .find((el) => el?.getClientRects().length);
      target?.focus({ preventScroll: true });
    }
    opener = null;
  }
  function toggle(button) {
    if (mode) { turnOff(); return; }
    opener = button;
    set("now", solarParameters(currentMinute()));
    find("h2").focus({ preventScroll: true });
  }

  let chosenSeason = "summer", chosenHour = "12:00";
  function applySeason() {
    const instant = seasonInstant(referenceYear, chosenSeason, chosenHour, selectedZone());
    if (!instant) return;
    set("manual", solarParameters(instant));
  }
  panel.querySelectorAll("[data-season]").forEach(b => b.onclick = () => {
    chosenSeason = b.dataset.season; applySeason();
  });
  panel.querySelectorAll("[data-season-hour]").forEach(b => b.onclick = () => {
    chosenHour = b.dataset.seasonHour; applySeason();
  });
  find("[data-off]").onclick = () => turnOff(true);
  nowButton.onclick = () => { if (mode !== "now") set("now", solarParameters(currentMinute())); };
  chooseButton.onclick = () => {
    if (mode === "now") set("manual", parameters);
    date.focus();
  };
  find(".daylight-local-link").onclick = () => {
    const tab = panelRoot.querySelector('[data-cptab="Daylight"]');
    tab?.click();
    tab?.focus();
  };
  date.addEventListener("input", clearNotice);
  time.addEventListener("input", clearNotice);
  form.onsubmit = (event) => {
    event.preventDefault();
    if (!form.checkValidity()) {
      notice.textContent = `Enter a date from ${SOLAR_YEARS.min} to ${SOLAR_YEARS.max} and a time.`;
      form.querySelector(":invalid")?.focus();
      return;
    }
    try {
      const result = localToUtc(date.value, time.value, selectedZone(), { disambiguation: occurrence.value || "earlier" });
      if (result.status === "nonexistent") {
        notice.textContent = "That time is skipped when the clocks change. Choose another time.";
        time.focus();
        return;
      }
      if (result.status === "ambiguous" && !occurrence.value) {
        occurrence.parentElement.hidden = false;
        notice.textContent = "The clocks go back at this time. Choose the first or second time.";
        occurrence.focus();
        return;
      }
      const movingFocus = document.activeElement === occurrence;
      set("manual", solarParameters(result.date));
      if (movingFocus) form.querySelector('button[type="submit"]').focus();
    } catch (error) {
      if (!(error instanceof RangeError)) throw error;
      notice.textContent = "Choose a time within the supported years, 1800 to 2100 UTC.";
    }
  };

  let previousZone = selectedZone();
  app.on("select", () => {
    const zone = selectedZone();
    if (mode) refresh(zone !== previousZone);
    previousZone = zone;
  });
  app.on("escape", () => {
    if (!mode || (!panel.contains(document.activeElement) && app.state.selectedCity)) return false;
    turnOff(true);
    return true;
  });
  document.addEventListener("visibilitychange", tick);
  app.hash.register("daylight", {
    get: () => mode === "now" ? "now" : parameters ? new Date(parameters.ms).toISOString() : null,
    set(value) {
      if (value === "now") return set("now", solarParameters(currentMinute()), false);
      if (value) {
        try { return set("manual", solarParameters(value), false); } catch (error) {
          if (!(error instanceof RangeError)) throw error;
        }
      }
      set(null, null, false);
    },
  });
}
