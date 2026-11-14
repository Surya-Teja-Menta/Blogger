// One component per kind of shot. blogwriter/video.py picks the kind and fills its fields from verified facts.
// Every shot moves the whole time: a moving background or photo, a slow camera drift, and reveals timed to the
// spoken word (s.cue: the frame the figure is said; s.hcue: the frame the highlighted word is said).
import React from "react";
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {geoCentroid, geoGraticule10, geoInterpolate, geoNaturalEarth1, geoPath} from "d3-geo";
import {feature} from "topojson-client";
import atlas from "world-atlas/countries-50m.json";
import {Backdrop, Camera, Glass, Kicker, Particles, PhotoCard, Plate, Shade, Title, Words, clamp, countUp, ease, useEnter} from "./fx";
import {pop} from "./motion";
import {C, FONT, SERIES, alpha} from "./theme";
import {DeriveScene, EquationScene, GraphScene, PlotScene} from "./math";
import {SurfaceScene} from "./surface";
import {CheckScene} from "./check";

const pad = (v) => (v ? {left: 70, right: 70} : {left: 120, right: 120});
const media = (s) => s.video || (s.images && s.images[0]);

// headline block used at the top of chart shots
const Head = ({s, vertical, top}) => <Title s={s} vertical={vertical} top={top ?? (vertical ? 250 : 90)}
                                              size={vertical ? 92 : 88}/>;

// ---- photo / hook: three layouts so consecutive photo shots never look the same -------------------------
export const PhotoScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const num = useEnter(s.cue ?? 4);
  const card = useEnter(6, 20);
  const card2 = useEnter(16, 20);
  const images = s.images || [];
  const layout = vertical || s.video ? 0 : i % 3;
  const figure = s.number && (
    <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 220 : 200, lineHeight: 0.95,
                 color: C.accent, opacity: clamp(num * 1.4), transform: `scale(${0.7 + 0.3 * num})`, transformOrigin: "left bottom",
                 textShadow: `0 0 60px ${alpha(C.accent, 0.35)}`}}>
      {countUp(s.number, num * 1.05)}
    </div>
  );
  if (!media(s)) {
    // typographic shot: the words are the picture
    return (
      <AbsoluteFill>
        <Backdrop word={s.kicker} i={i}/>
        <Camera i={i}>
          <AbsoluteFill style={{justifyContent: "center", alignItems: "center", padding: vertical ? "0 70px 520px" : "0 160px"}}>
            <Kicker text={s.kicker} size={vertical ? 32 : 28} center/>
            {figure && <div style={{display: "flex", justifyContent: "center"}}>{figure}</div>}
            <Words text={s.headline} highlight={s.highlight} size={vertical ? 120 : 140} delay={2} align="center"
                   markAt={s.hcue} maxWidth={vertical ? 940 : 1500}/>
          </AbsoluteFill>
        </Camera>
      </AbsoluteFill>
    );
  }
  if (layout === 1) {
    // headline left, the photo as a floating 3D card on the right
    return (
      <AbsoluteFill>
        <Backdrop word={s.kicker} i={i}/>
        <PhotoCard src={images[0]} w={880} h={620} p={card} tilt={-16} style={{position: "absolute", right: 110, top: 230}}/>
        {images[1] && <PhotoCard src={images[1]} w={380} h={270} p={card2} tilt={10}
                                 style={{position: "absolute", right: 760, top: 700}}/>}
        <div style={{position: "absolute", left: 120, top: 0, bottom: 0, width: 820, display: "flex", flexDirection: "column",
                     justifyContent: "center"}}>
          <Kicker text={s.kicker} size={28}/>
          {figure}
          <Words text={s.headline} highlight={s.highlight} size={104} delay={4} markAt={s.hcue} maxWidth={820}/>
        </div>
      </AbsoluteFill>
    );
  }
  if (layout === 2) {
    // the photo revealed through a growing circle, with a rotating ring around it
    const r = interpolate(ease(frame / 26), [0, 1], [0, 470]);
    const cx = width * 0.7, cy = height * 0.5;
    return (
      <AbsoluteFill>
        <Backdrop word={s.kicker} i={i}/>
        <AbsoluteFill style={{clipPath: `circle(${r}px at ${cx}px ${cy}px)`}}>
          <Plate s={s} i={i} grade={0.85}/>
        </AbsoluteFill>
        <svg width={width} height={height} style={{position: "absolute"}}>
          <circle cx={cx} cy={cy} r={r + 22} fill="none" stroke={C.accent} strokeWidth={4} strokeDasharray="60 24"
                  transform={`rotate(${frame * 0.8} ${cx} ${cy})`} opacity={0.9}/>
          <circle cx={cx} cy={cy} r={r + 48} fill="none" stroke={alpha(C.text, 0.25)} strokeWidth={2}
                  strokeDasharray="4 14" transform={`rotate(${-frame * 0.5} ${cx} ${cy})`}/>
        </svg>
        <div style={{position: "absolute", left: 120, top: 0, bottom: 0, width: 760, display: "flex", flexDirection: "column",
                     justifyContent: "center"}}>
          <Kicker text={s.kicker} size={28}/>
          {figure}
          <Words text={s.headline} highlight={s.highlight} size={100} delay={4} markAt={s.hcue} maxWidth={760}/>
        </div>
      </AbsoluteFill>
    );
  }
  // full-bleed footage or photo with the headline low on the frame
  return (
    <AbsoluteFill>
      <Plate s={s} i={i}/>
      <Shade vertical={vertical}/>
      <Particles n={14} seed={`ph${i}`}/>
      {images[1] && !s.video && (
        <PhotoCard src={images[1]} w={vertical ? 520 : 520} h={vertical ? 380 : 360} p={card} tilt={vertical ? 0 : 12}
                   style={{position: "absolute", right: vertical ? 280 : 120, top: vertical ? 300 : 140}}/>
      )}
      <div style={{position: "absolute", ...pad(vertical), bottom: vertical ? 620 : 120}}>
        <Kicker text={s.kicker} size={vertical ? 32 : 28}/>
        {figure}
        <Words text={s.headline} highlight={s.highlight} size={vertical ? 108 : 116} delay={4} markAt={s.hcue}
               maxWidth={vertical ? 940 : 1400}/>
      </div>
    </AbsoluteFill>
  );
};

