// Eight more animated backdrops (the first eight are in fx.jsx), chosen per video by blogwriter/palettes.py from the
// video's subject. Each is drawn from the theme's colours, kept faint so headlines stay readable, and seeded so a
// re-render is identical. `frame` already includes the design's pace.
import React from "react";
import {AbsoluteFill, random, useVideoConfig} from "remotion";
import {C, alpha} from "./theme";

const R = (tag, k = 0) => random(`bd${tag}${k}`);

// stars: a field of twinkling points drifting slowly, a few sparkles, a faint nebula in one corner
const Stars = ({frame}) => {
  const {width, height} = useVideoConfig();
  return (
    <>
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 85% 15%, ${alpha(C.violet, 0.28)}, transparent 55%), radial-gradient(ellipse at 10% 90%, ${alpha(C.cool, 0.18)}, transparent 55%)`}}/>
      <svg width={width} height={height} style={{position: "absolute"}}>
        {Array.from({length: 110}, (_, k) => {
          const depth = 0.3 + 0.7 * R("sd", k);
          const x = (((R("sx", k) * width - frame * depth * 0.5) % width) + width) % width, y = R("sy", k) * height;
          const tw = 0.45 + 0.55 * Math.sin(frame / (14 + 30 * R("st", k)) + k);
          return <circle key={k} cx={x} cy={y} r={0.8 + 2.4 * depth} fill={alpha(k % 9 === 0 ? C.accent : C.text, (0.25 + 0.55 * depth) * tw)}/>;
        })}
        {Array.from({length: 7}, (_, k) => {
          const x = R("kx", k) * width, y = R("ky", k) * height, s = 14 + 22 * R("ks", k), a = 0.5 + 0.5 * Math.sin(frame / 25 + k * 2);
          return <path key={k} d={`M${x},${y - s} Q${x},${y} ${x + s},${y} Q${x},${y} ${x},${y + s} Q${x},${y} ${x - s},${y} Q${x},${y} ${x},${y - s}Z`}
                       fill={alpha(C.accent, 0.6 * a)}/>;
        })}
      </svg>
    </>
  );
};

// circuit: traces with right-angle and 45 degree bends, a pulse of light running along each
const trace = (k, width, height) => {
  let x = Math.round(R("cx", k) * 24) * (width / 24), y = Math.round(R("cy", k) * 14) * (height / 14);
  let d = `M${x},${y}`;
  for (let j = 0; j < 5; j++) {
    const dir = Math.floor(R("cd", k * 7 + j) * 4), len = (1 + Math.floor(R("cl", k * 7 + j) * 3)) * (width / 24);
    const dx = [len, -len, 0, 0][dir], dy = [0, 0, len, -len][dir];
    if (j % 2) { x += dx * 0.6; y += dy * 0.6; d += ` L${x},${y}`; x += dx * 0.4 + (dir < 2 ? 0 : len * 0.4); y += dy * 0.4 + (dir < 2 ? len * 0.4 : 0); }
    else { x += dx; y += dy; }
    d += ` L${x},${y}`;
  }
  return {d, end: [x, y]};
};
const Circuit = ({frame}) => {
  const {width, height} = useVideoConfig();
  return (
    <svg width={width} height={height} style={{position: "absolute"}}>
      {Array.from({length: 16}, (_, k) => {
        const t = trace(k, width, height), col = k % 3 === 0 ? C.accent : C.cool;
        return (
          <g key={k}>
            <path d={t.d} fill="none" stroke={alpha(col, C.light ? 0.2 : 0.2)} strokeWidth={3} strokeLinejoin="round"/>
            <circle cx={t.end[0]} cy={t.end[1]} r={8} fill="none" stroke={alpha(col, 0.35)} strokeWidth={3}/>
            <path d={t.d} fill="none" stroke={alpha(C.accent, 0.85)} strokeWidth={4} strokeLinecap="round" pathLength={1000}
                  strokeDasharray="26 974" strokeDashoffset={-((frame * (4 + 6 * R("cv", k)) + 1000 * R("cp", k)) % 1000)}/>
          </g>
        );
      })}
    </svg>
  );
};

// hexgrid: honeycomb outlines with a few cells breathing and a wave of light sweeping across
const HexGrid = ({frame}) => {
  const {width, height} = useVideoConfig();
  const r = 78, w = Math.sqrt(3) * r, h = 1.5 * r;
  const cells = [];
  for (let row = -1; row < height / h + 1; row++) {
    for (let col = -1; col < width / w + 1; col++) {
      const cx = col * w + (row % 2 ? w / 2 : 0), cy = row * h;
      const pts = Array.from({length: 6}, (_, j) => `${(cx + r * 0.94 * Math.cos(Math.PI / 3 * j + Math.PI / 6)).toFixed(1)},${(cy + r * 0.94 * Math.sin(Math.PI / 3 * j + Math.PI / 6)).toFixed(1)}`).join(" ");
      const wave = Math.max(0, 1 - Math.abs(((cx + cy * 0.4 - frame * 6) % (width * 1.4) + width * 1.4) % (width * 1.4) - width * 0.5) / 260);
      const live = R("hx", row * 91 + col) < 0.07 ? 0.5 + 0.5 * Math.sin(frame / 22 + row + col) : 0;
      cells.push(<polygon key={`${row}_${col}`} points={pts} fill={alpha(C.accent, 0.22 * Math.max(wave, live))}
                          stroke={alpha(C.cool, 0.13 + 0.25 * wave)} strokeWidth={2}/>);
    }
  }
  return <svg width={width} height={height} style={{position: "absolute"}}>{cells}</svg>;
};

// bokeh: soft out-of-focus lights rising slowly, like city lights behind the shot
const Bokeh = ({frame}) => {
  const {width, height} = useVideoConfig();
  const cols = [C.accent, C.hot, C.cool, C.violet];
  return (
    <AbsoluteFill>
      {Array.from({length: 26}, (_, k) => {
        const s = (60 + 220 * R("bs", k)) * (width / 1920), v = 0.15 + 0.5 * R("bv", k);
        const y = (((R("by", k) * (height + s) - frame * v) % (height + s)) + height + s) % (height + s) - s / 2;
        const x = R("bx", k) * width + 40 * Math.sin(frame / (60 + 40 * R("bw", k)) + k);
        const c = cols[k % 4], a = 0.1 + 0.16 * R("ba", k);
        return <div key={k} style={{position: "absolute", left: x - s / 2, top: y - s / 2, width: s, height: s, borderRadius: "50%",
                                    background: `radial-gradient(circle, ${alpha(c, a)} 0 52%, ${alpha(c, a * 2)} 56% 60%, transparent 66%)`}}/>;
      })}
    </AbsoluteFill>
  );
};

// ripples: rings spreading from a few points, like rain on water or a signal travelling out
const Ripples = ({frame}) => {
  const {width, height} = useVideoConfig();
  const maxR = Math.max(width, height) * 0.5;
  return (
    <svg width={width} height={height} style={{position: "absolute"}}>
      {[0, 1, 2].map((c) => Array.from({length: 4}, (_, k) => {
        const p = (((frame / 110 + k / 4 + R("rp", c)) % 1) + 1) % 1;
        return <circle key={`${c}_${k}`} cx={width * (0.15 + 0.7 * R("rx", c))} cy={height * (0.2 + 0.6 * R("ry", c))} r={p * maxR}
                       fill="none" stroke={alpha(c === 1 ? C.accent : C.cool, 0.34 * (1 - p))} strokeWidth={3 + 4 * (1 - p)}/>;
      }))}
    </svg>
  );
};

// stripes: bold diagonal bands sliding across, with two wide lit sweeps
const Stripes = ({frame}) => {
  const {width, height} = useVideoConfig();
  const sweep = (k) => ((frame * (3 + k * 2) + k * width * 0.7) % (width * 2.4)) - width * 0.7;
  return (
    <AbsoluteFill style={{overflow: "hidden"}}>
      <AbsoluteFill style={{backgroundImage: `repeating-linear-gradient(-32deg, ${alpha(C.accent, C.light ? 0.07 : 0.08)} 0 70px, transparent 70px 190px)`,
                            backgroundPosition: `${frame * 1.6}px 0`}}/>
      {[0, 1].map((k) => (
        <div key={k} style={{position: "absolute", left: sweep(k), top: -height * 0.2, width: width * (0.12 + 0.08 * k), height: height * 1.6,
                             transform: "rotate(18deg)", background: `linear-gradient(90deg, transparent, ${alpha(k ? C.hot : C.cool, 0.14)}, transparent)`}}/>
      ))}
    </AbsoluteFill>
  );
};

// flow: streamlines through a slowly changing field, like wind or data moving through a system
const FlowField = ({frame}) => {
  const {width, height} = useVideoConfig();
  const t = frame / 70;
  return (
    <svg width={width} height={height} style={{position: "absolute"}}>
      {Array.from({length: 34}, (_, k) => {
        let x = R("fx", k) * width * 0.3 - 80, y = R("fy", k) * height;
        let d = `M${x.toFixed(1)},${y.toFixed(1)}`;
        for (let j = 0; j < 40; j++) {
          const a = Math.sin(x / 340 + t) + Math.cos(y / 290 - t * 1.3) + 0.6 * Math.sin((x + y) / 520 + t * 0.7);
          x += 50 * Math.cos(a * 0.9); y += 50 * Math.sin(a * 0.9);
          d += ` L${x.toFixed(1)},${y.toFixed(1)}`;
        }
        return <path key={k} d={d} fill="none" stroke={alpha(k % 4 === 0 ? C.accent : C.cool, k % 4 === 0 ? 0.3 : 0.16)} strokeWidth={k % 4 === 0 ? 3 : 2} strokeLinecap="round"/>;
      })}
    </svg>
  );
};

// mesh: a smooth colour mesh, four glows wandering over a gentle diagonal
const Mesh = ({frame}) => {
  const f = frame / 120;
  const glow = (k, c, a) => {
    const x = 50 + 42 * Math.sin(f * (0.7 + 0.25 * k) + k * 1.9), y = 50 + 40 * Math.cos(f * (0.55 + 0.2 * k) + k * 2.7);
    return `radial-gradient(circle at ${x.toFixed(1)}% ${y.toFixed(1)}%, ${alpha(c, a)}, transparent 46%)`;
  };
  const a = C.light ? 0.2 : 0.3;
  return <AbsoluteFill style={{background: [glow(0, C.accent, a), glow(1, C.cool, a), glow(2, C.violet, a * 0.9), glow(3, C.hot, a * 0.7),
                                           `linear-gradient(135deg, ${C.bg}, ${C.panel})`].join(", ")}}/>;
};

export const BACKS = {stars: Stars, circuit: Circuit, hexgrid: HexGrid, bokeh: Bokeh, ripples: Ripples, stripes: Stripes, flow: FlowField, mesh: Mesh};
