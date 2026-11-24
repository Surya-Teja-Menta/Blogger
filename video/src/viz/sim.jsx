// Pictures that RUN the real thing instead of decorating it: a small neural network that really trains (backpropagation in
// plain JavaScript), real optimisers walking a loss landscape, real orbits from a gravity integrator, a four-stroke
// engine drawn from its exact crank equations, meshing gears whose teeth really interlock. Each is a pure function of the
// frame: the computation is seeded and cached per picture, so every render of a frame is identical on every machine.
// (blogwriter/vizlib.py declares the fields the diagram designer fills in.)
import {React, box, clamp, ease, glide, lerp, pal, pop, timing, Txt, C, alpha} from "./kit";

// ---- a small seeded random source (the same numbers on every machine) ---------------------------------------------
const mulberry = (seed) => {
  let a = (seed >>> 0) || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};
const hash = (s) => [...String(s)].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) | 0, 7);
const memo = new Map();
const cached = (key, make) => {
  if (!memo.has(key)) memo.set(key, make());
  return memo.get(key);
};

// =================================================================================================================
// nntrain: a tiny network learns to separate two groups, live
// =================================================================================================================
const dataset = (kind, n, rnd) => {
  const pts = [];
  const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-9)) * Math.cos(2 * Math.PI * rnd());
  for (let i = 0; i < n; i++) {
    const c = i % 2;
    let x, y;
    if (kind === "xor") {
      x = (rnd() * 2 - 1) * 0.9; y = (rnd() * 2 - 1) * 0.9;
      pts.push({x, y, c: x * y > 0 ? 1 : 0});
      continue;
    }
    if (kind === "moons") {
      const a = rnd() * Math.PI;
      x = (c ? 1 - Math.cos(a) : Math.cos(a)) * 0.9 - 0.45 + gauss() * 0.07;
      y = (c ? 0.45 - Math.sin(a) : Math.sin(a)) * 0.9 - 0.1 + gauss() * 0.07;
    } else if (kind === "spiral") {
      const r = 0.15 + 0.8 * (i >> 1) / (n / 2), a = r * 3.6 * Math.PI + c * Math.PI + gauss() * 0.06;
      x = r * Math.cos(a); y = r * Math.sin(a);
    } else {                                          // circles: a ring around a core
      const r = c ? 0.65 + gauss() * 0.06 : 0.25 + Math.abs(gauss()) * 0.12, a = rnd() * 2 * Math.PI;
      x = r * Math.cos(a); y = r * Math.sin(a);
    }
    pts.push({x, y, c});
  }
  return pts;
};

