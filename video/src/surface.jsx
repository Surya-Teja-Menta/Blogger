// ---- surface: z = f(x, y) as a lit 3D mesh that rises out of the floor while the camera slowly orbits ----------
// Drawn as vector polygons (painter's algorithm, one light), so it is crisp at any resolution and needs no GPU
// (GitHub's runners have none). Marks: "descent" (a ball takes real gradient-descent steps down the surface,
// leaving its trail), "minimum" (the lowest point found and ringed) and "residuals" (data points with sticks to
// the surface, e.g. a plane fitted to two features). blogwriter/mathexpr.py checks every surface first.
import React, {useMemo} from "react";
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import {Backdrop, Camera, Title, clamp, ease} from "./fx";
import {compile} from "./expr";
import {Tex, useMathFonts} from "./math";
import {delay, glide, pop} from "./motion";
import {C, FONT, alpha} from "./theme";

const rgb = (c) => {
  const h = String(c || "#888888").replace("#", "");
  const f = h.length === 3 ? h.split("").map((x) => x + x).join("") : h.padEnd(6, "0");
  return [0, 2, 4].map((k) => parseInt(f.slice(k, k + 2), 16) || 0);
};
const css = (a) => `rgb(${a.map((v) => Math.round(Math.max(0, Math.min(255, v)))).join(",")})`;
const lerp3 = (a, b, t) => a.map((v, k) => v + (b[k] - v) * t);

const N = 28;           // mesh cells per side
const H = 0.55;         // half the height of the surface box, in units of half its width

