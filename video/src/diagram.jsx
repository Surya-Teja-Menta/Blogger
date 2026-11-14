// A diagram drawn for one sentence (blogwriter/diagram.py): points, point clouds, lines, arrows, curves, boxes,
// bars, labels, icons and formulas, each appearing on its spoken word, then moving, glowing or leaving on others.
// The composition is the model's; this file only draws it, in the video's own colours and motion language.
import React, {useMemo} from "react";
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from "remotion";
import {getLength, getPointAtLength} from "@remotion/paths";
import {interpolate as morphPath} from "flubber";
import {Backdrop, Camera, Title, clamp, ease} from "./fx";
import {Focus, Pen, Stamp, focusPlan, headlineShown, useFocus} from "./direct";
import {Icon} from "./graphics";
import {Physics, Samples, seedOf} from "./stats";
import {Cursor, Cycle, Grid, Network, Plot, Tree, Venn} from "./rich";
import {Bars, Code, Flow, Surface3D, Wave} from "./rich2";
import {VIZ} from "./viz";
import {HandText} from "./hand";
import {Tex, useMathFonts} from "./math";
import {delay, glide, pop} from "./motion";
import {C, FONT, alpha} from "./theme";

const col = (name) => ({accent: C.accent, hot: C.hot, cool: C.cool, violet: C.violet, text: C.text, muted: C.muted}[name] || C.accent);
const RICH = {plot: Plot, network: Network, tree: Tree, grid: Grid, venn: Venn, cycle: Cycle, code: Code, wave: Wave, surface: Surface3D,
              bars: Bars, flow: Flow, ...VIZ};      // parts that fill a region (rich.jsx, rich2.jsx, viz/)
const TexFonts = () => { useMathFonts(); return null; };

// a smooth path through points (Catmull-Rom as cubic Beziers)
const smooth = (pts) => pts.map((p, k) => {
  if (!k) return `M${p[0]},${p[1]}`;
  const a = pts[k - 2] || pts[k - 1], b = pts[k - 1], c = p, d = pts[k + 1] || p;
  return `C${b[0] + (c[0] - a[0]) / 6},${b[1] + (c[1] - a[1]) / 6} ${c[0] - (d[0] - b[0]) / 6},${c[1] - (d[1] - b[1]) / 6} ${c[0]},${c[1]}`;
}).join(" ");

// a point list stretched or squeezed to n points, so two shapes with different counts can morph
const resample = (pts, n) => Array.from({length: n}, (_, j) => {
  const t = (j * (pts.length - 1)) / Math.max(1, n - 1), a = Math.floor(t), b = Math.min(pts.length - 1, a + 1);
  return [pts[a][0] + (pts[b][0] - pts[a][0]) * (t - a), pts[a][1] + (pts[b][1] - pts[a][1]) * (t - a)];
});
const morph = (from, to, q) => {
  if (!to || q <= 0) return from;
  const n = Math.max(from.length, to.length), A = resample(from, n), B = resample(to, n);
  return A.map((p, j) => [p[0] + (B[j][0] - p[0]) * q, p[1] + (B[j][1] - p[1]) * q]);
};

// outlines for "shape" elements, as point rings around (0, 0) with radius 1; flubber morphs any one into any other
const ring = (n, r = (k) => 1, turn = -Math.PI / 2) => Array.from({length: n}, (_, k) => {
  const a = turn + (2 * Math.PI * k) / n;
  return [Math.cos(a) * r(k), Math.sin(a) * r(k)];
});
const OUTLINES = {
  circle: () => ring(64),
  square: () => ring(4, () => Math.SQRT2, -Math.PI / 4).map(([x, y]) => [x * 0.86, y * 0.86]),
  triangle: () => ring(3, () => 1.15).map(([x, y]) => [x, y + 0.2]),
  diamond: () => ring(4, () => 1.1),
  hexagon: () => ring(6, () => 1.02, 0),
  star: () => ring(10, (k) => (k % 2 ? 0.45 : 1.12)),
  heart: () => Array.from({length: 64}, (_, k) => {
    const t = (2 * Math.PI * k) / 64;
    return [(16 * Math.sin(t) ** 3) / 16, -(13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) / 16];
  }),
};
const outline = (name, cx, cy, r) => (OUTLINES[name] || OUTLINES.circle)().map(([x, y]) => [cx + x * r, cy + y * r]);
const pathOf = (pts) => `M${pts.map((p) => p.map((v) => v.toFixed(1)).join(",")).join("L")}Z`;