// ---- stat: one verified figure inside a gauge of ticks that light up as it counts ---------------------------
export const StatScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const at = s.cue ?? 4;
  const p = useEnter(at, 24);
  const fill = ease((frame - at) / 40);
  const R = vertical ? 330 : 300, size = R * 2 + 120, ticks = 72;
  return (
    <AbsoluteFill>
      {media(s) ? <><Plate s={s} i={i} grade={0.25}/><AbsoluteFill style={{background: `radial-gradient(circle, ${alpha(C.bg, 0.3)}, ${C.bg} 75%)`}}/></>
                : <Backdrop word={s.kicker} i={i}/>}
      <Camera i={i}>
        <AbsoluteFill style={{alignItems: "center", justifyContent: vertical ? "flex-start" : "center", paddingTop: vertical ? 260 : 0}}>
          <Kicker text={s.kicker} size={vertical ? 32 : 28} center/>
          <div style={{position: "relative", width: size, height: size, display: "flex", alignItems: "center", justifyContent: "center"}}>
            <svg width={size} height={size} style={{position: "absolute"}}>
              {Array.from({length: ticks}, (_, k) => {
                const a = (k / ticks) * 2 * Math.PI - Math.PI / 2;
                const on = k / ticks < fill * 0.82;
                const r0 = R + (k % 6 === 0 ? 8 : 18), r1 = R + 44;
                return <line key={k} x1={size / 2 + r0 * Math.cos(a)} y1={size / 2 + r0 * Math.sin(a)}
                             x2={size / 2 + r1 * Math.cos(a)} y2={size / 2 + r1 * Math.sin(a)}
                             stroke={on ? C.accent : alpha(C.text, 0.12)} strokeWidth={k % 6 === 0 ? 6 : 4} strokeLinecap="round"/>;
              })}
              <circle cx={size / 2} cy={size / 2} r={R - 20} fill={alpha(C.panel, 0.5)} stroke={alpha(C.text, 0.08)} strokeWidth={2}/>
              {(() => {
                const a = fill * 0.82 * 2 * Math.PI - Math.PI / 2;
                return <circle cx={size / 2 + (R + 26) * Math.cos(a)} cy={size / 2 + (R + 26) * Math.sin(a)} r={14} fill={C.text}
                               style={{filter: `drop-shadow(0 0 12px ${C.accent})`}} opacity={clamp(fill * 4)}/>;
              })()}
            </svg>
            <div style={{position: "relative", fontFamily: FONT.display, fontWeight: C.weight, fontSize: (vertical ? 210 : 190) * Math.min(1, 6 / Math.max(4, (s.number || "").length)),
                         lineHeight: 0.9, color: C.text, whiteSpace: "nowrap", transform: `scale(${0.75 + 0.25 * p})`,
                         textShadow: `0 0 60px ${alpha(C.accent, 0.4)}`}}>
              {countUp(s.number, p * 1.05)}
            </div>
          </div>
          <div style={{display: "flex", justifyContent: "center", marginTop: vertical ? 20 : 10}}>
            <Words text={s.label} highlight={s.highlight} size={vertical ? 62 : 54} delay={at + 8} align="center"
                   font={FONT.body} weight={800} maxWidth={vertical ? 900 : 1300} lineHeight={1.15}/>
          </div>
        </AbsoluteFill>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- compare: two or three figures as horizontal bars in a glass panel --------------------------------------
export const CompareScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = s.items || [];
  const max = Math.max(...items.map((x) => x.value), 1e-9);
  const track = vertical ? 620 : 1180;
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i} hue={C.cool}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.6}>
        <Glass p={useEnter(4)} style={{position: "absolute", ...pad(vertical), top: vertical ? 700 : 400, padding: vertical ? "50px 50px" : "50px 70px"}}>
          {items.map((it, k) => {
            const g = pop(frame - (s.cue ?? 12) - k * 9);
            const col = SERIES[k % SERIES.length];
            return (
              <div key={k} style={{marginBottom: k < items.length - 1 ? (vertical ? 56 : 40) : 0}}>
                <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 42 : 36, color: C.muted, marginBottom: 12}}>{it.label}</div>
                <div style={{display: "flex", alignItems: "center", gap: 28}}>
                  <div style={{position: "relative", width: track, height: vertical ? 64 : 58, borderRadius: 40, background: alpha(C.text, 0.06), overflow: "hidden"}}>
                    <div style={{width: `${100 * (it.value / max) * g}%`, height: "100%", borderRadius: 40,
                                 background: `linear-gradient(90deg, ${alpha(col, 0.55)}, ${col})`, boxShadow: `0 0 40px ${alpha(col, 0.5)}`}}/>
                    <div style={{position: "absolute", top: 0, bottom: 0, width: 120, left: `${100 * (it.value / max) * g - 12}%`,
                                 background: "linear-gradient(90deg, transparent, rgba(255,255,255,.35), transparent)", opacity: g < 0.98 ? 1 : 0}}/>
                  </div>
                  <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 74 : 72, color: C.text, minWidth: 220}}>
                    {countUp(it.display, g)}
                  </div>
                </div>
              </div>
            );
          })}
        </Glass>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- bars: a column chart, the largest column in the accent colour --------------------------------------------
