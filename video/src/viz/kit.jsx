// The shared drawing kit of the visual-technique library (blogwriter/vizlib.py declares the techniques). Every
// technique is a pure function of the frame, drawn in SVG inside its region `rect` = [x0, y0, x1, y1] of the
// diagram canvas, and receives its element `e` (fields cleaned by vizlib.fill, `e.at` its first frame, `e.glow.at`
// its key moment when the narration names one, `e.show` true when its numbers may be printed).
import React from "react";
import {randomLcg} from "d3-random";
import {clamp, ease} from "../fx";
import {Icon} from "../graphics";
import {glide, pop} from "../motion";
import {Caption, Txt} from "../rich";
import {C, FONT, alpha} from "../theme";

export {React, clamp, ease, glide, pop, Txt, Caption, C, FONT, alpha};

// the moments of a technique: when it starts, its key moment (the glow word, else 45% in) and progress after it
export const timing = (e, frame, end) => {
  const at = e.at ?? 0;
  const key = e.glow ? e.glow.at : Math.round(at + 0.45 * Math.max(30, end - at));
  return {at, key, t: frame - at, k: frame - key, tail: Math.max(24, end - key)};
};

// the region in handy numbers, and the type size that suits it
export const box = (rect, vertical) => {
  const [x0, y0, x1, y1] = rect;
  const W = x1 - x0, H = y1 - y0;
  return {x0, y0, x1, y1, W, H, cx: (x0 + x1) / 2, cy: (y0 + y1) / 2,
          fs: Math.round(clamp(Math.min(W / 22, H / 9), 22, vertical ? 40 : 34))};
};

// colours for a set of things: the element's own colour first, then the theme's other chart colours
export const pal = (e, k) => [e.color || C.accent, C.cool, C.hot, C.violet, C.accent, C.text][k % 6];
export const glowF = (c, s = 1) => `drop-shadow(0 0 ${8 + 12 * s}px ${alpha(c, 0.5 + 0.4 * clamp(s))})`;

export const rng = (seed) => randomLcg(((Math.abs(seed) % 9973) + 1) / 9974);
export const tw = (text, fs) => String(text || "").length * fs * 0.62;          // text width, roughly
export const fitFs = (text, fs, maxW) => Math.max(14, Math.min(fs, maxW / Math.max(1, String(text || "").length * 0.56)));
export const lerp = (a, b, t) => a + (b - a) * t;
export const fmt = (v) => (Math.abs(v) >= 100 || Number.isInteger(v) ? String(Math.round(v)) : Math.abs(v) < 1 ? String(Number(v.toPrecision(2))) : String(Math.round(v * 10) / 10));
export const row = (n, a, b) => Array.from({length: n}, (_, k) => (n === 1 ? (a + b) / 2 : a + ((b - a) * k) / (n - 1)));
export const spread = (n, a, b) => Array.from({length: n}, (_, k) => a + ((b - a) * (k + 0.5)) / n);

// a point a share t of the way along a polyline
export const along = (pts, t) => {
  const seg = [];
  let total = 0;
  for (let k = 1; k < pts.length; k++) {
    const d = Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]);
    seg.push(d);
    total += d;
  }
  let want = clamp(t) * total;
  for (let k = 1; k < pts.length; k++) {
    if (want <= seg[k - 1] || k === pts.length - 1) {
      const u = seg[k - 1] ? clamp(want / seg[k - 1]) : 0;
      return [lerp(pts[k - 1][0], pts[k][0], u), lerp(pts[k - 1][1], pts[k][1], u)];
    }
    want -= seg[k - 1];
  }
  return pts[pts.length - 1];
};

// a rounded card with an optional icon and a label: a server, a service, a store, a stage
export const Card = ({x, y, w, h, label, icon, color, p = 1, lit = 0, fs = 28, sub, dim = false}) => {
  const col = color || C.accent;
  const s = 0.7 + 0.3 * p;
  const iconSize = icon ? Math.min(h * (label ? (sub ? 0.34 : 0.42) : 0.6), w * 0.5) : 0;
  const lf = fitFs(label, fs, w * 0.9);
  return (
    <g opacity={clamp(p * 2) * (dim ? 0.35 : 1)} transform={`translate(${x + w / 2},${y + h / 2}) scale(${s}) translate(${-w / 2},${-h / 2})`}>
      <rect x={0} y={0} width={w} height={h} rx={Math.min(18, h / 4)} fill={lit ? alpha(col, 0.18 + 0.3 * lit) : alpha(C.panel, 0.95)}
            stroke={lit ? col : alpha(col, 0.7)} strokeWidth={lit ? 5 : 3} style={{filter: lit ? glowF(col, lit) : undefined}}/>
      {icon && <g transform={`translate(${w / 2 - iconSize / 2},${label ? h * (sub ? 0.08 : 0.12) : h / 2 - iconSize / 2})`}>
        <Icon name={icon} size={iconSize} color={col} draw={clamp(p * 1.2)}/></g>}
      {label && <Txt x={w / 2} y={icon ? h * (sub ? 0.64 : 0.78) : h / 2 - (sub ? lf * 0.35 : 0)} size={lf} color={C.text}>{label}</Txt>}
      {sub && <Txt x={w / 2} y={icon ? h * 0.87 : h / 2 + lf * 0.7} size={lf * 0.72} color={C.muted} weight={600}>{sub}</Txt>}
    </g>
  );
};

