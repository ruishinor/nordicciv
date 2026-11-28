import { esc } from "../format.js";
const publishers = { NO:"Statistics Norway", SE:"Statistics Sweden", DK:"Statistics Denmark" };
const agencies = { NO:"ssb", SE:"scb", DK:"dst" };
// Official table titles, checked against the publishers' table pages where available.
const titles = {
  "07459":"Population, by sex and one-year age groups (M)",
  "07984":"Employed persons, by sex, age and industry division (17 groups, SIC2007). 4th quarter (M)",
  "09280":"Area of land and fresh water, by municipality (km²) (M)",
  "06944":"Household income, by type of household. Number of households and median. Statistical tracts (M) (UD)",
  FOLK1A:"Population at the first day of the quarter by region, sex, age and marital status",
  RAS501:"Employed (end November) by workplace municipality, industry (DB25 36-grouping), socioeconomic status, age and sex",
};
export function flag(country) {
  const name = {NO:"Norway",SE:"Sweden",DK:"Denmark"}[country];
  return name ? `<img class="country-flag" src="assets/flags/${country}.svg" alt="${name}">` : "";
}
export function sourceRef(registry, country, table, label) {
  if (!table || !publishers[country]) return null;
  const source = registry.find(s => s.id === agencies[country]);
  const file = source?.files?.find(f => f.file?.startsWith(table + "_")) || registry.find(s => s.id === "regional_accounts")?.files?.find(f => f.file?.startsWith(agencies[country] + "_" + table + "_") || f.file?.startsWith(agencies[country] + "_" + table + "."));
  if (!file || !/^https:\/\//.test(file.url || "")) return null;
  const url = country === "NO" ? "https://www.ssb.no/en/statbank/table/" + table + "/" :
    country === "DK" ? "https://www.statbank.dk/statbank5a/SelectVarVal/Define.asp?Maintable=" + table + "&PLanguage=1" : file.url;
  return { url, publisher: publishers[country], label: titles[table] || label, table, retrieved: file.retrieved, titleVerified: !!titles[table] };
}
export function sourceLink(ref, label, note = "") {
  if (!ref) return "";
  const title = ref.titleVerified ? ref.label : `[${ref.label}]`;
  const retrieved = new Date(ref.retrieved || "");
  const date = Number.isFinite(retrieved.getTime()) ? ` Retrieved ${new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric", timeZone: "UTC" }).format(retrieved)}.` : "";
  const citation = `${ref.publisher}. (n.d.). ${title} (Table ${ref.table}) [Data set].${date}`;
  return `<details class="metric-source"><summary aria-label="${esc(label)}" title="${esc(citation + (note ? " " + note : ""))}">*</summary><div class="metric-pop">${esc(ref.publisher)}. (n.d.). <a href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer"><i>${esc(title)}</i> (Table ${esc(ref.table)})</a> [Data set].${esc(date)} ${esc(note)}</div></details>`;
}
