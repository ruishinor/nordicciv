import test from "node:test";
import assert from "node:assert/strict";
import { glacierChanges, glacierHistoryHtml, hazardLinksHtml } from "../web/js/ext/nordic/environment-history.js";

test("published glacier observations are scoped and not interpolated", () => {
  assert.equal(glacierChanges("").length, 3);
  assert.equal(glacierChanges("NO").length, 3);
  assert.deepEqual(glacierChanges("NO-46").map(g => [g.from, g.to, g.before, g.after, g.loss, g.percent]), [[1966, 2020, 486, 456, 30, 6.2]]);
  assert.deepEqual(glacierChanges("NO-56").map(g => [g.from, g.to, g.before, g.after, g.loss]), [[1970, 2023, 4.8, 1.4, 3.4], [1970, 2023, 14.9, 7.9, 7]]);
  assert.equal(glacierHistoryHtml("SE"), "");
  assert.equal(glacierHistoryHtml("NO-03"), "");
  assert.match(glacierHistoryHtml("NO-56"), /Nordmannsjøkelen/);
  assert.doesNotMatch(glacierHistoryHtml("NO-56"), /Jostedalsbreen/);
});
test("hazard links describe Norwegian susceptibility rather than current warnings", () => {
  assert.equal(hazardLinksHtml("DK"), "");
  assert.equal(hazardLinksHtml("SE-01"), "");
  assert.match(hazardLinksHtml("NO-03"), /temakart\.nve\.no/);
  assert.match(hazardLinksHtml("NO"), /not current warnings/);
});