// a 2 -> h -> h -> 1 network, tanh hidden units, sigmoid output, trained by full-batch gradient descent
const trainNet = (kind, h, seed, epochs, every) => {
  const rnd = mulberry(seed), data = dataset(kind, 110, rnd);
  const init = (r, c) => Array.from({length: r}, () => Array.from({length: c}, () => (rnd() * 2 - 1) * Math.sqrt(2 / (r + c)) * 1.6));
  let W1 = init(h, 2), W2 = init(h, h), W3 = init(1, h), b1 = Array(h).fill(0), b2 = Array(h).fill(0), b3 = [0];
  const lr = kind === "spiral" ? 0.2 : 0.3;
  const fwd = (x, y) => {
    const a1 = W1.map((w, i) => Math.tanh(w[0] * x + w[1] * y + b1[i]));
    const a2 = W2.map((w, i) => Math.tanh(w.reduce((s, v, j) => s + v * a1[j], 0) + b2[i]));
    const z = W3[0].reduce((s, v, j) => s + v * a2[j], 0) + b3[0];
    return {a1, a2, p: 1 / (1 + Math.exp(-z))};
  };
  const snaps = [];
  const snap = (ep) => {
    let loss = 0, ok = 0;
    for (const d of data) { const p = fwd(d.x, d.y).p; loss -= d.c ? Math.log(p + 1e-9) : Math.log(1 - p + 1e-9); ok += (p > 0.5) === !!d.c; }
    snaps.push({ep, W1: W1.map((r) => r.slice()), b1: b1.slice(), W2: W2.map((r) => r.slice()), b2: b2.slice(), W3: W3.map((r) => r.slice()), b3: b3.slice(),
                loss: loss / data.length, acc: ok / data.length});
  };
  snap(0);
  for (let ep = 1; ep <= epochs; ep++) {
    const g = {W1: W1.map((r) => r.map(() => 0)), b1: b1.map(() => 0), W2: W2.map((r) => r.map(() => 0)), b2: b2.map(() => 0), W3: [W3[0].map(() => 0)], b3: [0]};
    for (const d of data) {
      const {a1, a2, p} = fwd(d.x, d.y), dz = p - d.c;                         // d(loss)/d(output score)
      for (let j = 0; j < h; j++) g.W3[0][j] += dz * a2[j];
      g.b3[0] += dz;
      const da2 = a2.map((a, j) => dz * W3[0][j] * (1 - a * a));
      for (let i = 0; i < h; i++) { for (let j = 0; j < h; j++) g.W2[i][j] += da2[i] * a1[j]; g.b2[i] += da2[i]; }
      const da1 = a1.map((a, j) => da2.reduce((s, v, i) => s + v * W2[i][j], 0) * (1 - a * a));
      for (let i = 0; i < h; i++) { g.W1[i][0] += da1[i] * d.x; g.W1[i][1] += da1[i] * d.y; g.b1[i] += da1[i]; }
    }
    const k = lr / data.length;
    for (let i = 0; i < h; i++) { for (let j = 0; j < 2; j++) W1[i][j] -= k * g.W1[i][j]; b1[i] -= k * g.b1[i]; for (let j = 0; j < h; j++) W2[i][j] -= k * g.W2[i][j]; b2[i] -= k * g.b2[i]; }
    for (let j = 0; j < h; j++) W3[0][j] -= k * g.W3[0][j];
    b3[0] -= k * g.b3[0];
    if (ep % every === 0) snap(ep);
  }
  return {data, snaps, predict: (s, x, y) => {
    const a1 = s.W1.map((w, i) => Math.tanh(w[0] * x + w[1] * y + s.b1[i]));
    const a2 = s.W2.map((w, i) => Math.tanh(w.reduce((t, v, j) => t + v * a1[j], 0) + s.b2[i]));
    return 1 / (1 + Math.exp(-(s.W3[0].reduce((t, v, j) => t + v * a2[j], 0) + s.b3[0])));
  }};
};

export const NnTrain = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const net = cached(`nn${e.data}${e.units}${e.at}`, () => trainNet(e.data, e.units, hash(e.data + e.units), 600, 6));
  const run = Math.max(80, end - (e.at ?? 0) - 40), p = clamp((T.t - 14) / run);
  const s = net.snaps[Math.min(net.snaps.length - 1, Math.floor(Math.pow(p, 1.5) * (net.snaps.length - 1)))];
  const side = Math.min(vertical ? B.W * 0.92 : B.W * 0.5, B.H * 0.84), x0 = vertical ? B.cx - side / 2 : B.x0 + B.W * 0.04, y0 = vertical ? B.y0 + B.fs * 1.2 : B.cy - side / 2;
  const G = 26, cell = side / G, X = (v) => x0 + ((v + 1.1) / 2.2) * side, Y = (v) => y0 + (1 - (v + 1.1) / 2.2) * side;
  const cold = pal(e, 1), hot = pal(e, 2);
  const lx = vertical ? B.x0 + B.W * 0.06 : x0 + side + B.W * 0.06, lw = vertical ? B.W * 0.88 : B.x1 - lx - B.W * 0.02;
  const ly = vertical ? y0 + side + B.fs * 3 : y0 + side * 0.12, lh = vertical ? Math.max(120, B.y1 - ly - B.fs * 2) : side * 0.62;
  const maxLoss = Math.max(0.75, net.snaps[0].loss), done = net.snaps.filter((q) => q.ep <= s.ep);
  const LX = (ep) => lx + (ep / 600) * lw, LY = (v) => ly + lh - clamp(v / maxLoss) * lh;
  return (
    <g opacity={clamp(T.t / 10)}>
      <rect x={x0} y={y0} width={side} height={side} rx={14} fill={alpha(C.panel, 0.9)} stroke={alpha(C.muted, 0.6)} strokeWidth={3}/>
      {Array.from({length: G * G}, (_, k) => {
        const i = k % G, j = Math.floor(k / G), vx = -1.1 + ((i + 0.5) / G) * 2.2, vy = 1.1 - ((j + 0.5) / G) * 2.2, q = net.predict(s, vx, vy);
        return <rect key={k} x={x0 + i * cell} y={y0 + j * cell} width={cell + 0.6} height={cell + 0.6} fill={q > 0.5 ? hot : cold} opacity={0.08 + 0.42 * Math.abs(q - 0.5) * 2}/>;
      })}
      {net.data.map((d, k) => <circle key={k} cx={X(d.x)} cy={Y(d.y)} r={Math.max(5, side / 70)} fill={d.c ? hot : cold} stroke={C.bg} strokeWidth={2} opacity={pop(T.t - 4 - k * 0.3)}/>)}
      <line x1={lx} y1={ly + lh} x2={lx + lw} y2={ly + lh} stroke={C.muted} strokeWidth={3}/>
      <path d={done.map((q, k) => `${k ? "L" : "M"}${LX(q.ep).toFixed(1)},${LY(q.loss).toFixed(1)}`).join(" ")} fill="none" stroke={C.accent} strokeWidth={6} strokeLinejoin="round"/>
      <circle cx={LX(s.ep)} cy={LY(s.loss)} r={9} fill={C.accent}/>
      <Txt x={lx} y={ly - B.fs * 0.5} size={B.fs * 0.9} anchor="start" color={C.muted}>mistakes shrinking</Txt>
      <Txt x={lx + lw} y={ly + lh + B.fs * 1.1} size={B.fs * 0.8} anchor="end" color={C.muted}>training time →</Txt>
      <Txt x={x0 + side / 2} y={y0 + side + B.fs * 1.1} size={B.fs * 0.85} color={C.muted}>{e.show ? `step ${s.ep} · ${Math.round(s.acc * 100)}% right` : "the network's guess, regions coloured by group"}</Txt>
    </g>
  );
};