export const SurfaceScene = ({s, i, vertical}) => {
  useMathFonts();
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const g = s.surface || {fn: "x^2+y^2", x: [-3, 3], y: [-3, 3], mark: "descent", start: [2.5, -2.4], points: []};
  const T = s.frames || 210;
  const [x0, x1] = g.x, [y0, y1] = g.y;

  // the function sampled once; heights normalised to -H..H with spikes trimmed
  const data = useMemo(() => {
    let f;
    try { f = compile(g.fn, "y"); } catch (e) { f = (x, y) => x * x + y * y; }
    const F = (x, y) => { const z = f(x, y); return Number.isFinite(z) ? z : NaN; };
    const zs = [];
    const grid = [];
    for (let a = 0; a <= N; a++) {
      const row = [];
      for (let b = 0; b <= N; b++) {
        const z = F(x0 + ((x1 - x0) * a) / N, y0 + ((y1 - y0) * b) / N);
        row.push(z);
        if (!Number.isNaN(z)) zs.push(z);
      }
      grid.push(row);
    }
    zs.sort((p, q) => p - q);
    const lo = zs[Math.floor(zs.length * 0.02)] ?? -1, hi = zs[Math.max(0, Math.ceil(zs.length * 0.98) - 1)] ?? 1;
    const span = hi - lo > 1e-9 ? hi - lo : 1;
    const W = (z) => (Number.isNaN(z) ? -H : ((Math.max(lo, Math.min(hi, z)) - lo) / span) * 2 * H - H);
    // gradient descent from the start, in the data's own units (steps shrink as the slope flattens)
    let path = [];
    if (g.mark === "descent") {
      const dx = (x1 - x0) / 1e4, dy = (y1 - y0) / 1e4, diag = Math.hypot(x1 - x0, y1 - y0);
      const grad = (x, y) => [(F(x + dx, y) - F(x - dx, y)) / (2 * dx), (F(x, y + dy) - F(x, y - dy)) / (2 * dy)];
      let [x, y] = g.start;
      const g0 = grad(x, y), n0 = Math.hypot(g0[0], g0[1]) || 1;
      const lr = (0.13 * diag) / n0;
      path = [[x, y]];
      for (let k = 0; k < 24; k++) {
        const [gx, gy] = grad(x, y);
        if (!Number.isFinite(gx) || !Number.isFinite(gy)) break;
        const nx = Math.max(x0, Math.min(x1, x - lr * gx)), ny = Math.max(y0, Math.min(y1, y - lr * gy));
        if (Math.hypot(nx - x, ny - y) < diag * 0.004) break;
        x = nx; y = ny;
        path.push([x, y]);
      }
    }
    let min = [0, 0, Infinity];
    grid.forEach((row, a) => row.forEach((z, b) => { if (z < min[2]) min = [a, b, z]; }));
    return {F, W, grid, path, min};
  }, [g.fn, x0, x1, y0, y1, g.mark, (g.start || []).join(",")]);

  // world (u, v across, w up) to the screen; the camera orbits a little over the shot
  const az0 = -0.72, sweep = 0.55, el = 0.46;
  const view = (az) => (u, v, w) => {
    const ca = Math.cos(az), sa = Math.sin(az), ce = Math.cos(el), se = Math.sin(el);
    const px = u * ca - v * sa, py = u * sa + v * ca;
    const depth = py * ce - w * se;                      // larger is farther away
    const k = 1 / (1 + 0.14 * depth);                    // a touch of perspective
    return [px * k, -(w * ce + py * se) * k, depth];
  };
  const box = vertical ? {x0: 60, x1: 1020, y0: 560, y1: 1280} : {x0: 120, x1: 1420, y0: 290, y1: 940};
  // one fit for the whole orbit, so the surface never zooms or jumps
  const fit = useMemo(() => {
    let a = [Infinity, Infinity, -Infinity, -Infinity];
    [az0, az0 + sweep / 2, az0 + sweep].forEach((az) => {
      const P = view(az);
      for (let u = -1; u <= 1.001; u += 0.25) for (let v = -1; v <= 1.001; v += 0.25) for (const w of [-H - 0.1, H]) {
        const [sx, sy] = P(u, v, w);
        a = [Math.min(a[0], sx), Math.min(a[1], sy), Math.max(a[2], sx), Math.max(a[3], sy)];
      }
    });
    const S = Math.min((box.x1 - box.x0) / (a[2] - a[0]), (box.y1 - box.y0) / (a[3] - a[1]));
    return {S, cx: (box.x0 + box.x1) / 2 - ((a[0] + a[2]) / 2) * S, cy: (box.y0 + box.y1) / 2 - ((a[1] + a[3]) / 2) * S};
  }, [vertical]);

  const az = az0 + sweep * ease(clamp(frame / T)) ;
  const P = view(az);
  const rise = glide(frame - 6, 2.4);                    // the surface grows out of the floor
  const floor = -H - 0.1;
  const Wd = (z) => floor + (data.W(z) - floor) * rise;
  const U = (a) => (a / N) * 2 - 1;
  const at = (u, v, w) => { const [sx, sy, d] = P(u, v, w); return [fit.cx + sx * fit.S, fit.cy + sy * fit.S, d]; };
  const toU = (x) => ((x - x0) / (x1 - x0)) * 2 - 1, toV = (y) => ((y - y0) / (y1 - y0)) * 2 - 1;

  // the mesh: every cell lit by one light and coloured by its height
  const low = rgb(C.cool), high = rgb(C.accent);
  const light = [-0.45, -0.55, 0.7];
  const ln = Math.hypot(...light);
  const cells = [];
  for (let a = 0; a < N; a++) {
    for (let b = 0; b < N; b++) {
      const zs = [data.grid[a][b], data.grid[a + 1][b], data.grid[a + 1][b + 1], data.grid[a][b + 1]];
      if (zs.some(Number.isNaN)) continue;
      const corners = [[U(a), U(b)], [U(a + 1), U(b)], [U(a + 1), U(b + 1)], [U(a), U(b + 1)]].map(([u, v], k) => [u, v, Wd(zs[k])]);
      const pts = corners.map(([u, v, w]) => at(u, v, w));
      const e1 = corners[2].map((v, k) => v - corners[0][k]), e2 = corners[3].map((v, k) => v - corners[1][k]);
      const n = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]];
      const nl = Math.hypot(...n) || 1;
      const lit = Math.abs((n[0] * light[0] + n[1] * light[1] + n[2] * light[2]) / (nl * ln));
      const t = clamp((corners.reduce((m, c) => m + c[2], 0) / 4 + H) / (2 * H));
      const base = lerp3(low, high, t);
      const fill = lerp3(lerp3(base, [0, 0, 0], 0.38), lerp3(base, [255, 255, 255], 0.18), lit);
      cells.push({d: pts.reduce((m, p) => m + p[2], 0) / 4, pts, fill: css(fill)});
    }
  }
  cells.sort((p, q) => q.d - p.d);                       // far cells first

  // the floor, its grid and the axes
  const F4 = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([u, v]) => at(u, v, floor));
  const near = (pa, pb) => (at(...pa, floor)[2] < at(...pb, floor)[2] ? pa : pb);
  const xEdge = near([0, -1.22], [0, 1.22]), yEdge = near([1.22, 0], [-1.22, 0]);
  const back = [[-1, -1], [1, -1], [1, 1], [-1, 1]].reduce((m, c) => (at(...c, floor)[2] > at(...m, floor)[2] ? c : m));
  const axisIn = ease((frame - 2) / 18);
  const ink = alpha(C.text, 0.55);

  // the marks
  const marks = [];
  if (g.mark === "descent" && data.path.length > 1) {
    const t0 = T * 0.3, t1 = T * 0.86;
    const prog = clamp((frame - t0) / (t1 - t0));
    const pos = ease(prog) * (data.path.length - 1);
    const j = Math.floor(pos), fr = pos - j;
    const p0 = data.path[j], p1 = data.path[Math.min(j + 1, data.path.length - 1)];
    const cur = [p0[0] + (p1[0] - p0[0]) * fr, p0[1] + (p1[1] - p0[1]) * fr];
    const trail = [...data.path.slice(0, j + 1), cur].map(([x, y]) => at(toU(x), toV(y), Wd(data.F(x, y))));
    const ball = trail[trail.length - 1];
    const shadow = at(toU(cur[0]), toV(cur[1]), floor);
    const show = pop(frame - t0 + 8);
    marks.push(
      <g key="descent" opacity={clamp(show * 1.5)}>
        <line x1={ball[0]} y1={ball[1]} x2={shadow[0]} y2={shadow[1]} stroke={alpha(C.text, 0.35)} strokeWidth={2.5} strokeDasharray="7 7"/>
        <ellipse cx={shadow[0]} cy={shadow[1]} rx={16} ry={6} fill={alpha(C.text, 0.25)}/>
        <polyline points={trail.map((p) => `${p[0]},${p[1]}`).join(" ")} fill="none" stroke={C.hot} strokeWidth={6}
                  strokeLinecap="round" strokeLinejoin="round" style={{filter: `drop-shadow(0 0 8px ${alpha(C.hot, 0.8)})`}}/>
        {trail.slice(0, -1).map((p, k) => <circle key={k} cx={p[0]} cy={p[1]} r={6} fill={C.panel} stroke={C.hot} strokeWidth={3}/>)}
        <circle cx={ball[0]} cy={ball[1]} r={19 * (0.6 + 0.4 * show)} fill={C.hot} stroke={C.panel} strokeWidth={4}
                style={{filter: `drop-shadow(0 0 18px ${alpha(C.hot, 0.9)})`}}/>
      </g>);
  }
  if (g.mark === "minimum") {
    const [a, b, z] = data.min;
    const p = at(U(a), U(b), Wd(z));
    const on = pop(frame - T * 0.45);
    const ring = (frame / 30) % 1;
    marks.push(
      <g key="min" opacity={on}>
        <circle cx={p[0]} cy={p[1]} r={18 + 40 * ring} fill="none" stroke={C.hot} strokeWidth={4} opacity={1 - ring}/>
        <circle cx={p[0]} cy={p[1]} r={15} fill={C.hot} stroke={C.panel} strokeWidth={4}
                style={{filter: `drop-shadow(0 0 16px ${C.hot})`}}/>
      </g>);
  }
  if (g.mark === "residuals") {
    (g.points || []).forEach(([x, y, z], k) => {
      const on = pop(frame - T * 0.32 - delay(k, g.points.length, "res"));
      const stick = glide(frame - T * 0.5 - delay(k, g.points.length, "stick"));
      const sz = data.F(x, y);
      const lo = data.W(z), hiS = data.W(sz);
      const pt = at(toU(x), toV(y), floor + (lo - floor) * rise);
      const on3 = at(toU(x), toV(y), Wd(sz));
      const under = lo < hiS;
      const end = [pt[0] + (on3[0] - pt[0]) * stick, pt[1] + (on3[1] - pt[1]) * stick];
      marks.push(
        <g key={`r${k}`} opacity={on * (under ? 0.55 : 1)}>
          <line x1={pt[0]} y1={pt[1]} x2={end[0]} y2={end[1]} stroke={C.hot} strokeWidth={5} strokeLinecap="round"/>
          <circle cx={pt[0]} cy={pt[1]} r={12 * on} fill={C.panel} stroke={C.violet || C.cool} strokeWidth={5}/>
        </g>);
    });
  }

  const panel = {fontSize: vertical ? 50 : 46, padding: "14px 28px", borderRadius: 18, background: alpha(C.panel, 0.88),
                 border: `2px solid ${alpha(C.accent, 0.4)}`, color: C.text, whiteSpace: "nowrap"};
  const label = (p, text, anchor = "middle") => (
    <text x={p[0]} y={p[1]} textAnchor={anchor} fill={C.muted} fontFamily={FONT.body} fontWeight={800}
          fontSize={vertical ? 36 : 32} style={{paintOrder: "stroke", stroke: alpha(C.bg, 0.85), strokeWidth: 8}}>{text}</text>
  );
  const top = at(...back, H), foot = at(...back, floor);
  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <Camera i={i} amount={0.25}>
        <Title s={s} vertical={vertical} size={vertical ? 80 : 72}/>
        <svg width={width} height={height} style={{position: "absolute"}}>
          <g opacity={axisIn}>
            <polygon points={F4.map((p) => `${p[0]},${p[1]}`).join(" ")} fill={alpha(C.text, 0.04)} stroke={alpha(C.text, 0.25)} strokeWidth={2}/>
            {[-0.5, 0, 0.5].map((q) => {
              const a1 = at(q, -1, floor), a2 = at(q, 1, floor), b1 = at(-1, q, floor), b2 = at(1, q, floor);
              return (
                <g key={q}>
                  <line x1={a1[0]} y1={a1[1]} x2={a2[0]} y2={a2[1]} stroke={alpha(C.text, 0.1)} strokeWidth={1.5}/>
                  <line x1={b1[0]} y1={b1[1]} x2={b2[0]} y2={b2[1]} stroke={alpha(C.text, 0.1)} strokeWidth={1.5}/>
                </g>
              );
            })}
            <line x1={foot[0]} y1={foot[1]} x2={top[0]} y2={top[1]} stroke={ink} strokeWidth={3}/>
          </g>
          {cells.map((c, k) => (
            <polygon key={k} points={c.pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")} fill={c.fill}
                     stroke={alpha(C.light ? C.text : C.bg, 0.16)} strokeWidth={1} strokeLinejoin="round"
                     opacity={clamp(rise * 3)}/>
          ))}
          {marks}
          <g opacity={axisIn}>
            {label(at(...xEdge, floor), s.xlabel || "x")}
            {label(at(...yEdge, floor), s.ylabel || "y")}
            {label([top[0] + 14, top[1] + 10], s.zlabel || "z", "start")}
          </g>
        </svg>
        {g.tex && (
          <div style={{position: "absolute", ...(vertical ? {left: 60, right: 60, top: 1300, justifyContent: "center"}
                                                          : {left: 1440, right: 50, top: 340, justifyContent: "flex-start"}),
                       display: "flex"}}>
            <div style={{...panel, fontSize: Math.min(vertical ? 46 : 40, (vertical ? 820 : 420) / Math.max(1,
                           g.tex.replace(/\\[a-zA-Z]+/g, "X").replace(/[{}_^\s]/g, "").length) * 1.7),
                         opacity: ease((frame - 24) / 14)}}>
              <Tex tex={g.tex} color={C.accent}/>
            </div>
          </div>
        )}
      </Camera>
    </AbsoluteFill>
  );
};