export const BarsScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const items = s.items || [];
  const max = Math.max(...items.map((x) => x.value), 1e-9);
  const x0 = vertical ? 90 : 160, x1 = vertical ? width - 90 : width - 160;
  const top = vertical ? 700 : 360, base = vertical ? 1340 : 900, H = base - top;
  const slot = (x1 - x0) / items.length, bw = Math.min(slot * 0.58, 220);
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.6}>
        {[0.25, 0.5, 0.75, 1].map((g, k) => (
          <div key={k} style={{position: "absolute", left: x0, width: (x1 - x0) * ease((frame - 4 - k * 3) / 20), top: base - H * g,
                               height: 2, background: alpha(C.text, 0.08)}}/>
        ))}
        <div style={{position: "absolute", left: x0, width: x1 - x0, top: base, height: 3, background: alpha(C.text, 0.35)}}/>
        {items.map((it, k) => {
          const g = pop(frame - (s.cue ?? 10) - k * 6);
          const h = H * (it.value / max) * g;
          const big = it.value === max;
          const col = big ? C.accent : C.cool;
          const x = x0 + slot * k + (slot - bw) / 2;
          return (
            <React.Fragment key={k}>
              <div style={{position: "absolute", left: x, width: bw, top: base - h, height: h, borderRadius: "16px 16px 4px 4px",
                           background: `linear-gradient(to top, ${alpha(col, 0.35)}, ${col})`,
                           boxShadow: big ? `0 0 60px ${alpha(col, 0.55)}` : "none"}}/>
              <div style={{position: "absolute", left: x - 60, width: bw + 120, top: base - h - (vertical ? 92 : 84), textAlign: "center",
                           fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 64 : 60, color: big ? C.accent : C.text,
                           opacity: clamp(g * 1.5)}}>{countUp(it.display, g)}</div>
              <div style={{position: "absolute", left: x - 50, width: bw + 100, top: base + 20, textAlign: "center",
                           fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 34 : 30, color: C.muted, lineHeight: 1.15,
                           opacity: clamp(g * 2)}}>{it.label}</div>
            </React.Fragment>
          );
        })}
      </Camera>
    </AbsoluteFill>
  );
};

// ---- line: a trend that draws itself, with a glowing tip and value chips ------------------------------------
const smooth = (pts) => pts.map((p, k) => {
  if (k === 0) return `M${p[0]},${p[1]}`;
  const p0 = pts[k - 2] || pts[k - 1], p1 = pts[k - 1], p3 = pts[k + 1] || p;
  const c1 = [p1[0] + (p[0] - p0[0]) / 6, p1[1] + (p[1] - p0[1]) / 6], c2 = [p[0] - (p3[0] - p1[0]) / 6, p[1] - (p3[1] - p1[1]) / 6];
  return `C${c1[0]},${c1[1]} ${c2[0]},${c2[1]} ${p[0]},${p[1]}`;
}).join(" ");

