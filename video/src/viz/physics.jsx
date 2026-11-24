// "physics": a real rigid-body simulation drawn as a picture (video/src/viz/physcore.mjs runs it with Planck.js): a pendulum
// trading height for speed, chaos in a double pendulum, a lever, a collision that keeps its momentum, a pulley, a block on a
// ramp that slides or sticks by friction, Newton's cradle. The run is computed once from a fixed start and cached, then the
// picture just reads the frame it needs, so every render is identical.
import {React, box, clamp, pop, timing, Txt, C, alpha, pal} from "./kit";
import {run} from "./physcore.mjs";

const cache = new Map();
const sim = (e) => {
  const key = `${e.scene}|${e.a}|${e.b}|${!!e.elastic}`;
  if (!cache.has(key)) cache.set(key, run({scene: e.scene, a: e.a, b: e.b, elastic: e.elastic}));
  return cache.get(key);
};

export const Physics = ({e, rect, frame, end, vertical}) => {
  const B = box(rect, vertical), T = timing(e, frame, end), S = sim(e), [vx0, vy0, vx1, vy1] = S.view;
  const k = Math.min(B.W / (vx1 - vx0), (B.H * 0.88) / (vy1 - vy0)), ox = B.cx - ((vx0 + vx1) / 2) * k, oy = B.cy + ((vy0 + vy1) / 2) * k - B.fs * 0.2;
  const X = (x) => ox + x * k, Y = (y) => oy - y * k;
  const i = Math.max(0, Math.min(S.frames.length - 1, Math.floor((T.t - 8) * 2))), F = S.frames[i];
  const col = (role) => (role === "a" ? pal(e, 1) : role === "b" ? pal(e, 2) : role === "bob" ? C.accent : C.violet);
  const line = {stroke: alpha(C.text, 0.7), strokeWidth: Math.max(3, k * 0.025), strokeLinecap: "round"};
  const pos = (id) => (id === "pivot" ? [0, 0] : typeof id === "number" ? [F[id].x, F[id].y] : null);
  const moving = S.items.map((it, j) => {
    const b = F[j], sh = it.shape, c = col(it.role), tf = `translate(${X(b.x)},${Y(b.y)}) rotate(${(-b.a * 180) / Math.PI})`;
    if (sh.kind === "circle") return <circle key={j} cx={X(b.x)} cy={Y(b.y)} r={sh.r * k} fill={alpha(c, 0.85)} stroke={C.bg} strokeWidth={3}/>;
    if (sh.kind === "box") return <rect key={j} x={-sh.hw * k} y={-sh.hh * k} width={sh.hw * 2 * k} height={sh.hh * 2 * k} rx={4} transform={tf} fill={alpha(c, 0.85)} stroke={C.bg} strokeWidth={3}/>;
    return (                                                                  // the lever's plank with its two weights
      <g key={j} transform={tf}>
        <rect x={-sh.hw * k} y={-sh.hh * k} width={sh.hw * 2 * k} height={sh.hh * 2 * k} rx={4} fill={alpha(C.text, 0.85)}/>
        {sh.circles.map(([cx, cy, r, role], q) => <circle key={q} cx={cx * k} cy={-cy * k} r={r * k} fill={alpha(col(role), 0.9)} stroke={C.bg} strokeWidth={3}/>)}
      </g>
    );
  });
  const trails = (S.trail || []).map((id, q) => {
    const pts = S.frames.slice(Math.max(8, i - 140), i + 1).map((f) => `${X(f[id].x).toFixed(1)},${Y(f[id].y).toFixed(1)}`);
    return <polyline key={q} points={pts.join(" ")} fill="none" stroke={alpha(col(q ? "b" : "a"), 0.7)} strokeWidth={4} strokeLinejoin="round"/>;
  });
  const sep = S.trail.length ? Math.hypot(F[1].x - F[3].x, F[1].y - F[3].y) : 0;
  const energy = S.extra[i] && S.extra[i].ke !== undefined ? S.extra[i] : null;
  const mom = S.extra[i] && S.extra[i].pa !== undefined ? S.extra[i] : null;
  const bar = (x, y, w, h, v, vmax, c, label) => (
    <g>
      <rect x={x} y={y - h} width={w} height={h} rx={5} fill={alpha(C.muted, 0.25)}/>
      <rect x={x} y={y - h * clamp(v / vmax)} width={w} height={h * clamp(v / vmax)} rx={5} fill={c}/>
      <Txt x={x + w / 2} y={y + B.fs * 0.9} size={B.fs * 0.7} color={C.muted}>{label}</Txt>
    </g>
  );
  const caption = {
    pendulum: "height turns into speed, and back again", chaos: "the same swing, started a hair apart: soon nothing alike",
    lever: S.meta.ma > S.meta.mb ? "the heavier weight pulls its side down" : S.meta.ma < S.meta.mb ? "the heavier weight pulls its side down" : "equal weights balance",
    collision: S.meta.e ? "an elastic bounce: the total push is kept" : "sticky collision: the total push is still kept",
    pulley: "the heavier side falls, lifting the lighter one", ramp: S.meta.mu > Math.tan(S.meta.ang || 0) ? "friction wins: the block stays put" : "friction loses: the block slides",
    cradle: "the push passes through the middle and swings out the far end",
  }[e.scene];
  return (
    <g opacity={clamp(T.t / 10)}>
      {S.fixed.map((f, q) => {
        if (f.kind === "floor") return <line key={q} x1={X(-9)} y1={Y(0)} x2={X(9)} y2={Y(0)} stroke={C.muted} strokeWidth={5}/>;
        if (f.kind === "ramp") return <path key={q} d={`M${X(-3.2)},${Y(0)} L${X(6.2)},${Y(0)} M${X(0)},${Y(0)} L${X(f.x1)},${Y(f.y1)} L${X(f.x1)},${Y(0)}`} fill={alpha(C.muted, 0.18)} stroke={C.muted} strokeWidth={5}/>;
        if (f.kind === "fulcrum") return <path key={q} d={`M${X(f.x)},${Y(f.y)} L${X(f.x - 0.5)},${Y(0)} L${X(f.x + 0.5)},${Y(0)}Z`} fill={alpha(C.muted, 0.5)} stroke={C.muted} strokeWidth={4}/>;
        if (f.kind === "beam") return <line key={q} x1={X(f.x0)} y1={Y(f.y)} x2={X(f.x1)} y2={Y(f.y)} stroke={C.muted} strokeWidth={8} strokeLinecap="round"/>;
        if (f.kind === "pulley") return <circle key={q} cx={X(f.x)} cy={Y(f.y)} r={0.28 * k} fill={alpha(C.panel, 0.9)} stroke={C.text} strokeWidth={5}/>;
        return <circle key={q} cx={X(f.x)} cy={Y(f.y)} r={0.09 * k} fill={C.text}/>;       // a pivot
      })}
      {S.links.map((l, q) => {
        const a = l.ax !== undefined ? [l.ax, l.ay] : pos(l.a), b = pos(l.b);
        return a && b ? <line key={q} x1={X(a[0])} y1={Y(a[1])} x2={X(b[0])} y2={Y(b[1])} {...line}/> : null;
      })}
      {S.ropes.map(([rx, ry, role], q) => { const j = S.items.findIndex((it) => it.role === role); return <line key={q} x1={X(rx)} y1={Y(ry)} x2={X(F[j].x)} y2={Y(F[j].y + S.items[j].shape.hh)} {...line}/>; })}
      {S.ropes.length === 2 && <line x1={X(-1.6)} y1={Y(2.28)} x2={X(1.6)} y2={Y(2.28)} {...line}/>}
      {trails}{moving}
      {energy && bar(B.x1 - B.W * 0.2, B.y0 + B.H * 0.5, 34, B.H * 0.34, energy.ke, S.meta.mass * 9.8 * S.meta.L * (1 - Math.cos(1.5)), pal(e, 2), "speed")}
      {energy && bar(B.x1 - B.W * 0.12, B.y0 + B.H * 0.5, 34, B.H * 0.34, energy.pe, S.meta.mass * 9.8 * S.meta.L * (1 - Math.cos(1.5)), pal(e, 1), "height")}
      {mom && bar(B.x0 + B.W * 0.05, B.y0 + B.H * 0.28, 34, B.H * 0.2, Math.abs(S.extra[0].pa + S.extra[0].pb), 24, C.muted, "push before")}
      {mom && bar(B.x0 + B.W * 0.05 + 130, B.y0 + B.H * 0.28, 34, B.H * 0.2, Math.abs(mom.pa + mom.pb), 24, C.accent, "push now")}
      {S.trail.length > 0 && <Txt x={B.x0 + B.W * 0.12} y={B.y0 + B.fs * 1.2} size={B.fs * 0.85} anchor="start" color={C.muted}>{sep > 0.35 ? "far apart now" : "the two start almost together"}</Txt>}
      <Txt x={B.cx} y={B.y1 - B.fs * 0.3} size={B.fs * 0.8} color={C.muted} op={clamp((T.t - 30) / 12)}>{e.note || caption}</Txt>
    </g>
  );
};

export const PHYSICS = {rigidbody: Physics};
