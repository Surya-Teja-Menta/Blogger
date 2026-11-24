// Probability, run for real: random points estimating pi, a crowd of random walks spreading into a bell curve, a Markov
// chain whose visits settle on its stationary distribution, and Bayes' rule counted out in a crowd of 1000 people. Every
// random number comes from a seeded generator, so a re-render is identical; every curve and count is the actual outcome of
// the simulation, not a drawing of what one looks like.
import {React, box, clamp, ease, lerp, pal, pop, timing, Txt, C, alpha} from "./kit";

const mulberry = (seed) => {
  let a = (seed >>> 0) || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};
const hash = (s) => [...String(s)].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) | 0, 11);
const memo = new Map();
const cached = (key, make) => { if (!memo.has(key)) memo.set(key, make()); return memo.get(key); };
const path = (pts) => pts.map((q, j) => `${j ? "L" : "M"}${q[0].toFixed(1)},${q[1].toFixed(1)}`).join("");

// =================================================================================================================
export const MonteCarlo = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = e.dots;
  const data = cached(`mc${N}`, () => {
    const r = mulberry(1234), pts = [];
    let inside = 0;
    for (let i = 0; i < N; i++) { const x = r(), y = r(), ins = x * x + y * y <= 1; inside += ins; pts.push({x, y, ins, est: (4 * inside) / (i + 1)}); }
    return pts;
  });
  const side = Math.min(vertical ? B.W * 0.9 : B.W * 0.46, B.H * 0.82), x0 = vertical ? B.cx - side / 2 : B.x0 + B.W * 0.05, y0 = vertical ? B.y0 + B.fs : B.cy - side / 2;
  const shown = Math.floor(ease(clamp((T.t - 12) / Math.max(80, end - (e.at ?? 0) - 50))) * N), last = data[Math.max(0, shown - 1)];
  const gx = vertical ? B.x0 + B.W * 0.1 : x0 + side + B.W * 0.07, gw = vertical ? B.W * 0.8 : B.x1 - gx - B.W * 0.03, gy = vertical ? y0 + side + B.fs * 3.2 : y0 + side * 0.15, gh = vertical ? B.y1 - gy - B.fs * 2 : side * 0.6;
  const GX = (i) => gx + (i / N) * gw, GY = (v) => gy + gh - clamp((v - 2.6) / 1.2) * gh;
  const step = Math.max(1, Math.floor(shown / 160)), curve = [];
  for (let i = 0; i < shown; i += step) curve.push([GX(i), GY(data[i].est)]);
  return (
    <g opacity={clamp(T.t / 10)}>
      <rect x={x0} y={y0} width={side} height={side} fill={alpha(C.panel, 0.9)} stroke={C.muted} strokeWidth={3}/>
      <path d={`M${x0},${y0 + side} A${side},${side} 0 0 1 ${x0 + side},${y0}`} fill="none" stroke={alpha(C.accent, 0.8)} strokeWidth={4}/>
      {data.slice(0, shown).filter((_, i) => i % Math.max(1, Math.floor(N / 700)) === 0).map((p, i) => <circle key={i} cx={x0 + p.x * side} cy={y0 + side - p.y * side} r={Math.max(2.5, side / 190)} fill={p.ins ? pal(e, 1) : pal(e, 2)} opacity={0.85}/>)}
      <line x1={gx} y1={GY(Math.PI)} x2={gx + gw} y2={GY(Math.PI)} stroke={C.violet} strokeWidth={3} strokeDasharray="10 8"/>
      <Txt x={gx + gw} y={GY(Math.PI) - B.fs * 0.8} size={B.fs * 0.85} anchor="end" color={C.violet}>the true value</Txt>
      <path d={path(curve)} fill="none" stroke={C.accent} strokeWidth={5} strokeLinejoin="round"/>
      <Txt x={gx} y={gy - B.fs * 0.7} size={B.fs * 0.9} anchor="start" color={C.muted}>{e.show && last ? `guess so far: ${last.est.toFixed(2)}` : "the guess settles as points pile up"}</Txt>
      <Txt x={x0 + side / 2} y={y0 + side + B.fs * 1.1} size={B.fs * 0.85} color={C.muted}>inside the curve: one colour, outside: the other</Txt>
    </g>
  );
};

