// Quantum computing and quantum mechanics, with the real mathematics: a qubit's state on the Bloch sphere turned by actual gate
// rotations, a two-qubit circuit run on an exact state vector (entanglement and all) with a seeded sample of measurements, and
// the double-slit pattern built photon by photon from the real interference formula. Nothing here is a picture of what the
// result looks like: each is the computed result, drawn.
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
const hash = (s) => [...String(s)].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) | 0, 5);

// =================================================================================================================
// qubit: the Bloch sphere. A gate is a rotation of the sphere about an axis: X, Y, Z by half a turn, H about the diagonal of x and z,
// S and T by a quarter and an eighth of a turn about z.
const GATES = {X: [[1, 0, 0], Math.PI], Y: [[0, 1, 0], Math.PI], Z: [[0, 0, 1], Math.PI], H: [[Math.SQRT1_2, 0, Math.SQRT1_2], Math.PI], S: [[0, 0, 1], Math.PI / 2], T: [[0, 0, 1], Math.PI / 4]};
const rodrigues = (v, k, a) => {                                    // v turned by angle a about the unit axis k
  const c = Math.cos(a), s = Math.sin(a), d = k[0] * v[0] + k[1] * v[1] + k[2] * v[2];
  const cr = [k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0]];
  return [0, 1, 2].map((i) => v[i] * c + cr[i] * s + k[i] * d * (1 - c));
};

export const Qubit = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), gates = e.gates.filter((g) => GATES[g]);
  const per = Math.max(34, Math.min(60, (end - (e.at ?? 0) - 40) / (gates.length + 1))), t = Math.max(0, T.t - 14);
  let v = [0, 0, 1], cur = -1;
  const trail = [[0, 0, 1]];
  gates.forEach((g, i) => {                                         // the gates already finished, and the one turning now
    const u = clamp((t - i * per) / per);
    if (u <= 0) return;
    cur = i;
    const [axis, angle] = GATES[g], base = v, steps = Math.max(1, Math.ceil(u * 24));
    for (let k = 1; k <= steps; k++) trail.push(rodrigues(base, axis, (angle * u * k) / steps));
    v = rodrigues(base, axis, angle * u);
  });
  const done = Math.floor(t / per) >= gates.length, pr0 = (1 + v[2]) / 2;
  const r = Math.min(B.W * (vertical ? 0.36 : 0.2), B.H * 0.34), cx = vertical ? B.cx : B.x0 + B.W * 0.3, cy = vertical ? B.y0 + B.H * 0.36 : B.cy;
  const yaw = -0.6, pitch = 0.42;
  const P = (p) => { const x = p[0] * Math.cos(yaw) - p[1] * Math.sin(yaw), y = p[0] * Math.sin(yaw) + p[1] * Math.cos(yaw), z = p[2]; return [cx + x * r, cy - (z * Math.cos(pitch) + y * Math.sin(pitch)) * r]; };
  const ring = (f) => Array.from({length: 73}, (_, k) => P(f((k / 72) * 2 * Math.PI)));
  const poly = (pts) => pts.map((q, j) => `${j ? "L" : "M"}${q[0].toFixed(1)},${q[1].toFixed(1)}`).join("");
  const tip = P(v), barX = vertical ? B.x0 + B.W * 0.2 : B.x0 + B.W * 0.62, barW = vertical ? B.W * 0.6 : B.W * 0.3, barY = vertical ? B.y0 + B.H * 0.78 : B.cy - B.H * 0.05;
  const rnd = mulberry(hash(gates.join("")) + 3), outcome = rnd() < pr0 ? 0 : 1, collapsed = e.measure && done && t - gates.length * per > 20;
  return (
    <g opacity={clamp(T.t / 10)}>
      <circle cx={cx} cy={cy} r={r} fill={alpha(C.panel, 0.55)} stroke={alpha(C.muted, 0.7)} strokeWidth={3}/>
      <path d={poly(ring((a) => [Math.cos(a), Math.sin(a), 0]))} fill="none" stroke={alpha(C.muted, 0.5)} strokeWidth={2.5}/>
      <path d={poly(ring((a) => [Math.cos(a), 0, Math.sin(a)]))} fill="none" stroke={alpha(C.muted, 0.3)} strokeWidth={2}/>
      <path d={poly(ring((a) => [0, Math.cos(a), Math.sin(a)]))} fill="none" stroke={alpha(C.muted, 0.3)} strokeWidth={2}/>
      <line x1={P([0, 0, 0])[0]} y1={P([0, 0, 0])[1]} x2={P([0, 0, 1])[0]} y2={P([0, 0, 1])[1]} stroke={alpha(C.muted, 0.6)} strokeWidth={3}/>
      <Txt x={P([0, 0, 1.18])[0]} y={P([0, 0, 1.18])[1]} size={B.fs} color={pal(e, 1)}>|0⟩</Txt>
      <Txt x={P([0, 0, -1.18])[0]} y={P([0, 0, -1.18])[1]} size={B.fs} color={pal(e, 2)}>|1⟩</Txt>
      <path d={poly(trail.map(P))} fill="none" stroke={alpha(C.accent, 0.5)} strokeWidth={4} strokeLinecap="round"/>
      <line x1={P([0, 0, 0])[0]} y1={P([0, 0, 0])[1]} x2={collapsed ? P([0, 0, outcome ? -1 : 1])[0] : tip[0]} y2={collapsed ? P([0, 0, outcome ? -1 : 1])[1] : tip[1]} stroke={C.accent} strokeWidth={7} strokeLinecap="round"/>
      <circle cx={collapsed ? P([0, 0, outcome ? -1 : 1])[0] : tip[0]} cy={collapsed ? P([0, 0, outcome ? -1 : 1])[1] : tip[1]} r={12} fill={C.accent} stroke={C.bg} strokeWidth={3} style={{filter: `drop-shadow(0 0 12px ${C.accent})`}}/>
      {gates.map((g, i) => <g key={i}><rect x={(vertical ? B.cx - (gates.length * 80) / 2 : cx - r) + i * 80} y={(vertical ? B.y0 : cy - r) - B.fs * 3.6} width={68} height={B.fs * 1.8} rx={10} fill={alpha(i <= cur ? C.accent : C.muted, i === cur ? 0.4 : 0.15)} stroke={i <= cur ? C.accent : C.muted} strokeWidth={i === cur ? 5 : 3}/>
        <Txt x={(vertical ? B.cx - (gates.length * 80) / 2 : cx - r) + i * 80 + 34} y={(vertical ? B.y0 : cy - r) - B.fs * 2.7} size={B.fs} color={C.text}>{g}</Txt></g>)}
      {[0, 1].map((k) => { const p = collapsed ? (outcome === k ? 1 : 0) : k ? 1 - pr0 : pr0; return (
        <g key={k}>
          <rect x={barX} y={barY + k * B.fs * 2.2} width={barW} height={B.fs * 1.3} rx={8} fill={alpha(C.muted, 0.2)}/>
          <rect x={barX} y={barY + k * B.fs * 2.2} width={barW * p} height={B.fs * 1.3} rx={8} fill={pal(e, 1 + k)}/>
          <Txt x={barX - 10} y={barY + k * B.fs * 2.2 + B.fs * 0.65} size={B.fs * 0.9} anchor="end" color={C.text}>{k ? "|1⟩" : "|0⟩"}</Txt>
          {e.show && <Txt x={barX + barW + 10} y={barY + k * B.fs * 2.2 + B.fs * 0.65} size={B.fs * 0.8} anchor="start" color={C.muted}>{`${Math.round(p * 100)}%`}</Txt>}
        </g>); })}
      <Txt x={barX + barW / 2} y={barY - B.fs * 0.9} size={B.fs * 0.8} color={C.muted}>{collapsed ? "measured: one answer, the other gone" : "the chance of each answer"}</Txt>
    </g>
  );
};