const MorphShape = ({from, to, cx, cy, r, q, color, fill, op, glow, draw}) => {
  const unit = useMemo(() => (to && to !== from ? morphPath(outline(from, 0, 0, 100), outline(to, 0, 0, 100), {maxSegmentLength: 6}) : null),
    [from, to]);
  const d = unit && q > 0 ? unit(Math.min(1, q)) : pathOf(outline(from, 0, 0, 100));
  return (
    <path d={d} transform={`translate(${cx},${cy}) scale(${r / 100})`} fill={fill ? alpha(color, 0.22) : "none"} stroke={color}
          strokeWidth={(5 * 100) / Math.max(1, r)} strokeLinejoin="round" pathLength={1} strokeDasharray={1}
          strokeDashoffset={1 - draw} opacity={op} style={{filter: glow}}/>
  );
};

// a crowd of icons in a grid; `highlight` of them light up (spread out, not in a block) when the moment comes
const Crowd = ({e, w, h, frame, color, size}) => {
  const n = e.count, cols = Math.max(1, Math.round(Math.sqrt((n * w) / h))), rows = Math.ceil(n / cols);
  const cell = Math.min(w / cols, h / rows);
  const lit = useMemo(() => {
    const order = Array.from({length: n}, (_, k) => k).sort((a, b) => seedOf(`${a}|${n}`) - seedOf(`${b}|${n}`));
    return new Set(order.slice(0, e.highlight || 0));
  }, [n, e.highlight]);
  const on = e.glow ? e.glow.at : (e.at ?? 0) + 40;
  return (
    <div style={{display: "grid", gridTemplateColumns: `repeat(${cols}, ${cell}px)`, width: cols * cell}}>
      {Array.from({length: n}, (_, k) => {
        const p = clamp((frame - (e.at ?? 0) - k * (30 / n)) / 8);
        const hit = lit.has(k) ? clamp((frame - on - (k % 7)) / 8) : 0;
        return (
          <div key={k} style={{width: cell, height: cell, display: "flex", alignItems: "center", justifyContent: "center",
                               opacity: p, transform: `scale(${0.6 + 0.4 * p + 0.25 * hit * (1 - hit) * 4})`}}>
            <Icon name={e.name} size={cell * 0.78} color={hit > 0.5 ? color : alpha(C.muted, 0.7)} width={2}/>
          </div>
        );
      })}
    </div>
  );
};