// =================================================================================================================
// optimizers: three ways of walking downhill on the same landscape
// =================================================================================================================
const BOWL = {a: 1, b: 10, rot: 0.42};          // f = 0.5 (a u^2 + b v^2) in coordinates turned by rot: a long narrow valley
const bowl = (x, y) => { const c = Math.cos(BOWL.rot), s = Math.sin(BOWL.rot), u = c * x + s * y, v = -s * x + c * y; return 0.5 * (BOWL.a * u * u + BOWL.b * v * v); };
const bowlGrad = (x, y) => {
  const c = Math.cos(BOWL.rot), s = Math.sin(BOWL.rot), u = c * x + s * y, v = -s * x + c * y, gu = BOWL.a * u, gv = BOWL.b * v;
  return [c * gu - s * gv, s * gu + c * gv];
};
const walk = (method, steps) => {
  let x = -1.8, y = 1.0, vx = 0, vy = 0, m = [0, 0], v2 = [0, 0];
  const path = [[x, y]];
  for (let t = 1; t <= steps; t++) {
    const [gx, gy] = bowlGrad(x, y);
    if (method === "gd") { x -= 0.17 * gx; y -= 0.17 * gy; }
    else if (method === "momentum") { vx = 0.8 * vx - 0.02 * gx; vy = 0.8 * vy - 0.02 * gy; x += vx; y += vy; }
    else {
      m = [0.9 * m[0] + 0.1 * gx, 0.9 * m[1] + 0.1 * gy]; v2 = [0.999 * v2[0] + 0.001 * gx * gx, 0.999 * v2[1] + 0.001 * gy * gy];
      const c1 = 1 - Math.pow(0.9, t), c2 = 1 - Math.pow(0.999, t);
      x -= 0.2 * (m[0] / c1) / (Math.sqrt(v2[0] / c2) + 1e-8); y -= 0.2 * (m[1] / c1) / (Math.sqrt(v2[1] / c2) + 1e-8);
    }
    path.push([x, y]);
  }
  return path;
};

