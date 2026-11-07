// More rich diagram parts (see rich.jsx): pictures that make a thing visible and moving, all vector, all pure
// functions of the frame.
//   Code     a program typed out, then run line by line with a marker, a note beside each step and its output
//   Wave     waves that add up: the parts one by one and their sum (a square wave building itself), or the same as
//            turning circles whose tip draws the wave (Fourier epicycles)
//   Surface  a lit 3D landscape z = f(x, y) that rises and turns, with a ball taking gradient-descent steps down it
//   Bars     bars that grow, swap places and re-rank as the numbers change (a race, a before and after)
//   Flow     streams of particles through a pipeline whose width is each stage's share, the lost ones falling away
import React, {useMemo} from "react";
import {random} from "remotion";
import {clamp, ease} from "./fx";
import {compile} from "./expr";
import {glide, pop} from "./motion";
import {Caption, Txt, mixHex, smoothstep} from "./rich";
import {C, FONT, alpha} from "./theme";

// ---------------------------------------------------------------------------------------------------------------
const KEYWORDS = new Set(("def return if elif else for while in not and or import from class print True False None let const var " +
  "function new async await self lambda yield with as try except raise pass break continue is do end then SELECT FROM WHERE").split(" "));
const tokens = (line) => {
  const out = [];
  const re = /(#.*|\/\/.*)|("[^"]*"|'[^']*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_]\w*)|(\s+)|(.)/g;
  let m;
  while ((m = re.exec(line))) {
    const kind = m[1] ? "comment" : m[2] ? "string" : m[3] ? "number" : m[4] ? (KEYWORDS.has(m[4]) ? "keyword" : "name") : "plain";
    out.push({text: m[0], kind});
  }
  return out;
};

export const Code = ({e, rect, frame, end, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const lines = e.lines, steps = e.steps || [], out = e.output || [];
  const rows = lines.length + (out.length ? out.length + 0.9 : 0) + 1.7;
  let lh = Math.min(66, (H - 40) / rows);
  const longest = Math.max(...lines.map((l) => l.length), 8);
  let fs = lh * 0.64;
  if (longest * fs * 0.6 > W - 190) { fs = (W - 190) / (longest * 0.6); lh = Math.min(lh, fs / 0.64); }
  const top = y0 + (H - rows * lh) / 2 + lh * 0.9, left = x0 + 125;
  // typing: every line after the one before it
  const speed = 1.7, start = at + 8;
  const typed = (k) => {
    const before = lines.slice(0, k).reduce((s, l) => s + l.length + 4, 0);
    return clamp((frame - start) * speed - before, 0, lines[k].length);
  };
  const totalType = lines.reduce((s, l) => s + l.length + 4, 0) / speed;
  const sAt = e.glow ? Math.max(e.glow.at, start + totalType) : start + totalType + 14;
  const stepF = Math.max(14, Math.min(34, (end - sAt - 40) / Math.max(1, steps.length)));
  const cur = steps.length && frame >= sAt ? Math.min(steps.length - 1, Math.floor((frame - sAt) / stepF)) : -1;
  const doneAt = sAt + steps.length * stepF;
  const col = {keyword: C.hot, string: C.accent, number: C.cool, comment: C.muted, name: C.text, plain: C.text};
  const lineY = (k) => top + (k + 0.5) * lh;
  const panelOp = clamp((frame - at) / 12);
  return (
    <g opacity={panelOp}>
      <rect x={x0 + 30} y={y0 + 10} width={W - 60} height={H - 20} rx={22} fill={alpha(C.panel, 0.97)} stroke={alpha(C.muted, 0.5)} strokeWidth={3}/>
      {[C.hot, C.accent, C.cool].map((c, k) => <circle key={k} cx={x0 + 66 + k * 30} cy={y0 + 44} r={9} fill={c} opacity={0.9}/>)}
      {e.lang && <Txt x={x1 - 56} y={y0 + 44} size={fs * 0.85} color={C.muted} anchor="end" mono>{e.lang}</Txt>}
      {cur >= 0 && <rect x={x0 + 44} y={lineY(steps[cur].line - 1) - lh / 2} width={W - 88} height={lh} rx={10} fill={alpha(C.hot, 0.2)} stroke={alpha(C.hot, 0.8)} strokeWidth={3}/>}
      {lines.map((l, k) => {
        const n = Math.floor(typed(k));
        let used = 0;
        return (
          <g key={`l${k}`}>
            <Txt x={x0 + 100} y={lineY(k)} size={fs * 0.8} color={alpha(C.muted, 0.8)} anchor="end" mono weight={600}>{k + 1}</Txt>
            <text x={left} y={lineY(k)} fontSize={fs} fontFamily={FONT.mono} fontWeight={700} dominantBaseline="central" xmlSpace="preserve" style={{whiteSpace: "pre"}}>
              {tokens(l).map((t, j) => {
                const take = Math.max(0, Math.min(t.text.length, n - used));
                used += t.text.length;
                return take ? <tspan key={j} fill={col[t.kind]}>{t.text.slice(0, take)}</tspan> : null;
              })}
              {n < l.length && n > 0 && frame % 20 < 12 && typed(k) < l.length && (k === 0 || typed(k - 1) >= lines[k - 1].length) && <tspan fill={C.accent}>▌</tspan>}
            </text>
          </g>
        );
      })}
      {cur >= 0 && <path d={`M${x0 + 56},${lineY(steps[cur].line - 1) - lh * 0.28} l${lh * 0.5},${lh * 0.28} l${-lh * 0.5},${lh * 0.28} z`} fill={C.hot}/>}
      {cur >= 0 && steps[cur].note && (
        <g transform={`translate(${x1 - 60},${lineY(steps[cur].line - 1)})`}>
          <rect x={-(steps[cur].note.length * fs * 0.62 + 36)} y={-lh * 0.4} width={steps[cur].note.length * fs * 0.62 + 36} height={lh * 0.8} rx={lh * 0.4} fill={C.hot}/>
          <Txt x={-(steps[cur].note.length * fs * 0.62 + 36) / 2} y={1} size={fs * 0.85} color="#fff" mono halo={false}>{steps[cur].note}</Txt>
        </g>
      )}
      {out.length > 0 && frame >= doneAt - 4 && (
        <g opacity={clamp((frame - doneAt + 4) / 10)}>
          <line x1={x0 + 60} x2={x1 - 60} y1={top + (lines.length + 0.35) * lh} y2={top + (lines.length + 0.35) * lh} stroke={alpha(C.muted, 0.5)} strokeWidth={2.5} strokeDasharray="8 8"/>
          {out.map((l, k) => <Txt key={`o${k}`} x={left} y={top + (lines.length + 1.1 + k) * lh} size={fs} color={C.accent} anchor="start" mono>{"> " + l.slice(0, Math.floor(Math.max(0, (frame - doneAt) * 1.4 - k * 6)))}</Txt>)}
        </g>
      )}
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Wave = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs = vertical ? 34 : 30, ws = e.waves, n = ws.length;
  const sAt = e.glow ? e.glow.at : at + 0.25 * (end - at);
  const stepAdd = Math.max(14, Math.min(34, (end - sAt - 30) / Math.max(1, n - 1)));
  const grown = (k) => (k === 0 ? 1 : glide(frame - (sAt + (k - 1) * stepAdd), 1.2));      // component k's strength
  const t = (frame - at) / 55;                                                              // seconds of wave time
  const sum = (u) => ws.reduce((s, w, k) => s + grown(k) * w.amp * Math.sin(2 * Math.PI * w.freq * u + (w.phase || 0)), 0);
  const norm = Math.max(0.5, ws.reduce((s, w) => s + w.amp, 0) * 0.95);
  const colors = [e.color, C.cool, C.hot, C.violet, C.accent];
  const appear = clamp((frame - at) / 14);
  if (e.mode === "fourier") {
    const R = Math.min(H * 0.27, W * 0.1), cx = x0 + W * 0.2, cy = (y0 + y1) / 2;
    let px = cx, py = cy;
    const parts = [];
    ws.forEach((w, k) => {
      const r = (R * w.amp * grown(k)) / ws[0].amp * 0.85, a = 2 * Math.PI * w.freq * t * 0.35 + (w.phase || 0);
      const nx = px + r * Math.cos(a), ny = py - r * Math.sin(a);
      parts.push(<g key={`c${k}`} opacity={clamp(grown(k) * 2)}>
        <circle cx={px} cy={py} r={Math.max(0, r)} fill="none" stroke={alpha(colors[k % colors.length], 0.55)} strokeWidth={3}/>
        <line x1={px} y1={py} x2={nx} y2={ny} stroke={colors[k % colors.length]} strokeWidth={5} strokeLinecap="round"/>
      </g>);
      px = nx; py = ny;
    });
    const plotX = x0 + W * 0.42, plotW = W * 0.54, scale = R * 0.85 / Math.max(1e-6, ws[0].amp);
    const hist = [];
    for (let k = 0; k <= 150; k++) {
      const u = (t - (k / 150) * 2.4) * 0.35;
      const y = ws.reduce((s, w, j) => s + grown(j) * w.amp * Math.sin(2 * Math.PI * w.freq * u + (w.phase || 0)), 0);
      hist.push([plotX + (k / 150) * plotW, cy - y * scale]);
    }
    return (
      <g opacity={appear}>
        <line x1={plotX} x2={plotX + plotW} y1={cy} y2={cy} stroke={alpha(C.muted, 0.5)} strokeWidth={3}/>
        {parts}
        <line x1={px} y1={py} x2={plotX} y2={hist[0][1]} stroke={alpha(C.text, 0.6)} strokeWidth={3} strokeDasharray="8 8"/>
        <path d={`M${hist.map((p) => p.map((v) => v.toFixed(1)).join(",")).join("L")}`} fill="none" stroke={C.text} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" style={{filter: `drop-shadow(0 0 10px ${alpha(e.color, 0.6)})`}}/>
        <circle cx={px} cy={py} r={13} fill={C.hot} stroke={C.bg} strokeWidth={4}/>
        <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs}/>
      </g>
    );
  }
  const ax0 = x0 + 50, ax1 = x1 - 50, cy = (y0 + y1) / 2 - 10, amp = H * 0.38;
  const path = (fn) => `M${Array.from({length: 241}, (_, k) => { const u = (k / 240) * 3 + t * 0.12; return `${(ax0 + ((ax1 - ax0) * k) / 240).toFixed(1)},${(cy - (fn(u) / norm) * amp).toFixed(1)}`; }).join("L")}`;
  return (
    <g opacity={appear}>
      <line x1={ax0} x2={ax1} y1={cy} y2={cy} stroke={alpha(C.muted, 0.5)} strokeWidth={3}/>
      {ws.map((w, k) => grown(k) > 0.02 && (
        <path key={`w${k}`} d={path((u) => grown(k) * w.amp * Math.sin(2 * Math.PI * w.freq * u + (w.phase || 0)))} fill="none" stroke={colors[k % colors.length]} strokeWidth={4}
              strokeLinecap="round" opacity={0.55 * clamp(grown(k) * 2)}/>
      ))}
      <path d={path(sum)} fill="none" stroke={C.text} strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" style={{filter: `drop-shadow(0 0 12px ${alpha(e.color, 0.7)})`}}/>
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
const rgb = (c) => { const h = String(c || "#888888").replace("#", ""); const f = h.length === 3 ? h.split("").map((x) => x + x).join("") : h.padEnd(6, "0");
  return [0, 2, 4].map((k) => parseInt(f.slice(k, k + 2), 16) || 0); };
const css = (a) => `rgb(${a.map((v) => Math.round(Math.max(0, Math.min(255, v)))).join(",")})`;
const lerp3 = (a, b, t) => a.map((v, k) => v + (b[k] - v) * t);
const NS = 24, HS = 0.55;

export const Surface3D = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const lo = e.lo, hi = e.hi;
  const data = useMemo(() => {
    let f;
    try { f = compile(e.expr, "y"); } catch (err) { f = (x, y) => x * x + y * y; }
    const F = (x, y) => { const z = f(x, y); return Number.isFinite(z) ? z : NaN; };
    const grid = [], zs = [];
    for (let a = 0; a <= NS; a++) { const row = []; for (let b = 0; b <= NS; b++) { const z = F(lo + ((hi - lo) * a) / NS, lo + ((hi - lo) * b) / NS); row.push(z); if (!Number.isNaN(z)) zs.push(z); } grid.push(row); }
    zs.sort((p, q) => p - q);
    const p02 = zs[Math.floor(zs.length * 0.02)] ?? -1, p98 = zs[Math.max(0, Math.ceil(zs.length * 0.98) - 1)] ?? 1;
    const zmin = zs[0] ?? -1, zmax = zs[zs.length - 1] ?? 1, range = zmax - zmin;
    const zl = p02 - zmin > 0.25 * range ? p02 : zmin, zh = zmax - p98 > 0.25 * range ? p98 : zmax, span = zh - zl > 1e-9 ? zh - zl : 1;
    const Wd = (z) => (Number.isNaN(z) ? -HS : ((Math.max(zl, Math.min(zh, z)) - zl) / span) * 2 * HS - HS);
    let path = [];
    if (e.descent) {
      const d = (hi - lo) / 1e4, diag = (hi - lo) * 1.4142;
      const grad = (x, y) => [(F(x + d, y) - F(x - d, y)) / (2 * d), (F(x, y + d) - F(x, y - d)) / (2 * d)];
      let [x, y] = e.start;
      const g0 = grad(x, y), n0 = Math.hypot(g0[0], g0[1]) || 1, lr = (0.13 * diag) / n0;
      path = [[x, y]];
      for (let k = 0; k < 22; k++) {
        const [gx, gy] = grad(x, y);
        if (!Number.isFinite(gx) || !Number.isFinite(gy)) break;
        const nx = Math.max(lo, Math.min(hi, x - lr * gx)), ny = Math.max(lo, Math.min(hi, y - lr * gy));
        if (Math.hypot(nx - x, ny - y) < diag * 0.004) break;
        x = nx; y = ny; path.push([x, y]);
      }
    }
    return {F, Wd, grid, path};
  }, [e.expr, lo, hi, e.descent, (e.start || []).join(",")]);
  const T = Math.max(60, end - at);
  const az = -0.72 + 0.6 * ease(clamp((frame - at) / T)), el = 0.46;
  const view = (a) => (u, v, w) => {
    const ca = Math.cos(a), sa = Math.sin(a), ce = Math.cos(el), se = Math.sin(el);
    const px = u * ca - v * sa, py = u * sa + v * ca, depth = py * ce - w * se, k = 1 / (1 + 0.14 * depth);
    return [px * k, -(w * ce + py * se) * k, depth];
  };
  const fit = useMemo(() => {
    let bb = [Infinity, Infinity, -Infinity, -Infinity];
    [-0.72, -0.42, -0.12].forEach((a) => { const P = view(a); for (let u = -1; u <= 1.001; u += 0.25) for (let v = -1; v <= 1.001; v += 0.25) for (const w of [-HS - 0.1, HS]) { const [sx, sy] = P(u, v, w); bb = [Math.min(bb[0], sx), Math.min(bb[1], sy), Math.max(bb[2], sx), Math.max(bb[3], sy)]; } });
    const S = Math.min((W - 80) / (bb[2] - bb[0]), (H - 40) / (bb[3] - bb[1]));
    return {S, cx: (x0 + x1) / 2 - ((bb[0] + bb[2]) / 2) * S, cy: (y0 + y1) / 2 - ((bb[1] + bb[3]) / 2) * S};
  }, [W, H, x0, y0]);
  const P = view(az), floor = -HS - 0.1, rise = glide(frame - at - 4, 2.2);
  const Wz = (z) => floor + (data.Wd(z) - floor) * rise, U = (a) => (a / NS) * 2 - 1;
  const at3 = (u, v, w) => { const [sx, sy, d] = P(u, v, w); return [fit.cx + sx * fit.S, fit.cy + sy * fit.S, d]; };
  const low = rgb(C.cool), high = rgb(e.color), light = [-0.45, -0.55, 0.7], ln = Math.hypot(...light);
  const cells = [];
  for (let a = 0; a < NS; a++) for (let b = 0; b < NS; b++) {
    const zs = [data.grid[a][b], data.grid[a + 1][b], data.grid[a + 1][b + 1], data.grid[a][b + 1]];
    if (zs.some(Number.isNaN)) continue;
    const cs = [[U(a), U(b)], [U(a + 1), U(b)], [U(a + 1), U(b + 1)], [U(a), U(b + 1)]].map(([u, v], k) => [u, v, Wz(zs[k])]);
    const pts = cs.map(([u, v, w]) => at3(u, v, w));
    const e1 = cs[2].map((v, k) => v - cs[0][k]), e2 = cs[3].map((v, k) => v - cs[1][k]);
    const nrm = [e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]], nl = Math.hypot(...nrm) || 1;
    const lit = Math.abs((nrm[0] * light[0] + nrm[1] * light[1] + nrm[2] * light[2]) / (nl * ln));
    const tt = clamp((cs.reduce((m, c) => m + c[2], 0) / 4 + HS) / (2 * HS)), base = lerp3(low, high, tt);
    cells.push({d: pts.reduce((m, p) => m + p[2], 0) / 4, pts, fill: css(lerp3(lerp3(base, [0, 0, 0], 0.38), lerp3(base, [255, 255, 255], 0.18), lit))});
  }
  cells.sort((p, q) => q.d - p.d);
  const to2 = (x, y) => { const z = Wz(data.F(x, y)); return at3(((x - lo) / (hi - lo)) * 2 - 1, ((y - lo) / (hi - lo)) * 2 - 1, z + 0.03); };
  const sAt = e.glow ? e.glow.at : at + 0.45 * (end - at);
  const stepF = Math.max(5, Math.min(14, (end - sAt - 20) / Math.max(1, data.path.length - 1)));
  const prog = data.path.length > 1 ? clamp((frame - sAt) / (stepF * (data.path.length - 1)), 0, 1) * (data.path.length - 1) : 0;
  const i0 = Math.floor(prog), fr = prog - i0;
  const trail = data.path.slice(0, i0 + 1).concat(i0 < data.path.length - 1 ? [[data.path[i0][0] + (data.path[i0 + 1][0] - data.path[i0][0]) * fr, data.path[i0][1] + (data.path[i0 + 1][1] - data.path[i0][1]) * fr]] : []);
  const ball = trail.length ? to2(...trail[trail.length - 1]) : null;
  return (
    <g opacity={clamp((frame - at) / 10)}>
      <polygon points={[[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([u, v]) => at3(u, v, floor).slice(0, 2).join(",")).join(" ")} fill={alpha(C.panel, 0.55)} stroke={alpha(C.muted, 0.6)} strokeWidth={3}/>
      {cells.map((c, k) => <polygon key={k} points={c.pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ")} fill={c.fill} stroke={c.fill} strokeWidth={1.2} strokeLinejoin="round"/>)}
      {frame >= sAt && trail.length > 1 && <polyline points={trail.map((p) => to2(...p).slice(0, 2).join(",")).join(" ")} fill="none" stroke={C.hot} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" style={{filter: `drop-shadow(0 0 8px ${alpha(C.hot, 0.8)})`}}/>}
      {e.descent && ball && frame >= sAt - 12 && <circle cx={ball[0]} cy={ball[1]} r={17} fill={C.hot} stroke={C.text} strokeWidth={4} style={{filter: `drop-shadow(0 6px 10px ${alpha("#000", 0.5)})`}}/>}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={vertical ? 34 : 30}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Bars = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs = vertical ? 34 : 30, items = e.items, n = items.length;
  const to = e.to || items.map((it) => it.value);
  const sAt = e.glow ? e.glow.at : at + 0.45 * (end - at);
  const q = glide(frame - sAt, 2.2);
  const vmax = Math.max(...items.map((it) => it.value), ...to) || 1;
  const rankOf = (vals) => vals.map((v, k) => vals.filter((w, j) => w > v || (w === v && j < k)).length);
  const r0 = rankOf(items.map((it) => it.value)), r1 = rankOf(to);
  const slot = (k) => (e.sort ? r0[k] + (r1[k] - r0[k]) * q : k);
  const labelW = Math.min(W * 0.28, 240), rowH = Math.min(86, (H - 20) / n), top = y0 + (H - rowH * n) / 2;
  const cols = [e.color, C.cool, C.hot, C.violet, C.accent];
  return (
    <g>
      {items.map((it, k) => {
        const p = pop(frame - at - k * 4), v = it.value + (to[k] - it.value) * q, w = (W - labelW - 130) * (v / vmax) * clamp(p * 1.4);
        const y = top + slot(k) * rowH, c = cols[k % cols.length];
        return (
          <g key={`b${k}`} opacity={clamp(p * 2)}>
            <Txt x={x0 + labelW - 14} y={y + rowH / 2} size={fs} anchor="end">{it.text}</Txt>
            <rect x={x0 + labelW} y={y + rowH * 0.14} width={Math.max(2, w)} height={rowH * 0.72} rx={rowH * 0.2} fill={c} style={{filter: `drop-shadow(0 0 10px ${alpha(c, 0.45)})`}}/>
            {e.show && <Txt x={x0 + labelW + Math.max(2, w) + 14} y={y + rowH / 2} size={fs} anchor="start" mono>{Math.round(v * 10) / 10}{e.unit ? ` ${e.unit}` : ""}</Txt>}
          </g>
        );
      })}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs}/>
    </g>
  );
};

// ---------------------------------------------------------------------------------------------------------------
export const Flow = ({e, rect, frame, end, seed = 0, vertical}) => {
  const [x0, y0, x1, y1] = rect, W = x1 - x0, H = y1 - y0, at = e.at ?? 0;
  const fs = vertical ? 34 : 30, st = e.stages, n = st.length;
  const colW = Math.min(W * 0.18, 240), gap = (W - colW) / (n - 1), cy = (y0 + y1) / 2 - 20, maxH = H * 0.46;
  const cx = (k) => x0 + colW / 2 + k * gap;
  const thick = (k) => Math.max(10, maxH * st[k].share);
  const speed = 0.0105;
  const parts = [];
  for (let k = 0; k < n - 1; k++) {
    const a = cx(k) + colW / 2, b = cx(k + 1) - colW / 2, len = b - a;
    const keep = st[k + 1].share / Math.max(1e-6, st[k].share), count = Math.max(6, Math.round(46 * st[k].share));
    for (let i = 0; i < count; i++) {
      const s0 = (frame - at - 10) * speed * (0.8 + 0.4 * random(`f${seed}-${k}-${i}-v`)) + i / count;
      const s = s0 - Math.floor(s0), alive = frame - at > 10 + i * 0.3;
      if (!alive) continue;
      const survives = random(`f${seed}-${k}-${i}-s`) < keep, side = (random(`f${seed}-${k}-${i}-y`) - 0.5) * 0.8;
      const th = thick(k) + (thick(k + 1) - thick(k)) * s;
      let px = a + len * s, py = cy + side * th, op = 1;
      if (!survives && s > 0.7) { const f = (s - 0.7) / 0.3; py += f * f * H * 0.3; op = 1 - f; px += f * 18; }
      parts.push(<circle key={`p${k}-${i}`} cx={px} cy={py} r={Math.max(4.5, Math.min(11, thick(k + 1) / 7))} fill={k % 2 ? C.cool : e.color} opacity={op * 0.95 * clamp((frame - at - 8) / 10)}/>);
    }
  }
  return (
    <g>
      {Array.from({length: n - 1}, (_, k) => {
        const a = cx(k) + colW / 2, b = cx(k + 1) - colW / 2, h0 = thick(k) / 2, h1 = thick(k + 1) / 2, g = ease((frame - at - k * 6) / 18);
        return <path key={`pipe${k}`} d={`M${a},${cy - h0} L${a + (b - a) * g},${cy - h0 + (h0 - h1) * g} L${a + (b - a) * g},${cy + h0 - (h0 - h1) * g} L${a},${cy + h0} Z`}
                     fill={alpha(mixHex(C.panel, e.color, 0.5), 0.35)} stroke={alpha(e.color, 0.7)} strokeWidth={3}/>;
      })}
      {parts}
      {st.map((s, k) => {
        const p = pop(frame - at - k * 6), h = thick(k) + 36;
        return (
          <g key={`s${k}`} opacity={clamp(p * 2)} transform={`translate(${cx(k)},${cy}) scale(${0.7 + 0.3 * p})`}>
            <rect x={-colW / 2} y={-h / 2} width={colW} height={h} rx={26} fill={alpha(C.panel, 0.96)} stroke={e.color} strokeWidth={5}/>
            <Txt x={0} y={0} size={Math.min(fs, colW / Math.max(4, s.text.length * 0.6))}>{s.text}</Txt>
          </g>
        );
      })}
      <Caption text={e.text} rect={rect} at={at} frame={frame} size={fs}/>
    </g>
  );
};