// =================================================================================================================
// qcircuit: two qubits on an exact state vector
const run2 = (gates) => {
  let s = [[1, 0], [0, 0], [0, 0], [0, 0]];                          // amplitudes [re, im] of |00>, |01>, |10>, |11> (qubit 0 first)
  const states = [s.map((x) => x.slice())];
  gates.forEach((gt) => {
    const next = s.map((x) => x.slice());
    for (let i = 0; i < 4; i++) {
      if (gt.g === "C") {
        const cb = gt.c === 0 ? (i >> 1) & 1 : i & 1;
        if (cb) next[i] = s[gt.t === 0 ? i ^ 2 : i ^ 1].slice();
        continue;
      }
      const bit = gt.q === 0 ? (i >> 1) & 1 : i & 1, j = gt.q === 0 ? i ^ 2 : i ^ 1;
      if (gt.g === "X") next[i] = s[j].slice();
      else if (gt.g === "Z") next[i] = bit ? [-s[i][0], -s[i][1]] : s[i].slice();
      else next[i] = bit ? [(s[j][0] - s[i][0]) * Math.SQRT1_2, (s[j][1] - s[i][1]) * Math.SQRT1_2] : [(s[i][0] + s[j][0]) * Math.SQRT1_2, (s[i][1] + s[j][1]) * Math.SQRT1_2];
    }
    s = next;
    states.push(s.map((x) => x.slice()));
  });
  return states;
};
const parseGate = (t) => (/^[HXZ][01]$/.test(t) ? {g: t[0], q: +t[1], label: t[0]} : /^CX[01][01]$/.test(t) && t[2] !== t[3] ? {g: "C", c: +t[2], t: +t[3], label: "X"} : null);

