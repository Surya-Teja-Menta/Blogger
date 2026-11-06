// Maths for lessons: an equation that builds term by term as each symbol is explained, and a data plot that shows
// the idea behind fitting a line (points, best fit, residuals, squared errors, gradient descent). The plot's data
// is generated here (seeded), and the fit and the descent are computed from it, so the picture is mathematically true.
import React, {useEffect, useLayoutEffect, useRef, useState} from "react";
import {AbsoluteFill, continueRender, delayRender, spring, useCurrentFrame, useVideoConfig} from "remotion";
import katex from "katex";
import "katex/dist/katex.min.css";
import {Backdrop, Camera, Title, clamp, ease} from "./fx";
import {delay, pop} from "./motion";
import {C, FONT, SERIES, alpha} from "./theme";
import {compile} from "./expr";

// KaTeX loads its fonts lazily; hold the frame until they are in, or the first frames show a fallback serif
const MATH_FONTS = ["48px KaTeX_Main", "italic 48px KaTeX_Math", "48px KaTeX_Size1", "48px KaTeX_Size2"];
const mathFontsIn = () => Promise.all(MATH_FONTS.map((f) => document.fonts.load(f))).catch(() => null);
export function useMathFonts() {
  const [handle] = useState(() => delayRender("KaTeX fonts"));
  useEffect(() => {
    mathFontsIn().then(() => continueRender(handle));
  }, []);
}

export const Tex = ({tex, color}) => (
  <span style={{color}} dangerouslySetInnerHTML={{__html: katex.renderToString(tex, {throwOnError: false})}}/>
);

// a formula that never runs past its box: drawn at `size`, measured as it is laid out, and shrunk until it is at
// most `max` pixels wide (never enlarged). A character count cannot know how wide \frac or a subscript sets.
// With `wrap`, a long formula first breaks after its = and + signs, as on a board, and shrinks only if one piece
// alone is still too wide; a narrow side panel then keeps a readable size.
// The frame is held until it has been measured in the real fonts (a fallback serif sets narrower), so a still
// such as the thumbnail is right too.
export const FitTex = ({tex, color, size, max, wrap}) => {
  const ref = useRef(null);
  const held = useRef(null);
  const [k, setK] = useState(1);
  const [fonts, setFonts] = useState(false);
  if (held.current === null) held.current = delayRender("fit a formula to its box");
  useEffect(() => {
    let live = true;
    mathFontsIn().then(() => live && setFonts(true));
    return () => {
      live = false;
      if (held.current) continueRender(held.current);
      held.current = 0;
    };
  }, []);
  // only ever shrinks (a wrapped formula re-wraps as it shrinks, so growing back could see-saw for ever)
  useLayoutEffect(() => {
    if (fonts && ref.current && max && ref.current.scrollWidth > max + 1) {
      setK(k * max / ref.current.scrollWidth * 0.99);
      return;
    }
    if (fonts && held.current) {
      continueRender(held.current);
      held.current = 0;
    }
  });
  return (
    <span ref={ref} style={{display: "inline-block", fontSize: size * k,
                            ...(wrap ? {whiteSpace: "normal", maxWidth: max, lineHeight: 1.6} : {whiteSpace: "nowrap"})}}>
      <Tex tex={tex} color={color}/>
    </span>
  );
};

const Head = ({s, vertical}) => <Title s={s} vertical={vertical} size={vertical ? 80 : 72}/>;

// faint symbols drifting behind, like a blackboard full of earlier working
const Symbols = () => {
  if (C.clean) return null;
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const marks = ["\\sum", "x^2", "\\partial", "\\hat{y}", "\\theta", "\\nabla", "\\frac{1}{n}", "\\epsilon"];
  return (
    <AbsoluteFill style={{overflow: "hidden"}}>
      {marks.map((m, k) => (
        <div key={k} style={{position: "absolute", left: ((k * 0.137 + 0.05) % 1) * width,
                             top: (((k * 0.31 + 0.1) % 0.9) * height + frame * (0.3 + (k % 3) * 0.15)) % height,
                             fontSize: 60 + (k % 3) * 30, opacity: 0.07, transform: `rotate(${(k % 2 ? 1 : -1) * (8 + frame * 0.05)}deg)`}}>
          <Tex tex={m} color={C.text}/>
        </div>
      ))}
    </AbsoluteFill>
  );
};

