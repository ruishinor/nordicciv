import { esc, int } from "../../format.js";
import { validLatLon } from "../../app/maps.js";
import { solarDay, zoneForCountry } from "../../util/solar.js";

const fin = Number.isFinite;
const fmt = v => v.toLocaleString("en-GB", {maximumFractionDigits: 1});
const sort = (a,b) => b.value - a.value || a.city.localeCompare(b.city);
const source = (title, stops, id) => ({id, title, stops});

/** Build short map tours from the shipped records, not estimated routes or flows. */
export function buildJourneys(data) {
  const cities = data.cities || [], world = data.world || {};
  const byId = new Map(cities.map(c => [c.id, c]));
  const lens = id => data.lenses?.lenses?.find(l => l.id === id);
  const cells = new Map();
  (world.owner || []).forEach((owner, i) => {
    const id = world.counties?.[world.county?.[i]]?.geoid;
    if (owner >= 0 && byId.has(id)) {
      if (!cells.has(id)) cells.set(id, []);
      cells.get(id).push(i);
    }
  });
  const localValues = (city, id) => (cells.get(city.id) || []).map(i => lens(id)?.values[i]).filter(fin);
  const routes = [];
  const add = (id, title, stops) => { if (stops.length >= 2) routes.push(source(title, stops, id)); };
  const hydro = (data.resources?.items || []).filter(p => p.type === "hydro" && fin(p.value) && p.value >= 50 && byId.get(p.cbsa)?.country === "NO")
    .map(p => ({city: p.cbsa, value: p.value, name: p.name}));
  const seen = new Set();
  add("hydropower", "Norwegian hydropower", hydro.sort(sort).filter(p => {
    if (seen.has(p.city)) return false; seen.add(p.city); return true;
  }).slice(0, 3).map(p => ({city:p.city, hydro:true,
    text: p.name + " has " + int(p.value) + " MW of installed hydropower capacity. That is capacity, not yearly electricity production.",
    source:"Powerplantmatching · mapped plants of 50 MW or more"})));
  const industry = cities.filter(c => c.country === "SE" && c.jobs?.BC >= 250 && fin(c.jobs_total) && c.jobs_total >= c.jobs.BC)
    .map(c => ({city:c.id, value:c.jobs.BC / c.jobs_total, jobs:c.jobs.BC}));
  add("industry", "Swedish industrial geography", industry.sort(sort).slice(0,3).map(p => ({
    city:p.city, lens:"share_BC", text:int(p.jobs) + " jobs in mining and manufacturing account for " + fmt(100*p.value) + "% of recorded local jobs.",
    source:"Statistics Sweden · workplaces, 2024 · municipalities with at least 250 mining and manufacturing jobs"
  })));
  const farmland = cities.filter(c => c.country === "DK").map(c => {
    const values = localValues(c,"farmland");
    return {city:c.id, count:values.length, value:values.length ? values.reduce((a,b)=>a+b,0)/values.length : null};
  }).filter(p=>p.count>=3 && fin(p.value) && p.value>0);
  add("farmland","Danish agricultural landscapes",farmland.sort(sort).slice(0,3).map(p=>({
    city:p.city,lens:"farmland",text:"The displayed farmland share averages "+fmt(p.value)+"% across "+p.count+" mapped land hexes assigned to this municipality.",
    source:"CORINE 2018 · average of map hex values, not the exact municipal land share"
  })));
  const winter = ["DK-101","SE-2584","NO-5501"].map(id=>byId.get(id)).filter(c=>c && validLatLon(c.lat,c.lon))
    .sort((a,b)=>a.lat-b.lat).map(c=>{
      const minutes=solarDay("2026-12-21",c.lat,c.lon,zoneForCountry(c.country)).daylightMinutes;
      const m=Math.round(minutes);
      return {city:c.id,daylight:true,text:"On 21 December 2026: "+Math.floor(m/60)+" h "+m%60+" min of daylight. Open Daylight to explore other dates.",
        source:"Calculated solar position · clear, level horizon at the map location"};
    });
  add("daylight","Winter daylight from south to north",winter);
  const growth = cities.map(c=>{
    const values=localValues(c,"urban_growth");
    return {city:c.id,value:values.reduce((a,b)=>a+b,0)};
  }).filter(p=>p.value>0);
  add("built-up","How built-up land changed",growth.sort(sort).slice(0,3).map(p=>({
    city:p.city,lens:"urban_growth",text:int(p.value)+" one-kilometre cells in the displayed hexes changed to built-up, industrial, mining or transport land between 1990 and 2018.",
    source:"CORINE 1990 and 2018 · mapped cells, not a yearly history"
  })));
  return routes;
}

export function resolveJourney(journeys,value) {
  if (typeof value !== "string") return null;
  const m=/^([a-z-]+):([0-9]+)$/.exec(value);
  if (!m) return null;
  const index=Number(m[2]), j=journeys.find(j=>j.id===m[1]);
  return j && Number.isSafeInteger(index) && j.stops[index] ? {id:j.id,index} : null;
}

export function satelliteUrl(city) {
  if (!validLatLon(city?.lat,city?.lon)) return null;
  const fixed = n => String(Math.round(n*1e5)/1e5);
  return "https://browser.dataspace.copernicus.eu/?" + new URLSearchParams({
    zoom:"11", lat:fixed(city.lat), lng:fixed(city.lon), datasetId:"S2_L2A_CDAS", layerId:"1_TRUE_COLOR", date:"latest"
  });
}
const link=(url,label)=>'<a class="chip" href="'+esc(url)+'" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">'+esc(label)+' ↗</a>';
export function contextLinks(city) {
  const satellite=satelliteUrl(city);
  if (!satellite) return "";
  return '<div class="chips">'+link(satellite,"Satellite imagery (Copernicus)")+link("https://www.yr.no/en","Find forecast on Yr")+'</div>'+
    '<p class="muted small">For Yr, search for '+esc(city.place || city.name)+' or enter '+city.lat.toFixed(4)+', '+city.lon.toFixed(4)+'. Copernicus opens around the map location; cloud cover and sign-in may affect imagery.</p>';
}