export const Optimizers = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = 70;
  const paths = cached("opt", () => ({gd: walk("gd", N), momentum: walk("momentum", N), adam: walk("adam", N)}));
  const side = Math.min(vertical ? B.W * 0.92 : B.W * 0.55, B.H * 0.9), x0 = vertical ? B.cx - side / 2 : B.x0 + B.W * 0.06, y0 = vertical ? B.y0 + B.fs * 0.5 : B.cy - side / 2;
  const lgx = vertical ? B.x0 + B.W * 0.08 : x0 + side + B.W * 0.05, lgy = vertical ? y0 + side + B.fs * 1.6 : B.cy - B.fs * 2.4;
  const X = (v) => x0 + ((v + 2.6) / 5.2) * side, Y = (v) => y0 + (1 - (v + 2) / 4) * side;
  const step = Math.floor(ease(clamp((T.t - 16) / Math.max(90, end - (e.at ?? 0) - 50))) * N);
  const which = e.methods === "gd-vs-momentum" ? ["gd", "momentum"] : e.methods === "gd-vs-adam" ? ["gd", "adam"] : ["gd", "momentum", "adam"];
  const names = {gd: "plain steps", momentum: "with momentum", adam: "Adam"}, cols = {gd: C.muted, momentum: C.hot, adam: C.accent};
  const rings = [0.1, 0.35, 0.8, 1.6, 3, 5];
  return (
    <g opacity={clamp(T.t / 10)}>
      <defs><clipPath id="optclip"><rect x={x0} y={y0} width={side} height={side} rx={14}/></clipPath></defs>
      <rect x={x0} y={y0} width={side} height={side} rx={14} fill={alpha(C.panel, 0.85)} stroke={alpha(C.muted, 0.6)} strokeWidth={3}/>
      <g clipPath="url(#optclip)">{rings.map((lv, k) => {
        const pts = Array.from({length: 73}, (_, j) => {
          const a = (j / 72) * 2 * Math.PI, ru = Math.sqrt((2 * lv) / BOWL.a), rv = Math.sqrt((2 * lv) / BOWL.b), c = Math.cos(BOWL.rot), s = Math.sin(BOWL.rot);
          const u = ru * Math.cos(a), v = rv * Math.sin(a);
          return [X(c * u - s * v), Y(s * u + c * v)];
        });
        return <path key={k} d={pts.map((q, j) => `${j ? "L" : "M"}${q[0].toFixed(1)},${q[1].toFixed(1)}`).join("") + "Z"} fill="none" stroke={alpha(C.cool, 0.25 + 0.05 * k)} strokeWidth={2}/>;
      })}</g>
      <circle cx={X(0)} cy={Y(0)} r={11} fill={C.violet}/>
      <Txt x={X(0) + 18} y={Y(0) + B.fs * 1.5} size={B.fs * 0.85} anchor="start" color={C.violet}>lowest point</Txt>
      {which.map((m, k) => {
        const pts = paths[m].slice(0, step + 1), last = pts[pts.length - 1];
        return (
          <g key={m}>
            <path d={pts.map((q, j) => `${j ? "L" : "M"}${X(q[0]).toFixed(1)},${Y(q[1]).toFixed(1)}`).join("")} fill="none" stroke={cols[m]} strokeWidth={5} strokeLinejoin="round" opacity={0.9}/>
            <circle cx={X(last[0])} cy={Y(last[1])} r={11} fill={cols[m]} stroke={C.bg} strokeWidth={3}/>
            <Txt x={lgx} y={lgy + B.fs * 1.4 * k} size={B.fs * 0.95} anchor="start" color={cols[m]}>● {names[m]}</Txt>
          </g>
        );
      })}
    </g>
  );
};

// =================================================================================================================
// orbits: real gravity, a leapfrog integrator, Kepler's laws appear by themselves
// =================================================================================================================
const orbit = (a, ecc, steps, dt) => {
  const r0 = a * (1 - ecc), v0 = Math.sqrt((1 + ecc) / r0);                  // GM = 1, starting at the nearest point
  let x = r0, y = 0, vx = 0, vy = v0;
  const out = [[x, y]];
  const acc = (px, py) => { const r3 = Math.pow(px * px + py * py, 1.5); return [-px / r3, -py / r3]; };
  let [ax, ay] = acc(x, y);
  for (let k = 0; k < steps; k++) {
    vx += 0.5 * dt * ax; vy += 0.5 * dt * ay;
    x += dt * vx; y += dt * vy;
    [ax, ay] = acc(x, y);
    vx += 0.5 * dt * ax; vy += 0.5 * dt * ay;
    out.push([x, y]);
  }
  return out;
};

