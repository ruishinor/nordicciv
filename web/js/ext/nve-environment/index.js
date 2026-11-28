import { esc } from "../../format.js";

const SPECS = [
  {id:"nve-flood200", groups:["flood200"], label:"NVE 200-year flood zones", icon:"map",
    title:"Modelled 200-year flood extent at selected mapped locations in Norway"},
  {id:"nve-glacier-outlines", groups:["glacier_old","glacier_new"], label:"Jostedalsbreen outlines", icon:"terrain",
    title:"NVE glacier outlines from 1999–2006 and 2018–2019"},
];
const PAINT = {
  flood200:{fill:"rgba(40,142,220,.46)", stroke:"#68c5ff"},
  glacier_old:{fill:null, stroke:"#e5a33d"},
  glacier_new:{fill:"rgba(145,224,244,.20)",stroke:"#9ee8f8"},
};

export function install(app) {
  const on = Object.fromEntries(SPECS.map(s=>[s.id,false]));
  const groups = new Map();
  const data = () => app.data.nve_environment;
  const pathOf = f => {
    if (f.path) return f.path;
    const p = new Path2D();
    for (const ring of f.rings) {
      p.moveTo(ring[0][0],ring[0][1]);
      for (const [x,y] of ring.slice(1)) p.lineTo(x,y);
      p.closePath();
    }
    return f.path = p;
  };
  for (const s of SPECS) {
    app.registerStaticLayer({
      id:s.id, z:59, minRpx:8,
      visible:()=>on[s.id] && s.groups.every(g=>groups.has(g)),
      sig:()=>s.id + "|" + on[s.id] + "|" + groups.size,
      draw(ctx,vp,w,view) {
        if (view.lens) return;
        for (const key of s.groups) {
          const paint=PAINT[key];
          ctx.strokeStyle=paint.stroke;
          ctx.lineWidth=1.4/view.s;
          for (const f of groups.get(key)||[]) {
            const [x0,y0,x1,y1]=f.bbox;
            if (x1<vp.x0||x0>vp.x1||y1<vp.y0||y0>vp.y1) continue;
            const path=pathOf(f);
            if (paint.fill) { ctx.fillStyle=paint.fill; ctx.fill(path,"evenodd"); }
            ctx.stroke(path);
          }
        }
      }
    });
    app.ui.addMapToggle({id:s.id,label:s.label,icon:s.icon,title:s.title,default:false,
      get:()=>on[s.id],set(v){on[s.id]=!!v;app.invalidate();}});
  }
  function section() {
    if (!data()) return "";
    return '<div class="nve-environment"><p>Blue areas show NVE’s modelled 200-year flood extent at selected mapped locations. Areas outside are not assessed here. This is not a current warning or a property-level map.</p>'+
      '<div class="chips"><button class="chip" data-nve-map="nve-flood200">Show 200-year flood zones</button></div>'+
      '<p>Compare Jostedalsbreen outlines: ochre for 1999–2006, light blue for 2018–2019. Zoom in to see the outlines.</p>'+
      '<div class="chips"><button class="chip" data-nve-map="nve-glacier-outlines">Compare glacier outlines</button></div>'+
      '<p class="muted small">Source: NVE (NLOD 1.0). The display uses simplified outlines. <a href="https://temakart.nve.no/tema/breatlas" target="_blank" rel="noopener noreferrer external" referrerpolicy="no-referrer">NVE glacier atlas ↗</a></p></div>';
  }
  app.nveEnvironment = {on, groups, advisor(city,region) {
    if (city && city.country !== "NO" || region && region.country !== "NO") return "";
    const html=section();
    return html ? '<div class="obs"><h4>Norwegian flood and glacier maps</h4>'+html+'</div>' : "";
  }};
  document.addEventListener("click",event=>{
    const b=event.target.closest("[data-nve-map]");
    if (!b||!data()) return;
    const id=b.dataset.nveMap;
    app.setLens(null);
    app.ui.setMapToggle(id,true);
    if(id==="nve-glacier-outlines"){
      const boxes=["glacier_old","glacier_new"].flatMap(k=>groups.get(k)||[]).map(f=>f.bbox);
      if(boxes.length) app.fitBounds(Math.min(...boxes.map(b=>b[0])),Math.min(...boxes.map(b=>b[1])),
        Math.max(...boxes.map(b=>b[2])),Math.max(...boxes.map(b=>b[3])),{maxScale:8});
    } else app.ui.toast("Zoom in to see mapped flood zones");
  });
  app.loadData("nve_environment").then(packet=>{
    if(!packet) return;
    for(const [key,g] of Object.entries(packet.groups)) groups.set(key,g.features.map(f=>({...f})));
    app.addCitySections(c=>c.country==="NO" ? [{tab:"Overview",title:"NVE map layers",html:section()}] : []);
    app.addStateSections(r=>r.country==="NO" ? [{title:"NVE map layers",html:section()}] : []);
    app.invalidate();
  });
}