export const DiagramScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const box = vertical ? {x0: 80, x1: 1000, y0: 600, y1: 1560} : {x0: 150, x1: 1770, y0: 310, y1: 925};
  const u = (box.y1 - box.y0) / 100;                       // size unit: 1% of the canvas height
  const X = (x) => box.x0 + ((box.x1 - box.x0) * x) / 100;
  const Y = (y) => box.y0 + ((box.y1 - box.y0) * y) / 100;
  const fs = {s: 34, m: 46, l: 66}, fScale = vertical ? 1.15 : 1;
  const els = (s.diagram && s.diagram.elements) || [];
  const hasTex = els.some((e) => e.type === "tex");

  // where an element is now: its own values, eased toward its move target once that word is said
  const state = (e) => {
    const p = pop(frame - (e.at ?? 0));
    const draw = ease((frame - (e.at ?? 0)) / 22);
    const q = e.move ? (e.move.along !== undefined ? glide : pop)(frame - e.move.at, 1.6) : 0;
    const v = (k) => (e.move && e.move[k] !== undefined ? e[k] + (e.move[k] - e[k]) * q : e[k]);
    const gone = e.hide ? clamp((frame - e.hide.at) / 12) : 0;
    const glow = e.glow && frame >= e.glow.at ? 0.5 + 0.5 * Math.sin((frame - e.glow.at) / 5) : 0;
    const pts = e.points && (e.move && e.move.points ? morph(e.points, e.move.points, q) : e.points);
    return {p, draw, v, q, pts, alive: frame >= (e.at ?? 0), fade: 1 - gone, glow};
  };
  // where a dot riding a curve is: from the curve point nearest its start to the one nearest its stop
  const ride = (e, q) => {
    const c = els[e.move.along];
    const d = smooth(c.points.map((pt) => [X(pt[0]), Y(pt[1])]));
    const L = getLength(d);
    const near = (x, y) => {
      let best = [Infinity, 0];
      for (let j = 0; j <= 120; j++) {
        const pt = getPointAtLength(d, (L * j) / 120);
        const dist = Math.hypot(pt.x - X(x), pt.y - Y(y));
        if (dist < best[0]) best = [dist, j / 120];
      }
      return best[1];
    };
    const u0 = near(e.x, e.y), u1 = e.move.x !== undefined ? near(e.move.x, e.move.y ?? e.y) : 1;
    const pt = getPointAtLength(d, L * (u0 + (u1 - u0) * Math.min(1, Math.max(0, q))));
    return [pt.x, pt.y];
  };
  const shadow = (c, g) => (g ? `drop-shadow(0 0 ${10 + 16 * g}px ${alpha(c, 0.9)})` : `drop-shadow(0 0 8px ${alpha(c, 0.35)})`);

  // where a piece sits on screen ([x0, y0, x1, y1]), as placed or once moved: the camera frames it, the pen rings it
  const texLen = (t) => String(t || "").replace(/\\[a-zA-Z]+/g, "X").replace(/[{}_^\s]/g, "").length;
  const boxOf = (e) => {
    const pts = (ps) => [Math.min(...ps.map((p) => p[0])), Math.min(...ps.map((p) => p[1])),
                         Math.max(...ps.map((p) => p[0])), Math.max(...ps.map((p) => p[1]))];
    const around = (x, y, rx, ry = rx) => [x - rx, y - ry, x + rx, y + ry];
    const t = e.type;
    if (t === "dot") return around(X(e.x), Y(e.y), (e.r || 2) * u);
    if (t === "circle") return around(X(e.x), Y(e.y), (e.r || 5) * u);
    if (t === "dots" || t === "curve") return e.points && e.points.length ? pts(e.points.map((p) => [X(p[0]), Y(p[1])])) : null;
    if (t === "box") return [X(e.x), Y(e.y), X(e.x + e.w), Y(e.y + e.h)];
    if (t === "line" || t === "arrow") return pts([[X(e.x1), Y(e.y1)], [X(e.x2), Y(e.y2)]]);
    if (t === "bar") return [X(e.x), Y(e.y) - (e.h * (box.y1 - box.y0)) / 100, X(e.x + e.w), Y(e.y)];
    if (t === "icon") return around(X(e.x), Y(e.y), ((e.size || 8) * u) / 2);
    if (t === "samples" || t === "physics" || t === "crowd" || RICH[t]) return [X(e.x), Y(e.y), X(e.x + e.w), Y(e.y + e.h)];
    if (t === "shape") return around(X(e.x), Y(e.y), (e.size || 10) * u);
    if (t === "stamp") return around(X(e.x), Y(e.y), String(e.text || "").length * 30 + 60, 70);
    if (t === "label" || t === "tex" || t === "counter") {
      const size = (fs[e.size] || fs.m) * fScale * (t === "tex" ? 1.25 : t === "counter" ? 1.6 : 1);
      const chars = t === "tex" ? texLen(e.tex) : t === "counter" ? String(e.to).length + 1 + String(e.text || "").length : String(e.text || "").length;
      const w = chars * size * 0.56, x = X(e.x);
      const x0 = t !== "label" || e.align === "center" ? x - w / 2 : e.align === "right" ? x - w : x;
      return [x0, Y(e.y) - size * 0.6, x0 + w, Y(e.y) + size * 0.6];
    }
    return null;
  };
  const moved = (e) => {
    if (!e.move) return e;
    const m = {...e, ...Object.fromEntries(Object.entries(e.move).filter(([k]) => k !== "at" && k !== "along"))};
    if (e.move.along !== undefined && els[e.move.along]) {
      const c = els[e.move.along];
      return {...m, type: "curve", points: c.points};             // a dot riding a curve: frame the whole ride
    }
    return m;
  };
  const keys = [], pens = [];
  els.forEach((e, k) => {
    const b0 = boxOf(e);
    if (!b0) return;
    keys.push({at: e.at ?? 0, box: b0});
    if (e.move && e.move.at != null) {
      const b1 = boxOf(moved(e));
      if (b1) keys.push({at: e.move.at, box: [Math.min(b0[0], b1[0]), Math.min(b0[1], b1[1]), Math.max(b0[2], b1[2]), Math.max(b0[3], b1[3])]});
    }
    if (e.glow && e.glow.at != null) {
      const g = e.move && e.move.at != null && e.move.at <= e.glow.at ? boxOf(moved(e)) || b0 : b0;
      keys.push({at: e.glow.at, box: g});
      const gone = e.hide && e.hide.at != null ? clamp((frame - e.hide.at) / 12) : 0;
      if (e.type !== "crowd" && !RICH[e.type]) {       // a rich part's glow word is its own moment (the wave, the path, the area)
        pens.push(<g key={`pen${k}`} opacity={1 - gone}><Pen box={g} at={e.glow.at} seed={k * 31 + (i || 0)}
                                                        color={e.color === "hot" ? C.accent : C.hot}/></g>);
      }
    }
    // a teacher's mark on its word: ringed, underlined, boxed or struck out
    if (e.mark && e.mark.at != null) {
      const g = e.move && e.move.at != null && e.move.at <= e.mark.at ? boxOf(moved(e)) || b0 : b0;
      keys.push({at: e.mark.at, box: g});
      const gone = e.hide && e.hide.at != null ? clamp((frame - e.hide.at) / 12) : 0;
      pens.push(<g key={`mark${k}`} opacity={1 - gone}><Pen box={g} at={e.mark.at} seed={k * 37 + (i || 0)} kind={e.mark.style}
                                                       color={e.color === "hot" ? C.accent : C.hot}/></g>);
    }
    if (e.click && e.click.at != null) {
      keys.push({at: e.click.at, box: b0});
      const gone = e.hide && e.hide.at != null ? clamp((frame - e.hide.at) / 12) : 0;
      pens.push(<g key={`click${k}`} opacity={1 - gone}><Cursor box={b0} at={e.click.at}/></g>);
    }
    if (e.fit && e.fit.at != null) keys.push({at: e.fit.at, box: b0});           // in close as the bell appears
  });
  // while a live part (samples, physics) is running it is the main event: every framing keeps it in view
  const live = els.filter((e) => e.type === "samples" || e.type === "physics" || RICH[e.type]).map((e) => ({at: e.at ?? 0, box: boxOf(e)}));
  const framed = keys.map((key) => live.reduce((kk, l) => (key.at >= l.at
    ? {at: kk.at, box: [Math.min(kk.box[0], l.box[0]), Math.min(kk.box[1], l.box[1]), Math.max(kk.box[2], l.box[2]), Math.max(kk.box[3], l.box[3])]}
    : kk), key));
  const view = useFocus(focusPlan(framed, {width, height, frames: s.frames || 300}));

  const shapes = [], texts = [];
  els.forEach((e, k) => {
    const st = state(e);
    if (!st.alive) return;
    const c = col(e.color);
    const op = st.fade;
    if (e.type === "dot") {
      const [cx, cy] = e.move && e.move.along !== undefined && els[e.move.along] ? ride(e, st.q) : [X(st.v("x")), Y(st.v("y"))];
      shapes.push(<circle key={k} cx={cx} cy={cy} r={e.r * u * (e.anim === "fade" ? 1 : st.p)}
                          fill={c} opacity={op * (e.anim === "fade" ? clamp(st.p) : 1)} style={{filter: shadow(c, st.glow)}}/>);
    } else if (e.type === "dots") {
      st.pts.forEach((pt, j) => {
        const pj = pop(frame - e.at - delay(j, e.points.length, `d${k}`));
        shapes.push(<circle key={`${k}-${j}`} cx={X(pt[0])} cy={Y(pt[1])} r={e.r * u * pj} fill={c} opacity={op}
                            stroke={C.bg} strokeWidth={2} style={{filter: shadow(c, st.glow)}}/>);
      });
    } else if (e.type === "circle") {
      const r = st.v("r") * u;
      shapes.push(<circle key={k} cx={X(st.v("x"))} cy={Y(st.v("y"))} r={r} fill={e.fill ? alpha(c, 0.18) : "none"}
                          stroke={c} strokeWidth={4} pathLength={1} strokeDasharray={1} strokeDashoffset={1 - st.draw}
                          opacity={op} style={{filter: shadow(c, st.glow)}}/>);
      if (e.text) texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), text: e.text, size: fs.m, color: C.text, p: st.draw, op, center: true});
    } else if (e.type === "box") {
      const rad = ((C.fx || {}).cards || {}).radius ?? 18;
      shapes.push(<rect key={k} x={X(e.x)} y={Y(e.y)} width={(box.x1 - box.x0) * e.w / 100} height={(box.y1 - box.y0) * e.h / 100}
                        rx={rad} fill={alpha(c, 0.14 * st.draw)} stroke={c} strokeWidth={3.5} pathLength={1}
                        strokeDasharray={1} strokeDashoffset={1 - st.draw} opacity={op}
                        style={{transform: `translate(${(st.v("x") - e.x) * (box.x1 - box.x0) / 100}px, ${(st.v("y") - e.y) * (box.y1 - box.y0) / 100}px)`,
                                filter: shadow(c, st.glow)}}/>);
      if (e.text) texts.push({k, x: X(st.v("x") + e.w / 2), y: Y(st.v("y") + e.h / 2), text: e.text, size: fs.m, color: C.text,
                              p: clamp((frame - e.at - 10) / 12), op, center: true});
    } else if (e.type === "line" || e.type === "arrow") {
      const x1 = X(st.v("x1")), y1 = Y(st.v("y1")), x2 = X(st.v("x2")), y2 = Y(st.v("y2"));
      const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
      const bend = e.bend || 0;
      const cx = (x1 + x2) / 2 - dy * bend, cy = (y1 + y2) / 2 + dx * bend;
      const d = e.type === "arrow" ? `M${x1},${y1} Q${cx},${cy} ${x2},${y2}` : `M${x1},${y1} L${x2},${y2}`;
      shapes.push(<path key={k} d={d} fill="none" stroke={c} strokeWidth={e.type === "arrow" ? 6 : 5} strokeLinecap="round"
                        pathLength={e.dashed ? undefined : 1} strokeDasharray={e.dashed ? "16 12" : 1}
                        strokeDashoffset={e.dashed ? 0 : 1 - st.draw} opacity={op * (e.dashed ? st.draw : 1)}
                        style={{filter: shadow(c, st.glow)}}/>);
      if (e.type === "arrow") {
        const tx = x2 - cx, ty = y2 - cy, tl = Math.hypot(tx, ty) || 1, ux = tx / tl, uy = ty / tl, h = 26;
        shapes.push(<polygon key={`${k}h`} points={`${x2},${y2} ${x2 - ux * h - uy * h * 0.55},${y2 - uy * h + ux * h * 0.55} ${x2 - ux * h + uy * h * 0.55},${y2 - uy * h - ux * h * 0.55}`}
                             fill={c} opacity={op * clamp((st.draw - 0.85) * 7)}/>);
        if (e.text) texts.push({k, x: (x1 + 2 * cx + x2) / 4, y: (y1 + 2 * cy + y2) / 4 - 34, text: e.text, size: fs.s, color: c,
                                p: clamp((frame - e.at - 14) / 10), op, center: true, chip: true});
      }
      void len;
    } else if (e.type === "curve") {
      shapes.push(<path key={k} d={smooth(st.pts.map((pt) => [X(pt[0]), Y(pt[1])]))} fill="none" stroke={c} strokeWidth={6}
                        strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1}
                        strokeDashoffset={1 - ease((frame - e.at) / 30)} opacity={op} style={{filter: shadow(c, st.glow)}}/>);
    } else if (e.type === "bar") {
      const hh = (st.v("h") * (box.y1 - box.y0) / 100) * (e.anim === "fade" ? 1 : st.p);
      const w = (box.x1 - box.x0) * e.w / 100;
      shapes.push(<rect key={k} x={X(e.x)} y={Y(e.y) - hh} width={w} height={Math.max(0, hh)} rx={Math.min(12, w / 4)}
                        fill={c} opacity={op} style={{filter: shadow(c, st.glow)}}/>);
      if (e.text) texts.push({k, x: X(e.x) + w / 2, y: Y(e.y) + 34, text: e.text, size: fs.s, color: C.muted, p: st.draw, op, center: true});
    } else if (e.type === "label") {
      const handed = C.look && C.look.hand;     // a board look writes its labels by hand, from the label's own word
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), text: handed ? undefined : e.text, size: fs[e.size] || fs.m, color: c,
                  p: handed ? 1 : st.p, op, align: e.align, display: e.size === "l", glow: st.glow,
                  node: handed ? <HandText text={e.text} size={(fs[e.size] || fs.m) * fScale * 1.15} at={e.at ?? 0}
                                           font={C.look.hand} color={c} align={e.align || "center"} maxWidth={900}/> : undefined});
    } else if (e.type === "icon") {
      const sz = e.size * u;
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), node: <Icon name={e.name} size={sz} color={c} draw={st.draw}/>,
                  p: st.p, op, center: true, glow: st.glow, color: c});
    } else if (e.type === "tex") {
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), node: <Tex tex={e.tex} color={c}/>, size: (fs[e.size] || fs.m) * 1.25,
                  p: st.p, op, center: true, glow: st.glow, color: c});
    } else if (e.type === "samples" || e.type === "physics") {
      const Part = e.type === "samples" ? Samples : Physics;
      shapes.push(<g key={k} opacity={op}><Part e={e} rect={[X(e.x), Y(e.y), X(e.x + e.w), Y(e.y + e.h)]} frame={frame}
                                                end={s.frames || 300} seed={k * 101 + (i || 0)} vertical={vertical}/></g>);
    } else if (e.type === "counter") {
      const q = ease((frame - (e.at ?? 0)) / 45);
      const dec = (String(e.to).split(".")[1] || "").length;
      const v = e.from + (e.to - e.from) * q;
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), text: `${v.toFixed(dec)}${e.text ? ` ${e.text}` : ""}`,
                  size: (fs[e.size] || fs.l) * 1.6, color: c, p: st.p, op, center: true, display: true, glow: st.glow});
    } else if (e.type === "shape") {
      shapes.push(<MorphShape key={k} from={e.shape} to={e.move && e.move.shape} cx={X(st.v("x"))} cy={Y(st.v("y"))}
                              r={st.v("size") * u * (e.anim === "fade" ? 1 : 0.5 + 0.5 * st.p)} q={st.q} color={c} fill={e.fill}
                              op={op} glow={shadow(c, st.glow)} draw={st.draw}/>);
    } else if (e.type === "stamp") {          // a verdict slammed onto the picture on its word
      texts.push({k, x: X(e.x), y: Y(e.y), center: true, p: 1, op,
                  node: <Stamp text={e.text} at={e.at ?? 0} color={e.color === "accent" ? C.hot : c} seed={k + (i || 0)}
                               size={(fs[e.size] || fs.l) * fScale * 1.5}/>});
    } else if (RICH[e.type]) {
      const Part = RICH[e.type];
      shapes.push(<g key={k} opacity={op}><Part e={{...e, color: c}} rect={[X(e.x), Y(e.y), X(e.x + e.w), Y(e.y + e.h)]} frame={frame}
                                                end={s.frames || 300} seed={k * 101 + (i || 0)} vertical={vertical}/></g>);
    } else if (e.type === "crowd") {
      texts.push({k, x: X(e.x), y: Y(e.y), corner: true, p: 1, op,
                  node: <Crowd e={e} w={X(e.x + e.w) - X(e.x)} h={Y(e.y + e.h) - Y(e.y)} frame={frame} color={c}/>});
    }
  });

  return (
    <AbsoluteFill>
      {hasTex && <TexFonts/>}
      <Backdrop word="" i={i}/>
      <Camera i={i} amount={0.35}>
        <AbsoluteFill style={{opacity: headlineShown(view)}}><Title s={s} vertical={vertical}/></AbsoluteFill>
        <Focus view={view}>
        <svg width={width} height={height} style={{position: "absolute", overflow: "visible"}}>{shapes}{pens}</svg>
        {texts.map((t) => {
          const shift = t.corner ? "0%" : t.center || t.align === "center" ? "-50%" : t.align === "right" ? "-100%" : "0%";
          return (
            <div key={`t${t.k}`} style={{position: "absolute", left: t.x, top: t.y,
                                          transform: `translate(${shift}, ${t.corner ? "0%" : "-50%"}) translateY(${(1 - clamp(t.p)) * 24}px) scale(${0.85 + 0.15 * clamp(t.p)})`,
                                          opacity: clamp(t.p * 1.5) * t.op, whiteSpace: "nowrap",
                                          fontFamily: t.display ? FONT.display : FONT.body, fontWeight: t.display ? C.weight : 800,
                                          fontSize: (t.size || fs.m) * fScale, color: t.color, lineHeight: 1.1,
                                          textTransform: t.display && C.upper ? "uppercase" : "none",
                                          ...(t.chip ? {padding: "6px 16px", borderRadius: 100, background: alpha(C.panel, 0.85)} : {}),
                                          textShadow: t.node ? undefined : `0 2px 18px ${alpha(C.bg, 0.9)}`,
                                          filter: t.glow ? `drop-shadow(0 0 ${8 + 14 * t.glow}px ${alpha(t.color || C.accent, 0.8)})` : undefined}}>
              {t.node || t.text}
            </div>
          );
        })}
        </Focus>
      </Camera>
    </AbsoluteFill>
  );
};