export const Orbits = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), n = e.planets.length;
  const dt = 0.01, axes = e.planets.map((_, k) => 1 + 0.85 * k);
  const sims = cached(`orb${n}${e.ecc}`, () => axes.map((a, k) => orbit(a, e.ecc, Math.ceil((2 * Math.PI * 2.4) / dt), dt)));
  const aMax = axes[n - 1] * (1 + e.ecc), R = Math.min(B.W, B.H) * 0.47 / aMax, cx = B.cx - R * aMax * e.ecc * 0.3, cy = B.cy;
  const frames = Math.max(120, end - (e.at ?? 0) - 20), speed = ((2 * Math.PI * 1.0) / (frames / 2.2)) / dt / 1, idx = Math.max(0, T.t - 8) * speed / 1;
  const at = (k, i) => sims[k][Math.min(sims[k].length - 1, Math.floor(i))];
  const cols = [pal(e, 1), pal(e, 2), pal(e, 3)];
  const wedge = (k, i0, i1, color) => {
    const pts = [[cx, cy]];
    for (let i = Math.floor(i0); i <= Math.floor(i1); i += 2) { const q = at(k, i); pts.push([cx + q[0] * R, cy - q[1] * R]); }
    return <path d={pts.map((q, j) => `${j ? "L" : "M"}${q[0].toFixed(1)},${q[1].toFixed(1)}`).join("") + "Z"} fill={alpha(color, 0.3)} stroke={alpha(color, 0.8)} strokeWidth={2}/>;
  };
  return (
    <g opacity={clamp(T.t / 10)}>
      {axes.map((a, k) => <ellipse key={k} cx={cx - a * e.ecc * R} cy={cy} rx={a * R} ry={a * R * Math.sqrt(1 - e.ecc * e.ecc)} fill="none" stroke={alpha(C.muted, 0.3)} strokeWidth={2} strokeDasharray="6 10"/>)}
      <circle cx={cx} cy={cy} r={R * 0.16} fill={C.accent} style={{filter: `drop-shadow(0 0 ${R * 0.3}px ${alpha(C.accent, 0.9)})`}}/>
      {e.law2 && T.k > 0 && (() => {                        // the same area is swept in the same time, near the sun or far from it
        const period = Math.round(2 * Math.PI / dt), span = Math.round(period * 0.07 * clamp(T.k / 20));
        const base = Math.floor(idx / period) * period;
        return <g>{wedge(0, base, base + span, C.violet)}{wedge(0, base + period / 2 - span / 2, base + period / 2 + span / 2, C.hot)}</g>;
      })()}
      {e.planets.map((name, k) => {
        const trail = [];
        for (let i = Math.max(0, idx - 420); i <= idx; i += 4) { const q = at(k, i); trail.push([cx + q[0] * R, cy - q[1] * R]); }
        const q = at(k, idx), px = cx + q[0] * R, py = cy - q[1] * R;
        return (
          <g key={k}>
            <path d={trail.map((t, j) => `${j ? "L" : "M"}${t[0].toFixed(1)},${t[1].toFixed(1)}`).join("")} fill="none" stroke={alpha(cols[k], 0.55)} strokeWidth={4} strokeLinecap="round"/>
            <circle cx={px} cy={py} r={Math.max(9, R * 0.07)} fill={cols[k]} stroke={C.bg} strokeWidth={3}/>
            <Txt x={px} y={py - Math.max(24, R * 0.12)} size={B.fs * 0.85} color={cols[k]}>{name}</Txt>
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.3} size={B.fs * 0.8} color={C.muted}>{e.law2 ? "closer to the sun it moves faster: equal areas, equal times" : "a closer orbit is a faster orbit"}</Txt>
    </g>
  );
};

// =================================================================================================================
// engine4: a four-stroke engine from its exact crank geometry, with the pressure-volume loop drawn as it runs
// =================================================================================================================
const STROKES = ["INTAKE", "COMPRESSION", "POWER", "EXHAUST"];
const smooth = (x, a, b) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };

// pressure (relative to the intake) and volume (relative to the clearance volume) at a crank angle in degrees (0 .. 720)
const otto = (deg) => {
  const cr = 8, g = 1.35, r = 1, l = 2.8;
  const th = (deg * Math.PI) / 180, x = r * Math.cos(th) + Math.sqrt(l * l - r * r * Math.sin(th) ** 2);          // piston height above the crank
  const V = 1 + (cr - 1) * ((l + r - x) / (2 * r));                               // 1 at the top, cr at the bottom
  const d = ((deg % 720) + 720) % 720;
  let P;
  if (d < 180) P = 1;                                                              // intake
  else if (d < 360) P = Math.pow(cr / V, g);                                        // compression
  else if (d < 540) P = Math.pow(cr / 1, g) * 3 * Math.pow(1 / V, g);              // after the spark: hot gas expands
  else P = 1 + (Math.pow(cr, g) * 3 * Math.pow(1 / cr, g) - 1) * (1 - smooth(d, 540, 556));   // the exhaust valve opens: the pressure drops
  if (d >= 345 && d < 365) P = lerp(Math.pow(cr / V, g), Math.pow(cr, g) * 3 * Math.pow(1 / V, g), smooth(d, 350, 362));   // the spark
  return {V, P, x};
};

export const Engine4 = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const deg = Math.max(0, T.t - 14) * (3.2 + 1.6 * (e.speed - 1)), d = deg % 720, stroke = Math.floor(d / 180), th = (deg * Math.PI) / 180;
  const r = 1, l = 2.8, u = Math.min(B.H * 0.9 / 6.4, (vertical ? B.W * 0.9 : B.W * 0.42) / 5.2);
  const ex = vertical ? B.cx : B.x0 + B.W * 0.27, ey = vertical ? B.y0 + B.H * 0.5 : B.y1 - B.fs * 2.2 - u * 1.1;
  const x = r * Math.cos(th) + Math.sqrt(l * l - r * r * Math.sin(th) ** 2), py = ey - x * u;
  const pin = [ex + r * Math.sin(th) * u, ey - r * Math.cos(th) * u];
  const bore = 1.9 * u, top = ey - (l + r + 0.4) * u - 0.9 * u, headY = top + 0.9 * u;
  const intakeOpen = stroke === 0 ? 1 : 0, exhaustOpen = stroke === 3 ? 1 : 0;
  const spark = d > 352 && d < 372, burn = d >= 360 && d < 540 ? 1 - (d - 360) / 220 : 0;
  const gas = stroke === 0 ? alpha(C.cool, 0.35) : stroke === 1 ? alpha(C.cool, 0.35 + 0.3 * smooth(d, 180, 360)) : stroke === 2 ? alpha(C.hot, 0.25 + 0.55 * burn) : alpha(C.muted, 0.35 * (1 - smooth(d, 560, 720) * 0.6));
  const valve = (cxv, open, color) => (
    <g>
      <rect x={cxv - 0.28 * u} y={headY - 0.62 * u + open * 0.32 * u} width={0.56 * u} height={0.16 * u} rx={3} fill={open ? color : C.muted}/>
      <line x1={cxv} y1={headY - 1.2 * u + open * 0.32 * u} x2={cxv} y2={headY - 0.46 * u + open * 0.32 * u} stroke={open ? color : C.muted} strokeWidth={Math.max(3, u * 0.08)}/>
    </g>
  );
  // the pressure-volume loop, drawn as the engine turns
  const gx0 = vertical ? B.x0 + B.W * 0.1 : B.x0 + B.W * 0.6, gw = vertical ? B.W * 0.8 : B.W * 0.36, gh = vertical ? B.H * 0.2 : B.H * 0.5, gy1 = vertical ? B.y1 - B.fs * 1.5 : B.cy + gh * 0.5;
  const loop = Array.from({length: Math.min(720, Math.floor(deg)) + 1}, (_, i) => otto(i));
  const GX = (V) => gx0 + ((V - 1) / 7) * gw, GY = (P) => gy1 - (P / 52) * gh, cur = otto(d), colors = [C.cool, C.violet, C.hot, C.muted];
  return (
    <g opacity={clamp(T.t / 10)}>
      <rect x={ex - bore / 2 - 12} y={top} width={bore + 24} height={ey - top - u * 0.2} rx={10} fill={alpha(C.panel, 0.9)} stroke={C.muted} strokeWidth={4}/>
      <rect x={ex - bore / 2} y={headY} width={bore} height={Math.max(2, py - headY - 0.3 * u)} fill={gas}/>
      {valve(ex - 0.55 * u, intakeOpen, C.cool)}{valve(ex + 0.55 * u, exhaustOpen, C.muted)}
      <rect x={ex - 0.08 * u} y={headY - 0.9 * u} width={0.16 * u} height={0.9 * u} fill={C.muted}/>
      {spark && <g><circle cx={ex} cy={headY + 0.1 * u} r={0.5 * u} fill={alpha("#ffffff", 0.9)}/><circle cx={ex} cy={headY + 0.1 * u} r={0.9 * u} fill={alpha(C.hot, 0.5)}/></g>}
      <rect x={ex - bore / 2 + 4} y={py - 0.3 * u} width={bore - 8} height={0.6 * u} rx={6} fill={alpha(C.accent, 0.9)} stroke={C.bg} strokeWidth={3}/>
      <line x1={ex} y1={py} x2={pin[0]} y2={pin[1]} stroke={C.text} strokeWidth={Math.max(6, u * 0.16)} strokeLinecap="round"/>
      <circle cx={ex} cy={ey} r={r * u} fill="none" stroke={C.muted} strokeWidth={4} strokeDasharray="6 8"/>
      <line x1={ex} y1={ey} x2={pin[0]} y2={pin[1]} stroke={C.violet} strokeWidth={Math.max(8, u * 0.2)} strokeLinecap="round"/>
      <circle cx={ex} cy={ey} r={0.22 * u} fill={C.text}/><circle cx={pin[0]} cy={pin[1]} r={0.2 * u} fill={C.violet}/>
      {intakeOpen && <path d={`M${ex - 0.55 * u - 1.4 * u},${headY - 1.1 * u} L${ex - 0.55 * u - 0.3 * u},${headY - 0.8 * u}`} stroke={C.cool} strokeWidth={Math.max(6, u * 0.14)} markerEnd="" strokeLinecap="round"/>}
      {exhaustOpen && <path d={`M${ex + 0.55 * u + 0.3 * u},${headY - 0.8 * u} L${ex + 0.55 * u + 1.4 * u},${headY - 1.1 * u}`} stroke={C.muted} strokeWidth={Math.max(6, u * 0.14)} strokeLinecap="round"/>}
      {e.labels && <g>
        <Txt x={ex + bore / 2 + 0.7 * u} y={headY + 0.2 * u} size={B.fs * 0.8} anchor="start" color={C.muted}>valves</Txt>
        <Txt x={ex - bore / 2 - 0.4 * u} y={py} size={B.fs * 0.8} anchor="end" color={C.accent}>piston</Txt>
        <Txt x={ex - r * u - 0.5 * u} y={ey + 0.4 * u} size={B.fs * 0.8} anchor="end" color={C.violet}>crankshaft</Txt>
        <Txt x={ex} y={headY - 1.45 * u} size={B.fs * 0.8} color={C.muted}>spark plug</Txt>
      </g>}
      <Txt x={vertical ? B.cx : gx0 + gw / 2} y={vertical ? B.y0 + B.fs * 0.9 : gy1 - gh - B.fs * 2.4} size={B.fs * 1.5} color={colors[stroke]} weight={900}>{STROKES[stroke]}</Txt>
      <line x1={gx0} y1={gy1} x2={gx0 + gw} y2={gy1} stroke={C.muted} strokeWidth={3}/><line x1={gx0} y1={gy1} x2={gx0} y2={gy1 - gh} stroke={C.muted} strokeWidth={3}/>
      <Txt x={gx0 + gw / 2} y={gy1 + B.fs * 1.1} size={B.fs * 0.8} color={C.muted}>volume →</Txt>
      <Txt x={gx0 - 10} y={gy1 - gh - B.fs * 0.5} size={B.fs * 0.8} anchor="start" color={C.muted}>pressure ↑</Txt>
      {loop.slice(1).map((q, i) => { const a = loop[i]; return <line key={i} x1={GX(a.V)} y1={GY(a.P)} x2={GX(q.V)} y2={GY(q.P)} stroke={colors[Math.floor((((i + 1) % 720) / 180)) % 4]} strokeWidth={5} strokeLinecap="round"/>; })}
      <circle cx={GX(cur.V)} cy={GY(cur.P)} r={10} fill={colors[stroke]} stroke={C.bg} strokeWidth={3}/>
    </g>
  );
};

