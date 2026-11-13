import fs from 'fs';
import * as THREE from 'three';
const { W, H, counties } = JSON.parse(fs.readFileSync('geo.json','utf8'));
const src = fs.readFileSync(process.argv[2] || 'template.html','utf8');
const INSET = +src.match(/const INSET = ([\d.]+)/)[1];
const fn = src.slice(src.indexOf('function cleanRing'), src.indexOf('const pos = []'));
const [insetRing, prep] = new Function('THREE','INSET', fn + '; return [insetRing, cleanRing];')(THREE, INSET);
const seg = (a,b,c,d) => { const o=(p,q,r)=>Math.sign((q.x-p.x)*(r.y-p.y)-(q.y-p.y)*(r.x-p.x)); return o(a,b,c)*o(a,b,d)<0 && o(c,d,a)*o(c,d,b)<0; };
const selfX = r => { const n=r.length; for (let i=0;i<n;i++) for (let j=i+2;j<n;j++) { if (i===0&&j===n-1) continue; if (seg(r[i],r[(i+1)%n],r[j],r[(j+1)%n])) return true; } return false; };
const st = { polys:0, closedDup:0, tiny:[], sliver:[], selfXorig:0, selfXinset:[], triBad:[], fallback:0, multi:0 };
for (const c of counties) {
  if (c.g.length>1) st.multi++;
  const areas = c.g.map(p => { const v=[]; for(let i=0;i<p[0].length;i+=2) v.push(new THREE.Vector2(p[0][i]/10,p[0][i+1]/10)); return Math.abs(THREE.ShapeUtils.area(v)); });
  const big = Math.max(...areas);
  c.g.forEach((poly, pi) => {
    st.polys++;
    let rings = poly.map(r => { const v=[]; for (let i=0;i<r.length;i+=2) v.push(new THREE.Vector2(r[i]/10-W/2, r[i+1]/10-H/2)); return v; });
    const f=rings[0][0], l=rings[0][rings[0].length-1]; if (f.x===l.x&&f.y===l.y) st.closedDup++;
    rings = rings.map(prep).filter(r => r.length >= 3);
    if (!rings.length) { st.tiny.push([c.n,c.s,0]); return; }
    if (THREE.ShapeUtils.isClockWise(rings[0])) rings[0].reverse();
    for (let h=1;h<rings.length;h++) if (!THREE.ShapeUtils.isClockWise(rings[h])) rings[h].reverse();
    const a0 = Math.abs(THREE.ShapeUtils.area(rings[0]));
    let per=0; rings[0].forEach((p,i)=>{const q=rings[0][(i+1)%rings[0].length]; per+=Math.hypot(q.x-p.x,q.y-p.y);});
    if (a0 < .15) st.tiny.push([c.n,c.s,+a0.toFixed(3), areas.length>1 && a0<big ? 'islet':'WHOLE']);
    else if (4*Math.PI*a0/(per*per) < .08) st.sliver.push([c.n,c.s,+a0.toFixed(2),+(4*Math.PI*a0/(per*per)).toFixed(3)]);
    if (selfX(rings[0])) st.selfXorig++;
    const ins = rings.map(insetRing);
    if (ins[0]===rings[0]) st.fallback++;
    if (ins.some(selfX)) st.selfXinset.push([c.n,c.s,+a0.toFixed(2)]);
    const flat = ins.flat(); const tris = THREE.ShapeUtils.triangulateShape(ins[0], ins.slice(1));
    let ta=0; for (const t of tris){const [p,q,r]=t.map(k=>flat[k]); ta+=Math.abs((q.x-p.x)*(r.y-p.y)-(q.y-p.y)*(r.x-p.x))/2;}
    const ea = Math.abs(THREE.ShapeUtils.area(ins[0])) - ins.slice(1).reduce((s,h)=>s+Math.abs(THREE.ShapeUtils.area(h)),0);
    if (Math.abs(ta-ea) > Math.max(.02, ea*.02)) st.triBad.push([c.n,c.s,+ea.toFixed(2),+ta.toFixed(2)]);
  });
}
console.log('polys',st.polys,'multi-part counties',st.multi,'closing-duplicate rings',st.closedDup,'inset fallbacks',st.fallback,'orig self-x',st.selfXorig);
console.log('tiny (<.15):',st.tiny.length, JSON.stringify(st.tiny.slice(0,25)));
console.log('slivers:',st.sliver.length, JSON.stringify(st.sliver.slice(0,25)));
console.log('inset self-x:',st.selfXinset.length, JSON.stringify(st.selfXinset.slice(0,25)));
console.log('tri mismatch:',st.triBad.length, JSON.stringify(st.triBad.slice(0,25)));
