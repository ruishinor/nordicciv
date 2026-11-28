// Deterministic, periodic illustration geometry. These are map textures, not surveyed trees or fields.
// All geometry is generated in logical pixels; raster density never changes its placement.
const TAU = Math.PI * 2;
function random(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 16807) % 2147483647) / 2147483647);
}
const mod = (n, d) => ((n % d) + d) % d;

export function woodlandPoints(size, spacing, seed) {
  const r = random(seed), out = [], n = Math.round(size / spacing);
  const a = r() * TAU, b = r() * TAU, c = r() * TAU;
  for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
    const u = (i + r()) / n, v = (j + r()) / n;
    const density = .55 + .23 * Math.sin(TAU * (u * 3 + v) + a)
      + .14 * Math.sin(TAU * (v * 4 - u * 2) + b) + .08 * Math.cos(TAU * (u * 7 + v * 3) + c);
    // Glades and close-packed stands, rather than a plantation grid.
    if (r() > density + .18) continue;
    const x = mod(u + .019 * Math.sin(TAU * v * 4 + b), 1) * size;
    const y = mod(v + .023 * Math.cos(TAU * u * 3 + a), 1) * size;
    out.push([x, y, .54 + r() * .9, r()]);
    if (density > .7 && r() < .35) {
      out.push([mod(x + (r() - .5) * spacing, size), mod(y + (r() - .5) * spacing, size), .37 + r() * .55, r()]);
    }
  }
  return out.sort((a, b) => a[1] - b[1]);
}

// Clip a polygon to the nearer side of the perpendicular bisector of two sites.
function clip(poly, x, y, a, b) {
  const dx = a-x, dy = b-y, limit = (a*a+b*b-x*x-y*y)/2;
  const signed = p => p[0]*dx+p[1]*dy-limit;
  const out = [];
  for (let i=0;i<poly.length;i++) {
    const p=poly[i], q=poly[(i+1)%poly.length], dp=signed(p), dq=signed(q);
    if(dp<=0) out.push(p);
    if((dp<=0)!==(dq<=0)) {
      const t=dp/(dp-dq);
      out.push([p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])]);
    }
  }
  return out;
}

export function fieldParcels(size, seed, cols=10, rows=9) {
  const r=random(seed), sites=[];
  for(let j=0;j<rows;j++) for(let i=0;i<cols;i++) {
    sites.push({x:mod((i+.12+r()*.76+(j%2)*.34)*size/cols,size),
      y:(j+.12+r()*.76)*size/rows, crop:r(), angle:r()*Math.PI, furrow:r()<.68});
  }
  return sites.map(site=>{
    const {x,y}=site;
    let poly=[[x-size/2,y-size/2],[x+size/2,y-size/2],[x+size/2,y+size/2],[x-size/2,y+size/2]];
    for(const p of sites) for(const ox of [-size,0,size]) for(const oy of [-size,0,size]){
      if(p===site && ox===0 && oy===0)continue;
      const a=p.x+ox,b=p.y+oy;
      // Far sites cannot intersect this locally bounded polygon.
      if(Math.abs(a-x)>size/2 || Math.abs(b-y)>size/2)continue;
      poly=clip(poly,x,y,a,b);
      if(!poly.length)break;
    }
    return {...site,poly};
  });
}

// Periodic value noise on several scales. Fine grain plus gentle terrain variation,
// generated in one pixel pass rather than thousands of gradient draw calls.
export function terrainGrain(size=256, seed=1234567) {
  const r=random(seed), layers=[[4,10],[11,15],[32,19],[96,10]].map(([n,amp])=>({
    n,amp,grid:Float32Array.from({length:n*n},()=>r()*2-1)
  }));
  const result=new Uint8ClampedArray(size*size*4);
  const smooth=t=>t*t*(3-2*t);
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    let v=128+(r()-.5)*10;
    for(const {n,amp,grid} of layers){
      const gx=x*n/size,gy=y*n/size,ix=Math.floor(gx),iy=Math.floor(gy);
      const fx=smooth(gx-ix),fy=smooth(gy-iy),at=(a,b)=>grid[mod(b,n)*n+mod(a,n)];
      const top=at(ix,iy)*(1-fx)+at(ix+1,iy)*fx;
      const bot=at(ix,iy+1)*(1-fx)+at(ix+1,iy+1)*fx;
      v+=amp*(top*(1-fy)+bot*fy);
    }
    const i=(y*size+x)*4;
    result[i]=result[i+1]=result[i+2]=v;result[i+3]=255;
  }
  return result;
}
