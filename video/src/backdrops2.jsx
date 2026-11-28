// Eleven more animated backdrops (blogwriter/palettes.py BACKDROPS names them and says what each suits). Like the others:
// drawn from the theme's colours, slow and faint so headlines stay readable, and seeded so a re-render is identical.
// `frame` already includes the design's pace.
import React from "react";
import {AbsoluteFill, random, useVideoConfig} from "remotion";
import {C, alpha} from "./theme";

const R = (tag, k = 0) => random(`bd2${tag}${k}`);
const Svg = ({children}) => {
  const {width, height} = useVideoConfig();
  return <svg width={width} height={height} style={{position: "absolute"}}>{children}</svg>;
};

// dunes: layered sand-dune ridges, each sliding at its own speed
const Dunes = ({frame}) => {
  const {width, height} = useVideoConfig();
  return <Svg>{[0, 1, 2, 3].map((k) => {
    const base = height * (0.55 + k * 0.12), amp = height * (0.05 + 0.02 * k), shift = frame * (0.3 + 0.25 * k);
    const pts = Array.from({length: 41}, (_, j) => {
      const x = (j / 40) * width;
      return `${x},${base + amp * Math.sin((x + shift) / (width * 0.18) + k) + amp * 0.4 * Math.sin((x - shift) / (width * 0.07) + k * 2)}`;
    });
    return <path key={k} d={`M0,${height} L${pts.join(" L")} L${width},${height}Z`} fill={alpha([C.accent, C.hot, C.cool, C.violet][k], 0.05 + 0.025 * k)}/>;
  })}</Svg>;
};

// smoke: big soft plumes rising slowly
const Smoke = ({frame}) => {
  const {width, height} = useVideoConfig();
  return <AbsoluteFill style={{overflow: "hidden"}}>{Array.from({length: 7}, (_, k) => {
    const s = width * (0.25 + 0.2 * R("ss", k)), x = R("sx", k) * width - s / 2;
    const y = height - (((frame * (0.35 + 0.4 * R("sv", k)) + R("sy", k) * height * 1.4) % (height * 1.4)));
    return <div key={k} style={{position: "absolute", left: x + Math.sin(frame / 90 + k) * 40, top: y, width: s, height: s, borderRadius: "50%",
                                background: alpha(k % 2 ? C.accent : C.cool, C.light ? 0.08 : 0.1), filter: `blur(${s * 0.18}px)`}}/>;
  })}</AbsoluteFill>;
};