// =================================================================================================================
export const RandomWalk = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), W = e.walkers, S = e.steps;
  const walks = cached(`rw${W}${S}`, () => {
    const r = mulberry(77), out = [];
    for (let w = 0; w < W; w++) { let x = 0; const p = [0]; for (let t = 0; t < S; t++) { x += r() < 0.5 ? -1 : 1; p.push(x); } out.push(p); }
    return out;
  });
  const t = Math.floor(ease(clamp((T.t - 12) / Math.max(80, end - (e.at ?? 0) - 40))) * S);
  const lim = Math.sqrt(S) * 2.6, gx0 = B.x0 + B.W * 0.06, gw = B.W * 0.88, top = B.y0 + B.fs, ph = B.H * 0.5, hy0 = top + ph + B.fs * 1.4, hh = B.H * 0.28;
  const X = (v) => gx0 + ((v + lim) / (2 * lim)) * gw, Y = (s) => top + (s / S) * ph;
  const bins = 25, hist = Array(bins).fill(0);
  walks.forEach((p) => { const b = Math.min(bins - 1, Math.max(0, Math.floor(((p[t] + lim) / (2 * lim)) * bins))); hist[b]++; });
  const hmax = Math.max(...hist, W / 6), sd = Math.sqrt(t || 1), bw = gw / bins;
  const gauss = (v) => Math.exp(-(v * v) / (2 * sd * sd)) / (sd * Math.sqrt(2 * Math.PI));
  const bell = Array.from({length: 61}, (_, k) => { const v = -lim + (k / 60) * 2 * lim; return [X(v), hy0 + hh - clamp(gauss(v) * W * (2 * lim / bins) / hmax) * hh]; });
  return (
    <g opacity={clamp(T.t / 10)}>
      {[0, 1].map((s) => <path key={s} d={path(Array.from({length: 41}, (_, k) => [X((s ? 1 : -1) * Math.sqrt((k / 40) * S) * 1.0), Y((k / 40) * S)]))} fill="none" stroke={alpha(C.violet, 0.5)} strokeWidth={3} strokeDasharray="8 8"/>)}
      {walks.slice(0, Math.min(W, 60)).map((p, w) => <path key={w} d={path(p.slice(0, t + 1).map((v, s) => [X(v), Y(s)]))} fill="none" stroke={alpha(pal(e, 1 + (w % 3)), 0.35)} strokeWidth={2.5}/>)}
      {walks.slice(0, 60).map((p, w) => <circle key={w} cx={X(p[t])} cy={Y(t)} r={5} fill={pal(e, 1 + (w % 3))}/>)}
      {hist.map((h, b) => <rect key={b} x={gx0 + b * bw + 2} y={hy0 + hh - (h / hmax) * hh} width={bw - 4} height={(h / hmax) * hh} rx={3} fill={alpha(C.accent, 0.8)}/>)}
      <path d={path(bell)} fill="none" stroke={C.hot} strokeWidth={4}/>
      <Txt x={B.cx} y={hy0 + hh + B.fs * 1.1} size={B.fs * 0.85} color={C.muted}>{t > S * 0.5 ? "random steps pile up into a bell curve" : "many walkers, each step a coin flip"}</Txt>
    </g>
  );
};