export const LineScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const items = s.items || [];
  const vals = items.map((x) => x.value);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const floor = lo > 0 && lo / hi > 0.35 ? lo - (hi - lo) * 0.35 : Math.min(0, lo);
  const x0 = vertical ? 110 : 200, x1 = vertical ? width - 110 : width - 200;
  const top = vertical ? 760 : 380, base = vertical ? 1330 : 910;
  const pts = items.map((it, k) => [x0 + (x1 - x0) * (items.length === 1 ? 0.5 : k / (items.length - 1)),
                                    base - (base - top) * ((it.value - floor) / Math.max(1e-9, hi - floor))]);
  const start = s.cue ?? 10;
  const d = ease((frame - start) / Math.max(30, 14 * items.length));
  const tipX = x0 + (x1 - x0) * d;
  const seg = Math.min(pts.length - 2, Math.max(0, Math.floor(d * (pts.length - 1))));
  const local = pts.length > 1 ? clamp(d * (pts.length - 1) - seg) : 0;
  const tipY = pts.length > 1 ? pts[seg][1] + (pts[seg + 1][1] - pts[seg][1]) * local : pts[0][1];
  const line = smooth(pts);
  const area = `${line} L${pts[pts.length - 1][0]},${base} L${pts[0][0]},${base} Z`;
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i} hue={C.cool}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.5}>
        <svg width={width} height={height} style={{position: "absolute"}}>
          <defs>
            <linearGradient id={`area${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={C.accent} stopOpacity={0.45}/>
              <stop offset="100%" stopColor={C.accent} stopOpacity={0}/>
            </linearGradient>
            <clipPath id={`reveal${i}`}><rect x={0} y={0} width={tipX} height={height}/></clipPath>
          </defs>
          {[0, 0.25, 0.5, 0.75, 1].map((g, k) => (
            <line key={k} x1={x0} x2={x1} y1={top + (base - top) * g} y2={top + (base - top) * g} stroke={alpha(C.text, 0.08)}
                  strokeWidth={2} strokeDasharray={g === 1 ? "0" : "6 10"}/>
          ))}
          <g clipPath={`url(#reveal${i})`}>
            <path d={area} fill={`url(#area${i})`}/>
            <path d={line} fill="none" stroke={C.accent} strokeWidth={8} strokeLinecap="round"
                  style={{filter: `drop-shadow(0 0 14px ${alpha(C.accent, 0.7)})`}}/>
          </g>
          {d > 0 && d < 1 && <circle cx={tipX} cy={tipY} r={16} fill={C.text} style={{filter: `drop-shadow(0 0 16px ${C.accent})`}}/>}
          {d > 0 && <line x1={tipX} x2={tipX} y1={top - 20} y2={base} stroke={alpha(C.accent, 0.35)} strokeWidth={2} opacity={d < 1 ? 1 : 0}/>}
        </svg>
        {items.map((it, k) => {
          const reach = items.length === 1 ? 0.5 : k / (items.length - 1);
          const pp = pop(frame - start - Math.max(30, 14 * items.length) * reach * 0.8);
          const [x, y] = pts[k];
          const last = k === items.length - 1;
          return (
            <React.Fragment key={k}>
              <div style={{position: "absolute", left: x - 13, top: y - 13, width: 26, height: 26, borderRadius: 13, background: C.bg,
                           border: `6px solid ${last ? C.accent : C.text}`, transform: `scale(${pp})`}}/>
              <div style={{position: "absolute", left: x - 140, width: 280, top: y - (vertical ? 104 : 96), textAlign: "center",
                           opacity: clamp(pp * 1.5), transform: `translateY(${(1 - pp) * 20}px)`}}>
                <span style={{display: "inline-block", padding: "6px 18px", borderRadius: 14, fontFamily: FONT.display,
                              fontWeight: C.weight, fontSize: vertical ? 46 : 44, color: last ? (C.light ? "#fff" : C.bg) : C.text,
                              background: last ? C.accent : alpha(C.panel, 0.85), border: `1.5px solid ${alpha(C.text, 0.12)}`}}>
                  {countUp(it.display, pp)}
                </span>
              </div>
              <div style={{position: "absolute", left: x - 120, width: 240, top: base + 22, textAlign: "center", fontFamily: FONT.body,
                           fontWeight: 700, fontSize: vertical ? 32 : 30, color: C.muted, opacity: clamp(pp * 2)}}>{it.label}</div>
            </React.Fragment>
          );
        })}
      </Camera>
    </AbsoluteFill>
  );
};

