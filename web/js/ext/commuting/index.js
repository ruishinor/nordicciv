import { esc } from "../../format.js";

const fmt = new Intl.NumberFormat("en-GB");
export function partners(flows, id) {
  const incoming=[], outgoing=[];
  for (const [origin,destination,value] of flows) {
    if (origin===id) outgoing.push({id:destination,value});
    if (destination===id) incoming.push({id:origin,value});
  }
  const top = a => a.sort((a,b)=>b.value-a.value || a.id.localeCompare(b.id)).slice(0,8);
  return {incoming:top(incoming),outgoing:top(outgoing)};
}

export function install(app) {
  let packet=null, on=false;
  const byId=app.cityById;
  const index=new Map();
  const selected=()=>app.state.selectedCity;
  function list(city) {return index.get(city.id)||{incoming:[],outgoing:[]};}
  function rows(items) {
    if(!items.length) return '<p class="muted small">No qualifying published pairs in this selection.</p>';
    return '<ul class="commuting-partners">'+items.map(p=>'<li><button class="chip" data-commuting-city="'+esc(p.id)+'">'+esc(byId.get(p.id).name)+'</button><span>'+fmt.format(p.value)+'</span></li>').join("")+'</ul>';
  }
  function section(city) {
    if (!packet || city.country!=="NO") return [];
    const p=list(city);
    return [{tab:"Overview",title:"Commuting · 2024",html:
      '<div class="commuting-section"><p class="muted small">Employed residents and workplaces in other Norwegian municipalities, fourth quarter 2024. At least 25 people per direction; eight largest partners shown. Counts are people, not trips.</p>'+
      '<h4>Residents working elsewhere</h4>'+rows(p.outgoing)+
      '<h4>Workers living elsewhere</h4>'+rows(p.incoming)+
      '<div class="chips"><button class="chip" data-commuting-map>Show connections</button></div>'+
      '<p class="muted small">Blue dashed lines: incoming. Gold solid lines: outgoing. Lines connect municipality centres, not actual transport routes. <a href="'+esc(packet.source.url)+'" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">SSB table 03321 ↗</a></p></div>'}];
  }
  const coords = city => Number.isFinite(city?.x)&&Number.isFinite(city?.y) ? [city.x,city.y] : null;
  app.registerStaticLayer({id:"commuting-connections",z:app.layerZ.RESOURCES+1,
    visible:()=>on && !!packet && selected()?.country==="NO",
    sig:()=>String(on)+"|"+(selected()?.id||""),
    draw(ctx,vp,w,view) {
      const city=selected(), a=coords(city);
      if(!a) return;
      const p=list(city);
      ctx.save();
      for(const [key,color] of [["outgoing","#e4a34f"],["incoming","#68c5ff"]]) {
        ctx.strokeStyle=color;
        ctx.globalAlpha=.85;
        for(const item of p[key]) {
          const b=coords(byId.get(item.id));
          if(!b) continue;
          ctx.lineWidth=Math.min(5,1+Math.log10(item.value))/view.s;
          ctx.setLineDash(key==="incoming"?[6/view.s,4/view.s]:[]);
          ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
        }
      }
      ctx.restore();
    }
  });
  app.ui.addMapToggle({id:"commuting-connections",label:"Commuting connections",icon:"map",default:false,
    title:"Selected Norwegian municipality: incoming dashed blue, outgoing solid gold; schematic lines, not routes",
    get:()=>on,set(v){on=!!v;app.invalidate();}});
  document.addEventListener("click",event=>{
    const b=event.target.closest("[data-commuting-city],[data-commuting-map]");
    if(!b||!packet)return;
    if(b.dataset.commutingCity){app.selectCity(b.dataset.commutingCity);return;}
    app.ui.setMapToggle("commuting-connections",true);
    const city=selected();
    if(!city)return;
    const p=list(city);
    const points=[coords(city),...p.incoming.concat(p.outgoing).map(x=>coords(byId.get(x.id)))].filter(Boolean);
    if(points.length>1)app.fitBounds(Math.min(...points.map(x=>x[0])),Math.min(...points.map(x=>x[1])),
      Math.max(...points.map(x=>x[0])),Math.max(...points.map(x=>x[1])),{maxScale:8});
    app.ui.toast("Blue dashed: incoming · Gold: outgoing · Schematic connections");
  });
  app.loadData("commuting").then(data=>{
    if(!data)return;
    packet=data;
    const buckets=new Map();
    for(const flow of packet.flows)for(const id of flow.slice(0,2)){
      if(!buckets.has(id))buckets.set(id,[]);
      buckets.get(id).push(flow);
    }
    for(const [id,flows] of buckets)index.set(id,partners(flows,id));
    app.commuting={packet,index,get on(){return on;}};
    app.addCitySections(section);
    app.invalidate();
  });
}