// =================================================================================================================
export const Markov = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.states.length, S = e.steps;
  const model = cached(`mk${e.states.join("|")}${S}`, () => {
    const r = mulberry(hash(e.states.join("|")));
    const P = Array.from({length: n}, () => { const w = Array.from({length: n}, () => 0.15 + r()); const s = w.reduce((a, b) => a + b, 0); return w.map((x) => x / s); });
    let pi = Array(n).fill(1 / n);
    for (let k = 0; k < 400; k++) pi = pi.map((_, j) => P.reduce((s, row, i) => s + pi[i] * row[j], 0));
    let s = 0; const visits = Array(n).fill(0), seq = [0], hist = [];
    for (let t = 0; t < S; t++) { const u = r(); let a = 0, nx = n - 1; for (let j = 0; j < n; j++) { a += P[s][j]; if (u < a) { nx = j; break; } } s = nx; visits[s]++; seq.push(s); hist.push(visits.map((v) => v / (t + 1))); }
    return {P, pi, seq, hist};
  });
  const t = Math.floor(ease(clamp((T.t - 12) / Math.max(80, end - (e.at ?? 0) - 40))) * (S - 1)), cur = model.seq[t + 1], prev = model.seq[t];
  const R = Math.min(B.W * (vertical ? 0.3 : 0.2), B.H * 0.3), cx = vertical ? B.cx : B.x0 + B.W * 0.3, cy = vertical ? B.y0 + B.H * 0.28 : B.cy;
  const pos = (i) => [cx + Math.cos((i / n) * 2 * Math.PI - Math.PI / 2) * R, cy + Math.sin((i / n) * 2 * Math.PI - Math.PI / 2) * R];
  const bx = vertical ? B.x0 + B.W * 0.1 : B.x0 + B.W * 0.62, bw = vertical ? B.W * 0.8 : B.W * 0.34, by0 = vertical ? B.y0 + B.H * 0.62 : B.cy - B.H * 0.28, bh = B.H * (vertical ? 0.3 : 0.56);
  const cols = [pal(e, 1), pal(e, 2), pal(e, 3), pal(e, 0)], f = model.hist[t] || Array(n).fill(0), rr = Math.max(26, R * 0.34), q = (t % 1);
  return (
    <g opacity={clamp(T.t / 10)}>
      {model.P.flatMap((row, i) => row.map((p, j) => {
        if (i === j) return null;
        const [ax, ay] = pos(i), [bx2, by2] = pos(j), mx = (ax + bx2) / 2 + (by2 - ay) * 0.12, my = (ay + by2) / 2 - (bx2 - ax) * 0.12, lit = i === prev && j === cur;
        return <path key={`${i}${j}`} d={`M${ax},${ay} Q${mx},${my} ${bx2},${by2}`} fill="none" stroke={lit ? C.accent : alpha(C.muted, 0.15 + 0.7 * p)} strokeWidth={lit ? 7 : 2 + 7 * p}/>;
      }))}
      {e.states.map((name, i) => { const [x, y] = pos(i); return (
        <g key={i}><circle cx={x} cy={y} r={rr} fill={alpha(cols[i], i === cur ? 0.5 : 0.18)} stroke={cols[i]} strokeWidth={i === cur ? 7 : 4} style={{filter: i === cur ? `drop-shadow(0 0 14px ${cols[i]})` : undefined}}/>
          <Txt x={x} y={y} size={B.fs * 0.85} color={C.text}>{name}</Txt></g>); })}
      {e.states.map((name, i) => (
        <g key={i}>
          <rect x={bx + (i * bw) / n + 6} y={by0 + bh - f[i] * bh * 1.6} width={bw / n - 12} height={f[i] * bh * 1.6} rx={6} fill={cols[i]} opacity={0.85}/>
          <line x1={bx + (i * bw) / n} y1={by0 + bh - model.pi[i] * bh * 1.6} x2={bx + ((i + 1) * bw) / n} y2={by0 + bh - model.pi[i] * bh * 1.6} stroke={C.violet} strokeWidth={4} strokeDasharray="8 6"/>
          <Txt x={bx + (i + 0.5) * (bw / n)} y={by0 + bh + B.fs * 0.9} size={B.fs * 0.8} color={C.muted}>{name}</Txt>
        </g>))}
      <Txt x={bx + bw / 2} y={by0 - B.fs * 0.8} size={B.fs * 0.85} color={C.muted}>time spent in each state (dashes: where it settles)</Txt>
    </g>
  );
};