// ---- donut: shares of a whole, arcs drawn one after another, the first share in the centre -------------------
export const DonutScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = s.items || [];
  const R = vertical ? 270 : 250, W = vertical ? 70 : 64, size = 2 * R + W + 40, Cc = 2 * Math.PI * R;
  const start = s.cue ?? 8;
  let acc = 0;
  const center = pop(frame - start);
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.6}>
        <div style={{position: "absolute", left: vertical ? (1080 - size) / 2 : 220, top: vertical ? 620 : 330}}>
          <svg width={size} height={size} style={{transform: `rotate(${-90 + frame * 0.05}deg)`}}>
            <circle cx={size / 2} cy={size / 2} r={R} fill="none" stroke={alpha(C.text, 0.07)} strokeWidth={W}/>
            {items.map((it, k) => {
              const share = Math.min(1, it.value / 100);
              const g = ease((frame - start - k * 12) / 26);
              const el = <circle key={k} cx={size / 2} cy={size / 2} r={R} fill="none" stroke={SERIES[k % SERIES.length]} strokeWidth={W}
                                 strokeDasharray={`${Math.max(0, Cc * share * g - 6)} ${Cc}`} strokeDashoffset={-Cc * acc}
                                 style={{filter: k === 0 ? `drop-shadow(0 0 18px ${alpha(SERIES[0], 0.6)})` : "none"}}/>;
              acc += share;
              return el;
            })}
          </svg>
          <div style={{position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center"}}>
            <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 150 : 140, color: C.text, lineHeight: 1,
                         transform: `scale(${0.7 + 0.3 * center})`}}>{items[0] ? countUp(items[0].display, center) : ""}</div>
            <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: 30, color: C.muted, maxWidth: R * 1.4, textAlign: "center",
                         opacity: center}}>{items[0] ? items[0].label : ""}</div>
          </div>
        </div>
        <div style={{position: "absolute", left: vertical ? 90 : 1000, right: vertical ? 90 : 140, top: vertical ? 620 + size + 40 : 400}}>
          {items.map((it, k) => {
            const g = pop(frame - start - 6 - k * 10);
            return (
              <Glass key={k} p={g} style={{display: "flex", alignItems: "center", gap: 26, padding: vertical ? "18px 30px" : "24px 34px",
                                           marginBottom: vertical ? 16 : 24}}>
                <div style={{width: 26, height: 26, borderRadius: 8, background: SERIES[k % SERIES.length]}}/>
                <div style={{flex: 1, fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 36 : 38, color: C.text}}>{it.label}</div>
                <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 54 : 58, color: SERIES[k % SERIES.length]}}>
                  {countUp(it.display, g)}
                </div>
              </Glass>
            );
          })}
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- kpis: three or four figures as tiles that land one after another --------------------------------------
export const KpiScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = s.items || [];
  const cols = vertical ? 1 : items.length;
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.6}>
        <div style={{position: "absolute", ...pad(vertical), top: vertical ? 640 : 440, display: "grid",
                     gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: vertical ? 26 : 34}}>
          {items.map((it, k) => {
            const g = pop(frame - (s.cue ?? 8) - k * 8);
            const col = SERIES[k % SERIES.length];
            return (
              <Glass key={k} p={g} glow={col} style={{padding: vertical ? "30px 40px" : "46px 40px", position: "relative", overflow: "hidden",
                                                       display: vertical ? "flex" : "block", alignItems: "center", gap: 30}}>
                <div style={{position: "absolute", left: 0, top: 0, height: 6, width: `${100 * ease((frame - (s.cue ?? 8) - k * 8) / 30)}%`,
                             background: col, boxShadow: `0 0 20px ${col}`}}/>
                <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 100 : 104, color: col, lineHeight: 1,
                             minWidth: vertical ? 330 : 0}}>{countUp(it.display, g)}</div>
                <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 38 : 34, color: C.text, marginTop: vertical ? 0 : 18,
                             lineHeight: 1.2}}>{it.label}</div>
              </Glass>
            );
          })}
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- timeline: a glowing track that draws through the dates ---------------------------------------------------
export const TimelineScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const events = s.events || [];
  const n = Math.max(1, events.length);
  const span = 18 + 14 * n;
  const draw = ease((frame - 8) / span);
  const x0 = vertical ? 170 : 300, x1 = vertical ? 170 : width - 300;
  const y0 = vertical ? 680 : 640, y1 = vertical ? 1360 : 640;
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.5}>
        <div style={{position: "absolute", left: x0, top: y0 - 3, width: vertical ? 6 : (x1 - x0), height: vertical ? (y1 - y0) : 6,
                     background: alpha(C.text, 0.1), borderRadius: 4}}/>
        <div style={{position: "absolute", left: x0, top: y0 - 3, width: vertical ? 6 : (x1 - x0) * draw, height: vertical ? (y1 - y0) * draw : 6,
                     background: `linear-gradient(${vertical ? "180deg" : "90deg"}, ${C.cool}, ${C.accent})`, borderRadius: 4,
                     boxShadow: `0 0 30px ${alpha(C.accent, 0.6)}`}}/>
        {events.map((e, k) => {
          const at = n === 1 ? 0.5 : k / (n - 1);
          const x = x0 + (x1 - x0) * at, y = y0 + (y1 - y0) * at;
          const pp = pop(frame - 8 - span * at * 0.9);
          const above = !vertical && k % 2 === 0;
          return (
            <div key={k} style={{position: "absolute", left: x, top: y}}>
              <div style={{position: "absolute", left: -22, top: -22, width: 44, height: 44, borderRadius: 22, background: C.bg,
                           border: `7px solid ${C.accent}`, transform: `scale(${pp})`, boxShadow: `0 0 30px ${alpha(C.accent, 0.7)}`}}/>
              <Glass p={pp} style={vertical ? {position: "absolute", left: 60, top: -70, width: 740, padding: "20px 30px"}
                                            : {position: "absolute", left: -175, width: 350, padding: "22px 24px", textAlign: "center",
                                               top: above ? -250 : 50}}>
                <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 70 : 64, color: C.accent, lineHeight: 1}}>{e.date}</div>
                <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 38 : 32, color: C.text, lineHeight: 1.2, marginTop: 8}}>{e.label}</div>
              </Glass>
            </div>
          );
        })}
      </Camera>
    </AbsoluteFill>
  );
};

