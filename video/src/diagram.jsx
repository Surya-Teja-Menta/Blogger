// A diagram drawn for one sentence (blogwriter/diagram.py): points, point clouds, lines, arrows, curves, boxes,
// bars, labels, icons and formulas, each appearing on its spoken word, then moving, glowing or leaving on others.
// The composition is the model's; this file only draws it, in the video's own colours and motion language.
import React from "react";
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {Backdrop, Camera, Title, clamp, ease} from "./fx";
import {Icon} from "./graphics";
import {Tex, useMathFonts} from "./math";
import {C, FONT, alpha} from "./theme";

const col = (name) => ({accent: C.accent, hot: C.hot, cool: C.cool, violet: C.violet, text: C.text, muted: C.muted}[name] || C.accent);
const TexFonts = () => { useMathFonts(); return null; };

// a smooth path through points (Catmull-Rom as cubic Beziers)
const smooth = (pts) => pts.map((p, k) => {
  if (!k) return `M${p[0]},${p[1]}`;
  const a = pts[k - 2] || pts[k - 1], b = pts[k - 1], c = p, d = pts[k + 1] || p;
  return `C${b[0] + (c[0] - a[0]) / 6},${b[1] + (c[1] - a[1]) / 6} ${c[0] - (d[0] - b[0]) / 6},${c[1] - (d[1] - b[1]) / 6} ${c[0]},${c[1]}`;
}).join(" ");

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
    const p = spring({frame: frame - (e.at ?? 0), fps, config: {damping: C.damping ?? 15, mass: 0.7}});
    const draw = ease((frame - (e.at ?? 0)) / 22);
    const q = e.move ? spring({frame: frame - e.move.at, fps, config: {damping: 18}}) : 0;
    const v = (k) => (e.move && e.move[k] !== undefined ? e[k] + (e.move[k] - e[k]) * q : e[k]);
    const gone = e.hide ? clamp((frame - e.hide.at) / 12) : 0;
    const glow = e.glow && frame >= e.glow.at ? 0.5 + 0.5 * Math.sin((frame - e.glow.at) / 5) : 0;
    return {p, draw, v, alive: frame >= (e.at ?? 0), fade: 1 - gone, glow};
  };
  const shadow = (c, g) => (g ? `drop-shadow(0 0 ${10 + 16 * g}px ${alpha(c, 0.9)})` : `drop-shadow(0 0 8px ${alpha(c, 0.35)})`);

  const shapes = [], texts = [];
  els.forEach((e, k) => {
    const st = state(e);
    if (!st.alive) return;
    const c = col(e.color);
    const op = st.fade;
    if (e.type === "dot") {
      shapes.push(<circle key={k} cx={X(st.v("x"))} cy={Y(st.v("y"))} r={e.r * u * (e.anim === "fade" ? 1 : st.p)}
                          fill={c} opacity={op * (e.anim === "fade" ? clamp(st.p) : 1)} style={{filter: shadow(c, st.glow)}}/>);
    } else if (e.type === "dots") {
      e.points.forEach((pt, j) => {
        const pj = spring({frame: frame - e.at - j * 1.6, fps, config: {damping: 12}});
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
      shapes.push(<path key={k} d={smooth(e.points.map((pt) => [X(pt[0]), Y(pt[1])]))} fill="none" stroke={c} strokeWidth={6}
                        strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1}
                        strokeDashoffset={1 - ease((frame - e.at) / 30)} opacity={op} style={{filter: shadow(c, st.glow)}}/>);
    } else if (e.type === "bar") {
      const hh = (st.v("h") * (box.y1 - box.y0) / 100) * (e.anim === "fade" ? 1 : st.p);
      const w = (box.x1 - box.x0) * e.w / 100;
      shapes.push(<rect key={k} x={X(e.x)} y={Y(e.y) - hh} width={w} height={Math.max(0, hh)} rx={Math.min(12, w / 4)}
                        fill={c} opacity={op} style={{filter: shadow(c, st.glow)}}/>);
      if (e.text) texts.push({k, x: X(e.x) + w / 2, y: Y(e.y) + 34, text: e.text, size: fs.s, color: C.muted, p: st.draw, op, center: true});
    } else if (e.type === "label") {
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), text: e.text, size: fs[e.size] || fs.m, color: c, p: st.p, op,
                  align: e.align, display: e.size === "l", glow: st.glow});
    } else if (e.type === "icon") {
      const sz = e.size * u;
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), node: <Icon name={e.name} size={sz} color={c} draw={st.draw}/>,
                  p: st.p, op, center: true, glow: st.glow, color: c});
    } else if (e.type === "tex") {
      texts.push({k, x: X(st.v("x")), y: Y(st.v("y")), node: <Tex tex={e.tex} color={c}/>, size: (fs[e.size] || fs.m) * 1.25,
                  p: st.p, op, center: true, glow: st.glow, color: c});
    }
  });

  return (
    <AbsoluteFill>
      {hasTex && <TexFonts/>}
      <Backdrop word="" i={i}/>
      <Camera i={i} amount={0.35}>
        <Title s={s} vertical={vertical}/>
        <svg width={width} height={height} style={{position: "absolute", overflow: "visible"}}>{shapes}</svg>
        {texts.map((t) => {
          const shift = t.center || t.align === "center" ? "-50%" : t.align === "right" ? "-100%" : "0%";
          return (
            <div key={`t${t.k}`} style={{position: "absolute", left: t.x, top: t.y,
                                          transform: `translate(${shift}, -50%) translateY(${(1 - clamp(t.p)) * 24}px) scale(${0.85 + 0.15 * clamp(t.p)})`,
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
      </Camera>
    </AbsoluteFill>
  );
};