// a pill with a word in it, centred on (x, y)
export const Chip = ({x, y, text, color, p = 1, fs = 26, fill = false, lit = 0, strike = false}) => {
  const col = color || C.accent;
  const w = tw(text, fs) + fs * 1.2, h = fs * 1.7;
  return (
    <g opacity={clamp(p * 2)} transform={`translate(${x},${y}) scale(${0.6 + 0.4 * p})`}>
      <rect x={-w / 2} y={-h / 2} width={w} height={h} rx={h / 2} fill={fill || lit ? alpha(col, 0.25 + 0.4 * lit) : alpha(C.panel, 0.95)}
            stroke={col} strokeWidth={3} style={{filter: lit ? glowF(col, lit) : undefined}}/>
      <Txt x={0} y={1} size={fs} color={C.text}>{text}</Txt>
      {strike && <line x1={-w / 2 + 6} y1={0} x2={-w / 2 + 6 + (w - 12) * clamp(strike)} y2={0} stroke={C.hot} strokeWidth={5}/>}
    </g>
  );
};

// an arrow from a to b that draws itself (draw 0 -> 1), optionally bent, dashed and labelled at its middle
export const Arrow = ({a, b, draw = 1, color, width = 4, bend = 0, label, fs = 24, dashed = false, head = true, op = 1}) => {
  const col = color || C.muted;
  const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const c = [mx - dy * bend, my + dx * bend];
  const d = `M${a[0]},${a[1]} Q${c[0]},${c[1]} ${b[0]},${b[1]}`;
  const t = clamp(draw);
  const ang = Math.atan2(b[1] - c[1], b[0] - c[0]);
  const hs = 10 + width * 2;
  const lp = [0.25 * a[0] + 0.5 * c[0] + 0.25 * b[0], 0.25 * a[1] + 0.5 * c[1] + 0.25 * b[1]];
  return (
    <g opacity={op}>
      <path d={d} fill="none" stroke={col} strokeWidth={width} strokeLinecap="round" pathLength={1}
            strokeDasharray={dashed ? "0.025 0.02" : 1} strokeDashoffset={dashed ? 0 : 1 - t} opacity={dashed ? t : 1}/>
      {head && t > 0.92 && <path d={`M${b[0]},${b[1]} L${b[0] - hs * Math.cos(ang - 0.45)},${b[1] - hs * Math.sin(ang - 0.45)} L${b[0] - hs * Math.cos(ang + 0.45)},${b[1] - hs * Math.sin(ang + 0.45)} Z`} fill={col}/>}
      {label && t > 0.5 && <Txt x={lp[0]} y={lp[1] - fs * 0.75} size={fs} color={C.text} op={clamp((t - 0.5) * 3)}>{label}</Txt>}
    </g>
  );
};

// a glowing dot travelling along a polyline (t 0 -> 1); hidden outside that span
export const Packet = ({pts, t, color, r = 9}) => {
  if (!(t > 0 && t < 1)) return null;
  const [x, y] = along(pts, t);
  const col = color || C.hot;
  return <circle cx={x} cy={y} r={r} fill={col} style={{filter: glowF(col, 0.8)}}/>;
};

// an icon centred on (x, y)
export const Ico = ({name, x, y, size = 60, color, draw = 1, op = 1}) => (
  <g opacity={op} transform={`translate(${x - size / 2},${y - size / 2})`}><Icon name={name} size={size} color={color || C.accent} draw={draw}/></g>
);

// a value label that only prints when the numbers are spoken (e.show)
export const Num = ({e, v, x, y, fs, color, op = 1, prefix = "", suffix = ""}) => (e.show ? (
  <Txt x={x} y={y} size={fs} color={color || C.text} op={op}>{prefix}{fmt(v)}{suffix}</Txt>
) : null);

// a pulsing ring around a point (the eye is drawn there)
export const Ring = ({x, y, r, color, frame, from}) => {
  const t = frame - from;
  if (t < 0) return null;
  const q = (t % 40) / 40;
  return <circle cx={x} cy={y} r={r * (1 + q * 0.6)} fill="none" stroke={color || C.hot} strokeWidth={4} opacity={(1 - q) * 0.8}/>;
};

// a smooth path through points (Catmull-Rom to Bezier)
export const smoothPath = (pts) => {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let k = 0; k < pts.length - 1; k++) {
    const p0 = pts[k - 1] || pts[k], p1 = pts[k], p2 = pts[k + 1], p3 = pts[k + 2] || p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
  }
  return d;
};

// the gaussian, for bells and densities
export const gauss = (x, m = 0, s = 1) => Math.exp(-((x - m) ** 2) / (2 * s * s));
