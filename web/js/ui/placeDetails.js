import { esc } from "../format.js";
const publishers = { NO:"Statistics Norway", SE:"Statistics Sweden", DK:"Statistics Denmark" };
const agencies = { NO:"ssb", SE:"scb", DK:"dst" };
export function flag(country) {
  const name = {NO:"Norway",SE:"Sweden",DK:"Denmark"}[country];
  return name ? `<img class="country-flag" src="assets/flags/${country}.svg" alt="${name}">` : "";
}
export function sourceRef(registry, country, table, label) {
  if (!table || !publishers[country]) return null;
  const source = registry.find(s => s.id === agencies[country]);
  const file = source?.files?.find(f => f.file?.startsWith(table + "_"));
  if (!file || !/^https:\/\//.test(file.url || "")) return null;
  const url = country === "NO" ? "https://www.ssb.no/en/statbank/table/" + table + "/" :
    country === "DK" ? "https://www.statbank.dk/" + table : file.url;
  return { url, publisher: publishers[country], label, table };
}
export function sourceLink(ref, label, note = "") {
  if (!ref) return "";
  const citation = `${ref.publisher}. (n.d.). ${ref.label} (Table ${ref.table}) [Data set].`;
  return `<details class="metric-source"><summary aria-label="${esc(label)}" title="${esc(citation + (note ? " " + note : ""))}">*</summary><div class="metric-pop">${esc(ref.publisher)}. (n.d.). <a href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer"><i>${esc(ref.label)}</i> (Table ${esc(ref.table)})</a> [Data set]. ${esc(note)}</div></details>`;
}