// ---- steps: how something works, as cards joined by arrows that draw themselves -----------------------------
export const StepsScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width} = useVideoConfig();
  const items = s.items || [];
  const n = Math.max(1, items.length);
  const gap = vertical ? 40 : 60;
  const cw = vertical ? 900 : (width - 240 - gap * (n - 1)) / n, ch = vertical ? 170 : 340;
  const pos = (k) => vertical ? [90, 640 + k * (ch + gap)] : [120 + k * (cw + gap), 470];
  return (
    <AbsoluteFill>
      <Backdrop word={s.kicker} i={i}/>
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.5}>
        {items.map((it, k) => {
          const at = (s.cue ?? 8) + k * 14;
          const g = pop(frame - at);
          const [x, y] = pos(k);
          const arrow = k < n - 1 && ease((frame - at - 8) / 10);
          return (
            <React.Fragment key={k}>
              <Glass p={g} glow={k === n - 1 ? C.accent : undefined}
                     style={{position: "absolute", left: x, top: y, width: cw, height: ch, padding: vertical ? "0 36px" : "36px 34px",
                             boxSizing: "border-box", display: "flex", flexDirection: vertical ? "row" : "column",
                             alignItems: vertical ? "center" : "flex-start", gap: vertical ? 30 : 18}}>
                <div style={{width: vertical ? 84 : 76, height: vertical ? 84 : 76, borderRadius: 22, flexShrink: 0, display: "flex",
                             alignItems: "center", justifyContent: "center", background: k === n - 1 ? C.accent : alpha(C.accent, 0.15),
                             fontFamily: FONT.display, fontWeight: C.weight, fontSize: 46, color: k === n - 1 ? (C.light ? "#fff" : C.bg) : C.accent}}>
                  {k + 1}
                </div>
                <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 44 : 48, color: C.text, lineHeight: 1.2}}>{it.label}</div>
              </Glass>
              {k < n - 1 && (vertical ? (
                <div style={{position: "absolute", left: x + 70, top: y + ch, width: 6, height: gap * arrow, background: C.accent}}/>
              ) : (
                <div style={{position: "absolute", left: x + cw, top: y + ch / 2 - 3, width: gap * arrow, height: 6, background: C.accent,
                             boxShadow: `0 0 16px ${C.accent}`}}>
                  <div style={{position: "absolute", right: -6, top: -9, width: 0, height: 0, borderTop: "12px solid transparent",
                               borderBottom: "12px solid transparent", borderLeft: `16px solid ${C.accent}`, opacity: arrow > 0.9 ? 1 : 0}}/>
                </div>
              ))}
            </React.Fragment>
          );
        })}
      </Camera>
    </AbsoluteFill>
  );
};

// ---- map: the world, then a zoom onto the countries in the story -------------------------------------------
const WORLD = feature(atlas, atlas.objects.countries);

