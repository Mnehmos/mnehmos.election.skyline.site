// node project.mjs <counties-10m.json> <joined.json> <out.json>
import fs from 'fs';
import { geoAlbersUsa, geoPath } from 'd3-geo';
import { feature } from 'topojson-client';
import { presimplify, simplify, quantile } from 'topojson-simplify';

const [topoPath, joinedPath, outPath] = process.argv.slice(2);
let topo = JSON.parse(fs.readFileSync(topoPath, 'utf8'));
topo = presimplify(topo);
topo = simplify(topo, quantile(topo, 0.35));
const fc = feature(topo, topo.objects.counties);
const W = 1000, H = 620;
const proj = geoAlbersUsa().fitSize([W, H], fc);
const joined = JSON.parse(fs.readFileSync(joinedPath, 'utf8'));

// us-atlas 10m omits 12 small Virginia independent cities; fold each into its surrounding county
const FOLD = { '51530': '51163', '51540': '51003', '51580': '51005', '51595': '51081', '51600': '51059', '51660': '51165',
  '51678': '51163', '51690': '51089', '51720': '51195', '51790': '51015', '51820': '51015', '51840': '51069',
  // these exist in the shapes but collapse to ~0 area at this scale: fold them too
  '51640': '51035', '51750': '51121', '51775': '51161', '51670': '51149', '51610': '51059', '51620': '51175',
  '51685': '51153', '51520': '51191', '51570': '51041', '51830': '51095', '51683': '51153', '51630': '51177',
  '15005': '15009' };
for (const [city, host] of Object.entries(FOLD)) {
  const c = joined.counties[city], h = joined.counties[host];
  if (!c || !h) continue;
  h.p += c.p || 0; h.a += c.a || 0;
  for (const r of ['sen', 'gov']) if (c[r]) h[r] = (h[r] || [0, 0, 0]).map((v, i) => v + c[r][i]);
  (h.inc = h.inc || []).push(c.n);
  delete joined.counties[city];
}
for (const h of Object.values(joined.counties)) if (h.inc) { h.n += ' (incl. ' + h.inc.join(', ') + ')'; delete h.inc; }
const out = [];
let pts = 0;
// cut out the smaller loop wherever a simplified ring crosses itself
function untangle(r) {
  const pt = i => [r[i * 2], r[i * 2 + 1]];
  for (let guard = 0; guard < 20; guard++) {
    const n = r.length / 2; let hit = null;
    outer: for (let i = 0; i < n; i++) {
      const [ax, ay] = pt(i), [bx, by] = pt((i + 1) % n);
      for (let j = i + 2; j < n; j++) {
        if (i === 0 && j === n - 1) continue;
        const [cx, cy] = pt(j), [dx, dy] = pt((j + 1) % n);
        const den = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx); if (!den) continue;
        const t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / den, u = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / den;
        if (t >= 0 && t <= 1 && u >= 0 && u <= 1 && (t > 0 && t < 1 || u > 0 && u < 1)) { hit = [i, j, Math.round(ax + t * (bx - ax)), Math.round(ay + t * (by - ay))]; break outer; }
      }
    }
    if (!hit) return r;
    const [i, j, x, y] = hit;
    const A = [...r.slice(0, (i + 1) * 2), x, y, ...r.slice((j + 1) * 2)];
    const B = [x, y, ...r.slice((i + 1) * 2, (j + 1) * 2)];
    r = ringArea(A) >= ringArea(B) ? A : B;
  }
  return r;
}
const ringArea = r => { let a = 0; for (let i = 0; i < r.length; i += 2) { const j = (i + 2) % r.length; a += r[i] * r[j + 1] - r[j] * r[i + 1]; } return Math.abs(a) / 200; };
// where each folded city sat, so the host county's hole for it can be filled in
const foldedBoxes = fc.features.filter(f => f.geometry && FOLD[String(f.id).padStart(5, '0')]).map(f => {
  const b = [1e9, 1e9, -1e9, -1e9];
  for (const poly of (f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates)) for (const c of poly[0]) {
    const p = proj(c); if (!p) continue;
    b[0] = Math.min(b[0], p[0] * 10); b[1] = Math.min(b[1], p[1] * 10); b[2] = Math.max(b[2], p[0] * 10); b[3] = Math.max(b[3], p[1] * 10);
  }
  return b;
});
const inFolded = ring => { let x = 0, y = 0; for (let i = 0; i < ring.length; i += 2) { x += ring[i]; y += ring[i + 1]; } x /= ring.length / 2; y /= ring.length / 2;
  return foldedBoxes.some(b => x >= b[0] - 15 && x <= b[2] + 15 && y >= b[1] - 15 && y <= b[3] + 15); };
for (const f of fc.features) {
  const g = f.geometry;
  if (!g) continue;
  if (FOLD[String(f.id).padStart(5, '0')]) continue;
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  const P = [];
  for (const poly of polys) {
    const rings = [];
    for (const ring of poly) {
      let r = [];
      for (const c of ring) {
        const p = proj(c);
        if (!p) continue;
        const x = Math.round(p[0] * 10), y = Math.round(p[1] * 10);
        if (r.length >= 2 && r[r.length - 2] === x && r[r.length - 1] === y) continue;
        r.push(x, y);
      }
      // drop the closing duplicate of the first point
      while (r.length >= 4 && r[0] === r[r.length - 2] && r[1] === r[r.length - 1]) r.length -= 2;
      r = untangle(r);
      if (r.length >= 6) rings.push(r);
    }
    if (rings.length) P.push([rings[0], ...rings.slice(1).filter(h => !inFolded(h))]);
  }
  if (!P.length) continue;
  // speck islands (< ~0.15 sq units, i.e. under a pixel) become floating crumbs: keep only real parts
  const biggest = Math.max(...P.map(p => ringArea(p[0])));
  for (let k = P.length - 1; k >= 0; k--) if (P.length > 1 && ringArea(P[k][0]) < Math.max(.15, biggest * .002)) P.splice(k, 1);
  pts += P.flat(2).length / 2;
  const id = String(f.id).padStart(5, '0');
  const j = joined.counties[id];
  out.push({ id, g: P, ...(j || { n: f.properties.name, s: '', p: null, a: null }) });
}
fs.writeFileSync(outPath, JSON.stringify({ W, H, counties: out, races: joined.races }));
console.log('counties', out.length, 'points', pts, 'missing census', out.filter(c => c.p == null).map(c => c.id + ' ' + c.n));
