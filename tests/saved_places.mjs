import test from "node:test";
import assert from "node:assert/strict";
import {placeLists,SAVED_KEY} from "../web/js/ext/explore/places.js";
const valid = id => /^NO-\d+$/.test(id);
const storage = () => {
  const data = new Map();
  return {getItem:k=>data.get(k),setItem:(k,v)=>data.set(k,v)};
};
test("saved places survive reload but recent visits do not", () => {
  const s = storage(), a = placeLists(valid,s);
  a.toggle("NO-1"); a.toggle("NO-2"); a.visit("NO-1"); a.visit("NO-2"); a.visit("NO-1");
  assert.deepEqual(a.recent,["NO-1","NO-2"]);
  const b = placeLists(valid,s);
  assert.deepEqual(b.saved,["NO-2","NO-1"]);
  assert.deepEqual(b.recent,[]);
  b.remove("NO-1"); assert.deepEqual(JSON.parse(s.getItem(SAVED_KEY)),["NO-2"]);
  a.clearRecent(); assert.deepEqual(a.recent,[]);
});
test("invalid saved IDs, duplicates, limits and unavailable storage", () => {
  const s = storage();
  s.setItem(SAVED_KEY,JSON.stringify(["NO-1","NO-1","invalid",null]));
  const a = placeLists(valid,s);
  assert.deepEqual(a.saved,["NO-1"]);
  for(let n=2;n<=40;n++) { a.toggle("NO-"+n); a.visit("NO-"+n); }
  assert.equal(a.saved.length,30); assert.equal(a.recent.length,12);
  const b = placeLists(valid,{getItem(){throw Error("denied")},setItem(){throw Error("denied")}});
  assert.equal(b.toggle("NO-1"),true); assert.equal(b.persistent,false);
  assert.deepEqual(b.saved,["NO-1"]);
});