// =================================================================================================================
export const Bayes = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = 1000;
  const sick = Math.max(1, Math.round(N * e.prevalence)), tp = Math.round(sick * e.sens), fp = Math.round((N - sick) * e.fpr);
  const post = tp / Math.max(1, tp + fp);
  const cols = 40, rows = 25, side = Math.min((vertical ? B.W * 0.94 : B.W * 0.56) / cols, (B.H * 0.78) / rows), gx = vertical ? B.cx - (cols * side) / 2 : B.x0 + B.W * 0.04, gy = vertical ? B.y0 + B.fs : B.cy - (rows * side) / 2;
  const kind = (i) => (i < tp ? "tp" : i < sick ? "fn" : i < sick + fp ? "fp" : "tn");            // who is who: the first people are the sick
  const s1 = clamp((T.t - 14) / 24), s2 = clamp((T.t - 50) / 24), s3 = clamp((T.t - 100) / 30);
  const names = e.labels && e.labels.length ? e.labels : ["sick", "healthy"];
  const rx = vertical ? B.cx : gx + cols * side + B.W * 0.12, ry = vertical ? gy + rows * side + B.fs * 4 : B.cy, rr = Math.min(B.W * (vertical ? 0.2 : 0.13), B.H * 0.2);
  const arc = (a0, a1) => { const p = (a) => [rx + Math.cos(a - Math.PI / 2) * rr, ry + Math.sin(a - Math.PI / 2) * rr]; const [x0, y0] = p(a0), [x1, y1] = p(a1); return `M${rx},${ry} L${x0},${y0} A${rr},${rr} 0 ${a1 - a0 > Math.PI ? 1 : 0} 1 ${x1},${y1}Z`; };
  return (
    <g opacity={clamp(T.t / 10)}>
      {Array.from({length: N}, (_, i) => {
        const c = i % cols, r = Math.floor(i / cols), k = kind(i), isSick = i < sick, pos = i < tp || (i >= sick && i < sick + fp);
        const fill = s1 > 0 && isSick ? pal(e, 2) : C.text, ring = s2 > 0 && pos;
        return <rect key={i} x={gx + c * side + 1} y={gy + r * side + 1} width={side - 2} height={side - 2} rx={3} fill={alpha(fill, isSick && s1 > 0 ? 0.95 : 0.4)}
                     stroke={ring ? C.accent : "none"} strokeWidth={ring ? Math.max(2, side * 0.22) : 0} opacity={s2 > 0 && !pos && !(s1 > 0 && isSick) ? 0.4 : 1}/>;
      })}
      <Txt x={gx} y={gy + rows * side + B.fs * 1.2} size={B.fs * 0.85} anchor="start" color={C.muted}>{s2 > 0 ? "ringed: the test says positive" : s1 > 0 ? `${names[0]} people coloured` : "1000 people"}</Txt>
      {s3 > 0 && <g opacity={s3}>
        <circle cx={rx} cy={ry} r={rr} fill={alpha(C.muted, 0.2)}/>
        <path d={arc(0, 2 * Math.PI * post * s3)} fill={pal(e, 2)}/>
        <Txt x={rx} y={ry + rr + B.fs * 1.2} size={B.fs * 0.9} color={C.text}>{e.show ? `${Math.round(post * 100)}% of positives really are ${names[0]}` : `of those who test positive, this share really are ${names[0]}`}</Txt>
      </g>}
    </g>
  );
};

export const PROB = {montecarlo: MonteCarlo, randomwalk: RandomWalk, markov: Markov, bayes: Bayes};