export const QCircuit = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end);
  const gates = e.circuit.map(parseGate).filter(Boolean), states = run2(gates);
  const per = Math.max(30, Math.min(54, (end - (e.at ?? 0) - 60) / (gates.length + 1))), step = Math.min(gates.length, Math.floor(Math.max(0, T.t - 14) / per));
  const x0 = B.x0 + B.W * 0.05, gw = vertical ? B.W * 0.86 : B.W * 0.5, colw = gw / (gates.length + 1), yq = (q) => (vertical ? B.y0 + B.H * 0.12 : B.cy - B.H * 0.2) + q * B.H * (vertical ? 0.1 : 0.22);
  const st = states[step] || states[states.length - 1], prob = st.map((a) => a[0] * a[0] + a[1] * a[1]);
  const hx = vertical ? B.x0 + B.W * 0.1 : B.x0 + B.W * 0.62, hw = vertical ? B.W * 0.8 : B.W * 0.34, hy = vertical ? B.y0 + B.H * 0.52 : B.cy - B.H * 0.05, hh = B.H * (vertical ? 0.3 : 0.4);
  const rnd = mulberry(hash(e.circuit.join(""))), shots = Array(4).fill(0), cum = prob.reduce((a, p) => [...a, (a[a.length - 1] || 0) + p], []);
  const nShots = Math.floor(clamp((T.t - 14 - gates.length * per - 10) / 60) * 200);
  for (let k = 0; k < nShots; k++) { const u = rnd(); shots[Math.max(0, cum.findIndex((c) => u <= c + 1e-9))]++; }
  const labels = ["00", "01", "10", "11"], entangled = states.length > 1 && Math.abs(st[0][0] * st[3][0]) > 0.2 && st[1][0] * st[1][0] + st[2][0] * st[2][0] < 0.01;
  return (
    <g opacity={clamp(T.t / 10)}>
      {[0, 1].map((q) => <g key={q}><line x1={x0 + 40} y1={yq(q)} x2={x0 + gw} y2={yq(q)} stroke={alpha(C.muted, 0.8)} strokeWidth={4}/><Txt x={x0 + 20} y={yq(q)} size={B.fs} color={pal(e, 1 + q)}>{`q${q}`}</Txt></g>)}
      {gates.map((g, i) => {
        const cx = x0 + 40 + colw * (i + 1), on = i < step, p = pop(T.t - 10 - i * 6), box_ = B.fs * 1.9;
        return (
          <g key={i} opacity={clamp(p * 2) * (on ? 1 : 0.55)}>
            {g.g === "C" && <line x1={cx} y1={yq(g.c)} x2={cx} y2={yq(g.t)} stroke={C.accent} strokeWidth={5}/>}
            {g.g === "C" && <circle cx={cx} cy={yq(g.c)} r={11} fill={C.accent}/>}
            {(g.g !== "C" ? [g.q] : [g.t]).map((q) => g.g === "C"
              ? <g key={q}><circle cx={cx} cy={yq(q)} r={box_ * 0.42} fill={C.bg} stroke={C.accent} strokeWidth={5}/><line x1={cx - box_ * 0.42} y1={yq(q)} x2={cx + box_ * 0.42} y2={yq(q)} stroke={C.accent} strokeWidth={5}/><line x1={cx} y1={yq(q) - box_ * 0.42} x2={cx} y2={yq(q) + box_ * 0.42} stroke={C.accent} strokeWidth={5}/></g>
              : <g key={q}><rect x={cx - box_ / 2} y={yq(q) - box_ / 2} width={box_} height={box_} rx={10} fill={alpha(C.accent, on ? 0.35 : 0.12)} stroke={C.accent} strokeWidth={4}/><Txt x={cx} y={yq(q)} size={B.fs * 1.1} color={C.text}>{g.label}</Txt></g>)}
          </g>
        );
      })}
      {labels.map((lb, k) => (
        <g key={k}>
          <rect x={hx + (k * hw) / 4 + 8} y={hy + hh - prob[k] * hh} width={hw / 4 - 16} height={prob[k] * hh} rx={6} fill={alpha(pal(e, 1 + (k % 3)), 0.55)} stroke={pal(e, 1 + (k % 3))} strokeWidth={3}/>
          {nShots > 0 && <rect x={hx + (k * hw) / 4 + hw / 8 - 7} y={hy + hh - (shots[k] / Math.max(1, nShots)) * hh} width={14} height={(shots[k] / Math.max(1, nShots)) * hh} fill={C.text} opacity={0.85}/>}
          <Txt x={hx + (k + 0.5) * (hw / 4)} y={hy + hh + B.fs * 1} size={B.fs * 0.9} color={C.muted}>{`|${lb}⟩`}</Txt>
        </g>))}
      <Txt x={hx + hw / 2} y={hy - B.fs * 0.9} size={B.fs * 0.85} color={C.muted}>{nShots > 0 ? "bars: the exact chances; white: 200 measurements" : entangled ? "entangled: the two qubits only ever agree" : "the chance of each pair of answers"}</Txt>
    </g>
  );
};

