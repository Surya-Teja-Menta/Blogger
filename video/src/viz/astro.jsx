// Astronomy with the real formulas: a planet crossing its star dims the starlight by exactly the area it covers (limb darkening
// included), so the dip in the light curve is computed, not drawn; and a receding galaxy's spectral lines shift by the real
// Doppler redshift. Both are pure functions of the frame.
import {React, box, clamp, ease, lerp, pal, pop, timing, Txt, C, alpha} from "./kit";

// the share of a limb-darkened star's light that a planet of radius ratio k at centre distance d (in star radii) hides
const hidden = (d, k) => {
  const N = 220;
  let lit = 0, cover = 0;
  for (let i = 0; i < N; i++) {                                           // slices across the star, each as bright as its radius allows
    const x = -1 + ((i + 0.5) / N) * 2, h = Math.sqrt(Math.max(0, 1 - x * x));
    for (let j = 0; j < 24; j++) {
      const y = -h + ((j + 0.5) / 24) * 2 * h, mu = Math.sqrt(Math.max(0, 1 - x * x - y * y)), bright = 1 - 0.6 * (1 - mu), dx = x - d, dy = y;
      lit += bright;
      if (dx * dx + dy * dy < k * k) cover += bright;
    }
  }
  return cover / lit;
};

export const Transit = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), k = Math.sqrt(e.depth);
  const p = clamp((T.t - 14) / Math.max(90, end - (e.at ?? 0) - 40)), d = -2.4 + 4.8 * p;
  const R = Math.min(vertical ? B.W * 0.3 : B.W * 0.14, B.H * 0.2), sx = B.cx, sy = vertical ? B.y0 + B.H * 0.2 : B.cy - B.H * 0.2;
  const gx = B.x0 + B.W * 0.08, gw = B.W * 0.84, gy = vertical ? B.y0 + B.H * 0.52 : B.cy + B.H * 0.02, gh = B.H * (vertical ? 0.28 : 0.3);
  const curve = React.useMemo(() => Array.from({length: 81}, (_, i) => { const dd = -2.4 + (i / 80) * 4.8; return 1 - hidden(dd, k); }), [k]);
  const lo = 1 - 2.4 * e.depth, X = (q) => gx + q * gw, Y = (v) => gy + gh - clamp((v - lo) / (1 - lo + 0.0001)) * gh * 0.9 - gh * 0.05;
  const upto = Math.floor(p * 80);
  return (
    <g opacity={clamp(T.t / 10)}>
      <circle cx={sx} cy={sy} r={R * 1.5} fill={alpha(C.accent, 0.12)}/>
      <circle cx={sx} cy={sy} r={R} fill={C.accent} style={{filter: `drop-shadow(0 0 ${R * 0.5}px ${alpha(C.accent, 0.7)})`}}/>
      <circle cx={sx + d * R} cy={sy} r={Math.max(7, k * R)} fill={C.bg} stroke={alpha(C.text, 0.6)} strokeWidth={3}/>
      <line x1={gx} y1={Y(1)} x2={gx + gw} y2={Y(1)} stroke={alpha(C.muted, 0.6)} strokeWidth={3} strokeDasharray="8 8"/>
      <path d={curve.slice(0, upto + 1).map((v, i) => `${i ? "L" : "M"}${X(i / 80).toFixed(1)},${Y(v).toFixed(1)}`).join("")} fill="none" stroke={C.cool} strokeWidth={6} strokeLinejoin="round"/>
      {upto > 0 && <circle cx={X(upto / 80)} cy={Y(curve[upto])} r={9} fill={C.cool}/>}
      <Txt x={gx} y={gy - B.fs * 0.6} size={B.fs * 0.9} anchor="start" color={C.muted}>the star's brightness, as the planet crosses</Txt>
      <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 0.8} color={C.muted}>{p > 0.55 ? "the dip is as big as the share of the star the planet covers" : "a planet passes in front of its star"}</Txt>
    </g>
  );
};

// doppler: absorption lines of a galaxy, shifted toward red by z = v / c as it recedes
const LINES = [{nm: 397, name: "H"}, {nm: 410, name: "Hδ"}, {nm: 434, name: "Hγ"}, {nm: 486, name: "Hβ"}, {nm: 518, name: "Mg"}, {nm: 589, name: "Na"}, {nm: 656, name: "Hα"}];
const rgb = (nm) => { const t = clamp((nm - 380) / 320); return `hsl(${Math.round(270 - 270 * t)}, 90%, ${35 + 20 * Math.sin(Math.PI * t)}%)`; };

export const Doppler = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), v = e.speed * ease(clamp((T.t - 18) / 70));
  const x0 = B.x0 + B.W * 0.06, w = B.W * 0.88, nmX = (nm) => x0 + ((nm - 380) / 340) * w, sh = (nm) => nm * (1 + v);
  const specY = B.cy - B.H * 0.12, hgt = B.H * 0.15;
  return (
    <g opacity={clamp(T.t / 10)}>
      {[["at rest (laboratory)", 0], [e.object ? `${e.object}, moving away` : "a receding galaxy", 1]].map(([label, moving], row) => {
        const y = specY + (row ? hgt * 1.7 : -hgt * 1.0);
        return (
          <g key={row}>
            {Array.from({length: 85}, (_, i) => <rect key={i} x={x0 + (i / 85) * w} y={y} width={w / 85 + 1} height={hgt} fill={rgb(380 + (i / 85) * 340)}/>)}
            {LINES.map((ln) => { const nm = moving ? sh(ln.nm) : ln.nm; return nm < 720 ? <g key={ln.name}><rect x={nmX(nm) - 3} y={y} width={6} height={hgt} fill="#0b0b10"/>{!moving && <Txt x={nmX(nm)} y={y - B.fs * 0.8} size={B.fs * 0.6} color={C.muted}>{ln.name}</Txt>}</g> : null; })}
            <Txt x={x0} y={y + hgt + B.fs * 0.9} size={B.fs * 0.85} anchor="start" color={C.text}>{label}</Txt>
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 0.8} color={C.muted}>{v > e.speed * 0.5 ? "moving away stretches the light: every line slides toward red" : "the same lines, in light from a moving galaxy"}</Txt>
    </g>
  );
};

export const ASTRO = {transit: Transit, doppler: Doppler};