export const MapScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const names = new Set(s.countries || []);
  const picked = WORLD.features.filter((f) => names.has(f.properties.name));
  const zoom = spring({frame: frame - 6, fps, config: {damping: 30}, durationInFrames: 50});
  const world = geoNaturalEarth1().fitExtent([[40, 40], [width - 40, height - 40]], {type: "Sphere"});
  const box = vertical ? [[120, 520], [width - 120, height - 600]] : [[width * 0.38, 160], [width - 160, height - 160]];
  const near = geoNaturalEarth1().fitExtent(box, {type: "FeatureCollection", features: picked.length ? picked : WORLD.features});
  const k = Math.exp(interpolate(zoom, [0, 1], [Math.log(world.scale()), Math.log(Math.min(near.scale(), world.scale() * 14))]));
  const [wx, wy] = world.translate(), [nx, ny] = near.translate();
  const proj = geoNaturalEarth1().scale(k).translate([wx + (nx - wx) * zoom, wy + (ny - wy) * zoom]);
  const path = geoPath(proj);
  const pulse = 0.65 + 0.35 * Math.sin(frame / 8);
  const centers = picked.map((f) => geoCentroid(f));
  const arc = centers.length > 1 ? geoInterpolate(centers[0], centers[1]) : null;
  const draw = clamp((frame - 40) / 30);
  const arcPath = arc ? path({type: "LineString", coordinates: Array.from({length: 41}, (_, t) => arc((t / 40) * draw))}) : null;
  return (
    <AbsoluteFill style={{background: `radial-gradient(circle at 60% 50%, ${C.panel}, ${C.bg} 70%)`}}>
      <svg width={width} height={height}>
        <path d={path(geoGraticule10())} fill="none" stroke={alpha(C.text, 0.07)} strokeWidth={1}/>
        {WORLD.features.map((f, j) => (
          <path key={j} d={path(f)} fill={names.has(f.properties.name) ? C.accent : (C.light ? "#e4dccd" : alpha(C.text, 0.07))}
                fillOpacity={names.has(f.properties.name) ? pulse : 1} stroke={alpha(C.text, 0.15)} strokeWidth={0.8}/>
        ))}
        {arcPath && <path d={arcPath} fill="none" stroke={C.text} strokeWidth={5} strokeDasharray="14 10"/>}
        {centers.map((c, j) => {
          const [x, y] = proj(c);
          const t = (frame / 30 + j * 0.5) % 1;
          return <circle key={j} cx={x} cy={y} r={18 + 40 * t} fill="none" stroke={C.accent} strokeWidth={3} opacity={1 - t}/>;
        })}
      </svg>
      {picked.map((f, j) => {
        const [x, y] = proj(geoCentroid(f));
        const p = pop(frame - 36 - j * 8);
        const w = f.properties.name.length * (vertical ? 50 : 46) * 0.6 + 60;      // about the label's width
        const left = x + 30 + w > width - 40 ? Math.max(40, x - 30 - w) : x + 30;    // flip left at the edge
        return (
          <Glass key={j} p={p} style={{position: "absolute", left, top: y - 44, padding: "8px 22px", borderRadius: 14,
                                        fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 50 : 46, color: C.text,
                                        whiteSpace: "nowrap"}}>{f.properties.name}</Glass>
        );
      })}
      <Shade vertical={vertical} strong={0.9}/>
      <div style={{position: "absolute", ...pad(vertical), bottom: vertical ? 620 : 110}}>
        <Kicker text={s.kicker} size={vertical ? 32 : 28}/>
        <Words text={s.headline} highlight={s.highlight} size={100} delay={8} markAt={s.hcue} maxWidth={vertical ? 940 : 900}/>
      </div>
    </AbsoluteFill>
  );
};

// ---- list: three points as glass rows sliding in ----------------------------------------------------------------
export const ListScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill>
      {media(s) ? <><Plate s={s} i={i} grade={0.22}/><AbsoluteFill style={{background: alpha(C.bg, 0.45)}}/></> : <Backdrop word={s.kicker} i={i}/>}
      <Head s={s} vertical={vertical}/>
      <Camera i={i} amount={0.5}>
        <div style={{position: "absolute", ...pad(vertical), top: vertical ? 680 : 420}}>
          {(s.items || []).map((it, k) => {
            const p = pop(frame - 12 - k * 10);
            return (
              <Glass key={k} p={p} style={{display: "flex", alignItems: "center", gap: 36, padding: vertical ? "26px 36px" : "22px 40px",
                                           marginBottom: vertical ? 26 : 22, transform: `translateX(${(1 - p) * -120}px)`}}>
                <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 84 : 72, color: C.accent, width: vertical ? 120 : 110}}>
                  {String(k + 1).padStart(2, "0")}
                </div>
                <div style={{fontFamily: FONT.body, fontWeight: 800, fontSize: vertical ? 48 : 46, color: C.text, lineHeight: 1.15}}>{it.label}</div>
              </Glass>
            );
          })}
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- quote: typographic, the words light up as they are spoken ----------------------------------------------
export const QuoteScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const words = (s.quote || "").split(/\s+/).filter(Boolean);
  const shown = clamp((frame - 6) / Math.max(1, durationInFrames * 0.75 - 6)) * words.length;
  const p = useEnter(0);
  return (
    <AbsoluteFill>
      <Backdrop i={i}/>
      <Camera i={i}>
        <div style={{position: "absolute", left: vertical ? 70 : 220, right: vertical ? 70 : 220, top: vertical ? 300 : 0,
                     bottom: vertical ? undefined : 0, display: "flex", flexDirection: "column", justifyContent: "center"}}>
          <div data-audit="skip" style={{fontFamily: "Georgia, serif", fontSize: 340, lineHeight: 0.55, color: C.accent, opacity: p,
                       transform: `translateY(${(1 - p) * 40}px) scale(${0.6 + 0.4 * p})`, transformOrigin: "left",
                       textShadow: `0 0 60px ${alpha(C.accent, 0.4)}`}}>&ldquo;</div>
          <div style={{fontFamily: FONT.body, fontWeight: 700, fontSize: vertical ? 56 : 64, lineHeight: 1.3, color: C.text}}>
            {words.map((w, k) => {
              const on = clamp(shown - k + 1);
              return <span key={k} style={{opacity: 0.18 + 0.82 * on, display: "inline-block", marginRight: 16,
                                           transform: `translateY(${(1 - on) * 8}px)`}}>{w}</span>;
            })}
          </div>
          <div style={{display: "flex", alignItems: "center", gap: 20, marginTop: 44, opacity: clamp(shown / Math.max(1, words.length) * 3 - 1)}}>
            <div style={{width: 80, height: 4, background: C.accent}}/>
            <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: vertical ? 56 : 52, color: C.accent}}>{s.speaker}</div>
          </div>
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