// =================================================================================================================
// doubleslit: the real interference formula, one photon at a time; "watch" makes which-slit known and the fringes vanish
export const DoubleSlit = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), N = e.photons;
  const pts = React.useMemo(() => {
    const r = mulberry(e.watch ? 91 : 90), out = [], I = (y) => (e.watch ? 0.5 * (Math.exp(-((y - 0.28) ** 2) / 0.05) + Math.exp(-((y + 0.28) ** 2) / 0.05)) : Math.cos(9 * y) ** 2 * Math.exp(-(y * y) / 0.16));
    while (out.length < N) { const y = (r() * 2 - 1) * 0.95; if (r() < I(y) / (e.watch ? 1 : 1)) out.push(y); }
    return out;
  }, [N, e.watch]);
  const n = Math.floor(clamp((T.t - 12) / Math.max(90, end - (e.at ?? 0) - 40)) ** 1.2 * N);
  const H = B.H * 0.82, sx = B.x0 + B.W * 0.1, wallX = sx + B.W * 0.25, scrX = B.x0 + B.W * 0.7, cy = B.cy, Y = (y) => cy - y * (H / 2) / 0.95;
  const bins = 60, hist = Array(bins).fill(0);
  pts.slice(0, n).forEach((y) => { hist[Math.min(bins - 1, Math.max(0, Math.floor(((y + 0.95) / 1.9) * bins)))]++; });
  const hmax = Math.max(8, ...hist);
  const flying = pts.slice(Math.max(0, n - 4), n);
  return (
    <g opacity={clamp(T.t / 10)}>
      <circle cx={sx} cy={cy} r={12} fill={C.accent} style={{filter: `drop-shadow(0 0 12px ${C.accent})`}}/>
      <rect x={wallX - 7} y={cy - H / 2} width={14} height={H / 2 - 0.28 * (H / 2) / 0.95 - 14} fill={C.muted}/>
      <rect x={wallX - 7} y={Y(0.28) + 14} width={14} height={Y(-0.28) - Y(0.28) - 28} fill={C.muted}/>
      <rect x={wallX - 7} y={Y(-0.28) + 14} width={14} height={cy + H / 2 - Y(-0.28) - 14} fill={C.muted}/>
      {e.watch && <g><circle cx={wallX + 30} cy={Y(0.28)} r={14} fill="none" stroke={C.hot} strokeWidth={4}/><circle cx={wallX + 30} cy={Y(-0.28)} r={14} fill="none" stroke={C.hot} strokeWidth={4}/></g>}
      <line x1={scrX} y1={cy - H / 2} x2={scrX} y2={cy + H / 2} stroke={C.muted} strokeWidth={5}/>
      {flying.map((y, k) => <line key={k} x1={wallX} y1={Y(k % 2 ? 0.28 : -0.28)} x2={scrX} y2={Y(y)} stroke={alpha(C.accent, 0.25 + 0.1 * k)} strokeWidth={2.5}/>)}
      {pts.slice(0, n).filter((_, i) => i % Math.max(1, Math.floor(N / 500)) === 0).map((y, i) => <circle key={i} cx={scrX + 6 + (i % 3) * 3} cy={Y(y)} r={3} fill={pal(e, 1)} opacity={0.8}/>)}
      {hist.map((h, b) => <rect key={b} x={scrX + 28} y={cy - H / 2 + (b / bins) * H} width={(h / hmax) * B.W * 0.2} height={H / bins - 1} fill={alpha(C.accent, 0.85)}/>)}
      <Txt x={(sx + scrX) / 2} y={B.y1 - B.fs * 0.2} size={B.fs * 0.85} color={C.muted}>{e.watch ? "watch which slit: the stripes disappear" : n > N * 0.6 ? "one photon at a time, and still stripes appear" : "single photons, arriving one by one"}</Txt>
    </g>
  );
};

export const QUANTUM = {qubit: Qubit, qcircuit: QCircuit, doubleslit: DoubleSlit};
