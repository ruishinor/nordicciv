import { esc } from "../../format.js";
import { lonLatToMap, projectionFrom } from "../../util/geo.js";
import { localProfile, showOnMap, stationDetails } from "./profile.js";

export function install(app) {
  const id = "climate-stations";
  let on = false, selected = null, groups = [];
  let points = [], scale = 0, trigger = null;
  const data = () => app.data.climate;

  const card = document.createElement("section");
  card.className = "panel climate-station-card";
  card.id = "climate-station-card";
  card.hidden = true;
  card.setAttribute("aria-label", "Climate station");
  document.body.append(card);

  function close(restoreFocus = false) {
    card.hidden = true;
    selected = null;
    if (restoreFocus && trigger?.isConnected) trigger.focus();
    trigger = null;
    app.requestDraw();
  }

  function open(station, choices = [station], fly = false) {
    if (card.hidden) trigger = document.activeElement;
    selected = station.id;
    card.innerHTML = `<div class="climate-card-head"><h2>Climate station</h2>
      <button class="icon-btn" type="button" aria-label="Close climate station">×</button></div>
      <p class="muted small">Typical conditions, 1991–2020</p>
      ${choices.length > 1 ? `<label>Station <select>${choices.map((s) =>
        `<option value="${esc(s.id)}"${s.id === selected ? " selected" : ""}>${esc(s.name)}</option>`).join("")}</select></label>` : ""}
      ${stationDetails(data(), station)}`;
    card.hidden = false;
    const closeButton = card.querySelector("button");
    closeButton.onclick = () => close(true);
    const select = card.querySelector("select");
    if (select) select.onchange = () => {
      open(choices.find((s) => s.id === select.value), choices);
      card.querySelector("select").focus();
    };
    closeButton.focus();
    if (fly) app.flyTo(station.x, station.y, Math.max(app.cam.scale, 1.6));
    app.requestDraw();
  }

  function visibleGroups(s) {
    if (s === scale) return groups;
    scale = s;
    groups = [];
    for (const p of points) {
      const group = groups.find((g) => Math.hypot(g.x - p.x, g.y - p.y) * s < 14);
      if (group) group.stations.push(p);
      else groups.push({ x: p.x, y: p.y, stations: [p] });
    }
    return groups;
  }

  app.registerStaticLayer({
    id, z: app.layerZ.RESOURCES + 1,
    visible: () => on && points.length > 0,
    sig: () => `climate|${selected || ""}`,
    draw(ctx, vp, w, view) {
      const radius = 5 / view.s;
      ctx.strokeStyle = "#f5edda";
      ctx.lineWidth = 1.3 / view.s;
      for (const group of visibleGroups(view.s)) {
        const { x, y, stations } = group;
        if (x < vp.x0 - radius || x > vp.x1 + radius || y < vp.y0 - radius || y > vp.y1 + radius) continue;
        ctx.fillStyle = stations.some((s) => s.id === selected) ? "#c4772e" : "#295d5a";
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, 2 * Math.PI);
        ctx.fill();
        ctx.stroke();
        if (stations.length > 1) {
          ctx.fillStyle = "#f5edda";
          ctx.fillRect(x - 2 / view.s, y - 0.5 / view.s, 4 / view.s, 1 / view.s);
        }
      }
    },
    hit(x, y, Rpx) {
      const s = Rpx / app.w.grid.R;
      let best = null, distance = 10;
      for (const group of visibleGroups(s)) {
        const d = Math.hypot(group.x - x, group.y - y) * s;
        if (d < distance) { best = group; distance = d; }
      }
      return best;
    },
    tooltip: ({ stations }) => stations.length === 1
      ? `<b>${esc(stations[0].name)}</b><br>Climate station · 1991–2020`
      : `<b>${stations.length} climate stations</b><br>Select to see the stations`,
    click({ stations }) { open(stations[0], stations); return true; },
  });
  app.ui.addMapToggle({
    id, label: "Climate stations", icon: "terrain", default: false,
    title: "Weather station averages for 1991–2020",
    get: () => on,
    set(value) { on = value; if (!on) close(); },
  });

  const regionalReference = new Map();
  for (const city of app.data.cities) {
    const key = city.states[0];
    if (city.population > (regionalReference.get(key)?.population ?? -1)) regionalReference.set(key, city);
  }
  function local(city, region) {
    return localProfile(data(), city || regionalReference.get(region?.fips), region);
  }
  app.climate = {
    advisor(city, region) {
      if (!data()) return "";
      return `<div class="obs"><h4>Climate, 1991–2020</h4>${city || region ? local(city, region)
        : `<p>Explore temperature and precipitation at ${data().stations.length} selected weather stations.</p>${showOnMap}`}</div>`;
    },
  };
  app.addCitySections((city) => data() ? [{ tab: "Overview", title: "Climate", html: local(city) }] : []);
  app.addStateSections((region) => data() ? [{ title: "Climate", html: local(null, region) }] : []);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-climate-map], [data-climate-station]");
    if (!button) return;
    app.ui.setMapToggle(id, true);
    const station = points.find((p) => p.id === button.dataset.climateStation);
    if (station) open(station, [station], true);
  });
  app.on("escape", () => {
    if (card.hidden) return false;
    close(true);
    return true;
  });
  app.loadData("climate").then((result) => {
    if (!result) return;
    const proj = projectionFrom(app.w);
    points = result.stations.map((s) => ({ ...s, ...lonLatToMap(proj, s.lon, s.lat) })).filter((p) => Number.isFinite(p.x));
    scale = 0;
    app.invalidate();
    if (app.state.selectedCity) app.selectCity(app.state.selectedCity, { fly: false });
    else if (app.state.selectedState != null) app.selectState(app.w.raw.states[app.state.selectedState].fips, { fly: false });
  });
}
