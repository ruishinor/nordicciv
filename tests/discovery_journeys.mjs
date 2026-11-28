import test from "node:test";
import assert from "node:assert/strict";
import {buildJourneys,resolveJourney,satelliteUrl,contextLinks} from "../web/js/ext/explore/journeys.js";
test("journeys require actual distinct municipalities and positive qualifying values",()=>{
  const data={cities:[{id:"NO-1",country:"NO"},{id:"NO-2",country:"NO"}],resources:{items:[
    {type:"hydro",cbsa:"NO-1",value:100,name:"Plant A"},{type:"hydro",cbsa:"NO-1",value:90,name:"Plant B"},
    {type:"hydro",cbsa:"NO-2",value:80,name:"Plant C"},{type:"hydro",cbsa:"missing",value:200,name:"Unknown"}]}};
  const j=buildJourneys(data);
  assert.equal(j.length,1);
  assert.deepEqual(j[0].stops.map(s=>s.city),["NO-1","NO-2"]);
  assert.match(j[0].stops[0].text,/100 MW/);
  assert.deepEqual(resolveJourney(j,"hydropower:1"),{id:"hydropower",index:1});
  for(const bad of ["hydropower:2","hydropower:-1","hydropower:1.5","unknown:0","hydropower:0:0",null]) assert.equal(resolveJourney(j,bad),null);
});
test("external map links only contain valid public coordinates and safe attributes",()=>{
  const c={name:"<script>",lat:69.6492,lon:18.9553};
  const u=new URL(satelliteUrl(c));
  assert.equal(u.hostname,"browser.dataspace.copernicus.eu");
  assert.equal(u.searchParams.get("lat"),"69.6492");
  assert.equal(u.searchParams.get("lng"),"18.9553");
  assert.equal(u.searchParams.get("date"),"latest");
  const html=contextLinks(c);
  assert.match(html,/noopener noreferrer/);
  assert.match(html,/&lt;script&gt;/);
  assert.doesNotMatch(html,/<script>/);
  assert.equal(satelliteUrl({lat:91,lon:0}),null);
  assert.equal(contextLinks({lat:null,lon:0}),"");
});
