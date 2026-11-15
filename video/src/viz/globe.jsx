// A slowly turning dot-matrix globe: land drawn as thousands of small dots (so it reads as a rich instrument, not a flat
// map), pins on real places and arcs of traffic between them (blogwriter/places.py gives each place its longitude and
// latitude). A pure function of the frame: the same frame is always the same picture. Uses d3-geo only.
import {geoContains, geoDistance, geoInterpolate, geoOrthographic, geoPath, geoGraticule10} from "d3-geo";
import {feature} from "topojson-client";
import atlas from "world-atlas/countries-110m.json";
import {React, box, clamp, ease, pal, pop, timing, Txt, C, alpha} from "./kit";

const LAND = feature(atlas, atlas.objects.land);
let DOTS = null;          // land points on a 3 degree grid, built once per render
const dots = () => {
  if (!DOTS) {
    DOTS = [];
    for (let lat = -58; lat <= 80; lat += 3) {
      const step = 3 / Math.max(0.25, Math.cos((lat * Math.PI) / 180));          // fewer dots toward the poles: an even density
      for (let lon = -180; lon < 180; lon += step) if (geoContains(LAND, [lon, lat])) DOTS.push([lon, lat]);
    }
  }
  return DOTS;
};

export const Globe = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const R = Math.min(B.W, B.H) * 0.5;
  const geo = e.geo || [];
  // face the places: the middle of their longitudes, turning slowly past it
  const mid = geo.reduce((s, g) => s + g[0], 0) / Math.max(1, geo.length);
  const turn = -mid - 18 + 26 * Math.sin(T.t / 140);
  const proj = geoOrthographic().scale(R).translate([B.cx, B.cy]).rotate([turn, -18 + 8 * Math.cos(T.t / 170)]).clipAngle(90);
  const path = geoPath(proj);
  const grow = ease(clamp(T.t / 24));
  const links = (e.links === "chain" ? geo.slice(1).map((g, k) => [geo[k], g]) : geo.slice(1).map((g) => [geo[0], g]));
  return (
    <g>
      <defs>
        <radialGradient id="globe-sea" cx="38%" cy="32%" r="75%">
          <stop offset="0%" stopColor={alpha(C.accent, 0.2)}/>
          <stop offset="70%" stopColor={alpha(C.panel, 0.9)}/>
          <stop offset="100%" stopColor={alpha(C.bg, 0.95)}/>
        </radialGradient>
      </defs>
      <circle cx={B.cx} cy={B.cy} r={R * 1.06} fill="none" stroke={alpha(C.accent, 0.18)} strokeWidth={2} opacity={clamp(T.t / 12)}/>
      <circle cx={B.cx} cy={B.cy} r={R * grow} fill="url(#globe-sea)" stroke={alpha(C.accent, 0.4)} strokeWidth={2}/>
      <path d={path(geoGraticule10())} fill="none" stroke={alpha(C.muted, 0.16)} strokeWidth={1} opacity={grow}/>
      {dots().map((p, k) => {
        const xy = proj(p);
        if (!xy) return null;
        const edge = 1 - geoDistance(p, [-proj.rotate()[0], -proj.rotate()[1]]) / (Math.PI / 2);          // dimmer toward the rim
        return <circle key={k} cx={xy[0]} cy={xy[1]} r={Math.max(1.2, R / 150) * (0.5 + 0.5 * edge)} fill={alpha(C.text, 0.14 + 0.5 * edge)} opacity={grow}/>;
      })}
      {links.map(([a, b], k) => {
        const p = clamp((T.t - 24 - k * 14) / 40), mid2 = geoInterpolate(a, b);
        const pts = Array.from({length: 33}, (_, j) => mid2(j / 32));
        const line = path({type: "LineString", coordinates: pts.slice(0, Math.max(2, Math.round(2 + 31 * p)))});
        const head = proj(mid2(p));
        return (
          <g key={k} opacity={clamp(p * 4)}>
            <path d={line || ""} fill="none" stroke={pal(e, k + 1)} strokeWidth={Math.max(3, R / 70)} strokeLinecap="round"
                  style={{filter: `drop-shadow(0 0 8px ${alpha(pal(e, k + 1), 0.8)})`}}/>
            {head && <circle cx={head[0]} cy={head[1]} r={Math.max(5, R / 45)} fill={pal(e, k + 1)}/>}
          </g>
        );
      })}
      {geo.map((g, k) => {
        const xy = proj([g[0], g[1]]);
        if (!xy) return null;
        const q = pop(T.t - 12 - k * 8), pulse = 1 + 0.6 * ((T.t - k * 9) % 48) / 48;
        return (
          <g key={k} opacity={clamp(q * 2)}>
            <circle cx={xy[0]} cy={xy[1]} r={Math.max(7, R / 30) * pulse * 1.6} fill="none" stroke={pal(e, k)} strokeWidth={2} opacity={1 - ((T.t - k * 9) % 48) / 48}/>
            <circle cx={xy[0]} cy={xy[1]} r={Math.max(7, R / 30) * q} fill={pal(e, k)} stroke={C.bg} strokeWidth={3}/>
            <Txt x={xy[0]} y={xy[1] + (k % 2 ? 1 : -1) * Math.max(26, R / 11)} size={B.fs} color={C.text}>{g[2]}</Txt>
          </g>
        );
      })}
    </g>
  );
};

export const GLOBE = {globe: Globe};