// ---- chapter: kept for old scripts; new scripts carry acts as a sting on the shot instead --------------------
export const ChapterScene = ({s, i, vertical}) => (
  <AbsoluteFill style={{alignItems: "center", justifyContent: "center"}}>
    <Backdrop word={s.kicker} i={i}/>
    <Words text={s.headline} size={vertical ? 150 : 170} delay={2} align="center" maxWidth={vertical ? 940 : 1600}/>
  </AbsoluteFill>
);

// ---- outro: the full report as a 3D cover, and the call to subscribe -----------------------------------------
export const OutroScene = ({s, i, vertical}) => {
  const frame = useCurrentFrame();
  const p = useEnter(0, 20);
  const button = useEnter(26);
  const press = frame > 64 ? spring({frame: frame - 64, fps: 30, config: {damping: 10}}) : 0;
  return (
    // a Short's outro is top-aligned and compact: its subscribe button ends above the captions at 74%
    <AbsoluteFill style={{alignItems: "center", justifyContent: vertical ? "flex-start" : "center", paddingTop: vertical ? 170 : 0}}>
      <Backdrop word={s.card ? "" : "REPORT"} i={i}/>
      <div style={{display: "flex", flexDirection: vertical ? "column" : "row", alignItems: "center", gap: vertical ? 50 : 120}}>
        <div style={{perspective: 1400}}>
          <div style={{width: vertical ? 560 : 520, height: vertical ? 600 : 690, borderRadius: 18,
                       background: `linear-gradient(160deg, ${C.panel}, ${C.bg})`, border: `2px solid ${alpha(C.text, 0.12)}`,
                       padding: 50, boxSizing: "border-box", position: "relative",
                       transform: `rotateY(${-22 + 8 * Math.sin(frame / 50)}deg) rotateX(6deg) translateY(${(1 - p) * 80}px)`,
                       boxShadow: `30px 40px 80px ${alpha("#000000", 0.45)}, 0 0 80px ${alpha(C.accent, 0.2)}`, opacity: p}}>
            <div style={{fontFamily: FONT.body, fontWeight: 800, letterSpacing: 6, fontSize: 22, color: C.accent,
                         textTransform: "uppercase"}}>{s.card || "Documentary report"}</div>
            <div style={{fontFamily: FONT.display, fontWeight: C.weight, fontSize: Math.min(70, 760 / Math.max(6, ...String(s.headline || "").split(" ").map((w) => w.length))),
                         lineHeight: 1.05, color: C.text, marginTop: 30, overflowWrap: "anywhere"}}>{s.headline}</div>
            <div style={{position: "absolute", left: 50, right: 50, bottom: 50, fontFamily: FONT.body, fontSize: 26, color: C.muted,
                         borderTop: `2px solid ${alpha(C.text, 0.12)}`, paddingTop: 24}}>{s.label}</div>
          </div>
        </div>
        <div style={{textAlign: vertical ? "center" : "left", maxWidth: 760}}>
          <div style={{display: "flex", alignItems: "center", gap: 26, marginBottom: 30, opacity: p,
                       justifyContent: vertical ? "center" : "flex-start"}}>
            <Img src={staticFile("logo.png")} style={{width: 150, height: 150, transform: `scale(${0.7 + 0.3 * p}) rotate(${(1 - p) * -12}deg)`,
                                                     filter: `drop-shadow(0 10px 40px ${alpha(C.accent, 0.35)})`}}/>
            {s.channel && <Words text={s.channel} size={84} delay={4} maxWidth={560}/>}
          </div>
          <Words text={s.kicker} size={vertical ? 96 : 110} delay={10} align={vertical ? "center" : "left"} highlight={s.highlight} maxWidth={760}/>
          <div style={{display: "inline-flex", alignItems: "center", gap: 18, marginTop: 50, padding: "26px 54px",
                       borderRadius: 60, background: press > 0.5 ? alpha(C.text, 0.15) : C.hot,
                       transform: `scale(${1 - 0.08 * Math.sin(Math.PI * clamp(press))})`,
                       fontFamily: FONT.body, fontWeight: 800, fontSize: 44, color: press > 0.5 ? C.text : "#fff", opacity: button}}>
            {press > 0.5 ? "SUBSCRIBED" : s.channel ? `SUBSCRIBE TO ${s.channel.toUpperCase()}` : "SUBSCRIBE"}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const SCENES = {equation: EquationScene, plot: PlotScene, graph: GraphScene, derive: DeriveScene, surface: SurfaceScene, check: CheckScene, photo: PhotoScene, hook: PhotoScene, stat: StatScene, compare: CompareScene, bars: BarsScene,
                       line: LineScene, donut: DonutScene, kpis: KpiScene, timeline: TimelineScene, steps: StepsScene,
                       map: MapScene, list: ListScene, quote: QuoteScene, chapter: ChapterScene, outro: OutroScene};
