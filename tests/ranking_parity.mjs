// Checks the browser's ranking functions (web/js/stats.js) against the same hand-calculated fixture as the
// pipeline (tests/fixtures/ranking_cases.json). Exit code 0 = all cases agree.
import { readFileSync } from "node:fs";
import { competitionRanks, rankIntervals, rankList } from "../web/js/stats.js";

const { cases } = JSON.parse(readFileSync(new URL("./fixtures/ranking_cases.json", import.meta.url)));
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
let bad = 0;
for (const c of cases) {
  const r = competitionRanks(c.lo), iv = rankIntervals(c.lo, c.hi);
  if (!same(r, c.rank)) { bad++; console.log("rank", c.name, r, c.rank); }
  if (!same(iv, c.interval)) { bad++; console.log("interval", c.name, iv, c.interval); }
  // rankList over the same values must give the same rank and range per item, and count only available values
  const list = c.lo.map((v, i) => ({ id: String(i), name: "a", v, hi: c.hi ? c.hi[i] : null }));
  const out = rankList(list, (x) => x.v, { hiOf: c.hi ? (x) => x.hi : null });
  if (out.length !== c.n) { bad++; console.log("count", c.name, out.length, c.n); }
  for (const e of out) {
    const i = Number(e.x.id);
    const want = c.interval[i][0] !== c.interval[i][1] ? c.interval[i] : undefined;
    if (e.rank !== c.rank[i] || !same(e.range, want)) { bad++; console.log("rankList", c.name, i, e.rank, e.range); }
  }
  // ascending order is the mirror image: ranking -v descending
  const asc = rankList(list, (x) => x.v, { asc: true, hiOf: c.hi ? (x) => x.hi : null });
  const neg = c.lo.map((v, i) => (v == null ? null : -(c.hi ? c.hi[i] : v)));
  const negHi = c.lo.map((v) => (v == null ? null : -v));
  const mirror = rankIntervals(neg, negHi), mr = competitionRanks(c.lo.map((v) => (v == null ? null : -v)));
  for (const e of asc) {
    const i = Number(e.x.id);
    const want = mirror[i][0] !== mirror[i][1] ? mirror[i] : undefined;
    if (e.rank !== mr[i] || !same(e.range, want)) { bad++; console.log("asc", c.name, i, e.rank, e.range, mr[i], mirror[i]); }
  }
}
console.log(bad ? `${bad} mismatches` : `ranking parity: ${cases.length} cases agree`);
process.exit(bad ? 1 : 0);
