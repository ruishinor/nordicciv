import { esc } from "../../format.js";

const fmt = new Intl.NumberFormat("en-GB");
const LABELS = {all:"All categories", aviation:"Aviation", ferry:"Ferry passengers", freight:"Ferry freight"};
const COLORS = {aviation:"#68c5ff", ferry:"#65d1b3", freight:"#e4a34f"};
const coords = n => Number.isFinite(n?.x) && Number.isFinite(n?.y) ? [n.x,n.y] : null;
export const mapped = (packet, category="all") => packet.flows.filter(f =>
  (category==="all" || f.category===category) && coords(packet.nodes[f.origin]) && coords(packet.nodes[f.destination]));

export function install(app) {
  let packet=null, on=false, category="all";
  function related(city) {
    return packet?.flows.filter(f=>[f.origin,f.destination].some(id=>packet.nodes[id].city===city.id)) || [];
  }
  function nodeLabel(id,city) {
    const n=packet.nodes[id];
    return n.city && n.city!==city.id && app.cityById.has(n.city)
      ? '<button type="button" class="chip" data-transport-city="'+esc(n.city)+'">'+esc(n.name)+'</button>'
      : esc(n.name);
  }
  function section(city) {
    const flows=related(city);
    if(!flows.length)return [];
    const options=Object.entries(LABELS).map(([key,label])=>'<option value="'+key+'"'+(key===category?' selected':'')+'>'+label+'</option>').join("");
    const rows=flows.map(f=>'<li data-transport-category="'+f.category+'"'+(category!=="all"&&f.category!==category?' hidden':'')+'>'+
      '<div>'+nodeLabel(f.origin,city)+(f.directed?' → ':' ↔ ')+nodeLabel(f.destination,city)+'</div>'+
      '<div><b>'+fmt.format(f.value)+'</b> '+esc(f.unit)+' · '+esc(LABELS[f.category])+(f.directed?'':' · both directions')+'</div>'+
      '<div class="muted small">'+(!coords(packet.nodes[f.origin])||!coords(packet.nodes[f.destination])?'Listed only; no map line. ':'')+
      '<a href="'+esc(packet.tables[f.table].url)+'" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">Statistics Denmark '+esc(f.table)+' ↗</a></div></li>').join("");
    return [{tab:"Overview",title:"Transport · 2024",html:'<div class="transport-section">'+
      '<p class="muted small">Selected Danish airport and ferry statistics, 2024. Counts are rounded to thousands. Ferry totals combine both directions; passenger movements and freight tonnes are separate. Country-level airport totals are listed without map lines. Læsø uses its municipality centre; Fanø has no mapped endpoint.</p>'+
      '<label>Category <select data-transport-filter>'+options+'</select></label>'+
      '<div class="chips"><button type="button" class="chip" data-transport-map>Show transport connections</button></div>'+
      '<p class="muted small">Lines connect selected endpoints, not travel routes. Blue: aviation. Green: ferry passengers. Gold dashed: freight.</p>'+
      '<ul class="transport-observations">'+rows+'</ul><p data-transport-empty class="muted small"'+(flows.some(f=>category==="all"||f.category===category)?' hidden':'')+'>No published observations in this category for this municipality.</p></div>'}];
  }
  app.registerStaticLayer({id:"transport-connections",z:app.layerZ.RESOURCES+2,
    visible:()=>on&&!!packet,sig:()=>on+"|"+category,
    draw(ctx,vp,w,view) {
      if(!packet)return;
      ctx.save();
      for(const f of mapped(packet,category)) {
        const a=coords(packet.nodes[f.origin]),b=coords(packet.nodes[f.destination]);
        ctx.strokeStyle=COLORS[f.category];ctx.globalAlpha=.85;
        ctx.lineWidth=2/view.s;
        ctx.setLineDash(f.category==="freight"?[5/view.s,4/view.s]:[]);
        ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
        if(f.directed){
          const angle=Math.atan2(b[1]-a[1],b[0]-a[0]),x=a[0]+(b[0]-a[0])*.62,y=a[1]+(b[1]-a[1])*.62,d=7/view.s;
          ctx.beginPath();ctx.moveTo(x-d*Math.cos(angle-.45),y-d*Math.sin(angle-.45));ctx.lineTo(x,y);
          ctx.lineTo(x-d*Math.cos(angle+.45),y-d*Math.sin(angle+.45));ctx.stroke();
        }
      }
      ctx.restore();
    }
  });
  app.ui.addMapToggle({id:"transport-connections",label:"Transport connections",icon:"map",default:false,
    title:"Selected 2024 aviation and ferry connections; schematic lines",get:()=>on,set(v){on=!!v;app.invalidate();}});
  function setCategory(value, write=true) {
    if(!Object.hasOwn(LABELS,value))return;
    category=value;
    for(const section of document.querySelectorAll(".transport-section")){
      const select=section.querySelector("[data-transport-filter]");if(select)select.value=value;
      const rows=[...section.querySelectorAll("[data-transport-category]")];
      for(const row of rows)row.hidden=value!=="all"&&row.dataset.transportCategory!==value;
      const empty=section.querySelector("[data-transport-empty]");if(empty)empty.hidden=rows.some(row=>!row.hidden);
    }
    app.invalidate();
    if(write) app.hash.soon();
  }
  app.hash.register("transport-category", {
    get:()=>category==="all"?null:category,
    set:value=>setCategory(Object.hasOwn(LABELS,value)?value:"all",false),
  });
  document.addEventListener("change",event=>{
    if(event.target.matches("[data-transport-filter]"))setCategory(event.target.value);
  });
  document.addEventListener("click",event=>{
    const b=event.target.closest("[data-transport-city],[data-transport-map]");
    if(!b||!packet)return;
    if(b.dataset.transportCity){app.selectCity(b.dataset.transportCity);return;}
    app.ui.setMapToggle("transport-connections",true);
    const selected=app.state.selectedCity;
    const ids=new Set(related(selected||{}).filter(f=>category==="all"||f.category===category).flatMap(f=>[f.origin,f.destination]));
    const points=[...ids].map(id=>coords(packet.nodes[id])).filter(Boolean);
    if(points.length>1)app.fitBounds(Math.min(...points.map(p=>p[0])),Math.min(...points.map(p=>p[1])),
      Math.max(...points.map(p=>p[0])),Math.max(...points.map(p=>p[1])),{maxScale:8});
    app.ui.toast("Transport connections · 2024");
  });
  app.transport={get packet(){return packet;},get on(){return on;},get category(){return category;},setCategory,mapped:()=>packet?mapped(packet,category):[]};
  app.loadData("transport").then(data=>{
    if(!data)return;
    packet=data;
    app.addCitySections(section);
    const picks=["FLYV33:F10015:T10030:2024","SKIB32:10240:8005:2024","SKIB32:10270:8065:2024"];
    const discoveries=picks.map(id=>packet.flows.find(f=>f.id===id)).filter(Boolean).map(f=>({
      id:"transport:"+f.id,key:"transport",city:packet.nodes[f.origin].city,category:f.category,
      text:packet.nodes[f.origin].name+(f.directed?" to ":" and ")+packet.nodes[f.destination].name+": "+fmt.format(f.value)+" "+f.unit+" in 2024.",
      def:packet.tables[f.table].note
    }));
    app.explore?.addDiscoveries(discoveries,d=>{setCategory(d.category);app.ui.setMapToggle("transport-connections",true);});
    app.invalidate();
  });
}
