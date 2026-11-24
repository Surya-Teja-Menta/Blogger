// Chemistry from the real structures and the real rules: a molecule laid out by RDKit (atoms and bonds exactly as the
// substance is built), a gas of hard particles whose pressure is counted from the actual hits on the walls, and a reversible
// reaction run particle by particle until it settles at the equilibrium its rates predict. Seeded and cached, so every render
// of a frame is identical.
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
const memo = new Map();
const cached = (key, make) => { if (!memo.has(key)) memo.set(key, make()); return memo.get(key); };
const CPK = {H: "#f2f2f2", C: "#9aa0aa", N: "#5b86ff", O: "#ff6a5f", S: "#f0c040", Cl: "#46d160", P: "#ff9a3c", F: "#8ad66a"};

// =================================================================================================================
export const Molecule = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), M = e.mol, n = M.atoms.length;
  const R = Math.min(B.W, B.H) * 0.42, cx = B.cx, cy = B.cy - B.fs * 0.3;
  const jig = (i, ax) => 0.012 * Math.sin(T.t / 9 + i * 2.3 + ax) + 0.008 * Math.sin(T.t / 5 + i * 1.7 + ax * 2);
  const P = (i) => [cx + (M.atoms[i][1] + jig(i, 0)) * R, cy + (M.atoms[i][2] + jig(i, 1)) * R];
  const grow = (i) => pop(T.t - 6 - i * (n > 12 ? 2 : 5));
  const label = (i) => {
    const s = M.atoms[i][0], h = M.hs[i];
    if (s === "C" && n > 1) return "";
    return s + (h ? "H" + (h > 1 ? h : "") : "");
  };
  const rad = Math.max(16, Math.min(34, (R * 2) / (n + 3)));
  const line = {strokeLinecap: "round", stroke: alpha(C.text, 0.85)};
  return (
    <g opacity={clamp(T.t / 10)}>
      {M.bonds.map(([a, b, order], q) => {
        const [x1, y1] = P(a), [x2, y2] = P(b), len = Math.hypot(x2 - x1, y2 - y1) || 1, nx = (-(y2 - y1) / len) * rad * 0.28, ny = ((x2 - x1) / len) * rad * 0.28;
        const g = clamp((grow(a) + grow(b)) / 1.6), ex = lerp(x1, x2, g), ey = lerp(y1, y2, g), w = Math.max(4, rad * 0.22);
        return (
          <g key={q} opacity={0.2 + 0.8 * g}>
            {order === 1 && <line x1={x1} y1={y1} x2={ex} y2={ey} strokeWidth={w} {...line}/>}
            {order === 2 && [-1, 1].map((s) => <line key={s} x1={x1 + nx * s} y1={y1 + ny * s} x2={lerp(x1, x2, g) + nx * s} y2={lerp(y1, y2, g) + ny * s} strokeWidth={w * 0.85} {...line}/>)}
            {order === 3 && [-1.6, 0, 1.6].map((s) => <line key={s} x1={x1 + nx * s} y1={y1 + ny * s} x2={lerp(x1, x2, g) + nx * s} y2={lerp(y1, y2, g) + ny * s} strokeWidth={w * 0.75} {...line}/>)}
            {order === 1.5 && <g><line x1={x1} y1={y1} x2={ex} y2={ey} strokeWidth={w} {...line}/><line x1={x1 + nx * 1.7} y1={y1 + ny * 1.7} x2={lerp(x1, x2, g) + nx * 1.7} y2={lerp(y1, y2, g) + ny * 1.7} strokeWidth={w * 0.6} strokeDasharray="10 8" {...line}/></g>}
          </g>
        );
      })}
      {M.atoms.map(([s], i) => {
        const [x, y] = P(i), g = grow(i), col = CPK[s] || C.accent, text = label(i);
        return text || n === 1 ? (
          <g key={i} opacity={clamp(g * 2)}>
            <circle cx={x} cy={y} r={rad * (0.6 + 0.4 * g)} fill={alpha(col, 0.9)} stroke={C.bg} strokeWidth={4} style={{filter: `drop-shadow(0 0 10px ${alpha(col, 0.6)})`}}/>
            <Txt x={x} y={y} size={rad * 0.95} color={s === "H" ? "#222" : "#fff"} halo={false}>{text || s}</Txt>
          </g>
        ) : <circle key={i} cx={x} cy={y} r={rad * 0.3 * g} fill={alpha(C.text, 0.9)}/>;
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 1.1} color={C.text} weight={900}>{e.name}</Txt>
    </g>
  );
};

// =================================================================================================================
// gaslaw: hard particles in a box with a movable lid; the pressure is the momentum they really hand to the walls
const gasSim = (N, change, key) => cached(key, () => {
  const r = mulberry(4242), STEPS = 700, W = 1, rad = 0.028;
  const p = Array.from({length: N}, () => { const a = r() * 2 * Math.PI, s = 0.011 + r() * 0.006; return {x: 0.05 + r() * 0.9, y: 0.05 + r() * 0.9, vx: Math.cos(a) * s, vy: Math.sin(a) * s}; });
  const frames = [], pressure = [];
  let hits = [];
  for (let t = 0; t < STEPS; t++) {
    const lid = change !== "heat" ? 1 - 0.45 * clamp((t - 300) / 90) : 1;
    let impulse = 0;
    for (const q of p) {
      const k = change !== "squeeze" && t >= 300 && t < 360 ? Math.pow(1.9, 1 / 60) : 1;           // heating: every particle speeds up
      q.vx *= k; q.vy *= k;
      q.x += q.vx; q.y += q.vy;
      if (q.x < rad) { q.x = rad; q.vx = Math.abs(q.vx); impulse += 2 * Math.abs(q.vx); }
      if (q.x > W - rad) { q.x = W - rad; q.vx = -Math.abs(q.vx); impulse += 2 * Math.abs(q.vx); }
      if (q.y < rad) { q.y = rad; q.vy = Math.abs(q.vy); impulse += 2 * Math.abs(q.vy); }
      if (q.y > lid - rad) { q.y = lid - rad; q.vy = -Math.abs(q.vy); impulse += 2 * Math.abs(q.vy); }
    }
    for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {                    // elastic collisions between particles
      const a = p[i], b = p[j], dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy;
      if (d2 < 4 * rad * rad && d2 > 1e-12) {
        const d = Math.sqrt(d2), nx = dx / d, ny = dy / d, rel = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny;
        if (rel < 0) { a.vx += rel * nx; a.vy += rel * ny; b.vx -= rel * nx; b.vy -= rel * ny; }
        const push = (2 * rad - d) / 2; a.x -= nx * push; a.y -= ny * push; b.x += nx * push; b.y += ny * push;
      }
    }
    hits.push(impulse / Math.max(0.2, lid)); if (hits.length > 40) hits.shift();
    pressure.push(hits.reduce((s, v) => s + v, 0) / hits.length);
    frames.push({lid, pts: p.map((q) => [q.x, q.y, Math.hypot(q.vx, q.vy)])});
  }
  return {frames, pressure};
});

export const GasLaw = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), S = gasSim(e.particles, e.change, `gas${e.particles}${e.change}`);
  const i = Math.max(0, Math.min(S.frames.length - 1, Math.floor((T.t - 6) * 1.6))), F = S.frames[i];
  const side = Math.min(vertical ? B.W * 0.86 : B.W * 0.4, B.H * 0.84), bx = vertical ? B.cx - side / 2 : B.x0 + B.W * 0.08, by = vertical ? B.y0 + B.fs : B.cy - side / 2;
  const gx = vertical ? B.x0 + B.W * 0.14 : bx + side + B.W * 0.1, gw = vertical ? B.W * 0.72 : B.W * 0.12, gy1 = vertical ? by + side + B.fs * 5 : B.cy + side * 0.4, gh = vertical ? B.H * 0.16 : side * 0.8;
  const pMax = Math.max(...S.pressure) * 1.1 || 1, pr = S.pressure[i] / pMax, base = S.pressure.slice(0, 250).reduce((s, v) => s + v, 0) / 250 / pMax;
  const speedMax = 0.03;
  return (
    <g opacity={clamp(T.t / 10)}>
      <rect x={bx - 4} y={by - 4} width={side + 8} height={side + 8} rx={10} fill={alpha(C.panel, 0.8)} stroke={C.muted} strokeWidth={5}/>
      <rect x={bx - 4} y={by - 8} width={side + 8} height={(1 - F.lid) * side + 8} rx={4} fill={alpha(C.muted, 0.5)} stroke={C.text} strokeWidth={4}/>
      {F.pts.map(([x, y, s], q) => <circle key={q} cx={bx + x * side} cy={by + y * side} r={side * 0.028} fill={s > 0.0165 ? C.hot : C.cool} opacity={0.5 + 0.5 * clamp(s / speedMax)}/>)}
      <rect x={gx} y={gy1 - gh} width={gw} height={gh} rx={8} fill={alpha(C.muted, 0.2)}/>
      <rect x={gx} y={gy1 - gh * clamp(pr)} width={gw} height={gh * clamp(pr)} rx={8} fill={C.accent}/>
      <line x1={gx - 8} y1={gy1 - gh * base} x2={gx + gw + 8} y2={gy1 - gh * base} stroke={C.violet} strokeWidth={4} strokeDasharray="8 6"/>
      <Txt x={gx + gw / 2} y={gy1 + B.fs * 1} size={B.fs * 0.85} color={C.muted}>pressure (counted from the hits)</Txt>
      <Txt x={bx + side / 2} y={by + side + B.fs * 1.3} size={B.fs * 0.85} color={C.muted}>{i < 300 * 1.0 ? "particles bouncing, each hit pushes the wall" : e.change === "squeeze" ? "squeezed: more hits on the walls" : e.change === "heat" ? "hotter: faster, harder hits" : "hotter and squeezed: far more pressure"}</Txt>
    </g>
  );
};