// ---- equation: each part pops in when it is said; a labelled part gets its colour, a bracket and its name ---
export const EquationScene = ({s, i, vertical}) => {
  useMathFonts();
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const parts = s.parts || [];
  // size from the characters that will show: rac{1}{n} reads as about three, not eleven
  // (a labelled piece also takes margin for its box); sized to stay on one line, where labels cannot collide
  const shown = parts.reduce((n, p) => n + p.tex.replace(/\\[a-zA-Z]+/g, "X").replace(/[{}_^\s]/g, "").length +
                             (p.label ? 1.8 : 1.2), 0);
  const size = Math.min(vertical ? 96 : 140, (vertical ? 1400 : 2250) / Math.max(6, shown));
  let labelled = 0;
  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <Symbols/>
      <Camera i={i} amount={0.5}>
        <Head s={s} vertical={vertical}/>
        <AbsoluteFill style={{alignItems: "center", justifyContent: "center", paddingTop: vertical ? 200 : 120}}>
          <div style={{display: "flex", flexWrap: "wrap", justifyContent: "center", alignItems: "center",
                       maxWidth: vertical ? 980 : 1700, rowGap: 190, fontSize: size}}>
            {parts.map((p, k) => {
              const at = p.at ?? 6 + k * 6;
              const pp = pop(frame - at);
              const col = p.label ? SERIES[labelled++ % SERIES.length] : C.text;
              const lit = p.label ? ease((frame - at - 4) / 12) : 0;
              const above = p.label && labelled % 2 === 0;
              return (
                <div key={k} style={{position: "relative", margin: `0 ${size * (p.label ? 0.3 : 0.12)}px`, opacity: clamp(pp * 2),
                                     transform: `translateY(${(1 - pp) * 60}px) scale(${0.7 + 0.3 * pp})`,
                                     filter: `blur(${(1 - clamp(pp * 1.4)) * 10}px)`}}>
                  {p.label && <div style={{position: "absolute", inset: "-8% -10%", borderRadius: 18, background: alpha(col, 0.14 * lit),
                                           border: `3px solid ${alpha(col, 0.7 * lit)}`, boxShadow: `0 0 40px ${alpha(col, 0.3 * lit)}`}}/>}
                  <div style={{position: "relative"}}><Tex tex={p.tex} color={lit > 0.5 ? col : C.text}/></div>
                  {p.label && (
                    <div style={{position: "absolute", left: "50%", [above ? "bottom" : "top"]: "112%", transform: "translateX(-50%)",
                                 display: "flex", flexDirection: above ? "column-reverse" : "column", alignItems: "center", gap: 8}}>
                      <div style={{width: 4, height: 50 * lit, background: col, borderRadius: 2}}/>
                      <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 40 : 38, color: col, whiteSpace: "nowrap",
                                   opacity: lit, padding: "8px 18px", borderRadius: 12, background: alpha(C.panel, 0.85),
                                   border: `2px solid ${alpha(col, 0.5)}`}}>{p.label}</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </AbsoluteFill>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- the data behind every plot ----------------------------------------------------------------------------
function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const DATA = (() => {
  const r = rng(42);
  const gauss = () => Math.sqrt(-2 * Math.log(r() + 1e-9)) * Math.cos(2 * Math.PI * r());
  const pts = Array.from({length: 16}, (_, k) => {
    const x = 0.6 + (k + r() * 0.8) * 0.56;
    return [x, 1.3 + 0.62 * x + gauss() * 0.75];
  });
  const n = pts.length;
  const mx = pts.reduce((a, p) => a + p[0], 0) / n, my = pts.reduce((a, p) => a + p[1], 0) / n;
  const sxx = pts.reduce((a, p) => a + (p[0] - mx) ** 2, 0) / n, sxy = pts.reduce((a, p) => a + (p[0] - mx) * (p[1] - my), 0) / n;
  const best = sxy / sxx;
  const loss = (m) => pts.reduce((a, p) => a + (p[1] - (my + m * (p[0] - mx))) ** 2, 0) / n;   // line through the mean
  const lr = 0.45 / (2 * sxx);                       // each step closes 45% of the gap to the minimum
  const steps = [-0.35];
  for (let k = 0; k < 8; k++) steps.push(steps[k] - lr * (2 * sxx * steps[k] - 2 * sxy));
  return {pts, mx, my, best, loss, steps, grad: (m) => 2 * sxx * m - 2 * sxy};
})();

const Axes = ({box, xlabel, ylabel, p}) => {
  const {x0, y0, x1, y1} = box;
  return (
    <g>
      <line x1={x0} y1={y1} x2={x0 + (x1 - x0) * p} y2={y1} stroke={alpha(C.text, 0.6)} strokeWidth={3}/>
      <line x1={x0} y1={y1} x2={x0} y2={y1 - (y1 - y0) * p} stroke={alpha(C.text, 0.6)} strokeWidth={3}/>
      {Array.from({length: 6}, (_, k) => (
        <line key={k} x1={x0} x2={x1} y1={y1 - ((k + 1) * (y1 - y0)) / 6} y2={y1 - ((k + 1) * (y1 - y0)) / 6}
              stroke={alpha(C.text, 0.07)} strokeWidth={2} opacity={p}/>
      ))}
      <text x={x1} y={y1 + 52} textAnchor="end" fill={C.muted} fontFamily={FONT.body} fontWeight={700} fontSize={32} opacity={p}>{xlabel}</text>
      <text x={x0 - 20} y={y0 - 22} textAnchor="start" fill={C.muted} fontFamily={FONT.body} fontWeight={700} fontSize={32} opacity={p}>{ylabel}</text>
    </g>
  );
};

// ---- plot: scatter / fit / residuals / squares / descent ---------------------------------------------------
export const PlotScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {width, fps} = useVideoConfig();
  const mode = s.plot || "fit";
  const two = mode === "descent";
  const box = vertical ? {x0: 130, y0: 560, x1: 980, y1: two ? 1180 : 1500}
                       : {x0: two ? 170 : 300, y0: 330, x1: two ? 900 : 1500, y1: 905};   // labels clear of captions
  const X = (x) => box.x0 + (x / 10) * (box.x1 - box.x0);
  const Y = (y) => box.y1 - (y / 9) * (box.y1 - box.y0);
  const ky = (box.y1 - box.y0) / 9;
  const axes = ease((frame - 2) / 18);
  const T = s.frames || 180;
  const build = clamp((frame - T * 0.3) / (T * 0.45));           // the idea plays out over the middle of the shot
  const {pts, mx, my, best, loss, steps, grad} = DATA;

  // the slope on screen: flat -> best (fit, squares), best (residuals), the descent's current step (descent)
  let m = best, stepPos = 0;
  if (mode === "fit" || mode === "squares") m = ease(build) * best;
  if (mode === "scatter") m = null;
  if (mode === "descent") {
    stepPos = build * (steps.length - 1);
    const k = Math.min(steps.length - 2, Math.floor(stepPos));
    m = steps[k] + (steps[k + 1] - steps[k]) * ease(stepPos - k);
  }
  const lineAt = (x) => my + m * (x - mx);
  const lineDraw = mode === "residuals" ? ease((frame - 24) / 20) : mode === "scatter" ? 0 : clamp((frame - 20) / 12);
  const resid = mode === "residuals" || mode === "squares";
  const sse = pts.reduce((a, p) => a + (p[1] - lineAt(p[0])) ** 2, 0);
  const worst = pts.reduce((a, p) => a + (p[1] - my) ** 2, 0);

  // loss panel for the descent
  const lbox = vertical ? {x0: 130, y0: 1300, x1: 980, y1: 1760} : {x0: 1060, y0: 330, x1: 1780, y1: 905};
  const mRange = [-0.45, 1.65];
  const lMax = Math.max(loss(mRange[0]), loss(mRange[1]));
  const LX = (mm) => lbox.x0 + ((mm - mRange[0]) / (mRange[1] - mRange[0])) * (lbox.x1 - lbox.x0);
  const LY = (l) => lbox.y1 - (l / lMax) * (lbox.y1 - lbox.y0) * 0.92;
  const curve = Array.from({length: 61}, (_, k) => {
    const mm = mRange[0] + ((mRange[1] - mRange[0]) * k) / 60;
    return `${k ? "L" : "M"}${LX(mm)},${LY(loss(mm))}`;
  }).join(" ");

  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <Camera i={i} amount={0.4}>
        <Head s={s} vertical={vertical}/>
        <svg width={width} height={vertical ? 1920 : 1080} style={{position: "absolute"}}>
          <Axes box={box} xlabel={s.xlabel} ylabel={s.ylabel} p={axes}/>
          {m !== null && (
            <line x1={X(0)} y1={Y(lineAt(0))} x2={X(0) + (X(10) - X(0)) * lineDraw} y2={Y(lineAt(0) + (lineAt(10) - lineAt(0)) * lineDraw)}
                  stroke={C.accent} strokeWidth={7} strokeLinecap="round" style={{filter: `drop-shadow(0 0 12px ${alpha(C.accent, 0.7)})`}}/>
          )}
          {pts.map(([x, y], k) => {
            const p = pop(frame - 6 - delay(k, pts.length, "pts"));
            const ly = lineAt(x);
            const rd = resid ? ease((frame - (mode === "residuals" ? 46 : 34) - k * 3) / 10) : 0;
            const side = Math.abs(y - ly) * ky;
            return (
              <g key={k}>
                {mode === "squares" && (
                  <rect x={X(x)} y={Math.min(Y(y), Y(ly))} width={side * rd} height={side * rd} fill={alpha(C.hot, 0.18)}
                        stroke={alpha(C.hot, 0.7)} strokeWidth={2}/>
                )}
                {resid && <line x1={X(x)} y1={Y(y)} x2={X(x)} y2={Y(y) + (Y(ly) - Y(y)) * rd} stroke={C.hot} strokeWidth={4}
                                strokeDasharray="10 7"/>}
                <circle cx={X(x)} cy={Y(y)} r={14 * p * (1 + 0.08 * Math.sin((frame + k * 9) / 10))} fill={C.cool}
                        stroke={C.bg} strokeWidth={3} style={{filter: `drop-shadow(0 0 10px ${alpha(C.cool, 0.7)})`}}/>
              </g>
            );
          })}
          {mode === "descent" && (
            <g opacity={axes}>
              <Axes box={lbox} xlabel={s.mlabel || "slope"} ylabel={s.llabel || "error"} p={axes}/>
              <path d={curve} fill="none" stroke={C.violet} strokeWidth={6} pathLength={1} strokeDasharray={1}
                    strokeDashoffset={1 - ease((frame - 14) / 26)}/>
              {steps.slice(0, Math.floor(stepPos) + 1).map((mm, k) => (
                <circle key={k} cx={LX(mm)} cy={LY(loss(mm))} r={8} fill={alpha(C.accent, 0.5)}/>
              ))}
              {(() => {
                // the tangent at the ball: the gradient the next step follows downhill
                const g = grad(m), x = LX(m), y = LY(loss(m));
                const slopePx = -(g * (lbox.y1 - lbox.y0) * 0.92 / lMax) / ((lbox.x1 - lbox.x0) / (mRange[1] - mRange[0]));
                const len = 110 / Math.sqrt(1 + slopePx * slopePx);
                return (
                  <g opacity={clamp((frame - T * 0.3) / 10)}>
                    <line x1={x - len} y1={y - slopePx * len} x2={x + len} y2={y + slopePx * len} stroke={C.hot} strokeWidth={4}/>
                    <circle cx={x} cy={y - 22} r={20} fill={C.accent} style={{filter: `drop-shadow(0 0 16px ${C.accent})`}}/>
                  </g>
                );
              })()}
            </g>
          )}
        </svg>
        {mode === "squares" && (
          <div style={{position: "absolute", ...(vertical ? {left: 130, right: 100, top: 1580} : {left: 1580, top: 340, width: 220}),
                       fontFamily: FONT.body, color: C.text, opacity: clamp((frame - 40) / 12)}}>
            <div style={{fontWeight: 800, fontSize: 30, color: C.muted, marginBottom: 14}}>{s.llabel || "total squared error"}</div>
            <div style={{position: "relative", height: vertical ? 40 : 560, width: vertical ? "100%" : 70, borderRadius: 14,
                         background: alpha(C.text, 0.08), overflow: "hidden"}}>
              <div style={{position: "absolute", left: 0, bottom: 0, ...(vertical ? {top: 0, width: `${(100 * sse) / worst}%`}
                                                                              : {right: 0, height: `${(100 * sse) / worst}%`}),
                           background: `linear-gradient(0deg, ${C.hot}, ${alpha(C.hot, 0.5)})`, boxShadow: `0 0 30px ${alpha(C.hot, 0.5)}`}}/>
            </div>
          </div>
        )}
      </Camera>
    </AbsoluteFill>
  );
};

// ---- graph: any function of x, drawn on; a parameter a can sweep (the curve reshapes live) and a mark can
// trace it: a point, its tangent with the slope, or the area under it with the integral so far ------------------
const nice = (lo, hi, n = 5) => {
  const raw = (hi - lo) / n, mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((v) => v >= raw) || raw;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.abs(v) < step / 1e6 ? 0 : v);
  return out;
};
const fmt = (v) => (!Number.isFinite(v) ? "-" : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));

export const GraphScene = ({s, i, vertical}) => {
  useMathFonts();
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const g = s.graph || {curves: [{fn: "x^2", tex: "y = x^2"}], x: [-3, 3]};
  const T = s.frames || 180;
  const fns = g.curves.map((c) => {
    try { return compile(c.fn); } catch (e) { return () => NaN; }
  });
  const [x0, x1] = g.x;
  const pa = g.param || {from: 1, to: 1};
  const build = ease(clamp((frame - T * 0.32) / (T * 0.45)));
  const a = pa.from + (pa.to - pa.from) * build;
  // the y range covers every curve over the whole sweep, trimmed of spikes, so the axes never jump
  const ys = [];
  [pa.from, (pa.from + pa.to) / 2, pa.to].forEach((av) => fns.forEach((f) => {
    for (let k = 0; k <= 120; k++) {
      const y = f(x0 + ((x1 - x0) * k) / 120, av);
      if (Number.isFinite(y)) ys.push(y);
    }
  }));
  ys.sort((p, q) => p - q);
  let lo = ys.length ? ys[Math.floor(ys.length * 0.02)] : -1;
  let hi = ys.length ? ys[Math.max(0, Math.ceil(ys.length * 0.98) - 1)] : 1;
  if (lo > 0 && lo < (hi - lo) * 0.6) lo = 0;
  if (hi < 0 && -hi < (hi - lo) * 0.6) hi = 0;
  if (hi - lo < 1e-6) { lo -= 1; hi += 1; }
  const padY = (hi - lo) * 0.1;
  lo -= padY; hi += padY;
  const box = vertical ? {x0: 140, x1: 980, y0: 640, y1: 1440} : {x0: 230, x1: 1360, y0: 330, y1: 905};
  const mark = SERIES[1] || C.cool;                        // the tangent and readings: a colour unlike the first curve
  const X = (x) => box.x0 + ((x - x0) / (x1 - x0)) * (box.x1 - box.x0);
  const Y = (y) => box.y1 - ((y - lo) / (hi - lo)) * (box.y1 - box.y0);
  const inY = (y) => Number.isFinite(y) && y >= lo && y <= hi;
  const axisX = lo <= 0 && hi >= 0 ? Y(0) : box.y1;
  const axisY = x0 <= 0 && x1 >= 0 ? X(0) : box.x0;
  const axes = ease((frame - 2) / 18);
  const path = (f, av) => {
    let d = "", pen = false;
    for (let k = 0; k <= 240; k++) {
      const x = x0 + ((x1 - x0) * k) / 240, y = f(x, av);
      if (!inY(y)) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${X(x).toFixed(1)},${Y(y).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const f0 = fns[0];
  const mx = x0 + (x1 - x0) * (0.08 + 0.84 * build);       // where the mark is
  const my = f0(mx, a);
  const h = (x1 - x0) / 2000;
  const slope = (f0(mx + h, a) - f0(mx - h, a)) / (2 * h);
  let area = 0, areaPath = "";
  if (g.mark === "area") {
    let prev = null;
    for (let k = 0; k <= 160; k++) {
      const x = x0 + ((mx - x0) * k) / 160, y = f0(x, a);
      if (!Number.isFinite(y)) continue;
      if (prev) area += ((prev[1] + y) / 2) * (x - prev[0]);
      prev = [x, y];
      const yc = Math.max(lo, Math.min(hi, y));
      areaPath += `${areaPath ? "L" : `M${X(x).toFixed(1)},${axisX.toFixed(1)} L`}${X(x).toFixed(1)},${Y(yc).toFixed(1)}`;
    }
    if (prev) areaPath += `L${X(prev[0]).toFixed(1)},${axisX.toFixed(1)} Z`;
  }
  const markOn = g.mark && frame > T * 0.3 ? clamp((frame - T * 0.3) / 10) : 0;
  const readout = g.mark === "tangent" ? `\\frac{dy}{dx} = ${fmt(slope)}` : g.mark === "area" ? `\\int = ${fmt(area)}`
    : g.mark === "point" ? `(${fmt(mx)},\\ ${fmt(my)})` : "";
  const panel = {fontSize: vertical ? 50 : 46, padding: "14px 28px", borderRadius: 18, background: alpha(C.panel, 0.88),
                 border: `2px solid ${alpha(C.accent, 0.4)}`, color: C.text, whiteSpace: "nowrap"};
  const room = vertical ? 780 : 380;          // the side column's width less the panel's padding and border
  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <Symbols/>
      <Camera i={i} amount={0.4}>
        <Head s={s} vertical={vertical}/>
        {/* a calm plate behind the plot, so a busy moving background never fights the curves */}
        <div style={{position: "absolute", left: box.x0 - 90, top: box.y0 - 40, width: box.x1 - box.x0 + 150,
                     height: box.y1 - box.y0 + 110, borderRadius: 28, background: alpha(C.bg, 0.72 * axes),
                     border: `1.5px solid ${alpha(C.text, 0.06 * axes)}`}}/>
        <svg width={width} height={height} style={{position: "absolute"}}>
          <g opacity={axes}>
            {nice(x0, x1).map((v, k) => (
              <g key={`x${k}`}>
                <line x1={X(v)} x2={X(v)} y1={box.y0} y2={box.y1} stroke={alpha(C.text, 0.06)} strokeWidth={2}/>
                <text x={X(v)} y={axisX + 40} textAnchor="middle" fill={C.muted}
                      fontFamily={FONT.body} fontWeight={700} fontSize={vertical ? 34 : 30}>{+v.toFixed(4)}</text>
              </g>
            ))}
            {nice(lo, hi).map((v, k) => (
              <g key={`y${k}`}>
                <line x1={box.x0} x2={box.x1} y1={Y(v)} y2={Y(v)} stroke={alpha(C.text, 0.06)} strokeWidth={2}/>
                <text x={axisY - 16} y={Y(v) + 9} textAnchor="end" fill={C.muted}
                      fontFamily={FONT.body} fontWeight={700} fontSize={vertical ? 34 : 30}>{+v.toFixed(4)}</text>
              </g>
            ))}
            <line x1={box.x0} x2={box.x0 + (box.x1 - box.x0) * axes} y1={axisX} y2={axisX} stroke={alpha(C.text, 0.7)} strokeWidth={3}/>
            <line x1={axisY} x2={axisY} y1={box.y1} y2={box.y1 - (box.y1 - box.y0) * axes} stroke={alpha(C.text, 0.7)} strokeWidth={3}/>
            <text x={box.x1} y={axisX - 16} textAnchor="end" fill={C.muted} fontFamily={FONT.body} fontWeight={800} fontSize={32}>{s.xlabel || "x"}</text>
            <text x={axisY + 14} y={box.y0 + 10} fill={C.muted} fontFamily={FONT.body} fontWeight={800} fontSize={32}>{s.ylabel || "y"}</text>
          </g>
          {g.mark === "area" && markOn > 0 && <path d={areaPath} fill={alpha(C.accent, 0.22 * markOn)} stroke="none"/>}
          {fns.map((f, k) => {
            const col = SERIES[k % SERIES.length];
            const draw = ease((frame - 14 - k * 8) / (T * 0.2));
            return (
              <path key={k} d={path(f, a)} fill="none" stroke={col} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round"
                    pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw}
                    style={{filter: `drop-shadow(0 0 12px ${alpha(col, 0.6)})`}}/>
            );
          })}
          {markOn > 0 && inY(my) && (
            <g opacity={markOn}>
              {g.mark === "tangent" && (() => {
                const k = slope * ((box.y1 - box.y0) / (hi - lo)) / ((box.x1 - box.x0) / (x1 - x0));
                const len = 170 / Math.sqrt(1 + k * k);
                return <line x1={X(mx) - len} y1={Y(my) + k * len} x2={X(mx) + len} y2={Y(my) - k * len}
                             stroke={mark} strokeWidth={6} strokeLinecap="round"
                             style={{filter: `drop-shadow(0 0 10px ${alpha(mark, 0.7)})`}}/>;
              })()}
              <line x1={X(mx)} x2={X(mx)} y1={Y(my)} y2={axisX} stroke={alpha(C.text, 0.35)} strokeWidth={2} strokeDasharray="8 8"/>
              <circle cx={X(mx)} cy={Y(my)} r={16} fill={C.accent} stroke={C.bg} strokeWidth={4}
                      style={{filter: `drop-shadow(0 0 16px ${C.accent})`}}/>
            </g>
          )}
        </svg>
        {/* each curve's formula in its colour, the parameter's value, and the mark's reading */}
        <div style={{position: "absolute", ...(vertical ? {left: 140, right: 100, top: 1510, flexDirection: "row", flexWrap: "wrap"}
                                                        : {left: 1420, right: 60, top: 340, flexDirection: "column"}),
                     display: "flex", gap: 22, alignItems: "flex-start"}}>
          {g.curves.map((c, k) => c.tex ? (
            <div key={k} style={{...panel, borderColor: alpha(SERIES[k % SERIES.length], 0.6),
                                 opacity: ease((frame - 30 - k * 8) / 14)}}>
              <FitTex tex={c.tex} color={SERIES[k % SERIES.length]} max={room} wrap size={vertical ? 42 : 38}/>
            </div>
          ) : null)}
          {g.param && pa.from !== pa.to && (
            <div style={{...panel, opacity: clamp((frame - T * 0.28) / 10)}}><FitTex tex={`a = ${fmt(a)}`} color={C.accent} size={panel.fontSize} max={room}/></div>
          )}
          {readout && <div style={{...panel, opacity: markOn}}><FitTex tex={readout} color={mark} size={panel.fontSize} max={room}/></div>}
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- derive: a working written out line by line, like chalk on a board; each step slides the earlier lines up
// and says in a few words what changed --------------------------------------------------------------------------
export const DeriveScene = ({s, i, vertical}) => {
  useMathFonts();
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const steps = s.steps || [];
  const longest = Math.max(6, ...steps.map((st) => st.tex.replace(/\\[a-zA-Z]+/g, "X").replace(/[{}_^\s]/g, "").length));
  const size = Math.min(vertical ? 84 : 112, (vertical ? 1500 : 2700) / longest);
  const gap = size * 2.4;
  // the board scrolls one line per step, sprung, so the lines glide rather than jump
  const pos = steps.reduce((n, st, k) => n + (k ? pop(frame - (st.at ?? 8 + k * 30)) : 0), 0);
  const cy = vertical ? height * 0.55 : height * 0.6;
  return (
    <AbsoluteFill>
      <Backdrop word="" i={i}/>
      <Symbols/>
      <Camera i={i} amount={0.4}>
        <Head s={s} vertical={vertical}/>
        <AbsoluteFill style={{clipPath: `inset(${vertical ? 520 : 290}px 0 0 0)`}}>
          {steps.map((st, k) => {
            const at = st.at ?? 8 + k * 30;
            const write = clamp((frame - at) / 20);
            const d = k - pos;                         // 0 = the line being explained
            const focus = clamp(1 - Math.abs(d));
            return (
              <div key={k} style={{position: "absolute", left: 0, right: 0, top: cy + d * gap - size * 0.7,
                                   display: "flex", flexDirection: "column", alignItems: "center",
                                   opacity: write > 0 ? 0.3 + 0.7 * focus : 0, transform: `scale(${0.8 + 0.2 * focus})`}}>
                <div style={{position: "relative", padding: "6px 24px",
                             clipPath: `inset(-30% ${(1 - ease(write)) * 100}% -30% 0)`}}>
                  <FitTex tex={st.tex} color={focus > 0.5 ? C.text : C.muted} size={size} max={vertical ? 960 : 1720}/>
                </div>
                {st.note && (
                  <div style={{marginTop: size * 0.3, display: "flex", alignItems: "center", gap: 14, fontFamily: FONT.body,
                               fontWeight: 800, fontSize: vertical ? 40 : 36, color: C.accent,
                               padding: "8px 22px", borderRadius: 100, background: alpha(C.accent, 0.12),
                               opacity: focus * clamp((frame - at - 14) / 10)}}>
                    {st.note}
                  </div>
                )}
              </div>
            );
          })}
        </AbsoluteFill>
      </Camera>
    </AbsoluteFill>
  );
};
