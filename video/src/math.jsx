// Maths for lessons: an equation that builds term by term as each symbol is explained, and a data plot that shows
// the idea behind fitting a line (points, best fit, residuals, squared errors, gradient descent). The plot's data
// is generated here (seeded), and the fit and the descent are computed from it, so the picture is mathematically true.
import React, {useEffect, useState} from "react";
import {AbsoluteFill, continueRender, delayRender, spring, useCurrentFrame, useVideoConfig} from "remotion";
import katex from "katex";
import "katex/dist/katex.min.css";
import {Backdrop, Camera, Kicker, Words, clamp, ease} from "./fx";
import {C, FONT, SERIES, alpha} from "./theme";

// KaTeX loads its fonts lazily; hold the frame until they are in, or the first frames show a fallback serif
function useMathFonts() {
  const [handle] = useState(() => delayRender("KaTeX fonts"));
  useEffect(() => {
    Promise.all(["48px KaTeX_Main", "italic 48px KaTeX_Math", "48px KaTeX_Size1", "48px KaTeX_Size2"]
      .map((f) => document.fonts.load(f))).then(() => continueRender(handle), () => continueRender(handle));
  }, []);
}

const Tex = ({tex, color}) => (
  <span style={{color}} dangerouslySetInnerHTML={{__html: katex.renderToString(tex, {throwOnError: false})}}/>
);

const Head = ({s, vertical}) => (
  <div style={{position: "absolute", left: vertical ? 70 : 120, right: vertical ? 70 : 120, top: vertical ? 250 : 112}}>
    <Kicker text={s.kicker} size={vertical ? 32 : 26}/>
    <Words text={s.headline} highlight={s.highlight} size={vertical ? 80 : 72} delay={2} markAt={s.hcue}
           maxWidth={vertical ? 940 : 1600}/>
  </div>
);

// faint symbols drifting behind, like a blackboard full of earlier working
const Symbols = () => {
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
  const shown = parts.reduce((n, p) => n + p.tex.replace(/\\[a-zA-Z]+/g, "X").replace(/[{}_^\s]/g, "").length + 1.2, 0);
  const size = Math.min(vertical ? 96 : 140, (vertical ? 1500 : 2600) / Math.max(6, shown));
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
              const pop = spring({frame: frame - at, fps, config: {damping: 12, mass: 0.7}});
              const col = p.label ? SERIES[labelled++ % SERIES.length] : C.text;
              const lit = p.label ? ease((frame - at - 4) / 12) : 0;
              const above = p.label && labelled % 2 === 0;
              return (
                <div key={k} style={{position: "relative", margin: `0 ${size * (p.label ? 0.3 : 0.12)}px`, opacity: clamp(pop * 2),
                                     transform: `translateY(${(1 - pop) * 60}px) scale(${0.7 + 0.3 * pop})`,
                                     filter: `blur(${(1 - clamp(pop * 1.4)) * 10}px)`}}>
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
                       : {x0: two ? 170 : 300, y0: 330, x1: two ? 900 : 1500, y1: 960};
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
  const lbox = vertical ? {x0: 130, y0: 1300, x1: 980, y1: 1760} : {x0: 1060, y0: 330, x1: 1780, y1: 960};
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
            const p = spring({frame: frame - 6 - k * 2.2, fps, config: {damping: 11}});
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
