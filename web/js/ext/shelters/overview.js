import { OVERVIEW } from "./overview-data.js";
import { esc } from "../../format.js";

const int = n => n == null ? "Not reported" : n.toLocaleString("en-GB");
const link = (url,label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
const labels=["Building-associated shelters (sikringsrum)","Public concrete shelters (betondækningsgrave)","Other public shelters","Supplementary protective spaces","All reported places"];
const list=(items)=>`<dl class="shelter-overview-list">${items.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${int(v)}</dd></div>`).join("")}</dl>`;
function danish(ids) {
  const d=OVERVIEW.DK;
  const rows=ids.map(id=>d.municipalities[id]);
  if(!rows.length||rows.some(r=>!r))return '<p>Municipal inventory not available for this selection.</p>';
  const sums=rows.reduce((a,r)=>a.map((v,i)=>v+r[i]),[0,0,0,0,0]);
  return `<div class="shelter-overview"><p><b>${int(sums[1]+sums[2])}</b> reported public shelter places · June 2024</p>
  ${list(labels.map((k,i)=>[k,sums[i]]))}
  <p class="muted small">Building-associated rooms serve the building's occupants and workers. Supplementary spaces are a separate, less protective category. The 2024 inventory reports capacity, not current condition or access. No shelter addresses are included.</p>
  <p class="small">${link(d.url,"Municipal inventory, 19 June 2024")} · ${link(d.guidance,"Danish shelter guidance")}</p></div>`;
}
function swedish(ids) {
  const d=OVERVIEW.SE;
  let local="";
  if(d.municipalities && ids.length && ids.every(id=>Object.hasOwn(d.municipalities,id))){
    const vals=ids.map(id=>d.municipalities[id]);
    const n=vals.reduce((s,v)=>s+v[0],0),p=vals.reduce((s,v)=>s+v[1],0),missing=vals.reduce((s,v)=>s+v[2],0);
    local=`<div class="sh-stats"><div><b>${int(n)}</b><span>registered shelters</span></div><div><b>${int(p)}</b><span>registered places${missing ? " ("+int(missing)+" rooms without capacity)" : ""}</span></div></div><p class="muted small">MCF register, retrieved ${esc(d.retrieved.slice(0,10))}. Assigned by municipality boundaries${d.unassigned?.[0] ? "; "+int(d.unassigned[0])+" records could not be assigned nationwide" : ""}.</p>`;
  }else local='<p>Local shelter locations and capacity are available on MCF’s official map. Municipality totals are not yet included here.</p>';
  return `<div class="shelter-overview">${local}<p>Across Sweden, MCF reports more than ${int(d.shelters_approx)} shelters with room for about ${int(d.places_approx)} people. During heightened preparedness, shelters are made accessible to people who need protection, up to their capacity.</p>
  <p class="muted small">Registered capacity is not current access or readiness. The Swedish register includes shelters in privately owned buildings; it is not Norway’s public-only register.</p>
  <p class="small">${link(d.map,"Official Swedish shelter map")} · ${link(d.guidance,"Swedish shelter guidance")}</p></div>`;
}
export function overview(country, ids) {
  return country==="DK" ? danish(ids) : country==="SE" ? swedish(ids) : "";
}
export function nationalOverview(country) {
  return overview(country,country==="DK"?Object.keys(OVERVIEW.DK.municipalities):Object.keys(OVERVIEW.SE.municipalities||{}));
}