// =================================================================================================================
// equilibrium: A <-> B, each particle converting at random with fixed odds, until the two crowds stop changing in size
export const Equilibrium = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = 120, kf = e.forward, kr = e.reverse;
  const S = cached(`eq${kf}${kr}`, () => {
    const r = mulberry(31), st = Array(N).fill(0), pos = Array.from({length: N}, () => [r(), r(), (r() - 0.5) * 0.02, (r() - 0.5) * 0.02]), out = [];
    for (let t = 0; t < 600; t++) {
      for (let i = 0; i < N; i++) {
        const q = pos[i]; q[0] += q[2]; q[1] += q[3];
        if (q[0] < 0.03 || q[0] > 0.97) q[2] *= -1; if (q[1] < 0.03 || q[1] > 0.97) q[3] *= -1;
        if (r() < (st[i] ? kr : kf)) st[i] ^= 1;
      }
      out.push({st: st.slice(), pos: pos.map((q) => [q[0], q[1]]), nb: st.reduce((s, v) => s + v, 0)});
    }
    return out;
  });
  const i = Math.max(0, Math.min(S.length - 1, Math.floor((T.t - 6) * 1.8))), F = S[i], side = Math.min(vertical ? B.W * 0.86 : B.W * 0.38, B.H * 0.7);
  const bx = vertical ? B.cx - side / 2 : B.x0 + B.W * 0.06, by = vertical ? B.y0 + B.fs : B.cy - side / 2;
  const gx = vertical ? B.x0 + B.W * 0.1 : bx + side + B.W * 0.08, gw = vertical ? B.W * 0.8 : B.x1 - gx - B.W * 0.03, gy = vertical ? by + side + B.fs * 3.5 : by + side * 0.1, gh = vertical ? B.y1 - gy - B.fs * 2 : side * 0.75;
  const eq = kf / (kf + kr), X = (t) => gx + (t / 600) * gw, Y = (v) => gy + gh - v * gh;
  const names = e.labels && e.labels.length === 2 ? e.labels : ["A", "B"];
  const curve = (f) => S.slice(0, i + 1).filter((_, t) => t % 4 === 0).map((s, k) => `${k ? "L" : "M"}${X(k * 4).toFixed(1)},${Y(f(s)).toFixed(1)}`).join("");
  return (
    <g opacity={clamp(T.t / 10)}>
      <rect x={bx} y={by} width={side} height={side} rx={12} fill={alpha(C.panel, 0.85)} stroke={C.muted} strokeWidth={4}/>
      {F.pos.map(([x, y], q) => <circle key={q} cx={bx + x * side} cy={by + y * side} r={side * 0.022} fill={F.st[q] ? pal(e, 2) : pal(e, 1)} opacity={0.9}/>)}
      <line x1={gx} y1={Y(0)} x2={gx + gw} y2={Y(0)} stroke={C.muted} strokeWidth={3}/>
      <line x1={gx} y1={Y(eq)} x2={gx + gw} y2={Y(eq)} stroke={C.violet} strokeWidth={3} strokeDasharray="10 8"/>
      <path d={curve((s) => s.nb / N)} fill="none" stroke={pal(e, 2)} strokeWidth={6} strokeLinejoin="round"/>
      <path d={curve((s) => 1 - s.nb / N)} fill="none" stroke={pal(e, 1)} strokeWidth={6} strokeLinejoin="round"/>
      <Txt x={gx + gw} y={Y(eq) - B.fs * 0.8} size={B.fs * 0.8} anchor="end" color={C.violet}>where the rates balance</Txt>
      <Txt x={gx} y={gy - B.fs * 0.7} size={B.fs * 0.9} anchor="start" color={pal(e, 1)}>● {names[0]}</Txt>
      <Txt x={gx + B.W * 0.12} y={gy - B.fs * 0.7} size={B.fs * 0.9} anchor="start" color={pal(e, 2)}>● {names[1]}</Txt>
      <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 0.8} color={C.muted}>{i > 320 ? "both reactions still run, but the crowds stop changing" : "particles keep flipping between the two forms"}</Txt>
    </g>
  );
};

export const CHEM = {molecule: Molecule, gaslaw: GasLaw, equilibrium: Equilibrium};