// =================================================================================================================
// gears: a gear train whose teeth really mesh (the turn of each gear follows from its tooth count)
// =================================================================================================================
export const Gears = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = e.teeth.map((t) => Math.round(Math.min(48, Math.max(8, t))));
  const total = N.reduce((s, t) => s + t, 0), m = 0.8 * Math.min((vertical ? B.H * 0.8 : B.W * 0.94) / total, (vertical ? B.W * 0.84 : B.H * 0.8) / Math.max(...N));
  const R = N.map((t) => (t * m) / 2), centres = [];
  let acc = 0;
  N.forEach((t, k) => { if (k) acc += R[k - 1] + R[k]; centres.push(acc); });
  const span = acc, off = (vertical ? B.cy : B.cx) - span / 2;
  const th = [];
  const w1 = Math.max(0, T.t - 10) * 0.055;                                       // radians per frame of the first gear
  N.forEach((t, k) => {
    const pitch = (2 * Math.PI) / t, c = 0.3 * pitch;
    th.push(k === 0 ? w1 : Math.PI - c - pitch / 2 - (th[k - 1] + 0.3 * ((2 * Math.PI) / N[k - 1])) * (N[k - 1] / t));
  });
  const tooth = (n, rr, ang) => {
    const pitch = (2 * Math.PI) / n, root = rr - 1.25 * m, outer = rr + m, pts = [];
    for (let i = 0; i < n; i++) {
      const a0 = ang + i * pitch;
      [[root, 0], [outer, 0.16], [outer, 0.44], [root, 0.6]].forEach(([q, f]) => pts.push([Math.cos(a0 + f * pitch) * q, Math.sin(a0 + f * pitch) * q]));
    }
    return pts.map((q, j) => `${j ? "L" : "M"}${q[0].toFixed(1)},${q[1].toFixed(1)}`).join("") + "Z";
  };
  return (
    <g opacity={clamp(T.t / 10)}>
      {N.map((n, k) => {
        const gx = vertical ? B.cx : off + centres[k], gy = vertical ? off + centres[k] : B.cy, col = pal(e, k + 1), ang = th[k];
        const dir = k % 2 ? "↺" : "↻";
        return (
          <g key={k} transform={`translate(${gx},${gy})`} opacity={pop(T.t - 4 - k * 6)}>
            <path d={tooth(n, R[k], ang)} fill={alpha(col, 0.22)} stroke={col} strokeWidth={Math.max(3, m * 0.18)} strokeLinejoin="round"/>
            <circle r={R[k] * 0.62} fill="none" stroke={alpha(col, 0.5)} strokeWidth={3}/>
            {[0, 1, 2, 3, 4, 5].map((s) => <line key={s} x1={0} y1={0} x2={Math.cos(ang + (s * Math.PI) / 3) * R[k] * 0.6} y2={Math.sin(ang + (s * Math.PI) / 3) * R[k] * 0.6} stroke={alpha(col, 0.5)} strokeWidth={5}/>)}
            <circle r={R[k] * 0.1} fill={col}/>
            <Txt x={vertical ? R[k] + m * 1.2 : 0} y={vertical ? 0 : -R[k] - m * 1.6} size={B.fs * 0.9} anchor={vertical ? "start" : "middle"} color={col}>{`${dir} ${e.names && e.names[k] ? e.names[k] : ""}`.trim()}</Txt>
            {e.show && <Txt x={vertical ? R[k] + m * 1.2 : 0} y={vertical ? B.fs * 1.1 : R[k] + m * 3} size={B.fs * 0.85} anchor={vertical ? "start" : "middle"} color={C.muted}>{`${n} teeth`}</Txt>}
          </g>
        );
      })}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.2} size={B.fs * 0.8} color={C.muted}>{N[0] > N[N.length - 1] ? "a big gear turning a small one: the small one spins faster" : "a small gear turning a big one: slower, but stronger"}</Txt>
    </g>
  );
};

export const SIM = {nntrain: NnTrain, optimizers: Optimizers, orbits: Orbits, engine4: Engine4, gears: Gears};