// constellation: drifting points joined by thin lines when they come near (a network breathing)
const Constellation = ({frame}) => {
  const {width, height} = useVideoConfig();
  const pts = Array.from({length: 34}, (_, k) => [
    (R("cx", k) * width + Math.sin(frame / (120 + 80 * R("cs", k)) + k) * 60),
    (R("cy", k) * height + Math.cos(frame / (140 + 70 * R("ct", k)) + k) * 45)]);
  const near = width * 0.13;
  return <Svg>
    {pts.flatMap((a, i) => pts.slice(i + 1).map((b, j) => {
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      return d < near ? <line key={`${i}-${j}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={alpha(C.accent, 0.16 * (1 - d / near))} strokeWidth={1.5}/> : null;
    }))}
    {pts.map(([x, y], k) => <circle key={k} cx={x} cy={y} r={2.5 + 2 * R("cr", k)} fill={alpha(k % 5 ? C.text : C.accent, 0.3)}/>)}
  </Svg>;
};

// orbits: thin elliptical orbits with small bodies travelling on them
const Orbits = ({frame}) => {
  const {width, height} = useVideoConfig();
  const cx = width * 0.78, cy = height * 0.3;
  return <Svg>{[0, 1, 2, 3, 4].map((k) => {
    const rx = width * (0.12 + 0.09 * k), ry = rx * 0.38, a = frame / (160 + 70 * k) + k;
    return <g key={k} transform={`rotate(-18 ${cx} ${cy})`}>
      <ellipse cx={cx} cy={cy} rx={rx} ry={ry} fill="none" stroke={alpha(C.text, 0.07)} strokeWidth={1.5}/>
      <circle cx={cx + rx * Math.cos(a)} cy={cy + ry * Math.sin(a)} r={4 + k} fill={alpha([C.accent, C.cool, C.hot, C.violet, C.accent][k], 0.45)}/>
    </g>;
  })}<circle cx={cx} cy={cy} r={18} fill={alpha(C.accent, 0.18)}/></Svg>;
};

// glass: large frosted panes sliding past each other, a light edge on each
const Glass = ({frame}) => {
  const {width, height} = useVideoConfig();
  return <AbsoluteFill style={{overflow: "hidden"}}>{[0, 1, 2].map((k) => {
    const w = width * (0.35 + 0.1 * k), x = ((R("gx", k) * width + frame * (0.4 + 0.25 * k)) % (width + w)) - w;
    return <div key={k} style={{position: "absolute", left: x, top: height * (0.08 + 0.22 * k), width: w, height: height * 0.55,
                                transform: `skewX(-14deg)`, borderRadius: 28, background: alpha(C.text, C.light ? 0.035 : 0.03),
                                border: `1.5px solid ${alpha(C.accent, 0.12)}`, boxShadow: `inset 0 1px 0 ${alpha("#ffffff", 0.08)}`}}/>;
  })}</AbsoluteFill>;
};

// lattice: a faint isometric lattice drifting, like an architect's grid
const Lattice = ({frame}) => {
  const {width, height} = useVideoConfig();
  const s = 90, off = (frame * 0.4) % s;
  const lines = [];
  for (let k = -24; k < 40; k++) {
    const x = k * s + off;
    lines.push(<line key={`a${k}`} x1={x} y1={0} x2={x + height * 0.577} y2={height} stroke={alpha(C.text, 0.05)} strokeWidth={1}/>);
    lines.push(<line key={`b${k}`} x1={x} y1={0} x2={x - height * 0.577} y2={height} stroke={alpha(C.text, 0.05)} strokeWidth={1}/>);
  }
  return <><AbsoluteFill style={{background: `radial-gradient(ellipse at 70% 30%, ${alpha(C.accent, 0.12)}, transparent 60%)`}}/><Svg>{lines}</Svg></>;
};

// sheen: a slowly turning metallic sheen, like light across brushed metal
const Sheen = ({frame}) => (
  <AbsoluteFill style={{background: `conic-gradient(from ${frame * 0.25}deg at 60% 40%, ${alpha(C.accent, 0.1)}, transparent 25%, ${alpha(C.cool, 0.07)} 45%, transparent 65%, ${alpha(C.accent, 0.08)} 85%, ${alpha(C.accent, 0.1)})`,
                        filter: "blur(30px)"}}/>
);

// beam: one wide soft beam of light sweeping across, as on a stage
const Beam = ({frame}) => {
  const p = (frame % 420) / 420;
  return <AbsoluteFill style={{overflow: "hidden"}}>
    <div style={{position: "absolute", top: "-40%", left: `${-40 + 140 * p}%`, width: "28%", height: "180%", transform: "rotate(22deg)",
                 background: `linear-gradient(90deg, transparent, ${alpha(C.accent, C.light ? 0.08 : 0.11)}, transparent)`, filter: "blur(20px)"}}/>
  </AbsoluteFill>;
};

// drift: a few soft shapes falling slowly, turning as they fall
const Drift = ({frame}) => {
  const {width, height} = useVideoConfig();
  return <Svg>{Array.from({length: 16}, (_, k) => {
    const s = 10 + 26 * R("ds", k), x = R("dx", k) * width + Math.sin(frame / 50 + k) * 30;
    const y = ((frame * (0.5 + 0.6 * R("dv", k)) + R("dy", k) * height) % (height + 80)) - 40;
    return <rect key={k} x={x} y={y} width={s} height={s * 0.6} rx={s * 0.3} transform={`rotate(${frame * (0.3 + R("dr", k)) + k * 40} ${x + s / 2} ${y + s * 0.3})`}
                 fill={alpha(k % 3 ? C.accent : C.hot, 0.12)}/>;
  })}</Svg>;
};

// ink: washes of ink blooming and fading, one after another
const Ink = ({frame}) => {
  const {width, height} = useVideoConfig();
  return <AbsoluteFill style={{overflow: "hidden"}}>{Array.from({length: 5}, (_, k) => {
    const life = 300, t = ((frame + k * 60) % life) / life, s = width * (0.15 + 0.35 * t);
    return <div key={k} style={{position: "absolute", left: R("ix", k) * width - s / 2, top: R("iy", k) * height - s / 2, width: s, height: s,
                                borderRadius: "48% 52% 45% 55%", background: alpha(k % 2 ? C.violet : C.accent, 0.1 * Math.sin(Math.PI * t)),
                                filter: `blur(${s * 0.08}px)`, transform: `rotate(${k * 70 + t * 40}deg)`}}/>;
  })}</AbsoluteFill>;
};

// threads: long flowing threads, like silk strands in a slow current
const Threads = ({frame}) => {
  const {width, height} = useVideoConfig();
  return <Svg>{Array.from({length: 9}, (_, k) => {
    const y0 = height * (0.15 + 0.08 * k), a = height * 0.06, ph = frame / (90 + 10 * k) + k;
    const d = `M${-50},${y0} C${width * 0.3},${y0 + a * Math.sin(ph)} ${width * 0.6},${y0 - a * Math.cos(ph * 0.8)} ${width + 50},${y0 + a * 0.5 * Math.sin(ph * 1.3)}`;
    return <path key={k} d={d} fill="none" stroke={alpha(k % 3 ? C.accent : C.cool, 0.09 + 0.02 * (k % 3))} strokeWidth={1.5 + (k % 4)}/>;
  })}</Svg>;
};

export const BACKS2 = {dunes: Dunes, smoke: Smoke, constellation: Constellation, orbits: Orbits, glass: Glass, lattice: Lattice,
                       sheen: Sheen, beam: Beam, drift: Drift, ink: Ink, threads: Threads};
